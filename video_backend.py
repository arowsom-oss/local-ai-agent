"""Fixed LTX 2B profile; prompt encoder process exits before renderer loading."""
from io import BytesIO
from process_guard import Worker

WIDTH, HEIGHT, FRAMES, FPS, STEPS = 384, 256, 65, 24, 30
TOKENS, DIMENSION = 128, 4096
NEGATIVE = "watermark, logo, text, blurry, distorted, inconsistent motion"


def _require_vram(torch):
    from media_resources import GIB
    if torch.cuda.mem_get_info()[0] < 9 * GIB:
        raise ValueError("at least 9 GiB of free VRAM is required; release other GPU models first")
    # This caps the PyTorch allocator, not every CUDA/driver allocation.
    torch.cuda.set_per_process_memory_fraction(.82)
    torch.cuda.reset_peak_memory_stats()


def _encode_prompt(connection, initial):
    import torch
    from transformers import BitsAndBytesConfig, T5EncoderModel, T5TokenizerFast
    _require_vram(torch)
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                              bnb_4bit_compute_dtype=torch.bfloat16)
    encoder = T5EncoderModel.from_pretrained(initial["model"], subfolder="text_encoder",
        quantization_config=quant, device_map={"": 0}, torch_dtype=torch.bfloat16,
        local_files_only=True, use_safetensors=True, trust_remote_code=False)
    tokenizer = T5TokenizerFast.from_pretrained(initial["model"], subfolder="tokenizer",
        local_files_only=True, trust_remote_code=False)
    tokens = tokenizer([initial["prompt"], NEGATIVE], padding="max_length", max_length=TOKENS,
                       truncation=True, return_tensors="pt")
    with torch.inference_mode():
        embeds = encoder(input_ids=tokens.input_ids.to("cuda"),
                         attention_mask=tokens.attention_mask.to("cuda")).last_hidden_state
    # Plain bounded CPU bytes cross the pipe; no CUDA tensor or shared-storage handle.
    connection.send({"embeddings": embeds.to("cpu", dtype=torch.float32).numpy().tobytes(),
        "attention": bytes(value for row in tokens.attention_mask.tolist() for value in row),
        "cuda_peak_allocated": torch.cuda.max_memory_allocated(),
        "cuda_peak_reserved": torch.cuda.max_memory_reserved()})


def _valid_encoding(encoded):
    import numpy as np
    if (not isinstance(encoded, dict) or
            not isinstance(encoded.get("embeddings"), bytes) or
            len(encoded["embeddings"]) != 2 * TOKENS * DIMENSION * 4 or
            not isinstance(encoded.get("attention"), bytes) or
            len(encoded["attention"]) != 2 * TOKENS or
            any(value not in (0, 1) for value in encoded["attention"]) or
            not np.isfinite(np.frombuffer(encoded["embeddings"], dtype=np.float32)).all()):
        raise ValueError("invalid bounded prompt encoding")
    for key in ("cuda_peak_allocated", "cuda_peak_reserved"):
        if type(encoded.get(key)) is not int or encoded[key] < 0:
            raise ValueError("invalid prompt memory measurement")
    return encoded


def render_video(model, prompt, reference=None):
    # This is a nested owned Job. Closing the enclosing generation Job kills it too.
    encoder_worker = Worker(_encode_prompt, {"model": str(model), "prompt": prompt}, memory_mb=12 * 1024)
    try:
        encoded = encoder_worker.receive(120)
    finally:
        encoder_worker.stop()
    # stop() terminates the encoder process before any renderer or CUDA buffer is loaded.
    encoder_worker.process.join(timeout=5)
    if encoder_worker.process.is_alive():
        raise ValueError("prompt encoder did not exit before renderer loading")
    encoded = _valid_encoding(encoded)
    import torch
    from diffusers import LTXPipeline, LTXImageToVideoPipeline
    from PIL import Image, ImageOps
    _require_vram(torch)
    embeds = torch.frombuffer(bytearray(encoded["embeddings"]), dtype=torch.float32).reshape(
        2, TOKENS, DIMENSION).to(device="cuda", dtype=torch.bfloat16)
    masks = torch.frombuffer(bytearray(encoded["attention"]), dtype=torch.uint8).reshape(2, TOKENS).to("cuda").bool()
    cls = LTXImageToVideoPipeline if reference is not None else LTXPipeline
    pipeline = cls.from_pretrained(str(model), text_encoder=None, tokenizer=None,
        torch_dtype=torch.bfloat16, local_files_only=True, use_safetensors=True)
    pipeline.enable_model_cpu_offload()
    pipeline.vae.enable_tiling(tile_sample_min_num_frames=16, tile_sample_stride_num_frames=8)
    pipeline.vae.use_framewise_decoding = True
    args = dict(prompt_embeds=embeds[0:1], prompt_attention_mask=masks[0:1],
        negative_prompt_embeds=embeds[1:2], negative_prompt_attention_mask=masks[1:2],
        height=HEIGHT, width=WIDTH, num_frames=FRAMES, frame_rate=FPS,
        num_inference_steps=STEPS, guidance_scale=3.0, decode_timestep=.05,
        decode_noise_scale=.025, generator=torch.Generator("cuda").manual_seed(42))
    if reference is not None:
        from vision_input import prepare_image
        prepared = prepare_image(reference)
        with Image.open(BytesIO(prepared.png)) as source:
            args["image"] = ImageOps.pad(source.convert("RGB"), (WIDTH, HEIGHT), color="black")
    with torch.inference_mode():
        frames = pipeline(**args).frames[0]
    return frames, {
        "cuda_peak_allocated": max(encoded["cuda_peak_allocated"], torch.cuda.max_memory_allocated()),
        "cuda_peak_reserved": max(encoded["cuda_peak_reserved"], torch.cuda.max_memory_reserved()),
        "encoder_peak_allocated": encoded["cuda_peak_allocated"],
        "renderer_peak_allocated": torch.cuda.max_memory_allocated()}
