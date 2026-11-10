"""Calibrate a USB camera from chessboard images."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import yaml


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", required=True)
    parser.add_argument("--pattern-cols", type=int, required=True, help="inner corner columns")
    parser.add_argument("--pattern-rows", type=int, required=True, help="inner corner rows")
    parser.add_argument("--square-size", type=float, required=True, help="square size in mm or any fixed unit")
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    image_paths = sorted(Path(args.images).glob("*.jpg")) + sorted(Path(args.images).glob("*.png"))
    if not image_paths:
        raise SystemExit("no calibration images found")

    pattern = (args.pattern_cols, args.pattern_rows)
    objp = np.zeros((pattern[0] * pattern[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0 : pattern[0], 0 : pattern[1]].T.reshape(-1, 2)
    objp *= float(args.square_size)

    objpoints = []
    imgpoints = []
    image_size = None

    for path in image_paths:
        img = cv2.imread(str(path))
        if img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        image_size = gray.shape[::-1]
        ok, corners = cv2.findChessboardCorners(gray, pattern)
        if not ok:
            print(f"skip {path}: chessboard not found")
            continue
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        objpoints.append(objp)
        imgpoints.append(corners)
        print(f"use {path}")

    if len(objpoints) < 8:
        raise SystemExit(f"need at least 8 valid calibration images, got {len(objpoints)}")

    rms, camera_matrix, dist_coeffs, _, _ = cv2.calibrateCamera(objpoints, imgpoints, image_size, None, None)
    data = {
        "rms": float(rms),
        "image_width": int(image_size[0]),
        "image_height": int(image_size[1]),
        "camera_matrix": camera_matrix.tolist(),
        "dist_coeffs": dist_coeffs.reshape(-1).tolist(),
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    print(f"saved {out_path}, rms={rms:.4f}")


if __name__ == "__main__":
    main()

