"""Camera and calibration helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import yaml


@dataclass(slots=True)
class CameraCalibration:
    camera_matrix: np.ndarray
    dist_coeffs: np.ndarray

    @classmethod
    def load(cls, path: Optional[str]) -> Optional["CameraCalibration"]:
        if not path:
            return None
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls(
            camera_matrix=np.array(data["camera_matrix"], dtype=np.float64),
            dist_coeffs=np.array(data["dist_coeffs"], dtype=np.float64),
        )

    def undistort(self, frame):
        return cv2.undistort(frame, self.camera_matrix, self.dist_coeffs)


def open_usb_camera(camera_index: int, width: Optional[int], height: Optional[int], fps: Optional[float]):
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(camera_index)
    if width:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
    if height:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
    if fps:
        cap.set(cv2.CAP_PROP_FPS, float(fps))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open camera index {camera_index}")
    return cap


def crop_roi(frame, roi):
    if roi is None:
        return frame, (0, 0)
    x, y, w, h = roi
    height, width = frame.shape[:2]
    x = max(0, min(int(x), width - 1))
    y = max(0, min(int(y), height - 1))
    w = max(1, min(int(w), width - x))
    h = max(1, min(int(h), height - y))
    return frame[y : y + h, x : x + w], (x, y)

