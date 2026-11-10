"""Demo reader for R2 state-machine integration.

This script starts the vision app as a subprocess, reads JSON lines from
stdout, and prints the action a state machine would take. Replace the
print statements with chassis/gripper commands in the real R2 code.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=int, default=1)
    parser.add_argument("--model", default=r"models\rack_connector_v5_single_slot_best.pt")
    parser.add_argument("--config", default=r"configs\r2_gripper.yaml")
    parser.add_argument("--conf", type=float, default=0.40)
    parser.add_argument("--iou", type=float, default=0.25)
    parser.add_argument("--deadband", type=float, default=8.0)
    parser.add_argument("--show", action="store_true")
    return parser.parse_args()


def decide_action(output: dict, deadband: float) -> str:
    status = output.get("status")
    dx = output.get("dx_px")
    control_code = output.get("control_code")
    x_direction = output.get("x_direction")
    if control_code == -2 or status in {"search", "lost"} or dx is None:
        return "NO_GRAB search_or_reposition"
    if control_code == 2 or status == "locked":
        return "READY_TO_GRAB verify_mechanics_then_close"
    if control_code == 1 or x_direction == 1:
        return "NUDGE_RIGHT"
    if control_code == -1 or x_direction == -1:
        return "NUDGE_LEFT"
    if abs(float(dx)) <= deadband:
        return "HOLD_SLOW"
    if float(dx) > 0:
        return "NUDGE_RIGHT"
    return "NUDGE_LEFT"


def main():
    args = parse_args()
    cmd = [
        sys.executable,
        "-m",
        "head_rack_align.app",
        "--model",
        args.model,
        "--camera",
        str(args.camera),
        "--config",
        args.config,
        "--conf",
        str(args.conf),
        "--iou",
        str(args.iou),
    ]
    if args.show:
        cmd += ["--draw-detections", "--show"]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line.startswith("{"):
                continue
            output = json.loads(line)
            action = decide_action(output, args.deadband)
            print(
                f"{action} status={output['status']} dx={output['dx_px']} "
                f"code={output.get('control_code')} xdir={output.get('x_direction')} "
                f"valid={output.get('target_valid')} conf={output['confidence']:.2f} "
                f"stable={output['stable_frames']}"
            )
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
