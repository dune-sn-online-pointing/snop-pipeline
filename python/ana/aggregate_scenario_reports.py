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

    for cat_name, payload in cat_payloads:
        for row in payload.get("scenarios", []):
            label = row.get("label", row.get("scenario", "unknown"))
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
            entry["n_selected"].append(int(row.get("n_selected", 0)))
            entry["cat_names"].append(cat_name)

    summary = {}
    for label, vals in scenario_metrics.items():
        q68 = np.asarray(vals["q68"], dtype=float)
        theta = np.asarray(vals["theta"], dtype=float)
        cosv = np.asarray(vals["cos"], dtype=float)
        ct = np.asarray(vals["ct_accuracy"], dtype=float)
        nsel = np.asarray(vals["n_selected"], dtype=int)

        summary[label] = {
            "n_cats": int(len(vals["cat_names"])),
            "q68_median_deg": float(np.nanmedian(q68)) if q68.size else float("nan"),
            "q68_mean_deg": float(np.nanmean(q68)) if q68.size else float("nan"),
            "theta_median_deg": float(np.nanmedian(theta)) if theta.size else float("nan"),
            "theta_mean_deg": float(np.nanmean(theta)) if theta.size else float("nan"),
            "cos_median": float(np.nanmedian(cosv)) if cosv.size else float("nan"),
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
