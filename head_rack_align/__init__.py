"""R2 weapon-head rack alignment vision package."""

from .constants import SLOT_TYPES
from .geometry import RackGeometrySolver
from .stabilizer import SlotLockStabilizer
from .targeting import solve_single_target
from .types import Detection, SlotObservation, VisionOutput

__all__ = [
    "Detection",
    "RackGeometrySolver",
    "SLOT_TYPES",
    "SlotLockStabilizer",
    "SlotObservation",
    "VisionOutput",
    "solve_single_target",
]
