"""Auto-label images with a YOLO model and save labels beside images.

This is intended as a first-pass helper before manual review. It writes
YOLO-format .txt files next to each image, using class id 0 by default.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--images", required=True)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.25)
    parser.add_argument("--class-id", type=int, default=0)
    parser.add_argument("--max-boxes", type=int, default=1)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def image_paths(folder: Path):
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTS)


def write_label(path: Path, boxes, class_id: int):
    lines = []
    for xywhn in boxes:
        cx, cy, w, h = [float(v) for v in xywhn]
        lines.append(f"{class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def main():
    args = parse_args()
    folder = Path(args.images)
    images = image_paths(folder)
    if not images:
        raise SystemExit(f"no images found in {folder}")

    model = YOLO(args.model)
    written = 0
    skipped_existing = 0
    no_detection = 0

    for image in images:
        label_path = image.with_suffix(".txt")
        if label_path.exists() and not args.overwrite:
            skipped_existing += 1
            continue

        result = model.predict(
            source=str(image),
            conf=args.conf,
            iou=args.iou,
            verbose=False,
        )[0]

        boxes = []
        if result.boxes is not None and len(result.boxes) > 0:
            conf_order = result.boxes.conf.argsort(descending=True)
            for idx in conf_order[: args.max_boxes]:
                boxes.append(result.boxes.xywhn[int(idx)].tolist())

        if not boxes:
            no_detection += 1
            continue

        write_label(label_path, boxes, args.class_id)
        written += 1

    (folder / "classes.txt").write_text("rack_connector\n", encoding="utf-8")
    print(f"images: {len(images)}")
    print(f"labels written: {written}")
    print(f"skipped existing labels: {skipped_existing}")
    print(f"no detection: {no_detection}")


if __name__ == "__main__":
    main()
