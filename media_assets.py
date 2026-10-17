"""Fixed model assets. Runtime workers use local snapshots only."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent / "model_cache"
SPECS = {
    "audio": ("Systran/faster-whisper-tiny.en", ["config.json", "model.bin", "tokenizer.json", "vocabulary.txt"]),
    "image": ("stabilityai/sd-turbo", ["model_index.json", "scheduler/*.json", "tokenizer/*",
        "text_encoder/config.json", "text_encoder/*fp16.safetensors", "unet/config.json",
        "unet/*fp16.safetensors", "vae/config.json", "vae/*fp16.safetensors"]),
    "video": ("ali-vilab/text-to-video-ms-1.7b", ["model_index.json", "scheduler/*.json", "tokenizer/*",
        "text_encoder/config.json", "text_encoder/*fp16.safetensors", "unet/config.json",
        "unet/*fp16.safetensors", "vae/config.json", "vae/*fp16.safetensors"]),
}


def local_asset(kind):
    if kind not in SPECS:
        raise ValueError("unsupported model kind")
    manifest = ROOT / (kind + ".json")
    if not manifest.is_file():
        raise ValueError(f"{kind} weights missing; run setup_media.py {kind} yourself first")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("repo") != SPECS[kind][0] or not isinstance(data.get("revision"), str):
        raise ValueError("invalid local model manifest")
    path = (ROOT / data["path"]).resolve()
    if not path.is_relative_to(ROOT.resolve()) or not path.is_dir():
        raise ValueError("local model path is outside its cache")
    return path
