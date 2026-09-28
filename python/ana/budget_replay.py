#!/usr/bin/env python3
"""Offline re-evaluation of the v80_fixed_1000 campaign under the GENERATED-event budget.

The campaign bursts were built by a loader that counted events as a set of bare event
numbers (metadata column 0).  Event numbers restart at 1..40 in every input file, so the
set saturated at 40, the 330 ES / 3300 CC targets were never reached and every file was
loaded: each burst really holds 400 ES + up to 4000 CC GENERATED events.

The campaign kept every per-event input, so the correct bursts can be rebuilt offline
without regenerating anything:

  * the loader concatenates the CC rows (files in sorted order, rows inside a file in
    increasing match_id) then the ES rows, and shuffles with np.random.seed(42);
    np.random.permutation(N).  The permutation is invertible, so every row can be put
    back into its (class, file index, event number) slot;
  * inside a class block match_id (column 13) is strictly increasing within a file and
    restarts at a small value in the next file, so a non-increase marks a file boundary;
  * the ES file indices are checked against an EXACT replay of the regenerated ES cluster
    images (<cat>_..._r2_es.tar), the CC ones against the campaign's own product QC.

The budget then keeps the first 330 generated ES events (8 complete files + events 1..10
of the 9th) and the first 3300 generated CC events (82 complete files + events 1..20 of
the 83rd).  Events that left no matched cluster still consume the budget.

The six scenarios are recomputed with the pipeline's own code: the surviving rows are
written back into a scratch copy of the run directory and read by
ana.burst_direction.select_electrons_from_run / reconstruct_burst_direction, so the
selection and the fit are byte-for-byte the production ones.

Usage
    source scripts/init.sh
    python3 python/ana/budget_replay.py gate  --cats cat000623,... --out DIR
    python3 python/ana/budget_replay.py budget --cats cat000623,... --out-root ROOT
    python3 python/ana/budget_replay.py index  --cats ...            # file-index QC only
"""
import argparse
import io
import json
import os
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

CAMPAIGN_ROOT = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-campaign/v80_fixed_1000")
SAMPLES_ROOT = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples")
CLUSTER_SUFFIX = "_cluster_images_tick3_ch2_min2_tot3_e3p0"
QC_DIR = Path("/afs/cern.ch/work/e/evilla/private/dune/refactor-online-utils/condor/evilla/campaign_r2/qc")
QC_STATE = Path("/afs/cern.ch/work/e/evilla/private/dune/refactor-online-utils/condor/evilla/campaign_r2/state/campaign.json")
PDF_PATH = str(_HERE.parents[1] / "data" / "cosine_energy_pdf.npz")

EVENTS_PER_FILE = 40
N_ES_BUDGET = 330
N_CC_BUDGET = 3300
SHUFFLE_SEED = 42

# campaign emcee configuration (scenario_analysis_config.json of every cat)
EMCEE_CFG = {
    "enabled": True, "nwalkers": 128, "nsteps": 500, "discard": 100,
    "prior_type": "uniform", "prior_sigma_deg": 10.0, "likelihood_kappa": 25.0,
    "random_seed": 42,
}


# ---------------------------------------------------------------------------
# campaign QC: per-cat (n_es_files, n_cc_files) actually produced
# ---------------------------------------------------------------------------
_QC = {}


def qc_file_counts():
    if _QC:
        return _QC
    for f in sorted(QC_DIR.glob("batch*_products.json")):
        try:
            for r in json.loads(f.read_text()):
                _QC[r["cat"]] = {"n_es_files": int(r["ci_X"][0]), "n_cc_files": int(r["ci_X"][1]),
                                 "n_tps": int(r.get("n_tps", -1))}
        except Exception as e:  # pragma: no cover - QC is advisory
            print(f"  warning: unreadable QC file {f}: {e}")
    # The per-batch qc/batchNNN_products.json files do not cover the pilot cats, but
    # state/campaign.json carries the same prod_qc block for every cat the campaign
    # finished; fall back to it so all 1000 cats have a file-count reference.
    try:
        st = json.loads(QC_STATE.read_text()).get("cats", {})
        for cat, rec in st.items():
            if cat in _QC:
                continue
            q = rec.get("prod_qc") or {}
            if "ci_X" in q:
                _QC[cat] = {"n_es_files": int(q["ci_X"][0]), "n_cc_files": int(q["ci_X"][1]),
                            "n_tps": int(q.get("n_tps", -1))}
    except Exception as e:  # pragma: no cover - QC is advisory
        print(f"  warning: unreadable campaign state {QC_STATE}: {e}")
    return _QC


# ---------------------------------------------------------------------------
# tar access (in place, never extracted to EOS)
# ---------------------------------------------------------------------------
def _npz_from_tar(tf, name):
    return np.load(io.BytesIO(tf.extractfile(name).read()), allow_pickle=True)


def read_cat_products(cat, campaign_root=CAMPAIGN_ROOT):
    """Everything the six scenarios need, read straight out of the slim tar."""
    tar_path = Path(campaign_root) / cat / f"{cat}_scenarios_slim.tar"
    if not tar_path.exists():
        raise FileNotFoundError(f"missing slim tar: {tar_path}")
    out = {"metadata": None, "scenarios": {}}
    with tarfile.open(tar_path) as tf:
        names = tf.getnames()
        scens = sorted({n.split("/")[0] for n in names if n.startswith("scenario_")})
        for s in scens:
            pref = s + "/"
            vol = [n for n in names if n.startswith(pref) and n.endswith("volume_images/volumes.npz")]
            if not vol:
                continue
            run_prefix = vol[0].rsplit("/volume_images/", 1)[0]
            meta = np.asarray(_npz_from_tar(tf, vol[0])["metadata"])
            entry = {"run_prefix": run_prefix, "metadata": meta, "reco": None, "pred": None,
                     "reporting": None}
            cfg_name = pref + "config.json"
            if cfg_name in names:
                entry["reporting"] = json.loads(tf.extractfile(cfg_name).read()).get("reporting")
            rn = run_prefix + "/predictions/reco_directions.npz"
            if rn in names:
                d = _npz_from_tar(tf, rn)
                entry["reco"] = {"reco_dirs": np.asarray(d["reco_dirs"]),
                                 "has_reco": np.asarray(d["has_reco"])}
            pn = run_prefix + "/predictions/channel_predictions.npz"
            if pn in names:
                d = _npz_from_tar(tf, pn)
                entry["pred"] = {k: np.asarray(d[k]) for k in ("y_true", "y_pred", "y_pred_proba")
                                 if k in d}
            out["scenarios"][s] = entry
            if out["metadata"] is None:
                out["metadata"] = meta
    if not out["scenarios"]:
        raise RuntimeError(f"no scenarios in {tar_path}")
    return out


def es_replay_from_tar(cat, samples_root=SAMPLES_ROOT):
    """Exact replay of the loader on the regenerated ES cluster images.

    Returns (file_index_per_row, event_per_row, metadata_rows, n_files) in loader order,
    or None when the tar is absent.
    """
    tar = Path(samples_root) / cat / f"{cat}{CLUSTER_SUFFIX}_r2_es.tar"
    if not tar.exists():
        return None
    fidx, evs, metas = [], [], []
    with tarfile.open(tar) as tf:
        names = tf.getnames()
        xs = sorted(n for n in names if n.startswith("X/") and n.endswith("_planeX.npz"))
        for fi, n in enumerate(xs):
            mx = _npz_from_tar(tf, n)["metadata"]
            un = n.replace("X/", "U/").replace("planeX", "planeU")
            vn = n.replace("X/", "V/").replace("planeX", "planeV")
            if un not in names or vn not in names:
                continue
            mu = _npz_from_tar(tf, un)["metadata"]
            mv = _npz_from_tar(tf, vn)["metadata"]

            def idx(m):
                return {int(v): i for i, v in enumerate(m[:, 13]) if m[i, 2] == 1 and v != -1}

            ix, iu, iv = idx(mx), idx(mu), idx(mv)
            for mid in sorted(set(ix) & set(iu) & set(iv)):
                fidx.append(fi)
                evs.append(int(mx[ix[mid], 0]))
                metas.append(mx[ix[mid]])
        n_files = len(xs)
    if not metas:
        return None
    return (np.array(fidx, dtype=int), np.array(evs, dtype=int),
            np.array(metas, dtype=np.float32), n_files)


# ---------------------------------------------------------------------------
# row -> (class, file index, event number)
# ---------------------------------------------------------------------------
def _file_index_from_match_id(match_id):
    """File index of every row of one class block: match_id is strictly increasing
    inside a file and restarts at a small value in the next one."""
    fidx = np.zeros(len(match_id), dtype=int)
    cur = 0
    for i in range(1, len(match_id)):
        if match_id[i] <= match_id[i - 1]:
            cur += 1
        fidx[i] = cur
    return fidx


def row_file_index(cat, metadata, samples_root=SAMPLES_ROOT, qc=None):
    """Assign (is_es, file index, event number) to every row of volumes.npz.

    Returns a dict with per-row arrays in the SHUFFLED row order of volumes.npz plus
    validation flags.
    """
    meta = np.asarray(metadata)
    n_total = meta.shape[0]
    np.random.seed(SHUFFLE_SEED)
    perm = np.random.permutation(n_total)
    order = np.argsort(perm)           # original (pre-shuffle) index -> row in volumes.npz
    orig = meta[order]

    is_es_orig = orig[:, 3].astype(int) == 1
    n_es = int(is_es_orig.sum())
    n_cc = n_total - n_es
    flags = []
    if not (np.all(~is_es_orig[:n_cc]) and np.all(is_es_orig[n_cc:])):
        flags.append("block_split_failed")

    cc_mid = orig[:n_cc, 13].astype(int)
    es_mid = orig[n_cc:, 13].astype(int)
    cc_fidx = _file_index_from_match_id(cc_mid)
    es_fidx = _file_index_from_match_id(es_mid)
    n_cc_files = int(cc_fidx.max()) + 1 if n_cc else 0
    n_es_files = int(es_fidx.max()) + 1 if n_es else 0

    # --- ES cross-check: exact replay of the regenerated ES cluster images ----------
    es_replay_ok = None
    rep = es_replay_from_tar(cat, samples_root)
    if rep is not None:
        r_fidx, r_ev, r_meta, r_nfiles = rep
        if r_meta.shape == orig[n_cc:].shape and np.array_equal(r_meta, orig[n_cc:].astype(np.float32)):
            es_replay_ok = bool(np.array_equal(r_fidx, es_fidx))
            if not es_replay_ok:
                # the replay is the truth: a file with zero matched rows shifts the
                # match_id-derived indices, so take the replay's indices instead
                es_fidx = r_fidx
                n_es_files = r_nfiles
                flags.append("es_file_index_taken_from_tar_replay")
        else:
            flags.append("es_replay_metadata_mismatch")
    else:
        flags.append("es_tar_missing")

    # --- CC cross-check: campaign product QC ---------------------------------------
    qc = qc if qc is not None else qc_file_counts()
    q = qc.get(cat)
    cc_files_expected = q["n_cc_files"] if q else None
    es_files_expected = q["n_es_files"] if q else None
    if q is None:
        flags.append("no_qc_record")
    else:
        if n_cc_files != cc_files_expected:
            flags.append(f"cc_file_count_mismatch:{n_cc_files}vs{cc_files_expected}")
        if n_es_files != es_files_expected:
            flags.append(f"es_file_count_mismatch:{n_es_files}vs{es_files_expected}")

    fidx_row = np.empty(n_total, dtype=int)
    fidx_row[order] = np.concatenate([cc_fidx, es_fidx]) if n_total else np.array([], dtype=int)
    is_es_row = meta[:, 3].astype(int) == 1
    ev_row = meta[:, 0].astype(int)

    clean = not flags or flags == ["es_file_index_taken_from_tar_replay"]
    return {
        "file_index": fidx_row, "is_es": is_es_row, "event": ev_row,
        "n_total": n_total, "n_cc": n_cc, "n_es": n_es,
        "n_cc_files": n_cc_files, "n_es_files": n_es_files,
        "cc_files_expected": cc_files_expected, "es_files_expected": es_files_expected,
        "es_replay_ok": es_replay_ok, "flags": flags, "clean": clean,
    }


def budget_mask(index, n_es_budget=N_ES_BUDGET, n_cc_budget=N_CC_BUDGET,
                events_per_file=EVENTS_PER_FILE):
    """Rows of the first `n_*_budget` GENERATED events of each class.

    A class with fewer files than the budget needs keeps everything it has; the
    effective budget is then n_files * events_per_file (reduced statistics).
    """
    out = {}
    keep = np.zeros(index["n_total"], dtype=bool)
    for tag, want, avail in (("es", n_es_budget, index["n_es_files"]),
                             ("cc", n_cc_budget, index["n_cc_files"])):
        n_full, n_rest = divmod(int(want), int(events_per_file))
        need = n_full + (1 if n_rest else 0)
        reduced = avail < need
        if reduced:
            n_full, n_rest, need = avail, 0, avail
        cls = index["is_es"] if tag == "es" else ~index["is_es"]
        fi, ev = index["file_index"], index["event"]
        in_budget = fi < n_full
        if n_rest:
            in_budget = in_budget | ((fi == n_full) & (ev <= n_rest))
        keep |= cls & in_budget
        out[f"n_{tag}_generated_budget"] = int(n_full * events_per_file + n_rest)
        out[f"n_files_{tag}_used"] = int(need)
        out[f"n_files_{tag}_available"] = int(avail)
        out[f"reduced_{tag}_statistics"] = bool(reduced)
    out["mask"] = keep
    return out


# ---------------------------------------------------------------------------
# scenario re-evaluation with the pipeline's own code
# ---------------------------------------------------------------------------
def _write_run_dir(dest, metadata, reco, pred):
    dest = Path(dest)
    (dest / "volume_images").mkdir(parents=True, exist_ok=True)
    (dest / "predictions").mkdir(parents=True, exist_ok=True)
    np.savez(dest / "volume_images" / "volumes.npz", metadata=metadata)
    if reco is not None:
        np.savez(dest / "predictions" / "reco_directions.npz",
                 reco_dirs=reco["reco_dirs"], has_reco=reco["has_reco"])
    if pred is not None:
        np.savez(dest / "predictions" / "channel_predictions.npz", **pred)
    return dest


def evaluate_cat(cat, apply_budget, scratch, campaign_root=CAMPAIGN_ROOT,
                 samples_root=SAMPLES_ROOT, qc=None, catalog=None):
    """Recompute the six scenarios of one cat, with or without the generated-event budget."""
    t0 = time.time()
    prod = read_cat_products(cat, campaign_root)
    index = row_file_index(cat, prod["metadata"], samples_root, qc)

    if apply_budget:
        bud = budget_mask(index)
        mask = bud["mask"]
    else:
        bud = {}
        mask = np.ones(index["n_total"], dtype=bool)

    work = Path(scratch) / cat
    if work.exists():
        shutil.rmtree(work)
    rows = []
    for name in sorted(prod["scenarios"]):
        ent = prod["scenarios"][name]
        rep = ent["reporting"] or {}
        run_dir = _write_run_dir(
            work / name,
            ent["metadata"][mask],
            None if ent["reco"] is None else {k: v[mask] for k, v in ent["reco"].items()},
            None if ent["pred"] is None else {k: v[mask] for k, v in ent["pred"].items()},
        )
        ct_threshold = rep.get("ct_threshold")
        selected = select_electrons_from_run(
            run_dir,
            selection_mode=rep.get("selection_mode", "true-es"),
            direction_mode=rep.get("direction_mode", "reco"),
            min_energy_mev=float(rep.get("min_energy_mev", 0.0)),
            ct_threshold=float(ct_threshold) if ct_threshold is not None else None,
        )
        reco = reconstruct_burst_direction(
            selected_dirs=selected["selected_dirs"],
            selected_weights=selected["selected_weights"],
            selected_energies=selected["selected_energy"],
            true_burst_dir=selected["true_burst_dir"],
            use_emcee=True, emcee_cfg=EMCEE_CFG, pdf_path=PDF_PATH,
        )
        theta = reco["theta_samples_deg"]
        reco_dir = reco["reco_dir"]
        cos_to_truth = (float(np.clip(np.dot(reco_dir, selected["true_burst_dir"]), -1.0, 1.0))
                        if reco_dir is not None else float("nan"))
        if theta.size:
            q50 = float(np.quantile(theta, 0.50)); q68 = float(np.quantile(theta, 0.68))
            q68_cos = float(np.cos(np.radians(q68)))
            fwd = float(np.mean(np.cos(np.radians(theta)) > 0))
        else:
            q50 = q68 = q68_cos = fwd = float("nan")
        rows.append({
            "scenario": name,
            "label": rep.get("label", name),
            "run_dir": f"{campaign_root}/{cat}/{ent['run_prefix']}",
            "n_selected": selected["n_selected"],
            "selection_mode": rep.get("selection_mode"),
            "direction_mode": rep.get("direction_mode"),
            "direction_mode_used": selected["direction_mode_used"],
            "aggregation_method": reco["method"],
            "acceptance_fraction": reco["acceptance_fraction"],
            "min_energy_mev": float(rep.get("min_energy_mev", 0.0)),
            "single_pass_theta_deg": reco["single_pass_theta_deg"],
            "q50_theta_deg": q50, "q68_theta_deg": q68, "q68_cos": q68_cos,
            "cos_to_truth": cos_to_truth, "forward_frac": fwd, "ct_accuracy": None,
        })
    shutil.rmtree(work, ignore_errors=True)

    q68s = [r["q68_theta_deg"] for r in rows if not np.isnan(r["q68_theta_deg"])]
    report = {
        "aggregation_default": "emcee",
        "best_q68_theta_deg": float(np.nanmin(q68s)) if q68s else float("nan"),
        "scenarios": rows,
    }
    prov = {
        "cat": cat,
        "source_campaign": str(campaign_root),
        "budget_applied": bool(apply_budget),
        "events_per_file": EVENTS_PER_FILE,
        "n_rows_all": int(index["n_total"]),
        "n_rows_used": int(mask.sum()),
        "n_es_rows_all": int(index["n_es"]), "n_cc_rows_all": int(index["n_cc"]),
        "n_es_rows_used": int((mask & index["is_es"]).sum()),
        "n_cc_rows_used": int((mask & ~index["is_es"]).sum()),
        "n_es_files_found": index["n_es_files"], "n_cc_files_found": index["n_cc_files"],
        "n_es_files_expected_qc": index["es_files_expected"],
        "n_cc_files_expected_qc": index["cc_files_expected"],
        "es_replay_exact": index["es_replay_ok"],
        "file_index_clean": index["clean"],
        "flags": list(index["flags"]),
        "seconds": round(time.time() - t0, 1),
    }
    if apply_budget:
        prov.update({k: v for k, v in bud.items() if k != "mask"})
    report["budget_provenance"] = prov
    return report


def campaign_report(cat, campaign_root=CAMPAIGN_ROOT):
    p = Path(campaign_root) / cat / "scenario_cos_theta_report.json"
    return json.loads(p.read_text()) if p.exists() else None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _cat_list(args):
    if args.cats:
        return [c.strip() for c in args.cats.split(",") if c.strip()]
    if args.cat_file:
        return [l.strip() for l in Path(args.cat_file).read_text().splitlines() if l.strip()]
    raise SystemExit("give --cats or --cat-file")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["gate", "budget", "index"])
    ap.add_argument("--cats")
    ap.add_argument("--cat-file")
    ap.add_argument("--out-root", default=None,
                    help="budget mode: per-cat scenario_cos_theta_report.json goes here")
    ap.add_argument("--out", default=None, help="gate/index mode: json summary path")
    ap.add_argument("--campaign-root", default=str(CAMPAIGN_ROOT))
    ap.add_argument("--scratch", default=os.environ.get("TMPDIR", f"/tmp/{os.environ.get('USER','x')}")
                    + "/budget_replay")
    ap.add_argument("--force", action="store_true", help="budget mode: redo cats already written")
    args = ap.parse_args()

    cats = _cat_list(args)
    Path(args.scratch).mkdir(parents=True, exist_ok=True)
    qc = qc_file_counts()
    croot = Path(args.campaign_root)

    if args.mode == "index":
        out = []
        for cat in cats:
            try:
                prod = read_cat_products(cat, croot)
                idx = row_file_index(cat, prod["metadata"], qc=qc)
                out.append({k: (v.tolist() if isinstance(v, np.ndarray) else v)
                            for k, v in idx.items()
                            if k not in ("file_index", "is_es", "event")} | {"cat": cat})
                print(f"{cat}: es {idx['n_es_files']}/{idx['es_files_expected']} "
                      f"cc {idx['n_cc_files']}/{idx['cc_files_expected']} "
                      f"replay={idx['es_replay_ok']} clean={idx['clean']} {idx['flags']}")
            except Exception as e:
                out.append({"cat": cat, "error": str(e)})
                print(f"{cat}: ERROR {e}")
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(out, indent=1))
        return

    if args.mode == "gate":
        results = []
        for cat in cats:
            try:
                mine = evaluate_cat(cat, False, args.scratch, croot, qc=qc)
                ref = campaign_report(cat, croot)
                if ref is None:
                    results.append({"cat": cat, "error": "no campaign report"}); continue
                refmap = {r["scenario"]: r for r in ref["scenarios"]}
                rows = []
                for r in mine["scenarios"]:
                    b = refmap.get(r["scenario"])
                    if b is None:
                        rows.append({"scenario": r["scenario"], "error": "missing in campaign"}); continue
                    rows.append({
                        "scenario": r["scenario"],
                        "n_selected_mine": r["n_selected"], "n_selected_ref": b["n_selected"],
                        "n_ok": r["n_selected"] == b["n_selected"],
                        "cos_mine": r["cos_to_truth"], "cos_ref": b["cos_to_truth"],
                        "d_cos": abs(r["cos_to_truth"] - b["cos_to_truth"]),
                        "d_theta_deg": abs(r["single_pass_theta_deg"] - b["single_pass_theta_deg"]),
                    })
                ok = all(x.get("n_ok") and x.get("d_cos", 1) < 1e-6 for x in rows)
                results.append({"cat": cat, "ok": ok, "scenarios": rows,
                                "flags": mine["budget_provenance"]["flags"]})
                worst = max((x.get("d_cos", 0) for x in rows), default=0)
                print(f"{cat}: gate {'OK ' if ok else 'FAIL'} max|dcos|={worst:.3e} "
                      f"n_sel_ok={sum(1 for x in rows if x.get('n_ok'))}/{len(rows)}")
            except Exception as e:
                results.append({"cat": cat, "error": str(e)})
                print(f"{cat}: ERROR {e}")
            sys.stdout.flush()
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(results, indent=1))
        n_ok = sum(1 for r in results if r.get("ok"))
        print(f"\nGATE: {n_ok}/{len(results)} cats reproduce the campaign exactly")
        return

    # budget
    if not args.out_root:
        raise SystemExit("budget mode needs --out-root")
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    for cat in cats:
        dest = out_root / cat / "scenario_cos_theta_report.json"
        if dest.exists() and dest.stat().st_size > 0 and not args.force:
            print(f"{cat}: already done"); sys.stdout.flush(); continue
        try:
            rep = evaluate_cat(cat, True, args.scratch, croot, qc=qc)
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(rep, indent=2))
            os.replace(tmp, dest)
            p = rep["budget_provenance"]
            print(f"{cat}: ok rows {p['n_rows_used']}/{p['n_rows_all']} "
                  f"(ES {p['n_es_rows_used']}/{p['n_es_rows_all']}, "
                  f"CC {p['n_cc_rows_used']}/{p['n_cc_rows_all']}) "
                  f"clean={p['file_index_clean']} {p['seconds']}s")
        except Exception as e:
            print(f"{cat}: ERROR {type(e).__name__}: {e}")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
