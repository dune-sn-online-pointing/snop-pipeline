#!/usr/bin/env python3
"""Offline re-fit of the ed_retrain runs with alternative likelihood tables.

Reads the per-event outputs the runs kept (PRUNE_SCENARIO_OUTPUTS=2, then tarred per cat)
straight out of `<run>/<cat>/<cat>_scenarios.tar`, writes them into a scratch run
directory and re-runs the pipeline's OWN selection and fit
(ana.burst_direction.select_electrons_from_run / reconstruct_burst_direction), so only
the likelihood table changes.

Validation gates: with the table the run itself used, the offline theta68 must reproduce
the run's own number (R6 -> 15.20 with the deployed table, R4 -> 17.27 with the v63 ES
table on the same rows).

Usage:
  python3 python/ana/ed_mixture_eval.py --run <...>/R6_... --scenario scenario_3_full_pipeline \
      --tables T0=<path> T1=<path> ... --cats 623-672 --out <results.npz>
"""
import argparse
import io
import json
import shutil
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from ana.burst_direction import reconstruct_burst_direction, select_electrons_from_run

EMCEE_CFG = {"enabled": True, "nwalkers": 128, "nsteps": 500, "discard": 100,
             "prior_type": "uniform", "prior_sigma_deg": 10.0,
             "likelihood_kappa": 25.0, "random_seed": 42}
SCENARIO_SETTINGS = {
    "scenario_2_perfect_ct":    dict(selection_mode="true-es",      min_energy=3.0, ct_threshold=None),
    "scenario_3_full_pipeline": dict(selection_mode="predicted-es", min_energy=5.0, ct_threshold=0.80),
    "scenario_4_weighted_ct":   dict(selection_mode="weighted-ct",  min_energy=3.0, ct_threshold=None),
    "scenario_6_perfect_ct_e_gt_5mev": dict(selection_mode="true-es", min_energy=5.0, ct_threshold=None),
}


def extract_scenario(tar_path, scenario, dest):
    """Materialise <scenario>/pipeline_run_*/{volume_images,predictions} from a cat tar."""
    with tarfile.open(tar_path) as tf:
        names = tf.getnames()
        vol = [n for n in names if n.startswith(scenario + "/") and n.endswith("volume_images/volumes.npz")]
        if not vol:
            return None
        run_prefix = vol[0].rsplit("/volume_images/", 1)[0]
        dest = Path(dest)
        (dest / "volume_images").mkdir(parents=True, exist_ok=True)
        (dest / "predictions").mkdir(parents=True, exist_ok=True)
        with open(dest / "volume_images" / "volumes.npz", "wb") as fh:
            fh.write(tf.extractfile(vol[0]).read())
        for sub in ("reco_directions.npz", "channel_predictions.npz"):
            n = f"{run_prefix}/predictions/{sub}"
            if n in names:
                with open(dest / "predictions" / sub, "wb") as fh:
                    fh.write(tf.extractfile(n).read())
    return dest


def theta68(cos):
    cos = np.asarray(cos, dtype=np.float64)
    return float(np.degrees(np.arccos(np.clip(np.quantile(cos, 0.32), -1.0, 1.0))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="ed_retrain run directory (source of the rows)")
    ap.add_argument("--scenario", default="scenario_3_full_pipeline")
    ap.add_argument("--tables", nargs="+", required=True, help="TAG=/path/to/table.npz")
    ap.add_argument("--cats", default="623-672")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    lo, hi = (int(x) for x in args.cats.split("-"))
    tables = dict(t.split("=", 1) for t in args.tables)
    st = SCENARIO_SETTINGS[args.scenario]
    scratch = Path(tempfile.mkdtemp(prefix="edmix_"))
    run = Path(args.run)

    res = {tag: {} for tag in tables}
    nsel = {}
    t0 = time.time()
    try:
        for n in range(lo, hi + 1):
            cat = f"cat{n:06d}"
            tar = run / cat / f"{cat}_scenarios.tar"
            if not tar.exists():
                print(f"  {cat}: no tar, skipped", flush=True)
                continue
            work = scratch / cat
            if extract_scenario(tar, args.scenario, work) is None:
                print(f"  {cat}: scenario missing in tar, skipped", flush=True)
                continue
            sel = select_electrons_from_run(
                work, selection_mode=st["selection_mode"], direction_mode="reco",
                min_energy_mev=st["min_energy"], ct_threshold=st["ct_threshold"])
            nsel[cat] = sel["n_selected"]
            for tag, path in tables.items():
                reco = reconstruct_burst_direction(
                    selected_dirs=sel["selected_dirs"], selected_weights=sel["selected_weights"],
                    selected_energies=sel["selected_energy"], true_burst_dir=sel["true_burst_dir"],
                    use_emcee=True, emcee_cfg=EMCEE_CFG, pdf_path=path)
                cos = float(np.clip(np.dot(reco["reco_dir"], sel["true_burst_dir"]), -1, 1)) \
                    if reco["reco_dir"] is not None else float("nan")
                th = reco["theta_samples_deg"]
                res[tag][cat] = (cos, float(np.quantile(th, 0.68)) if th.size else float("nan"),
                                 sel["n_selected"])
            shutil.rmtree(work, ignore_errors=True)
            print(f"  {cat}: n_sel={sel['n_selected']:5d}  " +
                  "  ".join(f"{t}:{np.degrees(np.arccos(np.clip(res[t][cat][0],-1,1))):5.1f}"
                            for t in tables) + f"   ({time.time()-t0:.0f}s)", flush=True)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    cats = sorted(set.intersection(*[set(res[t]) for t in tables])) if tables else []
    payload = {"cats": np.asarray(cats), "scenario": np.asarray(args.scenario),
               "run": np.asarray(str(run)), "tables": np.asarray(json.dumps(tables))}
    print(f"\n{'table':22s} {'theta68':>8} {'median':>8} {'frac>30':>8} {'cover':>7} {'n_sel':>7}")
    summary = {}
    for tag in tables:
        cos = np.array([res[tag][c][0] for c in cats])
        q68 = np.array([res[tag][c][1] for c in cats])
        ns = np.array([res[tag][c][2] for c in cats])
        payload[f"cos_{tag}"] = cos
        payload[f"q68_{tag}"] = q68
        payload[f"nsel_{tag}"] = ns
        th = np.degrees(np.arccos(np.clip(cos, -1, 1)))
        summary[tag] = {"theta68": theta68(cos), "median_theta": float(np.median(th)),
                        "frac_gt_30": float(np.mean(th > 30)),
                        "coverage": float(theta68(cos) / np.median(q68)),
                        "mean_n_sel": float(np.mean(ns)), "n_cats": len(cats)}
        s = summary[tag]
        print(f"{tag:22s} {s['theta68']:8.2f} {s['median_theta']:8.2f} {s['frac_gt_30']:8.2f} "
              f"{s['coverage']:7.2f} {s['mean_n_sel']:7.0f}")
    np.savez(args.out, **payload)
    Path(str(args.out).replace(".npz", "_summary.json")).write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {args.out}  ({time.time()-t0:.0f}s, {len(cats)} cats)")


if __name__ == "__main__":
    main()
