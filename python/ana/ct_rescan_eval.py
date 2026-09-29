#!/usr/bin/env python3
"""Re-fit r3 bursts under alternative CT selection rules and their matching mixture tables.

Reads the per-event rows of `<cat>/<cat>_scenarios_slim.tar` (scenario_3_full_pipeline holds
ALL loaded clusters with CT v80 score and v63 reco direction) and, per variant, applies the
variant's selection and calls the pipeline's own fit:

  kind "emcee" : ana.burst_direction.reconstruct_burst_direction with the deployed emcee
                 config (clipped lookup, seeded, grid-seeded adaptive init, uniform prior).
                 `weights` chooses the per-event likelihood weight: ones (hard selection),
                 calib (w = P(ES|score) from the slice calibration) or score (w = raw CT score).
  kind "grid"  : ana.burst_direction.reconstruct_burst_direction_grid_mixture -- all events
                 above the energy cut (or, with an optional "rule", the events that pass it),
                 per-event p_i = P(ES|score), likelihood
                 prod_i [p_i pdf_ES(cos|E) + (1-p_i) pdf_CC], pdf_CC flat or the
                 detector-frame CC direction map.

The selection is reproduced in memory rather than through `select_electrons_from_run`
because the rules are energy dependent; `--verify-selection` checks the in-memory path
against the production function on the first N cats (must be exactly equal).

Nothing is written outside --out.  Cats 400-621 are refused.

Usage:
  python3 python/ana/ct_rescan_eval.py --variants variants.json --tags S0,S1_t070 \
      --cats 2-399,901-1224 --out <chunk.npz>
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

from ana.burst_direction import (normalize_rows, normalize_vector,
                                 reconstruct_burst_direction,
                                 reconstruct_burst_direction_grid_mixture,
                                 select_electrons_from_run)
from ana.ct_rescan_tables import rule_threshold

CAMPAIGN = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-campaign/v63_matchfix_1000")
SCENARIO = "scenario_3_full_pipeline"
EMCEE_CFG = {"enabled": True, "nwalkers": 128, "nsteps": 500, "discard": 100,
             "prior_type": "uniform", "prior_sigma_deg": 10.0,
             "likelihood_kappa": 25.0, "random_seed": 42}
GRID_N = 41253


def read_cat(tar_path):
    with tarfile.open(tar_path) as tf:
        names = tf.getnames()
        vol = [n for n in names if n.startswith(SCENARIO + "/")
               and n.endswith("volume_images/volumes.npz")]
        if not vol:
            return None
        pre = vol[0].rsplit("/volume_images/", 1)[0]
        rn, pn = f"{pre}/predictions/reco_directions.npz", f"{pre}/predictions/channel_predictions.npz"
        if rn not in names or pn not in names:
            return None
        meta = np.asarray(np.load(io.BytesIO(tf.extractfile(vol[0]).read()),
                                  allow_pickle=True)["metadata"], dtype=np.float64)
        rec = np.load(io.BytesIO(tf.extractfile(rn).read()), allow_pickle=True)
        prd = np.load(io.BytesIO(tf.extractfile(pn).read()), allow_pickle=True)
        return dict(meta=meta, dirs=normalize_rows(np.asarray(rec["reco_dirs"], dtype=np.float64)),
                    has=np.asarray(rec["has_reco"]).astype(bool),
                    proba=np.asarray(prd["y_pred_proba"], dtype=np.float64))


def extract_for_production(tar_path, dest):
    """Same extraction as ed_r3_eval.extract (for --verify-selection only)."""
    with tarfile.open(tar_path) as tf:
        names = tf.getnames()
        vol = [n for n in names if n.startswith(SCENARIO + "/")
               and n.endswith("volume_images/volumes.npz")]
        if not vol:
            return None
        pre = vol[0].rsplit("/volume_images/", 1)[0]
        dest = Path(dest)
        (dest / "volume_images").mkdir(parents=True, exist_ok=True)
        (dest / "predictions").mkdir(parents=True, exist_ok=True)
        (dest / "volume_images" / "volumes.npz").write_bytes(tf.extractfile(vol[0]).read())
        for sub in ("reco_directions.npz", "channel_predictions.npz"):
            n = f"{pre}/predictions/{sub}"
            if n in names:
                (dest / "predictions" / sub).write_bytes(tf.extractfile(n).read())
    return dest


def burst_dir(meta):
    v = meta[:, 15:18]
    ok = np.linalg.norm(v, axis=1) > 0
    if not ok.any():
        return None
    return normalize_vector(np.mean(normalize_rows(v[ok]), axis=0))


def load_calibration(path, monotone=True):
    z = np.load(path, allow_pickle=True)
    return (np.asarray(z["score_center"], dtype=np.float64),
            np.asarray(z["p_es_mono" if monotone else "p_es_raw"], dtype=np.float64))


def p_from_calibration(scores, calib):
    s, p = calib
    return np.clip(np.interp(np.clip(scores, 0.0, 1.0), s, p, left=p[0], right=p[-1]), 0.0, 1.0)


def theta68(cos):
    return float(np.degrees(np.arccos(np.clip(np.quantile(np.asarray(cos), 0.32), -1.0, 1.0))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", required=True, help="variants json (list of dicts)")
    ap.add_argument("--tags", required=True, help="comma list of variant tags to run, or ALL")
    ap.add_argument("--cats", required=True, help="ranges, e.g. 2-399,901-1224")
    ap.add_argument("--out", required=True)
    ap.add_argument("--campaign", default=str(CAMPAIGN))
    ap.add_argument("--verify-selection", type=int, default=0,
                    help="check the in-memory selection against select_electrons_from_run "
                         "on the first N cats (constant-threshold variants only)")
    args = ap.parse_args()

    ranges = [tuple(int(x) for x in r.split("-")) for r in args.cats.split(",")]
    for lo, hi in ranges:
        assert not (hi >= 400 and lo <= 621), f"range {lo}-{hi} touches the off-limits cats 400-621"
    spec = {v["tag"]: v for v in json.loads(Path(args.variants).read_text())}
    tags = sorted(spec) if args.tags == "ALL" else args.tags.split(",")
    for t in tags:
        assert t in spec, f"unknown variant {t!r}"
    calibs = {}
    for t in tags:
        c = spec[t].get("calib")
        if c and c not in calibs:
            calibs[c] = load_calibration(c)

    camp = Path(args.campaign)
    res = {t: {} for t in tags}
    ref, t0, n_done = {}, time.time(), 0
    verify_left = int(args.verify_selection)
    scratch = Path(tempfile.mkdtemp(prefix="ctrescan_")) if verify_left else None
    try:
        for lo, hi in ranges:
            for n in range(lo, hi + 1):
                cat = f"cat{n:06d}"
                tar = camp / cat / f"{cat}_scenarios_slim.tar"
                if not tar.exists():
                    continue
                try:
                    d = read_cat(tar)
                except Exception as e:  # noqa: BLE001
                    print(f"  {cat}: read failed {e!r}", flush=True)
                    continue
                if d is None:
                    continue
                meta, dirs, has, proba = d["meta"], d["dirs"], d["has"], d["proba"]
                if proba.shape[0] != meta.shape[0] or dirs.shape[0] != meta.shape[0]:
                    print(f"  {cat}: length mismatch, skipped", flush=True)
                    continue
                bd = burst_dir(meta)
                if bd is None:
                    continue
                ok = has & np.isfinite(dirs).all(axis=1) & (np.linalg.norm(dirs, axis=1) > 0)
                energy = meta[:, 10]
                is_es = meta[:, 3].astype(int) == 1

                rp = camp / cat / "scenario_cos_theta_report.json"
                if rp.exists():
                    try:
                        for s in json.load(open(rp))["scenarios"]:
                            if s["scenario"] == SCENARIO:
                                ref[cat] = (s["cos_to_truth"], s["n_selected"], s["q68_theta_deg"])
                    except Exception:  # noqa: BLE001
                        pass

                if verify_left > 0:
                    work = extract_for_production(tar, scratch / cat)
                    p_sel = select_electrons_from_run(work, selection_mode="predicted-es",
                                                      direction_mode="reco", min_energy_mev=5.0,
                                                      ct_threshold=0.80)
                    m = ok & (proba >= 0.80) & (energy >= 5.0)
                    same = (p_sel["n_selected"] == int(m.sum())
                            and np.array_equal(p_sel["selected_dirs"], dirs[m])
                            and np.array_equal(p_sel["selected_energy"], energy[m])
                            and np.allclose(p_sel["true_burst_dir"], bd, atol=0, rtol=0))
                    print(f"  VERIFY {cat}: in-memory == select_electrons_from_run: {same} "
                          f"(n={int(m.sum())})", flush=True)
                    shutil.rmtree(work, ignore_errors=True)
                    verify_left -= 1
                    if not same:
                        raise SystemExit("in-memory selection differs from the production function")

                for t in tags:
                    v = spec[t]
                    min_e = float(v.get("min_energy", 5.0))
                    if v["kind"] == "emcee":
                        m = ok & (proba >= rule_threshold(v["rule"], energy)) & (energy >= min_e)
                        nsel = int(m.sum())
                        if nsel == 0:
                            res[t][cat] = (np.nan, np.nan, 0, 0)
                            continue
                        w = np.ones(nsel)
                        if v.get("weights") == "calib":
                            w = p_from_calibration(proba[m], calibs[v["calib"]])
                        elif v.get("weights") == "score":
                            w = np.clip(proba[m], 0.0, 1.0)
                        r = reconstruct_burst_direction(
                            selected_dirs=dirs[m], selected_weights=w,
                            selected_energies=energy[m], true_burst_dir=bd,
                            use_emcee=True, emcee_cfg=EMCEE_CFG, pdf_path=v["table"])
                    elif v["kind"] == "grid":
                        m = ok & (energy >= min_e)
                        if v.get("rule"):
                            m = m & (proba >= rule_threshold(v["rule"], energy))
                        nsel = int(m.sum())
                        if nsel == 0:
                            res[t][cat] = (np.nan, np.nan, 0, 0)
                            continue
                        p_es = p_from_calibration(proba[m], calibs[v["calib"]])
                        r = reconstruct_burst_direction_grid_mixture(
                            selected_dirs=dirs[m], selected_energies=energy[m], p_es=p_es,
                            true_burst_dir=bd, pdf_es_path=v["pdf_es"],
                            cc_pdf_mode=v.get("cc_mode", "flat"),
                            cc_map_path=v.get("cc_map"), grid_n=GRID_N,
                            random_seed=EMCEE_CFG["random_seed"])
                    else:
                        raise ValueError(f"unknown variant kind {v['kind']!r}")
                    cos = (float(np.clip(np.dot(r["reco_dir"], bd), -1, 1))
                           if r["reco_dir"] is not None else float("nan"))
                    th = np.asarray(r["theta_samples_deg"])
                    res[t][cat] = (cos, float(np.quantile(th, 0.68)) if th.size else float("nan"),
                                   nsel, int((m & is_es).sum()))
                n_done += 1
                if n_done % 5 == 0:
                    print(f"  {n_done} cats, {time.time()-t0:.0f}s", flush=True)
    finally:
        if scratch is not None:
            shutil.rmtree(scratch, ignore_errors=True)

    cats = sorted(set.intersection(*[set(res[t]) for t in tags])) if tags else []
    if not cats:
        raise SystemExit("no cats fitted")
    payload = {"cats": np.asarray([int(c[3:]) for c in cats]),
               "tags": np.asarray(json.dumps(tags)),
               "variants": np.asarray(json.dumps({t: spec[t] for t in tags})),
               "ref_cos": np.asarray([ref.get(c, (np.nan,))[0] for c in cats]),
               "ref_nsel": np.asarray([ref[c][1] if c in ref else -1 for c in cats]),
               "ref_q68": np.asarray([ref[c][2] if c in ref else np.nan for c in cats])}
    for t in tags:
        payload[f"cos_{t}"] = np.asarray([res[t][c][0] for c in cats])
        payload[f"q68_{t}"] = np.asarray([res[t][c][1] for c in cats])
        payload[f"nsel_{t}"] = np.asarray([res[t][c][2] for c in cats])
        payload[f"nes_{t}"] = np.asarray([res[t][c][3] for c in cats])
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    np.savez(args.out, **payload)

    print(f"\n{'variant':14s} {'theta68':>8} {'median':>8} {'frac>30':>8} {'cover':>7} "
          f"{'n_sel':>7} {'purity':>7}")
    for t in tags:
        c = payload[f"cos_{t}"]
        good = np.isfinite(c)
        th = np.degrees(np.arccos(np.clip(c[good], -1, 1)))
        ns, ne = payload[f"nsel_{t}"], payload[f"nes_{t}"]
        print(f"{t:14s} {theta68(c[good]):8.2f} {np.median(th):8.2f} {np.mean(th > 30):8.2f} "
              f"{theta68(c[good])/np.median(payload['q68_'+t][good]):7.2f} "
              f"{ns.mean():7.1f} {ne.sum()/max(ns.sum(),1):7.3f}")
    print(f"\nwrote {args.out}  ({time.time()-t0:.0f}s, {len(cats)} cats)")


if __name__ == "__main__":
    main()
