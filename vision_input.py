"""Person-selected images and one-shot screenshots. No model-callable capture API."""
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import warnings

MAX_FILE_BYTES = 10_000_000
MAX_PIXELS = 20_000_000
MAX_SIDE = 1536
MAX_PNG_BYTES = 8_000_000


@dataclass(frozen=True)
class ImageInput:
    png: bytes
    width: int
    height: int
    label: str


def _normalize(image, label):
    from PIL import Image, ImageOps
    if image.width <= 0 or image.height <= 0 or image.width * image.height > MAX_PIXELS:
        raise ValueError("image exceeds the 20-megapixel limit")
    if getattr(image, "n_frames", 1) != 1:
        raise ValueError("only single-frame images are supported")
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    # Rebuild pixels so EXIF, comments and other file metadata are not sent.
    clean = Image.new("RGB", image.size)
    clean.paste(image)
    data = BytesIO()
    clean.save(data, format="PNG")
    png = data.getvalue()
    if len(png) > MAX_PNG_BYTES:
        raise ValueError("normalized image exceeds the 8 MB limit")
    return ImageInput(png, clean.width, clean.height, label)


def prepare_image(data: bytes, label="Selected image") -> ImageInput:
    """Decode bounded image bytes and strip metadata, without retaining a file path."""
    from PIL import Image
    if not isinstance(data, bytes) or not 1 <= len(data) <= MAX_FILE_BYTES:
        raise ValueError("image file must be between 1 byte and 10 MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data), formats=["PNG", "JPEG", "WEBP"]) as image:
                return _normalize(image, label)
    except Exception as exc:
        raise ValueError("image could not be decoded within the image limits") from exc


def load_image(path) -> ImageInput:
    """Only the UI file picker calls this; never expose it as an Ollama tool."""
    try:
        with Path(path).open("rb") as file:
            return prepare_image(file.read(MAX_FILE_BYTES + 1))
    except OSError as exc:
        raise ValueError("could not read the selected image") from exc


def capture_primary_screen() -> ImageInput:
    """Called once by the person's Screenshot button, after capture confirmation."""
    from PIL import ImageGrab
    try:
        with ImageGrab.grab(all_screens=False) as image:
            return _normalize(image, "Primary-screen screenshot")
    except Exception as exc:
        raise ValueError("could not capture the primary screen") from exc


def validate_image(image):
    """Check the exact immutable bytes shown in the preview before model inference."""
    from PIL import Image
    if (not isinstance(image, ImageInput) or not isinstance(image.png, bytes)
            or not 1 <= len(image.png) <= MAX_PNG_BYTES):
        raise ValueError("invalid prepared image")
    with Image.open(BytesIO(image.png), formats=["PNG"]) as decoded:
        if (decoded.size != (image.width, image.height)
                or not 1 <= image.width <= MAX_SIDE or not 1 <= image.height <= MAX_SIDE):
            raise ValueError("prepared image dimensions are invalid")
        decoded.verify()
    return image
