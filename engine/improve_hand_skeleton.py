"""Helper functions for hand skeleton normalization and coordinate restoration."""
import cv2
import numpy as np


def prepare_image(raw, crop, quarter_turns=0, mirror=False):
    """Integer right-angle transforms, exactly invertible in pixel coordinates."""
    x0, y0, x1, y1 = crop
    if not (0 <= x0 < x1 <= raw.shape[1] and 0 <= y0 < y1 <= raw.shape[0]):
        raise ValueError('Invalid crop')
    image = raw[y0:y1, x0:x1].copy()
    height, width = image.shape[:2]
    transform = np.array([[1.0, 0.0, -x0], [0.0, 1.0, -y0], [0.0, 0.0, 1.0]])
    for _ in range(quarter_turns % 4):
        image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        transform = np.array([[0.0, -1.0, height - 1], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]) @ transform
        width, height = height, width
    if mirror:
        image = cv2.flip(image, 1)
        transform = np.array([[-1.0, 0.0, width - 1], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]) @ transform
    return image, transform


def restore_hand(hand, image_shape, transform):
    h, w = image_shape[:2]
    points = np.array([[p.x * w, p.y * h] for p in hand], float)
    restored = cv2.perspectiveTransform(points[:, None, :], np.linalg.inv(transform))[:, 0]
    return restored.tolist()


def serialize(result, image_shape, transform):
    return [
        dict(
            pixel_landmarks=restore_hand(hand, image_shape, transform),
            handedness_raw=result.handedness[i][0].category_name,
            handedness_score=float(result.handedness[i][0].score),
            points_from_one_inference=True,
            per_finger_mixing=False,
        )
        for i, hand in enumerate(result.hand_landmarks)
    ]
