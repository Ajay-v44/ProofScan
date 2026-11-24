import cv2
import numpy as np

from proofscan.visual import compare_images, process_photo


def encoded(image):
    ok, data = cv2.imencode(".jpg", image)
    assert ok
    return data.tobytes()


def test_same_angle_compares_visible_change_and_rejects_reused_frames():
    tiles = np.random.default_rng(17).integers(55, 205, (28, 28), dtype=np.uint8)
    before = cv2.resize(tiles, (420, 420), interpolation=cv2.INTER_NEAREST)
    after = (before + 8).astype(np.uint8)
    damaged = after.copy()
    damaged[156:238, 164:258] = 22
    original = process_photo(encoded(before))
    matching = process_photo(encoded(after))
    changed = process_photo(encoded(damaged))
    assert (
        compare_images(original.jpeg, original.jpeg, original.descriptor, original.descriptor)[0]
        == "reused"
    )
    assert (
        compare_images(original.jpeg, matching.jpeg, original.descriptor, matching.descriptor)[0]
        == "no_clear_change"
    )
    assert (
        compare_images(original.jpeg, changed.jpeg, original.descriptor, changed.descriptor)[0]
        == "review"
    )
    assert compare_images(original.jpeg, None, original.descriptor, None)[0] == "unavailable"
