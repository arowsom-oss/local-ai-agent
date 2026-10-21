"""Small local generation jobs with fixed resource and output policies."""
from pathlib import Path
import os
import uuid
from media_assets import local_asset
from process_guard import Worker

OUTPUT_DIR = Path(__file__).resolve().parent / "generated"


def prompt_problem(prompt):
    if not isinstance(prompt, str) or not 1 <= len(prompt) <= 500 or not prompt.isprintable():
        return "prompt must be 1 to 500 printable characters"
    return ""


def _generate(connection, initial):
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    kind, prompt = initial["kind"], initial["prompt"]
    if kind not in {"image", "video"} or prompt_problem(prompt):
        raise ValueError("invalid generation job")
    import torch
    from io import BytesIO
    if not torch.cuda.is_available():
        connection.send({"error": "CUDA is required; no CPU fallback was started"})
        return
    model = local_asset("image" if kind == "image" else "video_ltx")
    OUTPUT_DIR.mkdir(exist_ok=True)
    name = uuid.uuid4().hex + (".png" if kind == "image" else ".mp4")
    path = OUTPUT_DIR / name
    staging = OUTPUT_DIR / (".agent-" + name + ".part")
    encoded = BytesIO()
    try:
        if kind == "image":
            from diffusers import AutoPipelineForText2Image
            pipeline = AutoPipelineForText2Image.from_pretrained(model, torch_dtype=torch.float16,
                variant="fp16", local_files_only=True, use_safetensors=True)
            pipeline.to("cuda")
            image = pipeline(prompt=prompt, height=512, width=512, num_inference_steps=2,
                             guidance_scale=0.0).images[0]
            image.save(encoded, format="PNG")
        else:
            from video_backend import render_video, WIDTH, HEIGHT, FPS
            frames, stats = render_video(model, prompt, initial.get("reference"))
            import av
            from PIL import Image
            # Own output is created exclusively; no model-chosen path or encoder options.
            with av.open(encoded, "w", format="mp4") as container:
                stream = container.add_stream("libx264", rate=FPS)
                stream.width, stream.height, stream.pix_fmt = WIDTH, HEIGHT, "yuv420p"
                for frame in frames:
                    frame = Image.fromarray((frame * 255).astype("uint8")) if not isinstance(frame, Image.Image) else frame
                    for packet in stream.encode(av.VideoFrame.from_image(frame)):
                        container.mux(packet)
                for packet in stream.encode():
                    container.mux(packet)
        body = encoded.getvalue()
        if len(body) > 20_000_000:
            raise ValueError("generated output exceeds its 20 MB cap")
        with staging.open("xb") as output:
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
        os.link(staging, path)  # Publish complete bytes without replacing an existing file.
        staging.unlink()
        connection.send({"name": name, "path": str(path), "kind": kind,
                         **({"memory": stats} if kind == "video" else {})})
    except Exception as exc:
        if staging.exists():
            staging.unlink()
        # Only the error's type name: it says what broke without copying prompt or path text.
        connection.send({"error": f"local generation failed ({type(exc).__name__}); "
                                  "no completed output was published"})


def run_generation(kind, prompt, stop_event=None, *, reference=None):
    problem = prompt_problem(prompt)
    if problem:
        return {"error": problem}
    if kind not in {"image", "video"}:
        return {"error": "unsupported generation kind"}
    if stop_event is not None and stop_event.is_set():
        return {"error": "stopped by the user"}
    try:
        initial = {"kind": kind, "prompt": prompt}
        if reference is not None:
            from vision_input import validate_image
            if kind != "video":
                return {"error": "a reference photo is supported only for video"}
            initial["reference"] = validate_image(reference).png
        local_asset("image" if kind == "image" else "video_ltx")
        from model_router import media_lease
        from media_resources import require_ram, receive_with_ram_guard
        with media_lease():
            if stop_event is not None and stop_event.is_set():
                return {"error": "stopped by the user"}
            require_ram(8 if kind == "video" else 3)
            if stop_event is not None and stop_event.is_set():
                return {"error": "stopped by the user"}
            # Windows CUDA/weight loading needs commit headroom beyond its working set.
            # The sampled system-RAM reserve remains active independently of this ceiling.
            worker = Worker(_generate, initial, memory_mb=(8 if kind == "image" else 16) * 1024)
            try:
                return receive_with_ram_guard(worker, 180 if kind == "image" else 600, stop_event)
            finally:
                worker.stop()
    except ValueError as exc:
        # Resource errors contain only fixed messages/numbers, never the prompt or selected path.
        return {"error": str(exc) if str(exc).startswith(("at least ", "could not unload")) else
                "required local weights or approved reference photo are unavailable"}
    except Exception:
        return {"error": "generation unavailable; check optional dependencies and installed local weights"}


def generate_image(prompt: str) -> str:
    """Create one 512-pixel local image after the core's exact-prompt approval.

    Args:
        prompt: 1 to 500 printable characters describing the requested image.
    """
    return "Error: generation must pass through core approval."


def generate_video(prompt: str) -> str:
    """Create one short local LTX video after exact-prompt approval; no paths accepted.

    Args:
        prompt: 1 to 500 printable characters describing the requested short clip.
    """
    return "Error: generation must pass through core approval."
