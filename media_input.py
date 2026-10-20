"""Bounded user-selected WAV/MP4 clips; no live microphone or model-selected path."""
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import os
import wave
from process_guard import Worker

MAX_CLIP_BYTES = 64_000_000
MAX_SECONDS = 60
MAX_FRAMES = 4


@dataclass(frozen=True)
class MediaInput:
    image: object
    observation: str
    seconds: float
    samples: int


def _transcribe(samples):
    from media_assets import local_asset
    from faster_whisper import WhisperModel
    model = WhisperModel(str(local_asset("audio")), device="cpu", compute_type="int8", local_files_only=True,
                         cpu_threads=2, num_workers=1)
    segments, _ = model.transcribe(samples, language="en", beam_size=1, vad_filter=True)
    text = ""
    for segment in segments:
        text += segment.text + " "
        if len(text) >= 6000:
            break
    return text[:6000].strip()


def _decode(connection, initial):
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    data, kind = initial["data"], initial["kind"]
    if not isinstance(data, bytes) or not 1 <= len(data) <= MAX_CLIP_BYTES:
        raise ValueError("clip file exceeds 64 MB")
    import numpy as np
    if kind == "wav":
        with wave.open(BytesIO(data)) as audio:
            rate, channels, count = audio.getframerate(), audio.getnchannels(), audio.getnframes()
            if (audio.getsampwidth() != 2 or channels not in (1, 2) or not 8000 <= rate <= 48000
                    or not 0 < count / rate <= MAX_SECONDS):
                raise ValueError("only up to 60 seconds of 16-bit mono/stereo WAV at 8-48 kHz is supported")
            raw = np.frombuffer(audio.readframes(count), dtype="<i2").reshape(-1, channels)
            mono = raw.astype(np.float32).mean(axis=1) / 32768.0
            seconds = count / rate
            samples = np.interp(np.arange(round(seconds * 16000)) / 16000,
                                np.arange(len(mono)) / rate, mono).astype(np.float32)
            transcript = _transcribe(samples)
        connection.send({"media": MediaInput(None, "Untrusted local audio transcript:\n" + transcript, seconds, 0)})
        return
    if kind != "mp4":
        raise ValueError("only WAV and MP4 are supported")
    import av
    from PIL import Image, ImageDraw
    from vision_input import _normalize
    with av.open(BytesIO(data), format="mp4", options={"protocol_whitelist": "pipe,data"}) as container:
        videos = container.streams.video
        if len(videos) != 1 or container.duration is None:
            raise ValueError("clip needs one video stream and a known duration")
        seconds = container.duration / av.time_base
        stream = videos[0]
        stream.thread_count = 2
        if not 0 < seconds <= MAX_SECONDS or not 0 < stream.width * stream.height <= 8_294_400:
            raise ValueError("clip exceeds 60 seconds or 4K frame bounds")
        targets = [seconds * i / MAX_FRAMES for i in range(MAX_FRAMES)]
        images, stamps = [], []
        decoded = 0
        for frame in container.decode(stream):
            decoded += 1
            if decoded > 3600:
                raise ValueError("clip has too many decoded frames")
            stamp = frame.time
            if stamp is None or not 0 <= stamp <= MAX_SECONDS:
                raise ValueError("invalid frame timestamp")
            if len(images) < MAX_FRAMES and stamp >= targets[len(images)]:
                if frame.width * frame.height > 8_294_400:
                    raise ValueError("decoded frame exceeds 4K bounds")
                image = frame.to_image().convert("RGB")
                image.thumbnail((740, 400))
                images.append(image)
                stamps.append(round(stamp, 2))
            if len(images) == MAX_FRAMES:
                break
        if not images:
            raise ValueError("clip has no readable frames")
    sheet = Image.new("RGB", (1500, 860), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (image, stamp) in enumerate(zip(images, stamps)):
        x, y = (index % 2) * 750, (index // 2) * 430
        draw.text((x + 5, y + 5), f"Sample at {stamp:.2f} seconds", fill="black")
        sheet.paste(image, (x + 5, y + 25))
    connection.send({"media": MediaInput(_normalize(sheet, "Selected video frame samples"),
        f"Selected MP4 duration {seconds:.2f}s. Only {len(images)} frames sampled at {stamps}; "
        "events between samples and the video's audio were not analyzed.", seconds, len(images))})


def prepare_media(path, stop_event=None):
    path = Path(path)
    kind = path.suffix.lower().removeprefix(".")
    if kind not in {"wav", "mp4"}:
        raise ValueError("choose a WAV or MP4 file")
    with path.open("rb") as file:
        data = file.read(MAX_CLIP_BYTES + 1)
    return prepare_media_bytes(data, kind, stop_event)


def prepare_media_bytes(data, kind, stop_event=None):
    """Decode person-approved local bytes; microphone audio never needs a temporary file."""
    if kind not in {"wav", "mp4"} or not isinstance(data, bytes):
        raise ValueError("only bounded local WAV or MP4 bytes are supported")
    if not 1 <= len(data) <= MAX_CLIP_BYTES:
        raise ValueError("clip file exceeds the 64 MB limit")
    worker = Worker(_decode, {"data": data, "kind": kind}, memory_mb=4096)
    try:
        result = worker.receive(120, stop_event)
        if "error" in result:
            raise ValueError(result["error"])
        return result["media"]
    finally:
        worker.stop()
