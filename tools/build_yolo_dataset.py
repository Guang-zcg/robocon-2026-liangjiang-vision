"""Build a YOLO dataset from one or more raw image folders.

The raw folders are expected to contain images and YOLO label txt files with
the same stem. Images without labels are skipped by default.
"""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", nargs="+", required=True)
    parser.add_argument("--negative-sources", nargs="*", default=[])
    parser.add_argument("--out", required=True)
    parser.add_argument("--class-name", default="rack_connector")
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--include-unlabeled", action="store_true")
    return parser.parse_args()


def collect_samples(sources: list[Path], include_unlabeled: bool):
    samples = []
    skipped = 0
    for source in sources:
        if not source.exists():
            raise SystemExit(f"source does not exist: {source}")
        for image_path in sorted(p for p in source.iterdir() if p.suffix.lower() in IMAGE_EXTS):
            label_path = image_path.with_suffix(".txt")
            if not label_path.exists() and not include_unlabeled:
                skipped += 1
                continue
            samples.append((source, image_path, label_path if label_path.exists() else None))
    return samples, skipped


def collect_negative_samples(sources: list[Path]):
    samples = []
    for source in sources:
        if not source.exists():
            raise SystemExit(f"negative source does not exist: {source}")
        for image_path in sorted(p for p in source.iterdir() if p.suffix.lower() in IMAGE_EXTS):
            samples.append((source, image_path, None))
    return samples


def prepare_dirs(out: Path):
    for split in ("train", "val"):
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)


def copy_sample(sample, split: str, out: Path):
    source, image_path, label_path = sample
    prefix = source.name
    dst_name = f"{prefix}_{image_path.name}"
    dst_image = out / "images" / split / dst_name
    dst_label = out / "labels" / split / f"{Path(dst_name).stem}.txt"
    shutil.copy2(image_path, dst_image)
    if label_path is None:
        dst_label.write_text("", encoding="utf-8")
    else:
        shutil.copy2(label_path, dst_label)


def write_yaml(out: Path, class_name: str):
    yaml_text = "\n".join(
        [
            f"path: {out.as_posix()}",
            "train: images/train",
            "val: images/val",
            "names:",
            f"  0: {class_name}",
            "",
        ]
    )
    yaml_path = out / f"{out.name}.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")
    return yaml_path


def main():
    args = parse_args()
    out = Path(args.out)
    sources = [Path(item) for item in args.sources]
    negative_sources = [Path(item) for item in args.negative_sources]
    samples, skipped = collect_samples(sources, args.include_unlabeled)
    negative_samples = collect_negative_samples(negative_sources)
    samples.extend(negative_samples)
    if not samples:
        raise SystemExit("no labeled images found")

    random.seed(args.seed)
    random.shuffle(samples)
    val_count = max(1, int(round(len(samples) * args.val_ratio))) if len(samples) > 1 else 0
    val_samples = samples[:val_count]
    train_samples = samples[val_count:]

    prepare_dirs(out)
    for sample in train_samples:
        copy_sample(sample, "train", out)
    for sample in val_samples:
        copy_sample(sample, "val", out)
    yaml_path = write_yaml(out, args.class_name)

    print(f"train images: {len(train_samples)}")
    print(f"val images: {len(val_samples)}")
    print(f"negative images: {len(negative_samples)}")
    print(f"skipped unlabeled images: {skipped}")
    print(f"dataset yaml: {yaml_path}")


if __name__ == "__main__":
    main()
