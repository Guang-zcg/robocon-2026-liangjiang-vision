"""Run head-rack alignment on one image for offline debugging."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from head_rack_align.camera import CameraCalibration, crop_roi
from head_rack_align.config import load_config
from head_rack_align.detector import YoloHeadDetector
from head_rack_align.draw import draw_alignment
from head_rack_align.geometry import RackGeometrySolver
from head_rack_align.stabilizer import SlotLockStabilizer
from head_rack_align.targeting import solve_single_target


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--config", default=None)
    parser.add_argument("--target-slot", type=int, default=None)
    parser.add_argument("--target-mode", choices=["slot", "single"], default=None)
    parser.add_argument("--target-class", default=None)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--calibration", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--show", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = load_config(args.config)
    if args.target_slot is not None:
        cfg.target_slot = args.target_slot
    if args.target_mode is not None:
        cfg.target_mode = args.target_mode
    if args.target_class is not None:
        cfg.target_class = args.target_class
    frame = cv2.imread(args.image)
    if frame is None:
        raise SystemExit(f"cannot read image: {args.image}")
    calibration = CameraCalibration.load(args.calibration)
    if calibration is not None:
        frame = calibration.undistort(frame)
    detector = YoloHeadDetector(args.model, device=args.device)
    solver = RackGeometrySolver(cfg.min_detections, cfg.min_confidence, cfg.type_consistency_weight, cfg.max_slot_spacing_cv)
    stabilizer = SlotLockStabilizer(
        target_slot=cfg.target_slot,
        grab_center_x=cfg.grab_center_x,
        grab_center_y=cfg.grab_center_y,
        target_type=cfg.target_class,
        alignment_axes=cfg.alignment_axes,
        align_threshold_px=cfg.align_threshold_px,
        lock_min_confidence=cfg.lock_min_confidence,
        lock_frames=1,
        lost_frames=cfg.lost_frames,
    )
    roi_frame, offset = crop_roi(frame, cfg.roi)
    detections = detector.predict(roi_frame, offset=offset)
    if cfg.target_mode == "single":
        result = solve_single_target(detections, cfg.target_slot, cfg.target_class, cfg.min_confidence)
    else:
        result = solver.solve(detections)
    output = stabilizer.update(result, frame.shape[1], frame.shape[0])
    print(output.to_json())
    grab_x = cfg.grab_center_x if cfg.grab_center_x is not None else frame.shape[1] / 2.0
    grab_y = cfg.grab_center_y if cfg.grab_center_y is not None else frame.shape[0] / 2.0
    annotated = draw_alignment(frame, result, output, (grab_x, grab_y))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(args.out, annotated)
    if args.show:
        cv2.imshow("head rack image debug", annotated)
        cv2.waitKey(0)


if __name__ == "__main__":
    main()
