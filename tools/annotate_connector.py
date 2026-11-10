"""Minimal YOLO bbox annotator for connector-like classes.

Controls:
- Drag left mouse button: draw one connector box; repeat for multiple boxes.
- s: save current labels and go next; empty labels are allowed after c.
- n or d: next image without saving.
- a: previous image.
- z or BACKSPACE: delete last box.
- c: clear all boxes.
- q or ESC: quit.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", required=True)
    parser.add_argument("--class-name", default="connector")
    parser.add_argument("--class-id", type=int, default=0)
    return parser.parse_args()


def load_images(path: Path):
    return sorted(p for p in path.iterdir() if p.suffix.lower() in IMAGE_EXTS)


def label_path(image_path: Path) -> Path:
    return image_path.with_suffix(".txt")


def read_existing_boxes(image_path: Path):
    txt = label_path(image_path)
    if not txt.exists():
        return []
    lines = [line.strip() for line in txt.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return []
    image = cv2.imread(str(image_path))
    if image is None:
        return []
    ih, iw = image.shape[:2]
    boxes = []
    for line in lines:
        parts = line.split()
        if len(parts) != 5:
            continue
        _, cx, cy, w, h = map(float, parts)
        x1 = int((cx - w / 2) * iw)
        y1 = int((cy - h / 2) * ih)
        x2 = int((cx + w / 2) * iw)
        y2 = int((cy + h / 2) * ih)
        box = normalize_box((x1, y1, x2, y2), iw, ih)
        if box is not None:
            boxes.append(box)
    return boxes


def normalize_box(box, width, height):
    x1, y1, x2, y2 = box
    x1, x2 = sorted((max(0, min(width - 1, int(x1))), max(0, min(width - 1, int(x2)))))
    y1, y2 = sorted((max(0, min(height - 1, int(y1))), max(0, min(height - 1, int(y2)))))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def save_yolo(image_path: Path, boxes, class_id: int):
    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError(f"cannot read {image_path}")
    ih, iw = image.shape[:2]
    lines = []
    for box in boxes:
        normalized = normalize_box(box, iw, ih)
        if normalized is None:
            continue
        x1, y1, x2, y2 = normalized
        cx = ((x1 + x2) / 2) / iw
        cy = ((y1 + y2) / 2) / ih
        w = (x2 - x1) / iw
        h = (y2 - y1) / ih
        lines.append(f"{class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
    label_path(image_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    args = parse_args()
    image_dir = Path(args.images)
    images = load_images(image_dir)
    if not images:
        raise SystemExit(f"no images found in {image_dir}")

    (image_dir / "classes.txt").write_text(f"{args.class_name}\n", encoding="utf-8")

    index = 0
    drawing = False
    start = None
    boxes = []
    preview_box = None
    window = "annotate connector"

    def mouse(event, x, y, flags, param):
        nonlocal drawing, start, boxes, preview_box
        if event == cv2.EVENT_LBUTTONDOWN:
            drawing = True
            start = (x, y)
            preview_box = None
        elif event == cv2.EVENT_MOUSEMOVE and drawing and start is not None:
            preview_box = (start[0], start[1], x, y)
        elif event == cv2.EVENT_LBUTTONUP and drawing and start is not None:
            drawing = False
            preview_box = (start[0], start[1], x, y)
            image = cv2.imread(str(images[index]))
            if image is not None:
                ih, iw = image.shape[:2]
                normalized = normalize_box(preview_box, iw, ih)
                if normalized is not None:
                    boxes.append(normalized)
            preview_box = None

    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window, mouse)

    while 0 <= index < len(images):
        image_path = images[index]
        boxes = read_existing_boxes(image_path)
        preview_box = None

        while index < len(images) and images[index] == image_path:
            image = cv2.imread(str(image_path))
            if image is None:
                index += 1
                break
            ih, iw = image.shape[:2]

            frame = image.copy()
            for box_index, box in enumerate(boxes, start=1):
                normalized = normalize_box(box, iw, ih)
                if normalized is not None:
                    x1, y1, x2, y2 = normalized
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
                    cv2.putText(
                        frame,
                        f"{args.class_name} {box_index}",
                        (x1, max(20, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 255),
                        2,
                    )

            if preview_box is not None:
                normalized = normalize_box(preview_box, iw, ih)
                if normalized is not None:
                    x1, y1, x2, y2 = normalized
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (80, 220, 255), 1)

            text = f"{index + 1}/{len(images)} {image_path.name}  boxes:{len(boxes)} | s save | z undo | n next | a prev | c clear | q quit"
            cv2.putText(frame, text, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
            cv2.imshow(window, frame)

            key = cv2.waitKey(20) & 0xFF
            if key in (27, ord("q")):
                index = len(images)
                break
            if key in (ord("c"),):
                boxes = []
            elif key in (ord("z"), 8):
                if boxes:
                    boxes.pop()
            elif key in (ord("s"),):
                save_yolo(image_path, boxes, args.class_id)
                print(f"saved {label_path(image_path)} boxes:{len(boxes)}")
                index += 1
                boxes = []
                break
            elif key in (ord("n"), ord("d")):
                index += 1
                boxes = []
                break
            elif key in (ord("a"),):
                index = max(0, index - 1)
                boxes = []
                break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
