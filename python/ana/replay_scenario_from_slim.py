#!/usr/bin/env python3
"""Replay ONE scenario's ANALYSIS stage on a campaign's stored per-event predictions.

The r3 campaign (`pipeline-campaign/v63_matchfix_1000`) no longer holds the CC cluster
images, so the full pipeline cannot be re-run on it.  Everything the burst fit needs is
still in `<cat>/<cat>_scenarios_slim.tar`, though:

    <scenario>/pipeline_run_*/volume_images/volumes.npz          (metadata, images dropped)
    <scenario>/pipeline_run_*/predictions/reco_directions.npz    (ED v63 directions)
    <scenario>/pipeline_run_*/predictions/channel_predictions.npz(CT v80 scores)
    <scenario>/pipeline_run_*/metrics.json, config_used.json

This driver extracts exactly those files into worker scratch, runs the SAME production code
path that python/ana/scenario_cos_theta_report.py runs for the scenario
(`select_electrons_from_run` + `reconstruct_burst_direction_grid_mixture`, or
`reconstruct_burst_direction` for the emcee scenarios), writes ONE json per cat with the same
fields `scenario_cos_theta_report.json` has for that scenario, and deletes the extracted
files.  Nothing else is written; the campaign is opened read-only.

The scenario settings come from a scenario catalog entry, mapped to the `reporting` block
exactly as test/run_small_sample_pipeline.sh does, so the replayed fit is bit-for-bit the
pipeline's own analysis stage.

NOTHING THAT DEFINES THE FIT IS HARD-CODED HERE.  The CT hard cut (`mixture.ct_hard_cut`), the
energy cut (`report_min_energy_mev`), the purity calibration and prior (`mixture.calibration_path`,
`pi_mode`, `pi_fixed`), the ES table (`mixture.pdf_es_path` / `pdf_path`), the CC component
(`mixture.cc_pdf_mode`, `cc_pdf_path`, `cc_map_path`), the acceptance coefficients
(`acceptance_path`, top level or inside `mixture`) and the grid (`mixture.grid_n`, `pdf_floor`) all
come from the catalog entry, and the sampler block from `--emcee-json`.  Re-running the campaign at
a different CT working point is therefore a catalog edit (new threshold, its matching ES table,
purity calibration and acceptance file) plus a new `--out`; no code change.  `--resolved-only`
prints what the entry resolves to and exits, for auditing that before a 1000-cat run.

Event trimming (supernova-distance study), OPT-IN, default off:
  --keep-fraction F[,F2,...] --trim-seed S[,S2,...] --chunk-out FILE.json
keeps, BEFORE the selection, a random subset of round(F * N_gen) of the burst's GENERATED ES
events and, independently, round(F * N_gen) of its GENERATED CC events (N_gen = --n-gen-es 330 /
--n-gen-cc 3300, the campaign's generated-event budget; see python/lib/sample_loader.py).  A burst
at distance d has N(d) = N(10 kpc) (10/d)^2 events of both classes, so F = (10/d)^2.  Generated
events that left no matched cluster are part of the budget (they occupy "empty" slots), so a kept
subset is a uniform random subset of the generated events, not of the reconstructed ones.  The
volumes.npz metadata does not store the input-file index of an event (only its per-file event
number), so the event identity used for the draw is the event's stored truth record (class,
event number, neutrino energy and momentum, true position): all clusters of one event share it
and it does not depend on the loader's shuffle.  The draw is reproducible from (seed, cat, class)
and NESTED in F for a given seed (the events kept at a smaller F are a subset of those kept at a
larger F).  The three per-cluster files are subset consistently and the UNCHANGED selection and
fit run on them; nothing is re-inferred.  The per-cluster predictions only exist for the loaded
330 + 3300 events, so F > 1 (closer supernovae) is impossible.  With --keep-fraction every
(F, seed) pair is fitted per cat from one tar extraction and all rows go to ONE json per job
(--chunk-out); no per-cat files are written.  Without --keep-fraction the driver is unchanged.

Usage:
  python3 python/ana/replay_scenario_from_slim.py \
      --catalog json/seven_scenarios_v63_acceptance.json \
      --scenario scenario_7_full_pipeline_acc \
      --source-scenario scenario_3_full_pipeline \
      --cats 2-31 \
      --campaign /eos/.../pipeline-campaign/v63_matchfix_1000 \
      --out /eos/.../pipeline-campaign/v63_matchfix_1000_acc \
      [--scratch $TMPDIR] [--overwrite]
"""
import argparse
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

from ana.burst_direction import (reconstruct_burst_direction,  # noqa: E402
                                 reconstruct_burst_direction_grid_mixture,
                                 select_electrons_from_run)
from ana.scenario_cos_theta_report import _mixture_row_extra  # noqa: E402

NEEDED = ("volume_images/volumes.npz", "predictions/reco_directions.npz",
          "predictions/channel_predictions.npz")
OPTIONAL = ("metrics.json", "config_used.json")
EMCEE_DEFAULT = {"nwalkers": 128, "nsteps": 500, "discard": 100, "prior_type": "uniform",
                 "prior_sigma_deg": 10.0, "likelihood_kappa": 25.0, "random_seed": 42,
                 "pdf_lookup": "clipped", "pdf_floor": 1e-4}


def parse_cats(spec):
    out = []
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = (int(x) for x in part.split("-"))
            out.extend(range(lo, hi + 1))
        else:
            out.append(int(part))
    bad = [c for c in out if 400 <= c <= 621]
    if bad:
        raise SystemExit(f"cats 400-621 are off limits (training cats): {bad[:5]}...")
    return sorted(set(out))


def reporting_from_catalog(entry):
    """The `reporting` block test/run_small_sample_pipeline.sh would write for this entry."""
    rep = {
        "selection_mode": str(entry.get("report_selection_mode", "predicted-es")),
        "direction_mode": str(entry.get("report_direction_mode", "reco")),
        "min_energy_mev": float(entry.get("report_min_energy_mev", 3.0)),
        "ct_threshold": float(entry.get("channel_tagger_threshold", 0.5)),
        "label": str(entry.get("report_label", entry["name"])),
    }
    if isinstance(entry.get("mixture"), dict):
        rep["mixture"] = entry["mixture"]
    if isinstance(entry.get("pdf_path"), str) and entry["pdf_path"].strip():
        rep["pdf_path"] = entry["pdf_path"].strip()
    if isinstance(entry.get("acceptance_path"), str) and entry["acceptance_path"].strip():
        rep["acceptance_path"] = entry["acceptance_path"].strip()
    return rep


def extract_run(tar_path, source_scenario, dest):
    """Extract the three prediction/metadata files of `source_scenario` into `dest`.

    Returns (run_dir, metrics dict, tar member prefix) or None when the tar has no usable run.
    """
    dest = Path(dest)
    with tarfile.open(tar_path) as tf:
        names = tf.getnames()
        vol = [n for n in names
               if n.startswith(source_scenario + "/") and n.endswith("volume_images/volumes.npz")]
        if not vol:
            return None
        pre = sorted(vol)[-1].rsplit("/volume_images/", 1)[0]
        for rel in NEEDED:
            if f"{pre}/{rel}" not in names:
                return None
        (dest / "volume_images").mkdir(parents=True, exist_ok=True)
        (dest / "predictions").mkdir(parents=True, exist_ok=True)
        for rel in NEEDED:
            (dest / rel).write_bytes(tf.extractfile(f"{pre}/{rel}").read())
        metrics = {}
        for rel in OPTIONAL:
            n = f"{pre}/{rel}"
            if n in names:
                try:
                    payload = json.loads(tf.extractfile(n).read().decode())
                except Exception:  # noqa: BLE001
                    continue
                if rel == "metrics.json":
                    metrics = payload
    return dest, metrics, pre


TRIM_FILES = NEEDED  # the per-cluster files subset consistently by the event trimming


def _event_keys(metadata):
    """Per-row event identity: (class, event number, nu energy, nu momentum, true position).

    Rows of one generated event share it; the loader's shuffle does not change it.  Returned as
    an integer label per row (0..n_events-1) in a CANONICAL order (lexicographic in the record),
    so the draw below does not depend on the row order in volumes.npz.
    """
    m = np.asarray(metadata, dtype=np.float64)
    rec = np.column_stack([m[:, 3], m[:, 0], m[:, 14], m[:, 15], m[:, 16], m[:, 17],
                           m[:, 4], m[:, 5], m[:, 6]])
    _, inv = np.unique(rec, axis=0, return_inverse=True)
    return np.asarray(inv).reshape(-1)


def trim_keep_mask(metadata, keep_fraction, seed, cat_number, n_gen_es, n_gen_cc):
    """Row mask keeping round(F*N_gen) generated events of each class (see module docstring)."""
    m = np.asarray(metadata, dtype=np.float64)
    is_es = m[:, 3].astype(int) == 1
    keys = _event_keys(m)
    keep = np.zeros(m.shape[0], dtype=bool)
    info = {}
    for cls, sel, n_gen, cls_id in (("es", is_es, int(n_gen_es), 1), ("cc", ~is_es, int(n_gen_cc), 0)):
        ev = np.unique(keys[sel])                      # canonical order of this class's events
        n_obs = int(ev.size)
        if n_obs > n_gen:
            raise ValueError(f"{cls}: {n_obs} reconstructed events > generated budget {n_gen}")
        n_keep = int(np.floor(float(keep_fraction) * n_gen + 0.5))
        rng = np.random.default_rng([int(seed), int(cat_number), cls_id])
        # a random rank for each of the n_gen generated-event slots; the n_obs reconstructed
        # events occupy slots 0..n_obs-1 in canonical order, the rest left no cluster
        rank = rng.permutation(n_gen)
        kept_ev = ev[rank[:n_obs] < n_keep]
        keep |= sel & np.isin(keys, kept_ev)
        info[f"n_gen_{cls}"] = n_gen
        info[f"n_gen_{cls}_kept"] = n_keep
        info[f"n_reco_{cls}_loaded"] = n_obs
        info[f"n_reco_{cls}_kept"] = int(kept_ev.size)
        info[f"n_rows_{cls}_kept"] = int(np.sum(keep & sel))
    return keep, info


def write_trimmed_run(src_dir, dest_dir, keep):
    """Copy the per-cluster files of `src_dir` into `dest_dir`, keeping the rows in `keep`."""
    src_dir, dest_dir = Path(src_dir), Path(dest_dir)
    n = keep.shape[0]
    for rel in TRIM_FILES:
        (dest_dir / rel).parent.mkdir(parents=True, exist_ok=True)
        with np.load(src_dir / rel, allow_pickle=True) as z:
            arrays = {k: (z[k][keep] if (z[k].ndim >= 1 and z[k].shape[0] == n) else z[k])
                      for k in z.files}
        with open(dest_dir / rel, "wb") as fh:
            np.savez(fh, **arrays)
    return dest_dir


def fit_one(run_dir, rep, emcee_cfg):
    """Exactly the per-scenario body of scenario_cos_theta_report.build_report."""
    selection_mode = rep["selection_mode"]
    mixture_cfg = rep.get("mixture") if selection_mode == "mixture-ct" else None
    acceptance_path = rep.get("acceptance_path") or None
    selected = select_electrons_from_run(
        run_dir, selection_mode=selection_mode, direction_mode=rep["direction_mode"],
        min_energy_mev=rep["min_energy_mev"], ct_threshold=rep.get("ct_threshold"),
        mixture_cfg=mixture_cfg)
    if selection_mode == "mixture-ct":
        mcfg = mixture_cfg or {}
        reco = reconstruct_burst_direction_grid_mixture(
            selected_dirs=selected["selected_dirs"],
            selected_energies=selected["selected_energy"],
            p_es=selected["mixture"]["p_es"],
            true_burst_dir=selected["true_burst_dir"],
            pdf_es_path=mcfg.get("pdf_es_path", rep.get("pdf_path")),
            pdf_cc_path=mcfg.get("pdf_cc_path"),
            cc_pdf_mode=mcfg.get("cc_pdf_mode", "table"),
            grid_n=int(mcfg.get("grid_n", 41253)),
            pdf_floor=float(mcfg.get("pdf_floor", 1e-4)),
            random_seed=int(emcee_cfg.get("random_seed", 42)),
            cc_map_path=mcfg.get("cc_map_path"),
            acceptance_path=mcfg.get("acceptance_path", acceptance_path),
        )
        extra = _mixture_row_extra(selected, reco)
    else:
        reco = reconstruct_burst_direction(
            selected_dirs=selected["selected_dirs"],
            selected_weights=selected["selected_weights"],
            selected_energies=selected["selected_energy"],
            true_burst_dir=selected["true_burst_dir"],
            use_emcee=bool(emcee_cfg.get("enabled", True)), emcee_cfg=emcee_cfg,
            pdf_path=rep.get("pdf_path"), acceptance_path=acceptance_path)
        extra = {}
    return selected, reco, extra


def row_from_fit(scenario_name, rep, run_dir, selected, reco, extra, metrics):
    theta = np.asarray(reco["theta_samples_deg"], dtype=np.float64)
    reco_dir = reco["reco_dir"]
    cos_to_truth = (float(np.clip(np.dot(reco_dir, selected["true_burst_dir"]), -1.0, 1.0))
                    if reco_dir is not None else float("nan"))
    if theta.size > 0:
        q50 = float(np.quantile(theta, 0.50))
        q68 = float(np.quantile(theta, 0.68))
        q68_cos = float(np.cos(np.radians(q68)))
        fwd = float(np.mean(np.cos(np.radians(theta)) > 0))
    else:
        q50 = q68 = q68_cos = fwd = float("nan")
    mcfg = rep.get("mixture") or {}
    return {
        "scenario": scenario_name,
        "label": rep["label"],
        "run_dir": str(run_dir),
        "n_selected": int(selected["n_selected"]),
        "selection_mode": rep["selection_mode"],
        "direction_mode": rep["direction_mode"],
        "direction_mode_used": selected["direction_mode_used"],
        "aggregation_method": reco["method"],
        "acceptance_fraction": reco["acceptance_fraction"],
        "min_energy_mev": rep["min_energy_mev"],
        "pdf_path": mcfg.get("pdf_es_path", rep.get("pdf_path")),
        "acceptance_path": mcfg.get("acceptance_path", rep.get("acceptance_path")),
        "single_pass_theta_deg": reco["single_pass_theta_deg"],
        "q50_theta_deg": q50,
        "q68_theta_deg": q68,
        "q68_cos": q68_cos,
        "cos_to_truth": cos_to_truth,
        "forward_frac": fwd,
        "ct_accuracy": (metrics.get("steps", {}).get("channel_tagging", {})
                        .get("performance", {}).get("accuracy")),
        **extra,
    }


def run_trimmed(args, rep, emcee_cfg, fracs, seeds):
    """Event-trimming mode: every (F, seed) per cat, all rows into ONE json (--chunk-out)."""
    camp, chunk_out = Path(args.campaign), Path(args.chunk_out)
    if chunk_out.is_file() and chunk_out.stat().st_size > 0 and not args.overwrite:
        print(f"{chunk_out} exists, nothing to do (use --overwrite)")
        return
    chunk_out.parent.mkdir(parents=True, exist_ok=True)
    cats = parse_cats(args.cats)
    scratch_root = Path(tempfile.mkdtemp(prefix="replay_trim_", dir=args.scratch))
    rows, errors = [], []
    t0 = time.time()
    try:
        for n in cats:
            cat = f"cat{n:06d}"
            tar = camp / cat / f"{cat}_scenarios_slim.tar"
            if not tar.is_file():
                print(f"  {cat}: no slim tar, skipped", flush=True)
                errors.append({"cat": n, "error": "no slim tar"})
                continue
            work = scratch_root / cat
            try:
                got = extract_run(tar, args.source_scenario, work / "full")
                if got is None:
                    errors.append({"cat": n, "error": f"no usable {args.source_scenario} run"})
                    continue
                run_dir, metrics, pre = got
                meta = np.load(run_dir / "volume_images" / "volumes.npz",
                               allow_pickle=True)["metadata"]
                for f in fracs:
                    for sd in seeds:
                        try:
                            keep, info = trim_keep_mask(meta, f, sd, n, args.n_gen_es,
                                                        args.n_gen_cc)
                            tdir = write_trimmed_run(run_dir, work / "trim", keep)
                            selected, reco, extra = fit_one(tdir, rep, emcee_cfg)
                            row = row_from_fit(args.scenario, rep, f"{tar}:{pre}", selected,
                                               reco, extra, metrics)
                            row.update({"cat": n, "keep_fraction": f, "trim_seed": sd,
                                        "true_burst_dir": [float(x) for x in
                                                           selected["true_burst_dir"]],
                                        "reco_dir": (None if reco["reco_dir"] is None else
                                                     [float(x) for x in reco["reco_dir"]]),
                                        **info})
                            rows.append(row)
                            print(f"  {cat} F={f:.4f} s={sd}: n={row['n_selected']} "
                                  f"theta={np.degrees(np.arccos(np.clip(row['cos_to_truth'], -1, 1))):.2f} "
                                  f"({time.time() - t0:.0f}s)", flush=True)
                        except Exception as exc:  # noqa: BLE001
                            errors.append({"cat": n, "keep_fraction": f, "trim_seed": sd,
                                           "error": repr(exc)})
                            print(f"  {cat} F={f} s={sd}: FAILED {exc!r}", flush=True)
                        finally:
                            shutil.rmtree(work / "trim", ignore_errors=True)
            except Exception as exc:  # noqa: BLE001
                errors.append({"cat": n, "error": repr(exc)})
                print(f"  {cat}: FAILED {exc!r}", flush=True)
            finally:
                shutil.rmtree(work, ignore_errors=True)
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)
    payload = {
        "driver": "python/ana/replay_scenario_from_slim.py (event-trimming mode)",
        "catalog": str(Path(args.catalog).resolve()),
        "scenario": args.scenario,
        "source_scenario": args.source_scenario,
        "campaign": str(camp),
        "cats": args.cats,
        "keep_fractions": fracs,
        "trim_seeds": seeds,
        "n_gen_es": args.n_gen_es,
        "n_gen_cc": args.n_gen_cc,
        "reporting": rep,
        "note": ("analysis stage only on the stored ED v63 directions and CT v80 scores; before "
                 "the selection round(F*N_gen) generated events of each class are kept "
                 "(uniform random subset by event identity, nested in F per seed)"),
        "rows": rows,
        "errors": errors,
    }
    tmp = chunk_out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload) + "\n")
    os.replace(tmp, chunk_out)
    print(f"done: {len(rows)} fits, {len(errors)} errors, {time.time() - t0:.0f}s -> {chunk_out}")
    if errors:
        raise SystemExit(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--scenario", required=True, help="catalog entry to replay")
    ap.add_argument("--source-scenario", default="scenario_3_full_pipeline",
                    help="scenario folder INSIDE the tar that holds the per-event predictions")
    ap.add_argument("--cats", required=True, help="ranges/list, e.g. 2-31,901-905")
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scratch", default=os.environ.get("TMPDIR") or None,
                    help="worker scratch for the extracted files (default: system temp)")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--emcee-json", default=None, help="optional json with the emcee block")
    ap.add_argument("--resolved-only", action="store_true",
                    help="print the settings the catalog entry resolves to, then exit")
    ap.add_argument("--keep-fraction", default=None,
                    help="OPT-IN event trimming: comma list of fractions F in (0, 1] of the "
                         "generated ES and CC events kept before the selection (F = (10/d)^2)")
    ap.add_argument("--trim-seed", default="1",
                    help="comma list of trimming seeds; every (F, seed) pair is fitted")
    ap.add_argument("--n-gen-es", type=int, default=330, help="generated ES events per burst")
    ap.add_argument("--n-gen-cc", type=int, default=3300, help="generated CC events per burst")
    ap.add_argument("--chunk-out", default=None,
                    help="with --keep-fraction: the ONE json this job writes (all rows)")
    args = ap.parse_args()
    trim_fracs = trim_seeds = None
    if args.keep_fraction is not None:
        trim_fracs = [float(x) for x in str(args.keep_fraction).split(",") if x.strip()]
        trim_seeds = [int(x) for x in str(args.trim_seed).split(",") if x.strip()]
        if not trim_fracs or any(not (0.0 < f <= 1.0) for f in trim_fracs):
            raise SystemExit("--keep-fraction values must be in (0, 1]: the stored predictions "
                             "only hold the loaded events, a closer supernova needs new samples")
        if not args.chunk_out:
            raise SystemExit("--keep-fraction needs --chunk-out (one output file per job)")

    catalog = json.loads(Path(args.catalog).read_text())
    entry = next((s for s in catalog.get("scenarios", []) if s.get("name") == args.scenario), None)
    if entry is None:
        raise SystemExit(f"scenario {args.scenario!r} not in {args.catalog}")
    rep = reporting_from_catalog(entry)
    emcee_cfg = dict(EMCEE_DEFAULT)
    if args.emcee_json:
        emcee_cfg.update(json.loads(Path(args.emcee_json).read_text()))
    mcfg = rep.get("mixture") or {}
    resolved = {
        "selection_mode": rep["selection_mode"],
        "direction_mode": rep["direction_mode"],
        "min_energy_mev": rep["min_energy_mev"],
        "ct_hard_cut": mcfg.get("ct_hard_cut"),
        "s_min": mcfg.get("s_min"),
        "p_floor": mcfg.get("p_floor"),
        "ct_source": mcfg.get("ct_source"),
        "pi_mode": mcfg.get("pi_mode"),
        "pi_fixed": mcfg.get("pi_fixed"),
        "calibration_path": mcfg.get("calibration_path"),
        "pdf_es_path": mcfg.get("pdf_es_path", rep.get("pdf_path")),
        "cc_pdf_mode": mcfg.get("cc_pdf_mode"),
        "cc_pdf_path": mcfg.get("pdf_cc_path"),
        "cc_map_path": mcfg.get("cc_map_path"),
        "acceptance_path": mcfg.get("acceptance_path", rep.get("acceptance_path")),
        "grid_n": mcfg.get("grid_n"),
        "pdf_floor": mcfg.get("pdf_floor"),
        "emcee_random_seed": emcee_cfg.get("random_seed"),
    }
    print(f"replaying {args.scenario} (from tar folder {args.source_scenario})")
    print("  resolved from the catalog entry (nothing hard-coded):")
    for k, v in resolved.items():
        print(f"    {k:18s} = {v}")
    missing = [k for k in ("calibration_path", "pdf_es_path", "cc_pdf_path", "cc_map_path",
                           "acceptance_path")
               if resolved[k] and not Path(str(resolved[k])).is_file()]
    if missing:
        raise SystemExit(f"these catalog paths do not exist: "
                         f"{ {k: resolved[k] for k in missing} }")
    if args.resolved_only:
        return
    if trim_fracs is not None:
        return run_trimmed(args, rep, emcee_cfg, trim_fracs, trim_seeds)

    camp, out_root = Path(args.campaign), Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    cats = parse_cats(args.cats)
    scratch_root = Path(tempfile.mkdtemp(prefix="replay_", dir=args.scratch))
    done = skipped = failed = 0
    t0 = time.time()
    try:
        for n in cats:
            cat = f"cat{n:06d}"
            # Named exactly like the pipeline's own per-cat report so that
            # python/ana/aggregate_scenario_reports.py and paired_campaign_compare.py read
            # this root unchanged; the "replay" block inside records that it is a replay.
            out_json = out_root / cat / "scenario_cos_theta_report.json"
            if out_json.is_file() and out_json.stat().st_size > 0 and not args.overwrite:
                skipped += 1
                continue
            tar = camp / cat / f"{cat}_scenarios_slim.tar"
            if not tar.is_file():
                print(f"  {cat}: no slim tar, skipped", flush=True)
                skipped += 1
                continue
            work = scratch_root / cat
            try:
                got = extract_run(tar, args.source_scenario, work)
                if got is None:
                    print(f"  {cat}: tar has no usable {args.source_scenario} run, skipped",
                          flush=True)
                    skipped += 1
                    continue
                run_dir, metrics, pre = got
                selected, reco, extra = fit_one(run_dir, rep, emcee_cfg)
                row = row_from_fit(args.scenario, rep, f"{tar}:{pre}", selected, reco, extra,
                                   metrics)
                payload = {
                    "aggregation_default": "emcee" if emcee_cfg.get("enabled", True) else
                                           "weighted-mean+bootstrap",
                    "best_q68_theta_deg": row["q68_theta_deg"],
                    "scenarios": [row],
                    "replay": {
                        "driver": "python/ana/replay_scenario_from_slim.py",
                        "catalog": str(Path(args.catalog).resolve()),
                        "scenario": args.scenario,
                        "source_scenario": args.source_scenario,
                        "source_tar": str(tar),
                        "source_run": pre,
                        "cat": cat,
                        "reporting": rep,
                        "note": ("analysis stage only: the stored ED v63 reco directions and CT v80 "
                                 "scores of the campaign run are re-fitted, nothing is re-inferred"),
                    },
                }
                out_json.parent.mkdir(parents=True, exist_ok=True)
                tmp = out_json.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(payload, indent=2) + "\n")
                os.replace(tmp, out_json)
                done += 1
                print(f"  {cat}: n={row['n_selected']} theta={row['single_pass_theta_deg']:.3f} "
                      f"q68={row['q68_theta_deg']:.3f} ({time.time() - t0:.0f}s)", flush=True)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"  {cat}: FAILED {exc!r}", flush=True)
            finally:
                shutil.rmtree(work, ignore_errors=True)
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)
    print(f"done: {done} fitted, {skipped} skipped, {failed} failed, {time.time() - t0:.0f}s")
    if failed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
