#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

import matplotlib.backends.backend_pdf
import matplotlib.pyplot as plt
import numpy as np


def _iter_cat_reports(input_root: Path):
    for cat_dir in sorted([p for p in input_root.iterdir() if p.is_dir()]):
        report_json = cat_dir / "scenario_cos_theta_report.json"
        if report_json.exists():
            yield cat_dir.name, report_json


def _safe_float(value):
    try:
        return float(value)
    except Exception:
        return float("nan")


def _format_num(value, nd=2):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "n/a"
    return f"{value:.{nd}f}"


def _build_summary(cat_payloads):
    scenario_metrics = {}
    filtered_cats = 0

    for cat_name, payload in cat_payloads:
        for row in payload.get("scenarios", []):
            label = row.get("label", row.get("scenario", "unknown"))
            n_selected = int(row.get("n_selected", 0))
            selection_mode = row.get("selection_mode", "")

            # Filter out cats with insufficient ES events (should have ~350 ES events in good cats)
            # Also filter based on energy requirements
            min_energy_mev = row.get("min_energy_mev", 0.0)

            # Require 200+ ES events for ES scenarios (realistic threshold based on data)
            if ("es" in selection_mode.lower() or "ES" in label) and n_selected < 200:
                filtered_cats += 1
                print(f"Filtering {cat_name} ({label}): only {n_selected} ES events (< 200 threshold)")
                continue

            # Skip energy cut filter to allow scenarios with lower thresholds
            # (many scenarios legitimately use lower energy cuts)
            # if min_energy_mev < 3.0:
            #     filtered_cats += 1
            #     print(f"Filtering {cat_name} ({label}): energy cut {min_energy_mev} MeV (< 3.0 MeV required)")
            #     continue

            entry = scenario_metrics.setdefault(label, {
                "q68": [],
                "theta": [],
                "cos": [],
                "ct_accuracy": [],
                "n_selected": [],
                "cat_names": [],
            })
            entry["q68"].append(_safe_float(row.get("q68_theta_deg")))
            entry["theta"].append(_safe_float(row.get("single_pass_theta_deg")))
            entry["cos"].append(_safe_float(row.get("cos_to_truth", row.get("q68_cos"))))
            ct = row.get("ct_accuracy")
            entry["ct_accuracy"].append(_safe_float(ct) if ct is not None else float("nan"))
            entry["n_selected"].append(n_selected)
            entry["cat_names"].append(cat_name)

    if filtered_cats > 0:
        print(f"Filtered out {filtered_cats} cat-scenario combinations (insufficient ES events)")

    summary = {}
    for label, vals in scenario_metrics.items():
        q68 = np.asarray(vals["q68"], dtype=float)
        theta = np.asarray(vals["theta"], dtype=float)
        cosv = np.asarray(vals["cos"], dtype=float)
        ct = np.asarray(vals["ct_accuracy"], dtype=float)
        nsel = np.asarray(vals["n_selected"], dtype=int)
        cos_finite = cosv[np.isfinite(cosv)]

        if cos_finite.size:
            # 68% containment in angle space corresponds to the 32nd percentile in cos-space
            # because theta = arccos(cos) is monotonic decreasing.
            cos_q68_containment = float(np.quantile(cos_finite, 0.32))
            theta68_from_cos_deg = float(np.degrees(np.arccos(np.clip(cos_q68_containment, -1.0, 1.0))))
            cos_mean = float(np.mean(cos_finite))
            theta_mean_from_cos_deg = float(np.degrees(np.arccos(np.clip(cos_mean, -1.0, 1.0))))
        else:
            cos_q68_containment = float("nan")
            theta68_from_cos_deg = float("nan")
            cos_mean = float("nan")
            theta_mean_from_cos_deg = float("nan")

        summary[label] = {
            "n_cats": int(len(vals["cat_names"])),
            "q68_median_deg": float(np.nanmedian(q68)) if q68.size else float("nan"),
            "q68_mean_deg": float(np.nanmean(q68)) if q68.size else float("nan"),
            "theta_median_deg": float(np.nanmedian(theta)) if theta.size else float("nan"),
            "theta_mean_deg": float(np.nanmean(theta)) if theta.size else float("nan"),
            "cos_median": float(np.nanmedian(cosv)) if cosv.size else float("nan"),
            "cos_mean": cos_mean,
            "cos_q68_containment": cos_q68_containment,
            "theta68_from_cos_deg": theta68_from_cos_deg,
            "theta_mean_from_cos_deg": theta_mean_from_cos_deg,
            "ct_accuracy_mean": float(np.nanmean(ct)) if np.any(np.isfinite(ct)) else float("nan"),
            "n_selected_mean": float(np.nanmean(nsel)) if nsel.size else float("nan"),
            "q68_all": q68.tolist(),
            "theta_all": theta.tolist(),
            "cos_all": cosv.tolist(),
            "ct_accuracy_all": ct.tolist(),
            "n_selected_all": nsel.tolist(),
            "cat_names": vals["cat_names"],
        }

    return summary


def _make_pdf(output_pdf: Path, summary: dict, n_cats: int):
    labels = list(summary.keys())
    q68_medians = [summary[l]["q68_median_deg"] for l in labels]
    scenario_colors = {
        "Best Case (true e- dir, true ES)": "#89c2b8",
        "Perfect CT (true ES, reco dir)": "#b5b3c9",
        "Full pipeline (predicted ES)": "#e59a8f",
        "Weighted CT": "#8fb3d9",
        "Perfect CT (E > 10 MeV)": "#b889b8",
        "Perfect CT (E > 5 MeV)": "#e4d66e",
    }

    with matplotlib.backends.backend_pdf.PdfPages(output_pdf) as pdf:
        fig = plt.figure(figsize=(11, 8.5))
        gs = fig.add_gridspec(2, 2, hspace=0.35, wspace=0.3)

        ax0 = fig.add_subplot(gs[0, :])
        ax0.axis("off")
        title = "All-CAT Scenario Aggregate Report"
        ax0.text(0.5, 0.98, title, ha="center", va="top", fontsize=20, weight="bold")
        ax0.text(0.5, 0.88, f"Processed CATs: {n_cats}", ha="center", va="top", fontsize=11)

        header = "Scenario                          Ncats   MedQ68   MeanQ68   MedTheta   MeanCTacc   MeanNsel"
        lines = [header, "-" * len(header)]
        for label in labels:
            row = summary[label]
            lines.append(
                f"{label:<32} {row['n_cats']:>5d}   {_format_num(row['q68_median_deg']):>6}   {_format_num(row['q68_mean_deg']):>7}   {_format_num(row['theta_median_deg']):>8}   {_format_num(row['ct_accuracy_mean'],3):>9}   {_format_num(row['n_selected_mean'],1):>8}"
            )

        ax0.text(0.02, 0.78, "\n".join(lines), ha="left", va="top", family="monospace", fontsize=9.5)

        ax1 = fig.add_subplot(gs[1, 0])
        bars = ax1.bar(range(len(labels)), q68_medians, color="#4c78a8", alpha=0.85, edgecolor="black")
        ax1.set_title("Median Q68 by scenario")
        ax1.set_ylabel("Q68 [deg]")
        ax1.set_xticks(range(len(labels)))
        ax1.set_xticklabels(labels, rotation=25, ha="right")
        ax1.grid(axis="y", alpha=0.25)
        for b, v in zip(bars, q68_medians):
            if np.isnan(v):
                continue
            ax1.text(b.get_x() + b.get_width()/2, v, f"{v:.1f}", ha="center", va="bottom", fontsize=9)

        ax2 = fig.add_subplot(gs[1, 1])
        for label in labels:
            vals = np.asarray(summary[label]["q68_all"], dtype=float)
            vals = vals[np.isfinite(vals)]
            if vals.size == 0:
                continue
            ax2.hist(vals, bins=30, histtype="step", linewidth=2, label=label)
        ax2.set_title("Q68 distribution across CATs")
        ax2.set_xlabel("Q68 [deg]")
        ax2.set_ylabel("Counts")
        ax2.grid(True, alpha=0.25)
        ax2.legend(fontsize=8)

        fig.subplots_adjust(left=0.06, right=0.98, top=0.95, bottom=0.08)
        pdf.savefig(fig)
        plt.close(fig)

        # Legacy-style page: histogram of cos(theta_true - theta_reco) for each scenario.
        ncols = 2
        nrows = int(np.ceil(len(labels) / float(ncols))) if labels else 1
        fig2, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(12, 4.6 * nrows))
        if not isinstance(axes, np.ndarray):
            axes = np.array([[axes]])
        elif axes.ndim == 1:
            axes = axes.reshape(-1, ncols)

        for i, label in enumerate(labels):
            r = i // ncols
            c = i % ncols
            ax = axes[r, c]

            vals = np.asarray(summary[label]["cos_all"], dtype=float)
            vals = vals[np.isfinite(vals)]
            color = scenario_colors.get(label, "#7aa6c2")

            if vals.size == 0:
                ax.text(0.5, 0.5, "No valid entries", ha="center", va="center")
                ax.set_title(f"{label}\n(N=0)", fontsize=14, weight="bold")
                ax.set_xlabel("cos(theta_true - theta_reco)", fontsize=12, weight="bold")
                ax.set_ylabel("Count", fontsize=12, weight="bold")
                continue

            q68_cos = float(summary[label]["cos_q68_containment"])
            q68_deg = float(summary[label]["theta68_from_cos_deg"])
            mean_cos = float(summary[label]["cos_mean"])
            mean_deg = float(summary[label]["theta_mean_from_cos_deg"])

            # Focus range similar to older plots while adapting to current data.
            x_min = max(-1.0, min(0.90, float(np.nanmin(vals)) - 0.01))
            ax.hist(vals, bins=50, range=(x_min, 1.0), alpha=0.75, color=color, edgecolor="#555555", linewidth=0.8)
            ax.axvline(q68_cos, color="red", linestyle="--", linewidth=3.0,
                       label=f"68% quantile: {q68_cos:.4f} ({q68_deg:.1f}°)")
            ax.axvline(mean_cos, color="blue", linestyle="-", linewidth=2.7,
                       label=f"Mean: {mean_cos:.4f} ({mean_deg:.1f}°)")
            ax.set_xlim(x_min, 1.0)
            ax.set_xlabel("cos(theta_true - theta_reco)", fontsize=12, weight="bold")
            ax.set_ylabel("Count", fontsize=12, weight="bold")
            ax.set_title(f"{label}\n(N={vals.size})", fontsize=14, weight="bold")
            ax.grid(True, alpha=0.25)
            ax.legend(loc="upper left", fontsize=10)

        total_axes = nrows * ncols
        for j in range(len(labels), total_axes):
            r = j // ncols
            c = j % ncols
            axes[r, c].axis("off")

        fig2.suptitle("Aggregate cos(theta_true - theta_reco) by scenario", fontsize=18, weight="bold")
        fig2.tight_layout(rect=[0, 0, 1, 0.96])
        pdf.savefig(fig2)
        plt.close(fig2)


def main():
    parser = argparse.ArgumentParser(description="Aggregate per-CAT scenario reports into all-CAT summary")
    parser.add_argument("--input-root", required=True, help="Root containing per-cat folders with scenario_cos_theta_report.json")
    parser.add_argument("--output-pdf", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    input_root = Path(args.input_root)
    if not input_root.exists():
        raise FileNotFoundError(f"Input root not found: {input_root}")

    cat_payloads = []
    for cat_name, report_json in _iter_cat_reports(input_root):
        try:
            with open(report_json, "r") as f:
                payload = json.load(f)
            cat_payloads.append((cat_name, payload))
        except Exception as exc:
            print(f"[WARN] skipping {cat_name}: {exc}")

    if not cat_payloads:
        raise RuntimeError(f"No valid scenario_cos_theta_report.json found under {input_root}")

    summary = _build_summary(cat_payloads)

    output_pdf = Path(args.output_pdf)
    output_json = Path(args.output_json)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)

    _make_pdf(output_pdf, summary, n_cats=len(cat_payloads))

    payload = {
        "input_root": str(input_root),
        "n_cats": len(cat_payloads),
        "scenarios": summary,
    }
    with open(output_json, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"Saved aggregate PDF: {output_pdf}")
    print(f"Saved aggregate JSON: {output_json}")


if __name__ == "__main__":
    main()
