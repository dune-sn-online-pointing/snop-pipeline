#!/usr/bin/env bash
# Example: run CT on prepared volumes
set -euo pipefail

MODEL_PATH="/path/to/ct_model"
VOLUMES_NPZ="/path/to/volumes.npz"
OUT="results/ct_predictions.npz"

mkdir -p $(dirname "$OUT")
python3 python/channel_tagger_runner.py "$MODEL_PATH" "$VOLUMES_NPZ" --out "$OUT"
echo "CT predictions written to $OUT"
