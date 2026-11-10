"""YOLO detector adapter."""

from __future__ import annotations

from typing import Optional

from .constants import TYPE_ALIASES
from .types import Detection


class YoloHeadDetector:
    """Adapter from Ultralytics results to package Detection objects."""

    def __init__(
        self,
        model_path: str,
        imgsz: int = 640,
        conf: float = 0.35,
        iou: float = 0.45,
        device: str = "cpu",
        max_det: int = 12,
        classes: Optional[list[int]] = None,
    ):
        from ultralytics import YOLO

        self.model = YOLO(model_path)
        self.imgsz = imgsz
        self.conf = conf
        self.iou = iou
        self.device = device
        self.max_det = max_det
        self.classes = classes

    def predict(self, frame, offset=(0, 0)) -> list[Detection]:
        result = self.model.predict(
            frame,
            imgsz=self.imgsz,
            conf=self.conf,
            iou=self.iou,
            max_det=self.max_det,
            classes=self.classes,
            device=self.device,
            verbose=False,
        )[0]
        return result_to_detections(result, offset=offset)


def result_to_detections(result, offset=(0, 0)) -> list[Detection]:
    xoff, yoff = offset
    names = getattr(result, "names", {}) or {}
    detections = []

    obb = getattr(result, "obb", None)
    if obb is not None and len(obb) > 0:
        xywhr = obb.xywhr.cpu().numpy()
        confs = obb.conf.cpu().numpy()
        cls_ids = obb.cls.cpu().numpy().astype(int)
        for box, conf, cls_id in zip(xywhr, confs, cls_ids):
            raw_name = names.get(int(cls_id), f"class_{int(cls_id)}")
            cls_name = TYPE_ALIASES.get(str(raw_name).lower(), str(raw_name).lower())
            detections.append(
                Detection(
                    x=float(box[0]) + xoff,
                    y=float(box[1]) + yoff,
                    w=float(box[2]),
                    h=float(box[3]),
                    confidence=float(conf),
                    cls_name=cls_name,
                    angle_deg=float(box[4]),
                )
            )
        return detections

    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return []

    xywh = boxes.xywh.cpu().numpy()
    confs = boxes.conf.cpu().numpy()
    cls_ids = boxes.cls.cpu().numpy().astype(int)
    for box, conf, cls_id in zip(xywh, confs, cls_ids):
        raw_name = names.get(int(cls_id), f"class_{int(cls_id)}")
        cls_name = TYPE_ALIASES.get(str(raw_name).lower(), str(raw_name).lower())
        detections.append(
            Detection(
                x=float(box[0]) + xoff,
                y=float(box[1]) + yoff,
                w=float(box[2]),
                h=float(box[3]),
                confidence=float(conf),
                cls_name=cls_name,
            )
        )
    return detections

