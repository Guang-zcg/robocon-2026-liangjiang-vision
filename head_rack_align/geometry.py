"""Geometry solver for the six-slot weapon-head rack."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, hypot
from typing import Iterable, Optional

import numpy as np

from .constants import RACK_SLOT_COUNT, SLOT_TYPES, TYPE_ALIASES
from .types import Detection, SlotObservation


@dataclass(slots=True)
class RackSolveResult:
    status: str
    slots: list[SlotObservation]
    axis_angle_deg: Optional[float]
    detected_count: int
    accepted_count: int
    message: str = ""

    def target(self, slot: int) -> Optional[SlotObservation]:
        for obs in self.slots:
            if obs.slot == slot:
                return obs
        return None


class RackGeometrySolver:
    """Estimate fixed rack slot positions from partial YOLO detections.

    The rule-book order is fixed north to south. In the camera image this
    package defines "slot 1" as the smaller projection value along the fitted
    rack axis. If the camera is mounted from the opposite side, set
    ``reverse_axis=True`` in the constructor.
    """

    def __init__(
        self,
        min_detections: int = 3,
        min_confidence: float = 0.35,
        type_consistency_weight: float = 0.18,
        max_slot_spacing_cv: float = 0.45,
        reverse_axis: bool = False,
    ):
        self.min_detections = max(2, int(min_detections))
        self.min_confidence = float(min_confidence)
        self.type_consistency_weight = float(type_consistency_weight)
        self.max_slot_spacing_cv = float(max_slot_spacing_cv)
        self.reverse_axis = bool(reverse_axis)

    def solve(self, detections: Iterable[Detection]) -> RackSolveResult:
        detections = list(detections)
        accepted = [d for d in detections if d.confidence >= self.min_confidence]
        accepted = [self._normalize_detection(d) for d in accepted]
        if len(accepted) < self.min_detections:
            return RackSolveResult(
                status="search",
                slots=[],
                axis_angle_deg=None,
                detected_count=len(detections),
                accepted_count=len(accepted),
                message="not enough detections",
            )

        points = np.array([[d.x, d.y] for d in accepted], dtype=np.float64)
        center = points.mean(axis=0)
        _, _, vh = np.linalg.svd(points - center, full_matrices=False)
        axis = vh[0]
        if self.reverse_axis:
            axis = -axis
        projections = (points - center) @ axis

        order = np.argsort(projections)
        ordered_dets = [accepted[int(i)] for i in order]
        ordered_t = projections[order]

        if len(ordered_t) >= 3:
            gaps = np.diff(ordered_t)
            mean_gap = float(np.mean(np.abs(gaps)))
            if mean_gap <= 1.0:
                return RackSolveResult("search", [], None, len(accepted), len(accepted), "degenerate rack axis")
            spacing_cv = float(np.std(np.abs(gaps)) / mean_gap)
            if spacing_cv > self.max_slot_spacing_cv and len(accepted) >= RACK_SLOT_COUNT:
                return RackSolveResult(
                    "search",
                    [],
                    self._axis_angle(axis),
                    len(accepted),
                    len(accepted),
                    "detections are not rack-like",
                )

        slots = self._assign_slots(ordered_dets, ordered_t, axis)
        if not slots:
            return RackSolveResult(
                "search",
                [],
                self._axis_angle(axis),
                len(accepted),
                len(accepted),
                "slot assignment failed",
            )

        return RackSolveResult(
            status="tracking",
            slots=slots,
            axis_angle_deg=self._axis_angle(axis),
            detected_count=len(accepted),
            accepted_count=len(accepted),
        )

    def _assign_slots(self, ordered_dets: list[Detection], ordered_t: np.ndarray, axis: np.ndarray) -> list[SlotObservation]:
        candidates = []
        det_count = len(ordered_dets)
        for start_slot in range(1, RACK_SLOT_COUNT - det_count + 2):
            end_slot = start_slot + det_count - 1
            expected_slots = list(range(start_slot, end_slot + 1))
            type_score = self._type_score(ordered_dets, expected_slots)
            span = float(ordered_t[-1] - ordered_t[0]) if det_count > 1 else 0.0
            pitch = span / max(1, end_slot - start_slot)
            if pitch <= 1.0:
                continue
            fit_score = self._fit_score(ordered_t, expected_slots, pitch)
            score = fit_score + type_score * self.type_consistency_weight
            candidates.append((score, start_slot, pitch))

        if not candidates:
            return []

        _, start_slot, pitch = max(candidates, key=lambda item: item[0])
        first_t = float(ordered_t[0] - (start_slot - 1) * pitch)
        normal = np.array([-axis[1], axis[0]], dtype=np.float64)
        points = np.array([[d.x, d.y] for d in ordered_dets], dtype=np.float64)
        center = points.mean(axis=0)
        lateral_offsets = (points - center) @ normal
        mean_lateral = float(np.mean(lateral_offsets))
        origin = center + normal * mean_lateral + axis * (first_t - float(np.mean(ordered_t)))

        matched_by_slot: dict[int, Detection] = {}
        for idx, det in enumerate(ordered_dets):
            slot = start_slot + idx
            if 1 <= slot <= RACK_SLOT_COUNT:
                matched_by_slot[slot] = det

        observations = []
        for slot in range(1, RACK_SLOT_COUNT + 1):
            target_point = origin + axis * ((slot - 1) * pitch)
            matched = matched_by_slot.get(slot)
            if matched is not None:
                x, y = matched.x, matched.y
                conf = matched.confidence
                inferred = False
            else:
                x, y = float(target_point[0]), float(target_point[1])
                conf = max(0.05, self._neighbor_confidence(slot, matched_by_slot) * 0.55)
                inferred = True
            observations.append(
                SlotObservation(
                    slot=slot,
                    slot_type=SLOT_TYPES[slot],
                    x=float(x),
                    y=float(y),
                    confidence=float(conf),
                    matched_detection=matched,
                    inferred=inferred,
                )
            )
        return observations

    def _fit_score(self, ordered_t: np.ndarray, expected_slots: list[int], pitch: float) -> float:
        first_t = float(ordered_t[0] - (expected_slots[0] - 1) * pitch)
        err = 0.0
        for t, slot in zip(ordered_t, expected_slots):
            expected_t = first_t + (slot - 1) * pitch
            err += abs(float(t) - expected_t) / pitch
        return -err / max(1, len(expected_slots))

    def _type_score(self, detections: list[Detection], slots: list[int]) -> float:
        score = 0.0
        for det, slot in zip(detections, slots):
            if det.cls_name == SLOT_TYPES[slot]:
                score += 1.0
            elif det.cls_name:
                score -= 0.35
        return score / max(1, len(detections))

    @staticmethod
    def _neighbor_confidence(slot: int, matched_by_slot: dict[int, Detection]) -> float:
        values = []
        for neighbor in (slot - 1, slot + 1):
            if neighbor in matched_by_slot:
                values.append(matched_by_slot[neighbor].confidence)
        if not values:
            return 0.1
        return sum(values) / len(values)

    @staticmethod
    def _axis_angle(axis: np.ndarray) -> float:
        return degrees(atan2(float(axis[1]), float(axis[0])))

    @staticmethod
    def _normalize_detection(det: Detection) -> Detection:
        cls_name = TYPE_ALIASES.get(str(det.cls_name).strip().lower(), str(det.cls_name).strip().lower())
        return Detection(
            x=det.x,
            y=det.y,
            w=det.w,
            h=det.h,
            confidence=det.confidence,
            cls_name=cls_name,
            angle_deg=det.angle_deg,
        )
