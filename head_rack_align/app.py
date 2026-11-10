"""USB camera YOLO alignment app."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

from .camera import CameraCalibration, crop_roi, open_usb_camera
from .config import load_config
from .detector import YoloHeadDetector
from .draw import draw_alignment
from .fallback import detect_dark_connector
from .geometry import RackGeometrySolver
from .stabilizer import SlotLockStabilizer
from .targeting import solve_single_target


def parse_classes(text):
    if not text:
        return None
    return [int(item.strip()) for item in text.split(",") if item.strip()]


def parse_args():
    parser = argparse.ArgumentParser("R2 weapon-head rack slot alignment")
    parser.add_argument("--config", default=None)
    parser.add_argument("--model", required=True)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--target-slot", type=int, default=None)
    parser.add_argument("--target-mode", choices=["slot", "single"], default=None)
    parser.add_argument("--target-class", default=None)
    parser.add_argument("--grab-center-x", type=float, default=None)
    parser.add_argument("--grab-center-y", type=float, default=None)
    parser.add_argument("--alignment-axes", choices=["x", "y", "xy"], default=None)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--min-confidence", type=float, default=None)
    parser.add_argument("--lock-min-confidence", type=float, default=None)
    parser.add_argument("--iou", type=float, default=0.45)
    parser.add_argument("--max-det", type=int, default=12)
    parser.add_argument("--classes", default=None)
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--fps", type=float, default=None)
    parser.add_argument("--calibration", default=None)
    parser.add_argument("--reverse-axis", action="store_true")
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--draw-detections", action="store_true")
    parser.add_argument("--fallback-dark", action="store_true")
    parser.add_argument("--fallback-threshold", type=int, default=85)
    parser.add_argument("--fallback-min-area", type=int, default=650)
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--no-json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)
    if args.target_slot is not None:
        cfg.target_slot = args.target_slot
    if args.target_mode is not None:
        cfg.target_mode = args.target_mode
    if args.target_class is not None:
        cfg.target_class = args.target_class
    if args.grab_center_x is not None:
        cfg.grab_center_x = args.grab_center_x
    if args.grab_center_y is not None:
        cfg.grab_center_y = args.grab_center_y
    if args.alignment_axes is not None:
        cfg.alignment_axes = args.alignment_axes
    if args.min_confidence is not None:
        cfg.min_confidence = args.min_confidence
    if args.lock_min_confidence is not None:
        cfg.lock_min_confidence = args.lock_min_confidence

    calibration = CameraCalibration.load(args.calibration)
    detector = YoloHeadDetector(
        model_path=args.model,
        imgsz=args.imgsz,
        conf=args.conf,
        iou=args.iou,
        device=args.device,
        max_det=args.max_det,
        classes=parse_classes(args.classes),
    )
    solver = RackGeometrySolver(
        min_detections=cfg.min_detections,
        min_confidence=cfg.min_confidence,
        type_consistency_weight=cfg.type_consistency_weight,
        max_slot_spacing_cv=cfg.max_slot_spacing_cv,
        reverse_axis=args.reverse_axis,
    )
    stabilizer = SlotLockStabilizer(
        target_slot=cfg.target_slot,
        grab_center_x=cfg.grab_center_x,
        grab_center_y=cfg.grab_center_y,
        target_type=cfg.target_class,
        alignment_axes=cfg.alignment_axes,
        align_threshold_px=cfg.align_threshold_px,
        lock_min_confidence=cfg.lock_min_confidence,
        lock_frames=cfg.lock_frames,
        lost_frames=cfg.lost_frames,
    )

    cap = open_usb_camera(args.camera, args.width, args.height, args.fps)
    json_out = None
    if args.json_out:
        json_path = Path(args.json_out)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_out = json_path.open("a", encoding="utf-8")
    window_name = "R2 Head Rack Alignment"
    if args.show:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            if calibration is not None:
                frame = calibration.undistort(frame)

            roi_frame, offset = crop_roi(frame, cfg.roi)
            detections = detector.predict(roi_frame, offset=offset)
            fallback_detection = None
            height, width = frame.shape[:2]
            grab_x = cfg.grab_center_x if cfg.grab_center_x is not None else width / 2.0
            grab_y = cfg.grab_center_y if cfg.grab_center_y is not None else height / 2.0
            if cfg.target_mode == "single":
                solve_result = solve_single_target(
                    detections=detections,
                    target_slot=cfg.target_slot,
                    target_class=cfg.target_class,
                    min_confidence=cfg.min_confidence,
                    grab_center=(grab_x, grab_y),
                    frame_size=(width, height),
                    max_dx_px=cfg.single_target_max_dx_px,
                    max_dy_px=cfg.single_target_max_dy_px,
                    min_area_ratio=cfg.single_target_min_area_ratio,
                    max_area_ratio=cfg.single_target_max_area_ratio,
                )
                if (
                    args.fallback_dark
                    and not solve_result.slots
                    and (cfg.target_class or "").strip().lower() == "rack_connector"
                ):
                    fallback_detection = detect_dark_connector(
                        frame,
                        grab_center=(grab_x, grab_y),
                        threshold=args.fallback_threshold,
                        min_area=args.fallback_min_area,
                        cls_name=cfg.target_class,
                    )
                    if fallback_detection is not None:
                        solve_result = solve_single_target(
                            detections=[fallback_detection],
                            target_slot=cfg.target_slot,
                            target_class=cfg.target_class,
                            min_confidence=0.01,
                            grab_center=(grab_x, grab_y),
                            frame_size=(width, height),
                            max_dx_px=cfg.single_target_max_dx_px,
                            max_dy_px=cfg.single_target_max_dy_px,
                            min_area_ratio=cfg.single_target_min_area_ratio,
                            max_area_ratio=cfg.single_target_max_area_ratio,
                        )
                        solve_result.message = "fallback_dark_connector"
            else:
                solve_result = solver.solve(detections)
            output = stabilizer.update(solve_result, width, height)

            output_json = output.to_json()
            if not args.no_json:
                print(output_json, flush=True)
            if json_out is not None:
                json_out.write(output_json + "\n")
                json_out.flush()

            if args.show:
                annotated = draw_alignment(
                    frame,
                    solve_result,
                    output,
                    (grab_x, grab_y),
                    detections=(
                        detections + ([fallback_detection] if fallback_detection is not None else [])
                        if args.draw_detections
                        else None
                    ),
                )
                cv2.imshow(window_name, annotated)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break
    finally:
        if json_out is not None:
            json_out.close()
        cap.release()
        if args.show:
            cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
