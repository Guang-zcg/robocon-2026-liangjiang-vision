"""Pick the gripper grab center in the camera image."""

from __future__ import annotations

import argparse

import cv2

from head_rack_align.camera import open_usb_camera


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--fps", type=float, default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    cap = open_usb_camera(args.camera, args.width, args.height, args.fps)
    window_name = "pick gripper grab center"
    picked = None
    printed_size = False

    def on_mouse(event, x, y, flags, param):
        nonlocal picked
        if event == cv2.EVENT_LBUTTONDOWN:
            picked = (x, y)
            print(f"grab_center_x: {x}")
            print(f"grab_center_y: {y}")

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window_name, on_mouse)
    print("Click the true gripper grab point. Press q/ESC to quit.")
    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            if not printed_size:
                height, width = frame.shape[:2]
                print(f"frame_width: {width}")
                print(f"frame_height: {height}")
                printed_size = True
            height, width = frame.shape[:2]
            cv2.drawMarker(
                frame,
                (width // 2, height // 2),
                (255, 160, 0),
                markerType=cv2.MARKER_CROSS,
                markerSize=24,
                thickness=2,
            )
            cv2.putText(
                frame,
                "image center",
                (width // 2 + 10, height // 2 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 160, 0),
                2,
            )
            if picked is not None:
                cv2.drawMarker(
                    frame,
                    picked,
                    (0, 255, 255),
                    markerType=cv2.MARKER_CROSS,
                    markerSize=28,
                    thickness=2,
                )
                cv2.putText(
                    frame,
                    f"grab_center=({picked[0]}, {picked[1]})",
                    (16, 34),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 255),
                    2,
                )
            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
