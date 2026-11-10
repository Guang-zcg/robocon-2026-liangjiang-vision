#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CAMERA="${CAMERA:-0}"
DEVICE="${DEVICE:-0}"
CONF="${CONF:-0.40}"
IOU="${IOU:-0.25}"
WIDTH="${WIDTH:-640}"
HEIGHT="${HEIGHT:-480}"
MODEL="${MODEL:-models/rack_connector_v5_single_slot_best.pt}"
CONFIG="${CONFIG:-configs/r2_gripper.yaml}"
JSON_OUT="${JSON_OUT:-}"
SHOW="${SHOW:-0}"

export PYTHONPATH="$ROOT"
export YOLO_CONFIG_DIR="$ROOT/Ultralytics"
export MPLCONFIGDIR="$ROOT/matplotlib_cache"

ARGS=(
  -m head_rack_align.app
  --model "$MODEL"
  --config "$CONFIG"
  --camera "$CAMERA"
  --device "$DEVICE"
  --width "$WIDTH"
  --height "$HEIGHT"
  --conf "$CONF"
  --iou "$IOU"
)

if [[ -n "$JSON_OUT" ]]; then
  ARGS+=(--json-out "$JSON_OUT")
fi

if [[ "$SHOW" == "1" ]]; then
  ARGS+=(--draw-detections --show)
fi

python3 "${ARGS[@]}"
