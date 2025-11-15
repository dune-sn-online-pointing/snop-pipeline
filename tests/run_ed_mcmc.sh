#!/usr/bin/env bash
# Example runner: run ED inference on MT clusters, then run MCMC
set -euo pipefail

ED_MODEL="/path/to/ed_model"
VOLUMES_NPZ="/path/to/volumes.npz"
MT_RESULTS_NPZ="/path/to/mt_results.npz"
ED_OUT="results/ed_inference_on_mt.npz"
MCMC_OUT="results/ed_mcmc_results.npz"

mkdir -p $(dirname "$ED_OUT")

# Run ED inference for MT-selected clusters
python3 python/ed_inference_from_mt.py "$ED_MODEL" "$VOLUMES_NPZ" "$MT_RESULTS_NPZ" --out "$ED_OUT"

# Run MCMC on ED outputs
python3 python/ed_mcmc.py "$ED_OUT" --out "$MCMC_OUT" --nsteps 3000 --proposal-scale 0.08

echo "ED MCMC results written to $MCMC_OUT"
