"""Explicit crop/redaction geometry; no automatic claim to find private information."""
from io import BytesIO
from PIL import Image, ImageDraw
from vision_input import validate_image, _normalize


def edit_image(image, rectangle, *, crop=False):
    validate_image(image)
    if (not isinstance(rectangle, (tuple, list)) or len(rectangle) != 4
            or any(isinstance(n, bool) or not isinstance(n, int) for n in rectangle)):
        raise ValueError("rectangle requires four integer coordinates")
    left, top, right, bottom = rectangle
    if not 0 <= left < right <= image.width or not 0 <= top < bottom <= image.height:
        raise ValueError("rectangle is outside the preview image")
    with Image.open(BytesIO(image.png)) as source:
        result = source.crop(rectangle) if crop else source.copy()
        if not crop:
            ImageDraw.Draw(result).rectangle((left, top, right - 1, bottom - 1), fill="black")
        return _normalize(result, "Cropped/redacted user-approved image")
