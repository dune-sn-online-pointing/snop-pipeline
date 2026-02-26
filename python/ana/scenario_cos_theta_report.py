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
    reconstruct_burst_direction,
    select_electrons_from_run,
)


def _latest_pipeline_run(scenario_dir: Path):
    runs = sorted(scenario_dir.glob("pipeline_run_*"))
    if not runs:
        return None
    return runs[-1]


def _load_scenario_settings(scenario_dir: Path):
    cfg_path = scenario_dir / "config.json"
    if not cfg_path.exists():
        return None
    with open(cfg_path, "r") as f:
        cfg = json.load(f)
    return cfg.get("reporting")


def _load_metrics(run_dir: Path):
    metrics_path = run_dir / "metrics.json"
    if not metrics_path.exists():
        return {}
    with open(metrics_path, "r") as f:
        return json.load(f)


def _scenario_color(index):
    palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
    return palette[index % len(palette)]


def _format_q(value):
    if value is None or np.isnan(value):
        return "n/a"
    return f"{value:.2f}"


def build_report(scenarios_root: Path, output_pdf: Path, default_selection_mode: str, use_emcee: bool, emcee_cfg: dict):
    scenario_dirs = sorted([p for p in scenarios_root.iterdir() if p.is_dir() and p.name.startswith("scenario_")])
    if not scenario_dirs:
        raise RuntimeError(f"No scenario_* directories found in {scenarios_root}")

    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    report_rows = []

    for idx, scenario_dir in enumerate(scenario_dirs):
        latest_run = _latest_pipeline_run(scenario_dir)
        if latest_run is None:
            continue

        scenario_settings = _load_scenario_settings(scenario_dir)
        if not scenario_settings:
            continue

        selection_mode = scenario_settings.get("selection_mode", default_selection_mode)
        direction_mode = scenario_settings.get("direction_mode", "reco")
        min_energy_mev = float(scenario_settings.get("min_energy_mev", 0.0))
        scenario_label = scenario_settings.get("label", scenario_dir.name)

        selected = select_electrons_from_run(
            latest_run,
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

        theta_deg = reco["theta_samples_deg"]
        cos_theta = np.cos(np.radians(theta_deg)) if theta_deg.size > 0 else np.array([], dtype=np.float64)

        if theta_deg.size > 0:
            q50_theta = float(np.quantile(theta_deg, 0.50))
            q68_theta = float(np.quantile(theta_deg, 0.68))
            q68_cos = float(np.cos(np.radians(q68_theta)))
            forward_frac = float(np.mean(cos_theta > 0))
        else:
            q50_theta = float("nan")
            q68_theta = float("nan")
            q68_cos = float("nan")
            forward_frac = float("nan")

        metrics = _load_metrics(latest_run)
        ct_accuracy = metrics.get("steps", {}).get("channel_tagging", {}).get("performance", {}).get("accuracy")

        reco_dir = reco["reco_dir"]
        if reco_dir is None:
            cos_to_truth = float("nan")
        else:
            cos_to_truth = float(np.clip(np.dot(reco_dir, selected["true_burst_dir"]), -1.0, 1.0))

        report_rows.append(
            {
                "scenario": scenario_dir.name,
                "label": scenario_label,
                "run_dir": latest_run,
                "selection_mode": selection_mode,
                "direction_mode": direction_mode,
                "direction_mode_used": selected["direction_mode_used"],
                "min_energy_mev": min_energy_mev,
                "n_selected": selected["n_selected"],
                "aggregation_method": reco["method"],
                "acceptance_fraction": reco["acceptance_fraction"],
                "single_pass_theta_deg": reco["single_pass_theta_deg"],
                "omega68_deg": reco["omega68_deg"],
                "q50_theta_deg": q50_theta,
                "q68_theta_deg": q68_theta,
                "q68_cos": q68_cos,
                "forward_frac": forward_frac,
                "cos_to_truth": cos_to_truth,
                "ct_accuracy": ct_accuracy,
                "theta_deg": theta_deg,
                "cos_theta": cos_theta,
                "color": _scenario_color(idx),
            }
        )

    if not report_rows:
        raise RuntimeError("No valid scenario runs found to build report")

    q68_values = [row["q68_theta_deg"] for row in report_rows if not np.isnan(row["q68_theta_deg"])]
    best_q68 = float(np.nanmin(q68_values)) if q68_values else float("nan")

    with matplotlib.backends.backend_pdf.PdfPages(output_pdf) as pdf:
        fig = plt.figure(figsize=(11, 8.5))
        gs = fig.add_gridspec(2, 2, hspace=0.35, wspace=0.3)

        ax_title = fig.add_subplot(gs[0, :])
        ax_title.axis("off")
        ax_title.text(0.5, 0.98, "Scenario Burst Pointing Comparison", ha="center", va="top", fontsize=20, weight="bold")
        method_txt = "emcee" if use_emcee else "weighted-mean+bootstrap"
        ax_title.text(0.5, 0.87, f"Aggregation default: {method_txt}", ha="center", va="top", fontsize=11, style="italic")

        header = "Scenario                          N_e   Theta[deg]   Q68[deg]   cos(theta)   CT acc   Method"
        lines = [header, "-" * len(header)]
        for row in report_rows:
            acc_txt = "n/a" if row["ct_accuracy"] is None else f"{row['ct_accuracy']:.3f}"
            lines.append(
                f"{row['label']:<32} {row['n_selected']:>3d}   {_format_q(row['single_pass_theta_deg']):>10}   {_format_q(row['q68_theta_deg']):>8}   {_format_q(row['cos_to_truth']):>10}   {acc_txt:>6}   {row['aggregation_method']}"
            )
        if not np.isnan(best_q68):
            lines.append("")
            lines.append(f"Best Q68 among scenarios: {best_q68:.2f} deg")

        ax_title.text(0.02, 0.72, "\n".join(lines), ha="left", va="top", family="monospace", fontsize=9.5)

        ax_q68 = fig.add_subplot(gs[1, 0])
        names = [row["label"] for row in report_rows]
        q68_deg = [row["q68_theta_deg"] for row in report_rows]
        colors = [row["color"] for row in report_rows]
        bars = ax_q68.bar(range(len(report_rows)), q68_deg, color=colors, alpha=0.85, edgecolor="black")
        ax_q68.set_title("68% burst-angle quantile by scenario")
        ax_q68.set_ylabel("Q68(theta) [deg]")
        ax_q68.set_xticks(range(len(report_rows)))
        ax_q68.set_xticklabels(names, rotation=25, ha="right")
        ax_q68.grid(axis="y", alpha=0.25)
        if not np.isnan(best_q68):
            ax_q68.axhline(best_q68, linestyle="--", color="black", linewidth=1.8, label=f"Best = {best_q68:.2f} deg")
            ax_q68.legend(loc="best")
        for bar, value in zip(bars, q68_deg):
            if np.isnan(value):
                continue
            ax_q68.text(bar.get_x() + bar.get_width() / 2.0, value, f"{value:.1f}", ha="center", va="bottom", fontsize=9)

        ax_overlay = fig.add_subplot(gs[1, 1])
        for row in report_rows:
            if row["theta_deg"].size == 0:
                continue
            ax_overlay.hist(
                row["theta_deg"],
                bins=45,
                range=(0, 180),
                histtype="step",
                linewidth=2.0,
                color=row["color"],
                label=f"{row['label']} (Q68={row['q68_theta_deg']:.1f}°)",
            )
        ax_overlay.set_title("Burst-angle posterior overlays")
        ax_overlay.set_xlabel("theta [deg]")
        ax_overlay.set_ylabel("Counts")
        ax_overlay.grid(True, alpha=0.25)
        ax_overlay.legend(fontsize=8)

        fig.subplots_adjust(left=0.06, right=0.98, top=0.95, bottom=0.08, hspace=0.35, wspace=0.3)
        pdf.savefig(fig)
        plt.close(fig)

        for row in report_rows:
            fig = plt.figure(figsize=(11, 8.5))
            gs = fig.add_gridspec(2, 2, hspace=0.35, wspace=0.3)

            fig.suptitle(f"{row['label']} - detailed burst pointing report", fontsize=16, weight="bold")

            ax1 = fig.add_subplot(gs[0, :])
            theta = row["theta_deg"]
            if theta.size == 0:
                ax1.text(0.5, 0.5, "No selected entries for this scenario", ha="center", va="center", fontsize=14)
                ax1.axis("off")
            else:
                ax1.hist(theta, bins=50, range=(0, 180), alpha=0.75, color=row["color"], edgecolor="black")
                ax1.axvline(row["single_pass_theta_deg"], color="red", linestyle="--", linewidth=2,
                            label=f"Theta(all e-) = {row['single_pass_theta_deg']:.2f}°")
                ax1.axvline(row["q68_theta_deg"], color="orange", linestyle="--", linewidth=2,
                            label=f"Q68 = {row['q68_theta_deg']:.2f}°")
                ax1.set_xlabel("theta [deg]")
                ax1.set_ylabel("Counts")
                ax1.set_title("Burst-angle posterior")
                ax1.grid(True, alpha=0.25)
                ax1.legend(loc="best")

            ax2 = fig.add_subplot(gs[1, 0])
            cos_theta = row["cos_theta"]
            if cos_theta.size == 0:
                ax2.text(0.5, 0.5, "No selected entries", ha="center", va="center")
                ax2.axis("off")
            else:
                ax2.hist(cos_theta, bins=50, range=(-1, 1), alpha=0.8, color="#4c78a8", edgecolor="black")
                ax2.axvline(0.0, color="black", linestyle=":", linewidth=1.5)
                ax2.axvline(row["q68_cos"], color="red", linestyle="--", linewidth=2,
                            label=f"cos(Q68) = {row['q68_cos']:.4f}")
                ax2.set_xlim(-1, 1)
                ax2.set_xlabel("cos(theta)")
                ax2.set_ylabel("Counts")
                ax2.set_title("Burst-direction cosine posterior")
                ax2.grid(True, alpha=0.25)
                ax2.legend(loc="best")

            ax3 = fig.add_subplot(gs[1, 1])
            ax3.axis("off")
            acc_txt = "n/a" if row["ct_accuracy"] is None else f"{row['ct_accuracy']:.3f}"
            accept_txt = "n/a" if np.isnan(row["acceptance_fraction"]) else f"{100.0 * row['acceptance_fraction']:.1f}%"
            summary_rows = [
                ["Scenario", row["label"]],
                ["Selection", row["selection_mode"]],
                ["Direction (requested)", row["direction_mode"]],
                ["Direction (used)", row["direction_mode_used"]],
                ["Energy cut [MeV]", f"{row['min_energy_mev']:.1f}"],
                ["Selected electrons", str(row["n_selected"])],
                ["Aggregation", row["aggregation_method"]],
                ["Acceptance", accept_txt],
                ["Theta(all e-) [deg]", _format_q(row["single_pass_theta_deg"])],
                ["Q68(theta) [deg]", _format_q(row["q68_theta_deg"])],
                ["cos(theta all e-)", _format_q(row["cos_to_truth"])],
                ["CT accuracy", acc_txt],
            ]
            table = ax3.table(
                cellText=summary_rows,
                colLabels=["Metric", "Value"],
                colLoc="left",
                cellLoc="left",
                bbox=[0.02, 0.05, 0.96, 0.9],
            )
            table.auto_set_font_size(False)
            table.set_fontsize(9)
            table[(0, 0)].set_facecolor("#d9e3f0")
            table[(0, 1)].set_facecolor("#d9e3f0")
            for ridx in range(1, len(summary_rows) + 1):
                color = "#f7f7f7" if ridx % 2 == 0 else "#ffffff"
                table[(ridx, 0)].set_facecolor(color)
                table[(ridx, 1)].set_facecolor(color)

            fig.subplots_adjust(left=0.06, right=0.98, top=0.92, bottom=0.08, hspace=0.35, wspace=0.3)
            pdf.savefig(fig)
            plt.close(fig)

    summary_json = output_pdf.with_suffix(".json")
    with open(summary_json, "w") as f:
        json.dump(
            {
                "aggregation_default": "emcee" if use_emcee else "weighted-mean+bootstrap",
                "best_q68_theta_deg": best_q68,
                "scenarios": [
                    {
                        "scenario": row["scenario"],
                        "label": row["label"],
                        "run_dir": str(row["run_dir"]),
                        "n_selected": row["n_selected"],
                        "selection_mode": row["selection_mode"],
                        "direction_mode": row["direction_mode"],
                        "direction_mode_used": row["direction_mode_used"],
                        "aggregation_method": row["aggregation_method"],
                        "acceptance_fraction": row["acceptance_fraction"],
                        "min_energy_mev": row["min_energy_mev"],
                        "single_pass_theta_deg": row["single_pass_theta_deg"],
                        "q50_theta_deg": row["q50_theta_deg"],
                        "q68_theta_deg": row["q68_theta_deg"],
                        "q68_cos": row["q68_cos"],
                        "cos_to_truth": row["cos_to_truth"],
                        "forward_frac": row["forward_frac"],
                        "ct_accuracy": row["ct_accuracy"],
                    }
                    for row in report_rows
                ],
            },
            f,
            indent=2,
        )

    return output_pdf, summary_json


def main():
    parser = argparse.ArgumentParser(description="Build scenario PDF report with burst-level pointing aggregation")
    parser.add_argument("--scenarios-root", default="output/test_pipeline_scenarios", help="Root folder containing scenario_* directories")
    parser.add_argument("--output-pdf", default="output/test_pipeline_scenarios/scenario_cos_theta_report.pdf", help="Output PDF path")
    parser.add_argument(
        "--selection-mode",
        choices=["predicted-es", "true-es", "all", "weighted-ct"],
        default="predicted-es",
        help="Default fallback selection mode when scenario config has no reporting.selection_mode",
    )
    parser.add_argument("--no-emcee", action="store_true", help="Disable emcee and use weighted mean + bootstrap")
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

    output_pdf, summary_json = build_report(
        scenarios_root=Path(args.scenarios_root),
        output_pdf=Path(args.output_pdf),
        default_selection_mode=args.selection_mode,
        use_emcee=(not args.no_emcee),
        emcee_cfg=emcee_cfg,
    )

    print(f"Saved report PDF: {output_pdf}")
    print(f"Saved report JSON: {summary_json}")


if __name__ == "__main__":
    main()
