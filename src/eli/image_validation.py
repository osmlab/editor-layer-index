"""Decode provider images and reject HTML/XML/JSON error documents."""

import io
import xml.etree.ElementTree as ET

from PIL import Image, UnidentifiedImageError


def image_payload(
    data: bytes, *, allow_svg: bool = False, expected_size: tuple[int, int] | None = None
) -> tuple[bool, bool]:
    """Return (decodable, blank); uniform imagery is suspicious, not necessarily wrong."""
    if allow_svg:
        try:
            root = ET.fromstring(data)
            if root.tag == "{http://www.w3.org/2000/svg}svg":
                return True, False
        except ET.ParseError:
            pass
    try:
        with Image.open(io.BytesIO(data)) as image:
            if expected_size is not None and image.size != expected_size:
                return False, False
            if image.width * image.height > 16_777_216:
                return False, False
            image.load()
            rgba = image.convert("RGBA")
            transparent = rgba.getchannel("A").getbbox() is None
            return True, transparent or len(rgba.getcolors(2) or []) == 1
    except UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError:
        return False, False
