#!/usr/bin/env python3
"""Convert the measured P(ES | CT score) into the calibration format the pipeline consumes.

The re-scan measures P(ES | score) directly on the r3 training slice
(`ct_rescan_tables.py` -> `p_es_given_score_e5.npz`).  The pipeline's scenario-7 path
(`selection_mode: "mixture-ct"`) instead reads a likelihood-ratio calibration
(`s_grid`, `lr_grid`, as written by `build_ct_calibration.py`) and forms

    p(s) = pi LR(s) / (pi LR(s) + 1 - pi)

with pi the assumed ES class prior.  Writing

    LR(s) = [ p_meas(s) / (1 - p_meas(s)) ] * [ (1 - pi0) / pi0 ]

with pi0 the measured ES fraction of the population p_meas was measured on makes the
pipeline reproduce p_meas exactly when it is run with `pi_mode: "fixed"`,
`pi_fixed: pi0`.  The check at the bottom verifies that on the measured grid.

Usage:
  python3 python/ana/ct_rescan_deploy_calib.py --p-es <p_es_given_score_e5.npz> \
      --out <ct_v80_calibration_r3slice_e5.npz>
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from ana.burst_direction import calibrated_p_es, load_ct_calibration

EPS = 1e-6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p-es", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    z = np.load(args.p_es, allow_pickle=True)
    s = np.asarray(z["score_center"], dtype=np.float64)
    p = np.clip(np.asarray(z["p_es_mono"], dtype=np.float64), EPS, 1 - EPS)
    n = np.asarray(z["n"], dtype=np.float64)
    n_es = np.asarray(z["n_es"], dtype=np.float64)
    pi0 = float(n_es.sum() / n.sum())
    lr = (p / (1.0 - p)) * ((1.0 - pi0) / pi0)
    # extend to the full [0, 1] score range with the end values (the pipeline interpolates)
    s_grid = np.concatenate([[0.0], s, [1.0]])
    lr_grid = np.concatenate([[lr[0]], lr, [lr[-1]]])

    np.savez(args.out, s_grid=s_grid, lr_grid=lr_grid, pi0=np.float64(pi0),
             p_es_measured=np.concatenate([[p[0]], p, [p[-1]]]),
             source=np.asarray(str(args.p_es)),
             note=np.asarray("LR(s) = [p/(1-p)] (1-pi0)/pi0 from P(ES|CT v80 score) measured "
                             "on the r3 training slice (cats 673-900, clusters with a valid "
                             "reco direction and E>5 MeV). Use with pi_mode='fixed', "
                             f"pi_fixed={pi0:.6f} to reproduce the measured P(ES|s)."))
    calib = load_ct_calibration(args.out)
    back = calibrated_p_es(s, calib, pi0)
    err = float(np.max(np.abs(back - p)))
    prov = {"p_es_source": str(args.p_es), "pi0": pi0, "n_bins": int(len(s)),
            "max_roundtrip_error": err, "lr_range": [float(lr.min()), float(lr.max())],
            "p_range": [float(p.min()), float(p.max())],
            "deploy": {"selection_mode": "mixture-ct", "pi_mode": "fixed", "pi_fixed": pi0,
                       "calibration_path": str(args.out)}}
    Path(str(args.out).replace(".npz", "_provenance.json")).write_text(json.dumps(prov, indent=2))
    print(f"pi0 = {pi0:.6f}, LR in [{lr.min():.3e}, {lr.max():.3e}], "
          f"round-trip max |p_pipeline - p_measured| = {err:.2e}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
