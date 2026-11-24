import os
from dataclasses import dataclass
from hashlib import sha256

os.environ.setdefault("OPENCV_IO_MAX_IMAGE_PIXELS", "6000000")

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from .blocking_work import WorkBudget  # noqa: E402

MAX_PHOTO_BYTES = 750_000
photo_work = WorkBudget(slots=2)


@dataclass(frozen=True)
class Photo:
    jpeg: bytes
    digest: str
    width: int
    height: int
    brightness: int
    sharpness: int


def process_photo(raw: bytes) -> Photo:
    if not raw.startswith(b"\xff\xd8\xff") or len(raw) > MAX_PHOTO_BYTES:
        raise ValueError("Choose a JPEG photo under 750 KB.")
    try:
        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    except cv2.error as exc:
        raise ValueError("This image could not be decoded.") from exc
    if image is None:
        raise ValueError("This image could not be decoded.")
    height, width = image.shape[:2]
    if min(width, height) < 225:
        raise ValueError("Move closer and take a larger, clearer photo.")
    scale = min(1.0, 1280 / max(width, height))
    if scale < 1:
        image = cv2.resize(
            image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA
        )
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    brightness = round(float(gray.mean()))
    sharpness = round(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
    if not 35 <= brightness <= 230:
        raise ValueError("Use even lighting and retake the photo.")
    if sharpness < 24:
        raise ValueError("Hold the camera steady and retake the blurry photo.")
    ok, cleaned = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 82])
    if not ok:
        raise ValueError("This photo could not be saved.")
    jpeg = cleaned.tobytes()
    return Photo(jpeg, sha256(jpeg).hexdigest(), width, height, brightness, sharpness)
