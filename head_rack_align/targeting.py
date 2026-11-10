"""Target selection modes for gripper visual correction."""

from __future__ import annotations

from .constants import SLOT_TYPES, TYPE_ALIASES
from .geometry import RackSolveResult
from .types import Detection, SlotObservation


def solve_single_target(
    detections: list[Detection],
    target_slot: int,
    target_class: str | None = None,
    min_confidence: float = 0.35,
    grab_center: tuple[float, float] | None = None,
    frame_size: tuple[int, int] | None = None,
    max_dx_px: float | None = None,
    max_dy_px: float | None = None,
    min_area_ratio: float = 0.0,
    max_area_ratio: float = 1.0,
) -> RackSolveResult:
    """Build a solver-like result from the best matching single detection.

    This mode is useful before the full rack is mechanically available:
    place one weapon head in front of the gripper camera and verify that
    dx/dy move in the expected direction.
    """

    expected_type = target_class or SLOT_TYPES[target_slot]
    expected_type = TYPE_ALIASES.get(str(expected_type).strip().lower(), str(expected_type).strip().lower())
    candidates = [
        _normalize_detection(det)
        for det in detections
        if det.confidence >= min_confidence and _normalize_detection(det).cls_name == expected_type
    ]
    if not candidates:
        return RackSolveResult(
            status="search",
            slots=[],
            axis_angle_deg=None,
            detected_count=len(detections),
            accepted_count=0,
            message=f"no {expected_type} target",
        )

    guarded = [
        det
        for det in candidates
        if _passes_single_target_guards(
            det,
            grab_center=grab_center,
            frame_size=frame_size,
            max_dx_px=max_dx_px,
            max_dy_px=max_dy_px,
            min_area_ratio=min_area_ratio,
            max_area_ratio=max_area_ratio,
        )
    ]
    if not guarded:
        return RackSolveResult(
            status="search",
            slots=[],
            axis_angle_deg=None,
            detected_count=len(detections),
            accepted_count=0,
            message=f"no {expected_type} target after guards",
        )

    guarded = _deduplicate_single_target_candidates(guarded)
    target = max(guarded, key=lambda det: _single_target_score(det, grab_center, max_dx_px, max_dy_px))
    return RackSolveResult(
        status="tracking",
        slots=[
            SlotObservation(
                slot=target_slot,
                slot_type=expected_type,
                x=target.x,
                y=target.y,
                confidence=target.confidence,
                matched_detection=target,
                inferred=False,
            )
        ],
        axis_angle_deg=target.angle_deg,
        detected_count=len(detections),
        accepted_count=len(guarded),
        message="single_target",
    )


def _normalize_detection(det: Detection) -> Detection:
    cls_name = TYPE_ALIASES.get(str(det.cls_name).strip().lower(), str(det.cls_name).strip().lower())
    if cls_name == det.cls_name:
        return det
    return Detection(
        x=det.x,
        y=det.y,
        w=det.w,
        h=det.h,
        confidence=det.confidence,
        cls_name=cls_name,
        angle_deg=det.angle_deg,
    )


def _passes_single_target_guards(
    det: Detection,
    grab_center: tuple[float, float] | None,
    frame_size: tuple[int, int] | None,
    max_dx_px: float | None,
    max_dy_px: float | None,
    min_area_ratio: float,
    max_area_ratio: float,
) -> bool:
    if grab_center is not None:
        gx, gy = grab_center
        if max_dx_px is not None and abs(det.x - gx) > float(max_dx_px):
            return False
        if max_dy_px is not None and abs(det.y - gy) > float(max_dy_px):
            return False

    if frame_size is not None:
        width, height = frame_size
        frame_area = max(1.0, float(width * height))
        area_ratio = float(det.w * det.h) / frame_area
        if area_ratio < float(min_area_ratio):
            return False
        if area_ratio > float(max_area_ratio):
            return False
    return True


def _deduplicate_single_target_candidates(candidates: list[Detection]) -> list[Detection]:
    """Collapse duplicate boxes on the same physical connector.

    YOLO can return one box for the upper connector body and another for the
    lower ring. For x-only gripper correction the higher-confidence box is a
    better representative than a lower-confidence partial duplicate.
    """

    groups: list[list[Detection]] = []
    for det in sorted(candidates, key=lambda item: item.confidence, reverse=True):
        matched_group = None
        for group in groups:
            if any(_same_physical_target(det, other) for other in group):
                matched_group = group
                break
        if matched_group is None:
            groups.append([det])
        else:
            matched_group.append(det)
    return [max(group, key=lambda item: item.confidence) for group in groups]


def _same_physical_target(a: Detection, b: Detection) -> bool:
    ax1, ay1, ax2, ay2 = _xyxy(a)
    bx1, by1, bx2, by2 = _xyxy(b)
    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = inter_w * inter_h
    area_a = max(1.0, (ax2 - ax1) * (ay2 - ay1))
    area_b = max(1.0, (bx2 - bx1) * (by2 - by1))
    iou = inter / max(1.0, area_a + area_b - inter)
    x_overlap = inter_w / max(1.0, min(ax2 - ax1, bx2 - bx1))
    x_close = abs(a.x - b.x) <= 0.35 * max(a.w, b.w, 1.0)
    return iou >= 0.22 or (x_overlap >= 0.55 and x_close)


def _xyxy(det: Detection) -> tuple[float, float, float, float]:
    return (
        det.x - det.w / 2.0,
        det.y - det.h / 2.0,
        det.x + det.w / 2.0,
        det.y + det.h / 2.0,
    )


def _single_target_score(
    det: Detection,
    grab_center: tuple[float, float] | None,
    max_dx_px: float | None,
    max_dy_px: float | None,
) -> float:
    if grab_center is None:
        return det.confidence
    gx, gy = grab_center
    dx_scale = max(1.0, float(max_dx_px) if max_dx_px is not None else 320.0)
    dy_scale = max(1.0, float(max_dy_px) if max_dy_px is not None else 240.0)
    distance_penalty = abs(det.x - gx) / dx_scale + abs(det.y - gy) / dy_scale
    return float(det.confidence) - 0.08 * distance_penalty
