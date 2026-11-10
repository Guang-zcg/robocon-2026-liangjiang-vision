"""Runtime configuration for head-rack alignment."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass(slots=True)
class AlignmentConfig:
    target_mode: str = "slot"
    target_slot: int = 1
    target_class: Optional[str] = None
    grab_center_x: Optional[float] = None
    grab_center_y: Optional[float] = None
    alignment_axes: str = "x"
    align_threshold_px: float = 18.0
    lock_min_confidence: float = 0.25
    lock_frames: int = 5
    lost_frames: int = 6
    min_detections: int = 3
    min_confidence: float = 0.35
    single_target_max_dx_px: Optional[float] = None
    single_target_max_dy_px: Optional[float] = None
    single_target_min_area_ratio: float = 0.0
    single_target_max_area_ratio: float = 1.0
    type_consistency_weight: float = 0.18
    max_slot_spacing_cv: float = 0.45
    roi: Optional[tuple[int, int, int, int]] = None
    model_names: dict[int, str] = field(default_factory=dict)


def load_config(path: Optional[str]) -> AlignmentConfig:
    if not path:
        return AlignmentConfig()

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    cfg = AlignmentConfig()
    for key, value in data.items():
        if not hasattr(cfg, key):
            continue
        if key == "roi" and value is not None:
            value = tuple(int(v) for v in value)
        setattr(cfg, key, value)
    return cfg
