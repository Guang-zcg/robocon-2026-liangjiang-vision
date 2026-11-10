"""Debug drawing helpers."""

from __future__ import annotations

import cv2


def draw_alignment(frame, solve_result, output, grab_center, detections=None):
    annotated = frame.copy()
    cx, cy = int(grab_center[0]), int(grab_center[1])
    cv2.drawMarker(annotated, (cx, cy), (0, 255, 255), markerType=cv2.MARKER_CROSS, markerSize=22, thickness=2)

    if detections:
        for det in detections:
            x1 = int(det.x - det.w / 2)
            y1 = int(det.y - det.h / 2)
            x2 = int(det.x + det.w / 2)
            y2 = int(det.y + det.h / 2)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (180, 80, 255), 2)
            cv2.putText(
                annotated,
                f"{det.cls_name} {det.confidence:.2f}",
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (180, 80, 255),
                2,
            )

    for slot in solve_result.slots:
        color = (80, 180, 255) if slot.inferred else (0, 220, 0)
        if slot.slot == output.target_slot:
            color = (0, 0, 255) if output.status == "locked" else (255, 80, 80)
        x, y = int(slot.x), int(slot.y)
        cv2.circle(annotated, (x, y), 7, color, -1)
        cv2.putText(
            annotated,
            f"{slot.slot}:{slot.slot_type}",
            (x + 8, y - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
        )

    dx_text = "None" if output.dx_px is None else f"{output.dx_px:.1f}"
    dy_text = "None" if output.dy_px is None else f"{output.dy_px:.1f}"
    cv2.putText(
        annotated,
        (
            f"{output.status} code={output.control_code} slot={output.target_slot} "
            f"dx={dx_text} dy={dy_text} stable={output.stable_frames}"
        ),
        (16, 34),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (0, 255, 255),
        2,
    )
    return annotated
