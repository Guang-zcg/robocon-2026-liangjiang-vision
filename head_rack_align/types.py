"""Data structures for rack alignment."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Optional


@dataclass(slots=True)
class Detection:
    """One model detection in image pixel coordinates."""

    x: float
    y: float
    w: float
    h: float
    confidence: float
    cls_name: str
    angle_deg: Optional[float] = None


@dataclass(slots=True)
class SlotObservation:
    """Estimated position of one head-rack slot."""

    slot: int
    slot_type: str
    x: float
    y: float
    confidence: float
    matched_detection: Optional[Detection]
    inferred: bool = False


@dataclass(slots=True)
class VisionOutput:
    """JSON-line output consumed by the R2 state machine."""

    status: str
    target_slot: int
    target_type: str
    dx_px: Optional[float]
    dy_px: Optional[float]
    confidence: float
    stable_frames: int
    timestamp_ms: int
    target_valid: int = 0
    control_code: int = -2
    x_direction: int = 0
    action_hint: str = "hold"
    angle_deg: Optional[float] = None
    detected_slots: int = 0
    alignment_axes: str = "x"
    message: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, separators=(",", ":"))
