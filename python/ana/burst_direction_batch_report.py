#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path

import matplotlib.backends.backend_pdf
import matplotlib.pyplot as plt
import numpy as np

python_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(python_root))

from ana.burst_direction import (
    angular_error_deg,
    direction_to_angles,
    reconstruct_burst_direction,
    select_electrons_from_run,
)


def _latest_run(cat_dir: Path):
    runs = sorted(cat_dir.glob("pipeline_run_*"))
    return runs[-1] if runs else None


def _load_metrics(run_dir: Path):
    metrics_path = run_dir / "metrics.json"
    if not metrics_path.exists():
        return {}
    with open(metrics_path, "r") as f:
        return json.load(f)


def _format_value(value, fmt="{:.2f}"):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "n/a"
    return fmt.format(value)


def _cat_rows(runs_root: Path):
    cat_dirs = sorted([p for p in runs_root.iterdir() if p.is_dir()])
    for cat_dir in cat_dirs:
        run = _latest_run(cat_dir)
        if run is None:
            continue
        yield cat_dir.name, run


def build_batch_report(
    runs_root: Path,
    output_pdf: Path,
    output_json: Path,
    selection_mode: str,
    direction_mode: str,
    min_energy_mev: float,
    use_emcee: bool,
    emcee_cfg: dict,
):
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)

    rows = []

    for cat_name, run_dir in _cat_rows(runs_root):
        selected = select_electrons_from_run(
            run_dir,
            selection_mode=selection_mode,
            direction_mode=direction_mode,
            min_energy_mev=min_energy_mev,
        )

        reco = reconstruct_burst_direction(
            selected_dirs=selected["selected_dirs"],
            selected_weights=selected["selected_weights"],
            true_burst_dir=selected["true_burst_dir"],
            use_emcee=use_emcee,
            emcee_cfg=emcee_cfg,
        )

        reco_dir = reco["reco_dir"]
        metrics = _load_metrics(run_dir)
        ct_acc = metrics.get("steps", {}).get("channel_tagging", {}).get("performance", {}).get("accuracy")

        if reco_dir is None:
            err_deg = float("nan")
            cos_theta = float("nan")
            theta_deg = float("nan")
            phi_deg = float("nan")
        else:
            err_deg = angular_error_deg(reco_dir, selected["true_burst_dir"])
            cos_theta = float(np.cos(np.radians(err_deg)))
            theta, phi = direction_to_angles(reco_dir)
            theta_deg = float(np.degrees(theta))
            phi_deg = float(np.degrees(phi))

        rows.append(
            {
                "cat": cat_name,
                "run_dir": str(run_dir),
                "n_selected": int(selected["n_selected"]),
                "selection_mode": selection_mode,
                "direction_mode": direction_mode,
                "direction_mode_used": selected["direction_mode_used"],
                "aggregation_method": reco["method"],
                "acceptance_fraction": reco["acceptance_fraction"],
                "angular_error_deg": err_deg,
                "cos_theta": cos_theta,
                "omega68_deg": reco["omega68_deg"],
                "theta_deg": theta_deg,
                "phi_deg": phi_deg,
                "ct_accuracy": ct_acc,
            }
        )

    if not rows:
        raise RuntimeError(f"No valid burst runs found under {runs_root}")

    valid_errors = [r["angular_error_deg"] for r in rows if np.isfinite(r["angular_error_deg"])]
    median_err = float(np.median(valid_errors)) if valid_errors else float("nan")
    q68_err = float(np.quantile(valid_errors, 0.68)) if valid_errors else float("nan")

    with matplotlib.backends.backend_pdf.PdfPages(output_pdf) as pdf:
        fig, (ax1, ax2) = plt.subplots(
            2,
            1,
            figsize=(11, 8.5),
            gridspec_kw={"height_ratios": [1.0, 1.1]},
        )

        cat_names = [r["cat"] for r in rows]
        errors = [r["angular_error_deg"] for r in rows]
        omega68 = [r["omega68_deg"] for r in rows]

        x = np.arange(len(cat_names))
        ax1.bar(x, errors, color="#4c78a8", alpha=0.85, edgecolor="black", label="Angular error")
        ax1.scatter(x, omega68, c="#f58518", s=25, label="Posterior Q68", zorder=3)
        if np.isfinite(median_err):
            ax1.axhline(median_err, linestyle="--", color="black", linewidth=1.5, label=f"Median={median_err:.2f}°")
        if np.isfinite(q68_err):
            ax1.axhline(q68_err, linestyle=":", color="black", linewidth=1.5, label=f"Q68={q68_err:.2f}°")
        ax1.set_ylabel("deg")
        ax1.set_title("Per-burst reconstructed direction error")
        ax1.grid(True, axis="y", alpha=0.25)
        ax1.legend(loc="best")

        if len(cat_names) <= 30:
            ax1.set_xticks(x)
            ax1.set_xticklabels(cat_names, rotation=25, ha="right")
        else:
            ax1.set_xticks([])

        ax2.axis("off")
        header = [
            "CAT",
            "N_e",
            "theta_err",
            "omega68",
            "cos(theta)",
            "CT acc",
            "Method",
        ]
        table_data = []
        for row in rows[:40]:
            ct_txt = "n/a" if row["ct_accuracy"] is None else f"{row['ct_accuracy']:.3f}"
            table_data.append(
                [
                    row["cat"],
                    str(row["n_selected"]),
                    _format_value(row["angular_error_deg"]),
                    _format_value(row["omega68_deg"]),
                    _format_value(row["cos_theta"], "{:.3f}"),
                    ct_txt,
                    row["aggregation_method"],
                ]
            )

        title = f"Burst Direction Summary ({'emcee' if use_emcee else 'weighted mean'})"
        ax2.text(0.0, 1.02, title, fontsize=12, weight="bold", transform=ax2.transAxes)
        table = ax2.table(
            cellText=table_data,
            colLabels=header,
            colLoc="left",
            cellLoc="left",
            bbox=[0.0, 0.0, 1.0, 0.95],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8.5)

        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    payload = {
        "aggregation_default": "emcee" if use_emcee else "weighted-mean+bootstrap",
        "selection_mode": selection_mode,
        "direction_mode": direction_mode,
        "min_energy_mev": float(min_energy_mev),
        "n_bursts": len(rows),
        "median_error_deg": median_err,
        "q68_error_deg": q68_err,
        "bursts": rows,
    }
    with open(output_json, "w") as f:
        json.dump(payload, f, indent=2)

    return payload


def main():
    parser = argparse.ArgumentParser(description="Build per-burst direction report from pipeline batch runs")
    parser.add_argument("--runs-root", required=True, help="Folder containing per-cat run directories")
    parser.add_argument("--output-pdf", required=True, help="Output PDF path")
    parser.add_argument("--output-json", required=True, help="Output JSON path")
    parser.add_argument("--selection-mode", choices=["predicted-es", "true-es", "all", "weighted-ct"], default="predicted-es")
    parser.add_argument("--direction-mode", choices=["true", "reco"], default="reco")
    parser.add_argument("--min-energy-mev", type=float, default=0.0)
    parser.add_argument("--no-emcee", action="store_true")
    parser.add_argument("--emcee-nwalkers", type=int, default=64)
    parser.add_argument("--emcee-nsteps", type=int, default=2000)
    parser.add_argument("--emcee-discard", type=int, default=400)
    parser.add_argument("--emcee-prior-kappa", type=float, default=25.0)
    parser.add_argument("--emcee-likelihood-kappa", type=float, default=25.0)
    parser.add_argument("--random-seed", type=int, default=42)
    args = parser.parse_args()

    emcee_cfg = {
        "nwalkers": args.emcee_nwalkers,
        "nsteps": args.emcee_nsteps,
        "discard": args.emcee_discard,
        "prior_kappa": args.emcee_prior_kappa,
        "likelihood_kappa": args.emcee_likelihood_kappa,
        "random_seed": args.random_seed,
    }

    build_batch_report(
        runs_root=Path(args.runs_root),
        output_pdf=Path(args.output_pdf),
        output_json=Path(args.output_json),
        selection_mode=args.selection_mode,
        direction_mode=args.direction_mode,
        min_energy_mev=args.min_energy_mev,
        use_emcee=(not args.no_emcee),
        emcee_cfg=emcee_cfg,
    )


if __name__ == "__main__":
    main()
