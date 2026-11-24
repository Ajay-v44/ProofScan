import os
from dataclasses import dataclass
from hashlib import sha256
from math import atan2, degrees, hypot
from typing import Literal

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
    descriptor: dict


def describe_image(gray) -> dict:
    small = cv2.resize(gray, (16, 16), interpolation=cv2.INTER_AREA).astype(np.float32).ravel()
    small -= small.mean()
    norm = float(np.linalg.norm(small))
    return {"version": 1, "values": np.round(small / max(norm, 1.0), 4).tolist()}


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
    return Photo(
        jpeg, sha256(jpeg).hexdigest(), width, height, brightness, sharpness, describe_image(gray)
    )


VisualStatus = Literal["unavailable", "retake", "reused", "review", "no_clear_change"]


def compare_images(
    first: bytes | None,
    second: bytes | None,
    first_descriptor: dict | None,
    second_descriptor: dict | None,
) -> tuple[VisualStatus, str]:
    if first is None or second is None:
        return "unavailable", "A matching view is missing or its image has expired."
    if first == second:
        return "reused", "The same image was supplied. Take a fresh photo of this view."
    if (
        first_descriptor
        and second_descriptor
        and first_descriptor.get("version") == second_descriptor.get("version") == 1
    ):
        similarity = float(np.dot(first_descriptor["values"], second_descriptor["values"]))
        if similarity < 0.2:
            return (
                "review",
                "The views look substantially different. Retake from the original angle before judging condition.",
            )
    before = cv2.imdecode(np.frombuffer(first, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    after = cv2.imdecode(np.frombuffer(second, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if before is None or after is None:
        return "unavailable", "One photo could not be read."
    before = cv2.resize(before, (480, 480), interpolation=cv2.INTER_AREA)
    after = cv2.resize(after, (480, 480), interpolation=cv2.INTER_AREA)
    detector = cv2.ORB.create(nfeatures=700)
    keypoints_left, descriptors_left = detector.detectAndCompute(after, None)
    keypoints_right, descriptors_right = detector.detectAndCompute(before, None)
    if descriptors_left is None or descriptors_right is None or len(descriptors_right) < 2:
        return (
            "retake",
            "There is too little detail to align the photos. Match the angle and use even light.",
        )
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    pairs = matcher.knnMatch(descriptors_left, descriptors_right, k=2)
    matches = [
        pair[0] for pair in pairs if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance
    ]
    if len(matches) < 15:
        return "retake", "The views could not be aligned. Retake from the same angle and distance."
    left = np.asarray([keypoints_left[match.queryIdx].pt for match in matches], dtype=np.float32)
    right = np.asarray([keypoints_right[match.trainIdx].pt for match in matches], dtype=np.float32)
    matrix, mask = cv2.estimateAffinePartial2D(left, right, method=cv2.RANSAC, ransacReprojThreshold=3)
    if matrix is None or mask is None:
        return "retake", "The views could not be aligned. Retake from the same angle."
    inliers = mask.ravel().astype(bool)
    scale = hypot(*matrix[0, :2])
    rotation = abs(degrees(atan2(matrix[1, 0], matrix[0, 0])))
    if (
        int(inliers.sum()) < 15
        or inliers.mean() < 0.55
        or min(np.ptp(right[inliers], axis=0)) < 100
        or not 0.82 <= scale <= 1.22
        or rotation > 20
    ):
        return "retake", "Alignment was weak. Match the original framing and distance."
    aligned = cv2.warpAffine(after, matrix, (480, 480))[48:-48, 48:-48]
    original = before[48:-48, 48:-48]
    region = cv2.warpAffine(np.ones_like(after), matrix, (480, 480))[48:-48, 48:-48] > 0
    if region.mean() < 0.85:
        return "retake", "Too little of the original view overlaps. Match the framing."
    delta = cv2.GaussianBlur(aligned, (5, 5), 0).astype(np.float32) - cv2.GaussianBlur(
        original, (5, 5), 0
    )
    delta -= np.median(delta[region])
    mask_pixels = np.asarray((np.abs(delta) > 28) & region, dtype=np.uint8)
    changed = cv2.morphologyEx(mask_pixels, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    _, _, stats, _ = cv2.connectedComponentsWithStats(changed)
    if len(stats) > 1 and int(max(stats[1:, cv2.CC_STAT_AREA])) >= 240:
        return (
            "review",
            "An aligned area looks different. Inspect it in person to distinguish damage from lighting or reflection.",
        )
    return (
        "no_clear_change",
        "No clear change was detected in the aligned area. Inspect the item in person.",
    )
