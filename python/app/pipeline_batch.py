#!/usr/bin/env python3
"""Run the full pipeline across many CAT folders from a JSON config."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# Add python modules to path
python_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(python_root))

from ana.burst_direction_batch_report import build_batch_report


def _require_init_done():
    if os.environ.get("INIT_DONE", "").lower() != "true":
        raise RuntimeError("Environment not initialized. Run: source scripts/init.sh")


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def discover_cats(samples_base: Path, cat_glob: str, n_cats: int):
    cats = sorted([p for p in samples_base.glob(cat_glob) if p.is_dir()])
    if n_cats > 0:
        cats = cats[:n_cats]
    return cats


def allocate(total: int, n_parts: int):
    base = total // n_parts
    rem = total % n_parts
    return [base + (1 if idx < rem else 0) for idx in range(n_parts)]


def resolve_cluster_x_dir(cat_dir: Path, cat_name: str, plane: str):
    candidates = sorted(cat_dir.glob(f"{cat_name}_cluster_images*/{plane.upper()}"))
    if not candidates:
        raise FileNotFoundError(f"Could not find cluster image folder for {cat_name} ({plane}) under {cat_dir}")
    return candidates[0]


def latest_pipeline_run(cat_output_base: Path):
    runs = sorted(cat_output_base.glob("pipeline_run_*"))
    if not runs:
        return None
    return runs[-1]


def run_single_pipeline(pipeline_py: Path, config_path: Path):
    cmd = ["python3", str(pipeline_py), "-j", str(config_path)]
    subprocess.run(cmd, check=True)


def build_summary_plot(out_png: Path, cat_labels, cc_selected, es_selected, cc_requested, es_requested):
    out_png.parent.mkdir(parents=True, exist_ok=True)

    indices = np.arange(len(cat_labels))
    width = 0.38

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 9), sharex=True)

    ax1.bar(indices - width / 2, cc_selected, width=width, label="CC selected", color="#1f77b4")
    ax1.bar(indices + width / 2, es_selected, width=width, label="ES selected", color="#ff7f0e")
    ax1.set_ylabel("Events")
    ax1.set_title("Per-CAT selected events")
    ax1.grid(True, alpha=0.2)
    ax1.legend()

    cum_cc = np.cumsum(cc_selected)
    cum_es = np.cumsum(es_selected)
    ax2.plot(indices, cum_cc, "-", linewidth=2, label="Cumulative CC", color="#1f77b4")
    ax2.plot(indices, cum_es, "-", linewidth=2, label="Cumulative ES", color="#ff7f0e")
    ax2.axhline(cc_requested, linestyle="--", color="#1f77b4", alpha=0.6, label=f"Target CC={cc_requested}")
    ax2.axhline(es_requested, linestyle="--", color="#ff7f0e", alpha=0.6, label=f"Target ES={es_requested}")
    ax2.set_ylabel("Cumulative events")
    ax2.set_xlabel("CAT index")
    ax2.set_title("Cumulative selected events vs target")
    ax2.grid(True, alpha=0.2)
    ax2.legend()

    fig.tight_layout()
    fig.savefig(out_png, dpi=180)
    plt.close(fig)


def main():
    _require_init_done()

    parser = argparse.ArgumentParser(description="Run batch full-pipeline over many CAT folders")
    parser.add_argument("-j", "--json", "--config", dest="config", required=True,
                        help="JSON batch config")
    args = parser.parse_args()

    cfg = load_json(args.config)
    batch_cfg = cfg.get("pipeline_batch", cfg)

    repo_root = Path(__file__).resolve().parents[2]
    pipeline_py = repo_root / "python" / "app" / "pipeline.py"

    base_pipeline_cfg_path = Path(batch_cfg["base_pipeline_config"])
    if not base_pipeline_cfg_path.is_absolute():
        base_pipeline_cfg_path = (repo_root / base_pipeline_cfg_path).resolve()
    base_pipeline_cfg = load_json(base_pipeline_cfg_path)

    samples_base = Path(batch_cfg["samples"]["base_dir"])
    cat_glob = batch_cfg["samples"].get("cat_glob", "cat[0-9][0-9][0-9][0-9][0-9][0-9]")
    n_bursts = int(batch_cfg["samples"].get("n_bursts", batch_cfg["samples"].get("n_cats", 100)))
    plane = batch_cfg["samples"].get("plane", "X").upper()

    output_cfg = batch_cfg["output"]
    output_base = Path(output_cfg["base_dir"])
    configs_dir = output_base / "generated_configs"
    runs_dir = output_base / "runs"
    output_base.mkdir(parents=True, exist_ok=True)
    configs_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    cats = discover_cats(samples_base, cat_glob, n_bursts)
    if not cats:
        raise RuntimeError(f"No cats found under {samples_base} with pattern {cat_glob}")

    total_cc = int(batch_cfg["selection"]["total_cc_events"])
    total_es = int(batch_cfg["selection"]["total_es_events"])

    cc_alloc = allocate(total_cc, len(cats))
    es_alloc = allocate(total_es, len(cats))

    ct_enabled = bool(batch_cfg.get("channel_tagger", {}).get("enabled", True))
    ct_model_path = batch_cfg.get("channel_tagger", {}).get("model_path")
    use_simple_mode = bool(batch_cfg.get("volume_creation", {}).get("use_simple_mode", True))
    continue_on_error = bool(batch_cfg.get("execution", {}).get("continue_on_error", False))

    summary_rows = []

    for idx, cat_dir in enumerate(cats):
        cat_name = cat_dir.name
        cat_cc = cc_alloc[idx]
        cat_es = es_alloc[idx]

        try:
            cluster_x_dir = resolve_cluster_x_dir(cat_dir, cat_name, plane)

            run_cfg = json.loads(json.dumps(base_pipeline_cfg))
            run_cfg.setdefault("input_data", {})
            run_cfg.setdefault("sample_selection", {})
            run_cfg.setdefault("volume_creation", {})
            run_cfg.setdefault("neural_networks", {}).setdefault("channel_tagger", {})
            run_cfg.setdefault("output", {})

            run_cfg["input_data"]["cc_folder"] = str(cluster_x_dir)
            run_cfg["input_data"]["es_folder"] = str(cluster_x_dir)
            run_cfg["input_data"]["file_pattern"] = f"*_plane{plane}.npz"
            run_cfg["input_data"]["cc_file_pattern"] = f"cc_*_plane{plane}.npz"
            run_cfg["input_data"]["es_file_pattern"] = f"es_*_plane{plane}.npz"

            run_cfg["sample_selection"]["n_cc_events"] = int(cat_cc)
            run_cfg["sample_selection"]["n_es_events"] = int(cat_es)

            run_cfg["volume_creation"]["use_simple_mode"] = use_simple_mode
            run_cfg["neural_networks"]["channel_tagger"]["enabled"] = ct_enabled
            if ct_model_path:
                run_cfg["neural_networks"]["channel_tagger"]["model_path"] = ct_model_path

            cat_output_base = runs_dir / cat_name
            cat_output_base.mkdir(parents=True, exist_ok=True)
            run_cfg["output"]["base_folder"] = str(cat_output_base)

            run_cfg_path = configs_dir / f"{cat_name}.json"
            with open(run_cfg_path, "w") as f:
                json.dump(run_cfg, f, indent=2)

            print(f"[{idx + 1}/{len(cats)}] Running pipeline for {cat_name} (CC={cat_cc}, ES={cat_es})")
            run_single_pipeline(pipeline_py, run_cfg_path)

            latest = latest_pipeline_run(cat_output_base)
            if latest is None:
                raise RuntimeError(f"No pipeline_run_* produced for {cat_name}")

            metrics_path = latest / "metrics.json"
            if not metrics_path.exists():
                raise RuntimeError(f"Missing metrics.json for {cat_name}: {metrics_path}")

            metrics = load_json(metrics_path)
            ss = metrics.get("steps", {}).get("sample_selection", {})
            summary_rows.append({
                "cat": cat_name,
                "requested_cc_events": cat_cc,
                "requested_es_events": cat_es,
                "selected_cc_events": int(ss.get("n_cc_events", 0)),
                "selected_es_events": int(ss.get("n_es_events", 0)),
                "selected_cc_clusters": int(ss.get("n_cc_clusters", 0)),
                "selected_es_clusters": int(ss.get("n_es_clusters", 0)),
                "metrics_json": str(metrics_path),
            })
        except Exception as exc:
            print(f"[ERROR] {cat_name}: {exc}", file=sys.stderr)
            if not continue_on_error:
                raise

    if not summary_rows:
        raise RuntimeError("Batch completed with no successful CAT runs")

    total_requested_cc = int(sum(r["requested_cc_events"] for r in summary_rows))
    total_requested_es = int(sum(r["requested_es_events"] for r in summary_rows))
    total_selected_cc = int(sum(r["selected_cc_events"] for r in summary_rows))
    total_selected_es = int(sum(r["selected_es_events"] for r in summary_rows))

    aggregate = {
        "n_bursts_requested": n_bursts,
        "n_cats_requested": n_bursts,
        "n_bursts_processed": len(summary_rows),
        "n_cats_processed": len(summary_rows),
        "requested_totals": {
            "cc_events": total_requested_cc,
            "es_events": total_requested_es,
        },
        "selected_totals": {
            "cc_events": total_selected_cc,
            "es_events": total_selected_es,
        },
        "matches_requested_totals": (
            total_requested_cc == total_selected_cc and total_requested_es == total_selected_es
        ),
        "per_cat": summary_rows,
    }

    aggregate_json = Path(output_cfg.get("aggregate_json", output_base / "aggregate_summary.json"))
    if not aggregate_json.is_absolute():
        aggregate_json = (repo_root / aggregate_json).resolve()
    aggregate_json.parent.mkdir(parents=True, exist_ok=True)
    with open(aggregate_json, "w") as f:
        json.dump(aggregate, f, indent=2)

    aggregate_plot = Path(output_cfg.get("aggregate_plot", output_base / "aggregate_summary.png"))
    if not aggregate_plot.is_absolute():
        aggregate_plot = (repo_root / aggregate_plot).resolve()

    cats_labels = [r["cat"] for r in summary_rows]
    cc_sel = [r["selected_cc_events"] for r in summary_rows]
    es_sel = [r["selected_es_events"] for r in summary_rows]
    build_summary_plot(aggregate_plot, cats_labels, cc_sel, es_sel, total_requested_cc, total_requested_es)

    report_cfg = batch_cfg.get("burst_direction_report", {})
    if report_cfg.get("enabled", True):
        use_emcee = bool(report_cfg.get("use_emcee", True))
        report_pdf = Path(report_cfg.get("output_pdf", output_base / "burst_direction_report.pdf"))
        if not report_pdf.is_absolute():
            report_pdf = (repo_root / report_pdf).resolve()
        report_json = Path(report_cfg.get("output_json", output_base / "burst_direction_report.json"))
        if not report_json.is_absolute():
            report_json = (repo_root / report_json).resolve()

        emcee_cfg = {
            "nwalkers": int(report_cfg.get("emcee_nwalkers", 64)),
            "nsteps": int(report_cfg.get("emcee_nsteps", 2000)),
            "discard": int(report_cfg.get("emcee_discard", 400)),
            "prior_kappa": float(report_cfg.get("emcee_prior_kappa", 25.0)),
            "likelihood_kappa": float(report_cfg.get("emcee_likelihood_kappa", 25.0)),
            "random_seed": int(report_cfg.get("random_seed", 42)),
        }

        print("\nBuilding burst-direction report...")
        report_payload = build_batch_report(
            runs_root=runs_dir,
            output_pdf=report_pdf,
            output_json=report_json,
            selection_mode=report_cfg.get("selection_mode", "predicted-es"),
            direction_mode=report_cfg.get("direction_mode", "reco"),
            min_energy_mev=float(report_cfg.get("min_energy_mev", 0.0)),
            use_emcee=use_emcee,
            emcee_cfg=emcee_cfg,
        )
        print(f"Burst report:      {report_pdf}")
        print(f"Burst report JSON: {report_json}")
        print(f"Burst report n:    {report_payload['n_bursts']}")

    print("\nBatch run complete")
    print(f"Processed cats: {len(summary_rows)}")
    print(f"Requested totals: CC={total_requested_cc}, ES={total_requested_es}")
    print(f"Selected totals:  CC={total_selected_cc}, ES={total_selected_es}")
    print(f"Totals match request: {aggregate['matches_requested_totals']}")
    print(f"Aggregate summary: {aggregate_json}")
    print(f"Aggregate plot:    {aggregate_plot}")


if __name__ == "__main__":
    main()
