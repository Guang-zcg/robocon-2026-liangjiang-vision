"""Classical fallback detectors for close gripper views."""

from __future__ import annotations

import cv2
import numpy as np

from .types import Detection


def detect_dark_connector(
    frame,
    grab_center: tuple[float, float] | None = None,
    roi: tuple[int, int, int, int] | None = None,
    threshold: int = 85,
    min_area: int = 650,
    cls_name: str = "rack_connector",
) -> Detection | None:
    """Estimate connector center from a dark vertical blob.

    This is a near-view safety fallback. It is intentionally conservative:
    huge dark regions touching the image edge, such as shirts or laptops, are
    rejected so they do not become false gripper targets.
    """

    height, width = frame.shape[:2]
    grab_x = float(grab_center[0]) if grab_center is not None else width / 2.0
    grab_y = float(grab_center[1]) if grab_center is not None else height / 2.0

    x1, y1, x2, y2 = _default_roi(width, height, grab_x) if roi is None else _clip_roi(roi, width, height)
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    value = hsv[:, :, 2]
    mask = cv2.inRange(value, 0, int(threshold))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    roi_h, roi_w = mask.shape[:2]
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < min_area:
            continue
        bx, by, bw, bh = cv2.boundingRect(contour)
        if bw < 12 or bh < 24:
            continue
        if bw > width * 0.55 or bh > height * 0.98:
            continue
        touches_left_right = bx <= 2 or bx + bw >= roi_w - 2
        touches_top_bottom = by <= 2 or by + bh >= roi_h - 2
        near_grab_x = abs((x1 + bx + bw / 2.0) - grab_x) <= width * 0.22
        if touches_left_right and area > min_area * 4:
            continue
        if touches_top_bottom and area > min_area * 4 and not near_grab_x:
            continue

        aspect = bh / max(1.0, bw)
        if aspect < 0.45:
            continue

        cx = x1 + bx + bw / 2.0
        cy = y1 + by + bh / 2.0
        distance_penalty = abs(cx - grab_x) / max(1.0, width * 0.45)
        vertical_bonus = min(2.5, aspect)
        lower_bonus = 1.0 + max(0.0, cy - grab_y) / max(1.0, height)
        score = area * vertical_bonus * lower_bonus / (1.0 + distance_penalty)

        if best is None or score > best[0]:
            best = (score, cx, cy, bw, bh)

    if best is None:
        return _column_projection_fallback(
            mask=mask,
            xoff=x1,
            yoff=y1,
            grab_x=grab_x,
            grab_y=grab_y,
            frame_width=width,
            cls_name=cls_name,
        )

    _, cx, cy, bw, bh = best
    return Detection(
        x=float(cx),
        y=float(cy),
        w=float(bw),
        h=float(bh),
        confidence=0.5,
        cls_name=cls_name,
    )


def _column_projection_fallback(
    mask,
    xoff: int,
    yoff: int,
    grab_x: float,
    grab_y: float,
    frame_width: int,
    cls_name: str,
) -> Detection | None:
    column_sum = mask.sum(axis=0).astype(np.float64) / 255.0
    if column_sum.size == 0 or float(column_sum.max()) < 12:
        return None
    kernel = np.ones(17, dtype=np.float64) / 17.0
    smooth = np.convolve(column_sum, kernel, mode="same")
    peak = int(np.argmax(smooth))
    threshold = max(float(smooth[peak]) * 0.35, 10.0)
    left = peak
    while left > 0 and smooth[left] >= threshold:
        left -= 1
    right = peak
    while right < smooth.size - 1 and smooth[right] >= threshold:
        right += 1
    if right - left < 12:
        return None

    roi_mask = mask[:, left:right]
    ys = np.where(roi_mask > 0)[0]
    if ys.size < 20:
        return None
    cx = xoff + (left + right) / 2.0
    cy = yoff + (float(ys.min()) + float(ys.max())) / 2.0
    if abs(cx - grab_x) > frame_width * 0.32:
        return None
    return Detection(
        x=float(cx),
        y=float(cy),
        w=float(right - left),
        h=float(ys.max() - ys.min() + 1),
        confidence=0.28,
        cls_name=cls_name,
    )


def _default_roi(width: int, height: int, grab_x: float) -> tuple[int, int, int, int]:
    half_width = int(width * 0.38)
    x1 = int(max(0, grab_x - half_width))
    x2 = int(min(width, grab_x + half_width))
    y1 = int(height * 0.06)
    y2 = height
    return x1, y1, x2, y2


def _clip_roi(roi: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = roi
    x1 = max(0, min(width - 1, int(x1)))
    y1 = max(0, min(height - 1, int(y1)))
    x2 = max(x1 + 1, min(width, int(x2)))
    y2 = max(y1 + 1, min(height, int(y2)))
    return x1, y1, x2, y2
