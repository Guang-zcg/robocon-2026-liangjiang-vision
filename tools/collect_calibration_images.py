"""Collect chessboard images for wide-angle camera calibration."""

from __future__ import annotations

import argparse
from pathlib import Path
import time

import cv2

from head_rack_align.camera import open_usb_camera


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--out", required=True)
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--fps", type=float, default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = open_usb_camera(args.camera, args.width, args.height, args.fps)
    index = 0
    print("Move the chessboard around the center and edges. Press s to save, q/ESC to quit.")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                continue
            cv2.imshow("collect calibration images", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
            if key == ord("s"):
                path = out_dir / f"calib_{int(time.time() * 1000)}_{index:04d}.jpg"
                cv2.imwrite(str(path), frame)
                print(path)
                index += 1
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

