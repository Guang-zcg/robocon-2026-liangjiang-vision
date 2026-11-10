"""Temporal lock logic for slot alignment."""

from __future__ import annotations

from time import monotonic
from typing import Optional

from .constants import SLOT_TYPES
from .geometry import RackSolveResult
from .types import VisionOutput


class SlotLockStabilizer:
    """Convert per-frame rack geometry into state-machine safe statuses."""

    def __init__(
        self,
        target_slot: int,
        grab_center_x: Optional[float],
        grab_center_y: Optional[float],
        target_type: Optional[str] = None,
        alignment_axes: str = "x",
        align_threshold_px: float = 18.0,
        lock_min_confidence: float = 0.25,
        lock_frames: int = 5,
        lost_frames: int = 6,
    ):
        if target_slot not in SLOT_TYPES:
            raise ValueError(f"target_slot must be 1..6, got {target_slot}")
        self.target_slot = int(target_slot)
        self.target_type = target_type or SLOT_TYPES[self.target_slot]
        self.grab_center_x = grab_center_x
        self.grab_center_y = grab_center_y
        self.alignment_axes = self._normalize_axes(alignment_axes)
        self.align_threshold_px = float(align_threshold_px)
        self.lock_min_confidence = float(lock_min_confidence)
        self.lock_frames = max(1, int(lock_frames))
        self.lost_frames = max(1, int(lost_frames))
        self.stable_frames = 0
        self.lost_count = 0
        self.has_seen_rack = False

    def update(self, solve_result: RackSolveResult, frame_width: int, frame_height: int) -> VisionOutput:
        timestamp_ms = int(monotonic() * 1000)
        grab_x = self.grab_center_x if self.grab_center_x is not None else frame_width / 2.0
        grab_y = self.grab_center_y if self.grab_center_y is not None else frame_height / 2.0

        target = solve_result.target(self.target_slot)
        if target is None:
            self.stable_frames = 0
            self.lost_count += 1
            status = "lost" if self.has_seen_rack and self.lost_count >= self.lost_frames else "search"
            return VisionOutput(
                status=status,
                target_slot=self.target_slot,
                target_type=self.target_type,
                dx_px=None,
                dy_px=None,
                confidence=0.0,
                stable_frames=0,
                timestamp_ms=timestamp_ms,
                target_valid=0,
                control_code=-2,
                x_direction=0,
                action_hint="no_target",
                angle_deg=solve_result.axis_angle_deg,
                detected_slots=len(solve_result.slots),
                alignment_axes=self.alignment_axes,
                message=solve_result.message,
            )

        self.has_seen_rack = True
        self.lost_count = 0
        dx = target.x - grab_x
        dy = target.y - grab_y
        aligned = self._is_aligned(dx, dy)

        lock_eligible = aligned and not target.inferred and target.confidence >= self.lock_min_confidence

        if lock_eligible:
            self.stable_frames += 1
        else:
            self.stable_frames = 0

        if self.stable_frames >= self.lock_frames:
            status = "locked"
        elif aligned:
            status = "aligned"
        else:
            status = "tracking"

        x_direction = self._x_direction(dx)
        control_code = self._control_code(status, x_direction)
        action_hint = self._action_hint(control_code)

        return VisionOutput(
            status=status,
            target_slot=self.target_slot,
            target_type=target.slot_type,
            dx_px=float(dx),
            dy_px=float(dy),
            confidence=float(target.confidence),
            stable_frames=self.stable_frames,
            timestamp_ms=timestamp_ms,
            target_valid=1,
            control_code=control_code,
            x_direction=x_direction,
            action_hint=action_hint,
            angle_deg=solve_result.axis_angle_deg,
            detected_slots=len([s for s in solve_result.slots if not s.inferred]),
            alignment_axes=self.alignment_axes,
            message="target inferred" if target.inferred else solve_result.message,
        )

    def _is_aligned(self, dx: float, dy: float) -> bool:
        if self.alignment_axes == "x":
            return abs(dx) <= self.align_threshold_px
        if self.alignment_axes == "y":
            return abs(dy) <= self.align_threshold_px
        return abs(dx) <= self.align_threshold_px and abs(dy) <= self.align_threshold_px

    def _x_direction(self, dx: float) -> int:
        if "x" not in self.alignment_axes:
            return 0
        if dx > self.align_threshold_px:
            return 1
        if dx < -self.align_threshold_px:
            return -1
        return 0

    @staticmethod
    def _control_code(status: str, x_direction: int) -> int:
        if status == "locked":
            return 2
        return x_direction

    @staticmethod
    def _action_hint(control_code: int) -> str:
        if control_code == -2:
            return "no_target"
        if control_code == 2:
            return "ready_to_grab"
        if control_code == 1:
            return "nudge_right"
        if control_code == -1:
            return "nudge_left"
        return "hold"

    @staticmethod
    def _normalize_axes(alignment_axes: str) -> str:
        axes = (alignment_axes or "x").strip().lower()
        if axes not in {"x", "y", "xy"}:
            raise ValueError("alignment_axes must be x, y, or xy")
        return axes
