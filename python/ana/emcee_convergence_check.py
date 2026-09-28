#!/usr/bin/env python3
"""Does the emcee fit converge for a very peaked posterior (best case, true directions)?

Uses the kept per-event outputs (scenario_7 mixture_events.npz: true_electron_dirs,
is_es_true, energy, true_burst_dir) to rebuild the scenario-1 selection (true ES,
E > 3 MeV, TRUE directions) and runs the pipeline's own _run_emcee under several
sampler settings. Reports theta68 across cats per setting.

Usage: python3 python/ana/emcee_convergence_check.py --input-root <root> [--n-cats 20] --out-md <md>
"""
import argparse
import glob
import json
from pathlib import Path

import numpy as np
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import burst_direction as bd  # noqa: E402

SETTINGS_CHAIN = {
    "uniform, 500 steps, discard 100 (pipeline)": dict(prior_type="uniform", nsteps=500, discard=100),
    "uniform, 1500 steps, discard 500": dict(prior_type="uniform", nsteps=1500, discard=500),
    "uniform, 3000 steps, discard 1000": dict(prior_type="uniform", nsteps=3000, discard=1000),
    "gaussian 10 deg around weighted mean, 500 steps": dict(prior_type="gaussian_around_mean", prior_sigma_deg=10.0, nsteps=500, discard=100),
}
# In _run_emcee the walker init width equals prior_sigma for the gaussian prior and is
# fixed at 45 deg for the uniform prior, so scanning prior_sigma separates "init width"
# from "prior pull": at 45 deg the gaussian prior is flat over any posterior we see.
SETTINGS_INIT = {
    "uniform prior, init 45 deg (pipeline)": dict(prior_type="uniform", nsteps=500, discard=100),
    "gaussian sigma 45 deg (= init 45, prior ~flat)": dict(prior_type="gaussian_around_mean", prior_sigma_deg=45.0, nsteps=500, discard=100),
    "gaussian sigma 20 deg (init 20)": dict(prior_type="gaussian_around_mean", prior_sigma_deg=20.0, nsteps=500, discard=100),
    "gaussian sigma 10 deg (init 10)": dict(prior_type="gaussian_around_mean", prior_sigma_deg=10.0, nsteps=500, discard=100),
    "gaussian sigma 5 deg (init 5)": dict(prior_type="gaussian_around_mean", prior_sigma_deg=5.0, nsteps=500, discard=100),
    "uniform prior, grid-seeded init 5 deg": dict(prior_type="uniform", init_mode="grid", init_sigma_deg=5.0, nsteps=500, discard=100),
    "uniform prior, grid-seeded init 10 deg": dict(prior_type="uniform", init_mode="grid", init_sigma_deg=10.0, nsteps=500, discard=100),
    "uniform prior, legacy init 45 deg (explicit)": dict(prior_type="uniform", init_mode="mean", nsteps=500, discard=100),
}
SETTINGS_FINAL = {
    "legacy: uniform prior, init 45 deg around weighted mean": dict(prior_type="uniform", init_mode="mean", nsteps=500, discard=100),
    "grid seed, fixed init 5 deg": dict(prior_type="uniform", init_mode="grid", init_sigma_deg=5.0, nsteps=500, discard=100),
    "grid seed, fixed init 10 deg": dict(prior_type="uniform", init_mode="grid", init_sigma_deg=10.0, nsteps=500, discard=100),
    "grid seed, auto init (68% grid-posterior radius, 5-45 deg)": dict(prior_type="uniform", init_mode="grid", init_sigma_deg="auto", nsteps=500, discard=100),
}
SETTINGS = SETTINGS_CHAIN


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", required=True)
    ap.add_argument("--n-cats", type=int, default=20)
    ap.add_argument("--pdf", default=str(Path(__file__).resolve().parents[2] / "data" / "cosine_energy_pdf.npz"))
    ap.add_argument("--selection", default="sc1", choices=["sc1", "sc2", "sc3", "sc5", "sc6"],
                    help="sc1 = true ES, true dirs, E>3; sc2 = true ES, reco dirs, E>3; "
                         "sc3 = CT score >= 0.8, reco dirs, E>5 (the deployed selection); "
                         "sc5 = true ES, reco dirs, E>10; sc6 = true ES, reco dirs, E>5")
    ap.add_argument("--settings", default="chain", choices=["chain", "init", "final"])
    ap.add_argument("--lookup", default="clipped", choices=["clipped", "hole"],
                    help="pdf lookup convention (hole = pre-fix behaviour)")
    ap.add_argument("--out-md", required=True)
    args = ap.parse_args()
    settings = {"chain": SETTINGS_CHAIN, "init": SETTINGS_INIT, "final": SETTINGS_FINAL}[args.settings]

    interp = bd.load_pdf_interpolator(args.pdf, mode=args.lookup)
    files = sorted(glob.glob(f"{args.input_root}/cat*/scenario_7_mixture_ct/pipeline_run_*/predictions/mixture_events.npz"))[: args.n_cats]
    res = {k: [] for k in settings}
    for f in files:
        d = np.load(f, allow_pickle=True)
        if args.selection == "sc3":
            sel = (d["ct_score"] >= 0.8) & (d["energy"] > 5.0)
        elif args.selection == "sc5":
            sel = d["is_es_true"] & (d["energy"] > 10.0)
        elif args.selection == "sc6":
            sel = d["is_es_true"] & (d["energy"] > 5.0)
        else:
            sel = d["is_es_true"] & (d["energy"] > 3.0)
        dirs = (d["true_electron_dirs"] if args.selection == "sc1" else d["reco_dirs"])[sel].astype(np.float64)
        dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
        en = d["energy"][sel].astype(np.float64)
        truth = np.asarray(d["true_burst_dir"], dtype=np.float64)
        for name, cfg in settings.items():
            c = {"nwalkers": 128, "random_seed": 42, **cfg}
            r = bd._run_emcee(dirs, np.ones(len(dirs)), en, truth, c, interp)
            res[name].append(float(np.clip(r["reco_dir"] @ truth, -1, 1)))
    lines = [f"selection {args.selection}, lookup {args.lookup}, {len(files)} cats from `{args.input_root}`", "",
             "| sampler setting | theta68 [deg] | median theta | max theta |", "|---|---|---|---|"]
    for name, cos in res.items():
        cos = np.array(cos); th = np.degrees(np.arccos(cos))
        lines.append(f"| {name} | {np.degrees(np.arccos(np.quantile(cos, 0.32))):.2f} | {np.median(th):.2f} | {th.max():.2f} |")
    Path(args.out_md).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
