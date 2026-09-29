#!/usr/bin/env python3
"""Offline re-fit of r3 scenario-3 bursts with the brems-study table variants.

Same contract as `ed_r3_eval.py`: the per-event rows come out of the campaign's slim tars,
the SELECTION and the FIT are the pipeline's own
(`select_electrons_from_run` / `reconstruct_burst_direction`).  The only things that change
per variant are (i) the table and (ii) the per-event value handed to the lookup as
`selected_energies`, which is what makes a different conditioning variable testable without
touching pipeline code.

A table tag is given as TAG=PATH[:VAR] with VAR in
  ereco   (default) reco main-cluster energy, exactly what the pipeline passes
  eprime  reco main-cluster energy + reco energy of the event's secondary MARLEY clusters
          (true-ES events only, from the regenerated per-cluster ES images; CC keeps ereco)
  etrue   TRUE electron energy |p_e| from the volume metadata
  pseudo  synthetic row axis (fine energy node x CT-score node) read from the table itself

Every cat is gated: the selection is recomputed independently and must reproduce
`selected_energy` element by element, and the r3 report's own cos_to_truth is recorded.

Usage:
  python3 python/ana/brems_eval.py --cats 901-1224 --tables TSg=<p> TSfE=<p> \
      TEp=<p>:eprime TPs=<p>:pseudo --out <dir>/s3_901_1224.npz
"""
import argparse
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

from ana.burst_direction import (normalize_rows, reconstruct_burst_direction,
                                 select_electrons_from_run)
from ana.brems_collect import CAMPAIGN, mkey, read_es_clusters

EMCEE_CFG = {"enabled": True, "nwalkers": 128, "nsteps": 500, "discard": 100,
             "prior_type": "uniform", "prior_sigma_deg": 10.0,
             "likelihood_kappa": 25.0, "random_seed": 42}
SCENARIO = "scenario_3_full_pipeline"
CT_MIN, E_MIN = 0.80, 5.0


def extract(tar_path, scenario, dest):
    with tarfile.open(tar_path) as tf:
        names = tf.getnames()
        vol = [n for n in names if n.startswith(scenario + "/")
               and n.endswith("volume_images/volumes.npz")]
        if not vol:
            return None
        pre = vol[0].rsplit("/volume_images/", 1)[0]
        dest = Path(dest)
        (dest / "volume_images").mkdir(parents=True, exist_ok=True)
        (dest / "predictions").mkdir(parents=True, exist_ok=True)
        with open(dest / "volume_images" / "volumes.npz", "wb") as fh:
            fh.write(tf.extractfile(vol[0]).read())
        for sub in ("reco_directions.npz", "channel_predictions.npz"):
            n = f"{pre}/predictions/{sub}"
            if n in names:
                with open(dest / "predictions" / sub, "wb") as fh:
                    fh.write(tf.extractfile(n).read())
    return dest


def pseudo_meta(path):
    z = np.load(path, allow_pickle=True)
    return (np.asarray(z["e_nodes"], dtype=np.float64),
            np.asarray(z["score_edges"], dtype=np.float64),
            int(z["n_score"]), np.asarray(z["row_centers"], dtype=np.float64))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cats", required=True)
    ap.add_argument("--tables", nargs="+", required=True, metavar="TAG=PATH[:VAR]")
    ap.add_argument("--out", required=True)
    ap.add_argument("--campaign", default=str(CAMPAIGN))
    ap.add_argument("--dump-events", action="store_true",
                    help="also store the per-event selected rows (energies, cos, truth, score)")
    args = ap.parse_args()

    ranges = [tuple(int(x) for x in r.split("-")) for r in args.cats.split(",")]
    for lo, hi in ranges:
        assert not (hi >= 400 and lo <= 621), f"{lo}-{hi} touches the off-limits cats 400-621"
    spec = {}
    for t in args.tables:
        tag, rest = t.split("=", 1)
        path, var = (rest.rsplit(":", 1) + ["ereco"])[:2] if ":" in rest else (rest, "ereco")
        spec[tag] = (path, var)
    need_eprime = any(v == "eprime" for _, v in spec.values())
    ps = {tag: pseudo_meta(p) for tag, (p, v) in spec.items() if v == "pseudo"}

    camp = Path(args.campaign)
    scratch = Path(tempfile.mkdtemp(prefix="brems_"))
    res = {tag: {} for tag in spec}
    ref, nsel, gate_ok, ev, bdir = {}, {}, {}, [], {}
    t0 = time.time()
    try:
        for lo, hi in ranges:
            for n in range(lo, hi + 1):
                cat = f"cat{n:06d}"
                tar = camp / cat / f"{cat}_scenarios_slim.tar"
                if not tar.exists():
                    continue
                work = scratch / cat
                if extract(tar, SCENARIO, work) is None:
                    continue
                try:
                    sel = select_electrons_from_run(
                        work, selection_mode="predicted-es", direction_mode="reco",
                        min_energy_mev=E_MIN, ct_threshold=CT_MIN)
                except Exception as e:                                       # noqa: BLE001
                    print(f"  {cat}: selection failed {e!r}", flush=True)
                    shutil.rmtree(work, ignore_errors=True)
                    continue

                # ---- independent reconstruction of the same mask, for the per-event aux
                m = np.asarray(np.load(work / "volume_images" / "volumes.npz",
                                       allow_pickle=True)["metadata"], dtype=np.float64)
                rz = np.load(work / "predictions" / "reco_directions.npz", allow_pickle=True)
                pz = np.load(work / "predictions" / "channel_predictions.npz", allow_pickle=True)
                d = normalize_rows(np.asarray(rz["reco_dirs"], dtype=np.float64))
                valid = np.isfinite(d).all(axis=1) & (np.linalg.norm(d, axis=1) > 0)
                valid &= np.asarray(rz["has_reco"]).astype(bool)
                proba = np.asarray(pz["y_pred_proba"], dtype=np.float64)
                mask = valid & (proba >= CT_MIN) & (m[:, 10] >= E_MIN)
                e_reco = m[mask, 10]
                gate_ok[cat] = bool(e_reco.shape == sel["selected_energy"].shape
                                    and np.array_equal(e_reco, sel["selected_energy"]))
                if not gate_ok[cat]:
                    print(f"  {cat}: SELECTION GATE FAILED", flush=True)

                e_true = np.linalg.norm(m[mask, 7:10], axis=1) * 1000.0
                ct = proba[mask]
                is_es = m[mask, 3].astype(int) == 1
                e_prime = e_reco.copy()
                if need_eprime:
                    esc = read_es_clusters(cat)
                    keys = mkey(m[mask, 7:10])
                    for i, k in enumerate(keys):
                        if is_es[i] and k in esc:
                            e_prime[i] = e_reco[i] + esc[k][1]
                nsel[cat] = sel["n_selected"]
                bdir[cat] = np.asarray(sel["true_burst_dir"], dtype=np.float64)
                cosb = np.clip(sel["selected_dirs"] @ sel["true_burst_dir"], -1, 1)
                if args.dump_events:
                    ev.append(np.column_stack([np.full(len(e_reco), n), e_reco, e_true, e_prime,
                                               ct, is_es.astype(float), cosb]).astype(np.float32))

                rp = camp / cat / "scenario_cos_theta_report.json"
                if rp.exists():
                    for s in json.load(open(rp))["scenarios"]:
                        if s["scenario"] == SCENARIO:
                            ref[cat] = (s["cos_to_truth"], s["n_selected"], s["q68_theta_deg"])

                for tag, (path, var) in spec.items():
                    if var == "ereco":
                        x = e_reco
                    elif var == "etrue":
                        x = e_true
                    elif var == "eprime":
                        x = e_prime
                    elif var == "pseudo":
                        e_nodes, s_edges, n_s, centers = ps[tag]
                        i_e = np.abs(e_reco[:, None] - e_nodes[None, :]).argmin(axis=1)
                        i_s = np.clip(np.digitize(ct, s_edges) - 1, 0, n_s - 1)
                        x = centers[i_e * n_s + i_s]
                    else:
                        raise ValueError(var)
                    r = reconstruct_burst_direction(
                        selected_dirs=sel["selected_dirs"], selected_weights=sel["selected_weights"],
                        selected_energies=x, true_burst_dir=sel["true_burst_dir"],
                        use_emcee=True, emcee_cfg=EMCEE_CFG, pdf_path=path)
                    if "unavailable" in str(r.get("method", "")):
                        raise SystemExit("emcee is not available in this environment: the fit "
                                         "silently fell back to weighted-mean+bootstrap, which "
                                         "ignores the table. source scripts/init.sh first.")
                    cos = float(np.clip(np.dot(r["reco_dir"], sel["true_burst_dir"]), -1, 1)) \
                        if r["reco_dir"] is not None else float("nan")
                    th = r["theta_samples_deg"]
                    rd = np.asarray(r["reco_dir"], dtype=np.float64) if r["reco_dir"] is not None \
                        else np.full(3, np.nan)
                    res[tag][cat] = (cos, float(np.quantile(th, 0.68)) if th.size else float("nan"), rd)
                shutil.rmtree(work, ignore_errors=True)
                if len(nsel) % 10 == 0:
                    print(f"  {len(nsel)} cats, {time.time()-t0:.0f}s", flush=True)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    cats = sorted(set.intersection(*[set(res[t]) for t in spec]))
    payload = {"cats": np.asarray([int(c[3:]) for c in cats]),
               "tables": np.asarray(json.dumps({k: list(v) for k, v in spec.items()})),
               "nsel": np.asarray([nsel[c] for c in cats]),
               "gate_ok": np.asarray([gate_ok[c] for c in cats]),
               "ref_cos": np.asarray([ref.get(c, (np.nan,))[0] for c in cats]),
               "ref_nsel": np.asarray([ref[c][1] if c in ref else -1 for c in cats]),
               "burst_dir": np.asarray([bdir[c] for c in cats])}
    for tag in spec:
        payload[f"cos_{tag}"] = np.asarray([res[tag][c][0] for c in cats])
        payload[f"q68_{tag}"] = np.asarray([res[tag][c][1] for c in cats])
        payload[f"dir_{tag}"] = np.asarray([res[tag][c][2] for c in cats])
    if ev:
        payload["events"] = np.vstack(ev)
        payload["event_cols"] = np.asarray(["cat", "e_reco", "e_true", "e_prime", "ct",
                                            "is_es", "cos_burst"])
    np.savez_compressed(args.out, **payload)

    th68 = lambda c: float(np.degrees(np.arccos(np.clip(np.quantile(c, 0.32), -1, 1))))
    print(f"\n{'table':14s} {'theta68':>8} {'median':>8}   gate")
    for tag in spec:
        c = payload[f"cos_{tag}"]
        t = np.degrees(np.arccos(np.clip(c, -1, 1)))
        print(f"{tag:14s} {th68(c):8.2f} {np.median(t):8.2f}")
    print(f"selection gate: {int(payload['gate_ok'].sum())}/{len(cats)} cats OK")
    print(f"wrote {args.out} ({time.time()-t0:.0f}s, {len(cats)} cats)")


if __name__ == "__main__":
    main()
