#!/usr/bin/env python3
"""ES purity f(E) of the CT-selected sample, per reconstructed-energy bin.

The full-pipeline scenario fits a sample that is only ~40% ES, so the per-event density
the burst likelihood should use is a MIXTURE

    p(cos | E) = f(E) * pdf_ES(cos | E) + (1 - f(E)) * pdf_CC(cos | E)

and f(E) is the ES purity of the selection (CT v80 score >= 0.80, E > 5 MeV) at the
deployed 330 ES + 3300 CC generated-event composition.

It is measured here on the v80_fixed_1000 campaign, whose per-event CT scores, truth and
energies survive in the per-cat slim tars, with the generated-event budget replayed
offline by `budget_replay` (the campaign itself was produced by the old all-events
loader).  Only cats 673-1224 are used: cats 623-672 are the dev bursts the mixture table
is evaluated on, and cats 1-621 are training/era cats.

Output: an npz with, per energy bin of the deployed table layout, n_es, n_tot, f, and the
binomial error on f, plus the overall purity.

Usage:
  python3 python/ana/ed_mixture_purity.py --cat-min 673 --cat-max 1224 --max-cats 250 \
      --out <...>/purity_fE.npz
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from ana.budget_replay import (CAMPAIGN_ROOT, SAMPLES_ROOT, budget_mask, qc_file_counts,
                               read_cat_products, row_file_index)

# energy binning of the deployed table (data/cosine_energy_pdf.npz)
ENERGY_BINS = np.array([(2, 4), (4, 6), (6, 8), (8, 10), (10, 12), (12, 14), (14, 16),
                        (16, 18), (18, 20), (20, 22), (22, 24), (24, 26), (26, 28),
                        (28, 30), (30, 35), (35, 40), (40, 50), (50, 70)], dtype=float)
CT_THRESHOLD = 0.80
MIN_ENERGY = 5.0


def cat_selection(cat, qc, samples_root=SAMPLES_ROOT, campaign_root=CAMPAIGN_ROOT,
                  apply_budget=True):
    """Rows of one cat that scenario 3 would fit: (energy, is_es) after budget + CT + E cut."""
    prod = read_cat_products(cat, campaign_root)
    entry = prod["scenarios"].get("scenario_3_full_pipeline")
    if entry is None or entry.get("pred") is None:
        return None, ["no_scenario_3_predictions"]
    meta = np.asarray(entry["metadata"], dtype=np.float64)
    index = row_file_index(cat, meta, samples_root, qc)
    keep = budget_mask(index)["mask"] if apply_budget else np.ones(len(meta), bool)

    proba = np.asarray(entry["pred"]["y_pred_proba"], dtype=np.float64)
    if proba.shape[0] != meta.shape[0]:
        return None, ["proba_length_mismatch"]
    energy = meta[:, 10]
    sel = keep & (proba >= CT_THRESHOLD) & (energy >= MIN_ENERGY)

    # the pipeline also requires a valid reconstructed direction
    reco = entry.get("reco")
    if reco is not None:
        has = np.asarray(reco["has_reco"]).astype(bool)
        d = np.asarray(reco["reco_dirs"], dtype=np.float64)
        ok = has & np.isfinite(d).all(axis=1) & (np.linalg.norm(d, axis=1) > 0)
        sel = sel & ok
    return (energy[sel], meta[sel, 3].astype(int) == 1), index["flags"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat-min", type=int, default=673)
    ap.add_argument("--cat-max", type=int, default=1224)
    ap.add_argument("--max-cats", type=int, default=250)
    ap.add_argument("--out", required=True)
    ap.add_argument("--campaign-root", default=str(CAMPAIGN_ROOT))
    args = ap.parse_args()
    assert args.cat_min >= 673, "cats 623-672 are the dev bursts: never measure f(E) on them"

    qc = qc_file_counts()
    n_es = np.zeros(len(ENERGY_BINS))
    n_tot = np.zeros(len(ENERGY_BINS))
    cats_used, cats_failed, flagged = [], [], []
    t0 = time.time()
    for n in range(args.cat_min, args.cat_max + 1):
        if len(cats_used) >= args.max_cats:
            break
        cat = f"cat{n:06d}"
        if not (Path(args.campaign_root) / cat / f"{cat}_scenarios_slim.tar").exists():
            continue
        try:
            res, flags = cat_selection(cat, qc, campaign_root=Path(args.campaign_root))
        except Exception as e:  # noqa: BLE001
            cats_failed.append((cat, repr(e)))
            continue
        if res is None:
            cats_failed.append((cat, flags))
            continue
        energy, is_es = res
        bad = [f for f in flags if f != "es_file_index_taken_from_tar_replay"]
        if bad:
            flagged.append((cat, bad))
        for i, (lo, hi) in enumerate(ENERGY_BINS):
            m = (energy >= lo) & (energy < hi)
            n_tot[i] += int(m.sum())
            n_es[i] += int((m & is_es).sum())
        cats_used.append(cat)
        if len(cats_used) % 25 == 0:
            print(f"  {len(cats_used)} cats, {n_tot.sum():.0f} selected events, "
                  f"{time.time() - t0:.0f}s", flush=True)

    f = np.divide(n_es, n_tot, out=np.full(len(n_tot), np.nan), where=n_tot > 0)
    err = np.sqrt(np.clip(f * (1 - f), 0, None) / np.where(n_tot > 0, n_tot, 1))
    overall = float(n_es.sum() / n_tot.sum()) if n_tot.sum() else float("nan")

    np.savez(args.out, energy_bins=ENERGY_BINS, n_es=n_es, n_tot=n_tot, f=f, f_err=err,
             overall_purity=np.float64(overall), n_cats=np.int64(len(cats_used)),
             ct_threshold=np.float64(CT_THRESHOLD), min_energy=np.float64(MIN_ENERGY),
             cats=np.asarray(cats_used))
    meta = {"cats_used": len(cats_used), "cat_range": [args.cat_min, args.cat_max],
            "n_selected_events": int(n_tot.sum()), "overall_purity": overall,
            "events_per_burst": float(n_tot.sum() / max(len(cats_used), 1)),
            "failed": cats_failed[:10], "n_failed": len(cats_failed),
            "flagged": flagged[:10], "n_flagged": len(flagged)}
    Path(str(args.out).replace(".npz", "_provenance.json")).write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))
    print(f"\n{'E bin':>10} {'n_tot':>9} {'n_es':>9} {'f(E)':>8} {'+-':>7}")
    for i, (lo, hi) in enumerate(ENERGY_BINS):
        print(f"{int(lo):4d}-{int(hi):<5d} {n_tot[i]:9.0f} {n_es[i]:9.0f} "
              f"{f[i]:8.3f} {err[i]:7.3f}")
    print(f"\noverall ES purity: {overall:.4f}  ({n_tot.sum():.0f} events, "
          f"{len(cats_used)} cats, {time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
