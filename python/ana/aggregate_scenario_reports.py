#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

import matplotlib.backends.backend_pdf
import matplotlib.pyplot as plt
import numpy as np


# Per-mode minimum n_selected thresholds.
# true-es / true-es+energy: 200 (raw ES after energy cut is a data-quality signal).
# predicted-es / weighted-ct: 100 (CT threshold 0.8 naturally reduces yield; a lower
#   bar still rejects genuinely empty runs without discarding most CT-enabled CATs).
_MIN_SELECTED = {
    "true-es": 200,
    "predicted-es": 100,
    "weighted-ct": 100,
}
_MIN_SELECTED_DEFAULT = 100

SCENARIO_COLORS = {
    "Best case (true ES, true dir)":        "#89c2b8",
    "Perfect CT (true ES, reco dir)":       "#b5b3c9",
    "Full pipeline (predicted ES)":         "#e59a8f",
    "Weighted CT (predicted ES weights)":   "#8fb3d9",
    "Perfect CT (E > 10 MeV)":             "#b889b8",
    "Perfect CT (E > 5 MeV)":              "#e4d66e",
}
_FALLBACK_COLORS = plt.cm.Set2(np.linspace(0, 1, 8))


def _color(label, idx):
    return SCENARIO_COLORS.get(label, _FALLBACK_COLORS[idx % len(_FALLBACK_COLORS)])


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

            threshold = _MIN_SELECTED.get(selection_mode, _MIN_SELECTED_DEFAULT)
            if n_selected < threshold:
                filtered_cats += 1
                print(f"Filtering {cat_name} ({label}): only {n_selected} events (< {threshold} threshold for {selection_mode})")
                continue

            entry = scenario_metrics.setdefault(label, {
                "q68": [],
                "theta": [],
                "cos": [],
                "ct_accuracy": [],
                "n_selected": [],
                "cat_names": [],
                "selection_mode": selection_mode,
            })
            entry["q68"].append(_safe_float(row.get("q68_theta_deg")))
            entry["theta"].append(_safe_float(row.get("single_pass_theta_deg")))
            entry["cos"].append(_safe_float(row.get("cos_to_truth", row.get("q68_cos"))))
            ct = row.get("ct_accuracy")
            entry["ct_accuracy"].append(_safe_float(ct) if ct is not None else float("nan"))
            entry["n_selected"].append(n_selected)
            entry["cat_names"].append(cat_name)

    if filtered_cats > 0:
        print(f"Filtered out {filtered_cats} cat-scenario combinations (insufficient events)")

    summary = {}
    for label, vals in scenario_metrics.items():
        q68 = np.asarray(vals["q68"], dtype=float)
        theta = np.asarray(vals["theta"], dtype=float)
        cosv = np.asarray(vals["cos"], dtype=float)
        ct = np.asarray(vals["ct_accuracy"], dtype=float)
        nsel = np.asarray(vals["n_selected"], dtype=int)
        cos_finite = cosv[np.isfinite(cosv)]
        q68_finite = q68[np.isfinite(q68)]

        if cos_finite.size:
            cos_q68_containment = float(np.quantile(cos_finite, 0.32))
            theta68_from_cos_deg = float(np.degrees(np.arccos(np.clip(cos_q68_containment, -1.0, 1.0))))
            cos_mean = float(np.mean(cos_finite))
            theta_mean_from_cos_deg = float(np.degrees(np.arccos(np.clip(cos_mean, -1.0, 1.0))))
        else:
            cos_q68_containment = theta68_from_cos_deg = cos_mean = theta_mean_from_cos_deg = float("nan")

        summary[label] = {
            "selection_mode": vals["selection_mode"],
            "n_cats": int(len(vals["cat_names"])),
            "q68_median_deg": float(np.nanmedian(q68)) if q68_finite.size else float("nan"),
            "q68_mean_deg": float(np.nanmean(q68)) if q68_finite.size else float("nan"),
            "q68_std_deg": float(np.nanstd(q68)) if q68_finite.size else float("nan"),
            "theta_median_deg": float(np.nanmedian(theta)) if theta.size else float("nan"),
            "theta_mean_deg": float(np.nanmean(theta)) if theta.size else float("nan"),
            "cos_median": float(np.nanmedian(cosv)) if cosv.size else float("nan"),
            "cos_mean": cos_mean,
            "cos_q68_containment": cos_q68_containment,
            "theta68_from_cos_deg": theta68_from_cos_deg,
            "theta_mean_from_cos_deg": theta_mean_from_cos_deg,
            "ct_accuracy_mean": float(np.nanmean(ct)) if np.any(np.isfinite(ct)) else float("nan"),
            "n_selected_mean": float(np.nanmean(nsel)) if nsel.size else float("nan"),
            "n_selected_std": float(np.nanstd(nsel)) if nsel.size else float("nan"),
            "q68_all": q68.tolist(),
            "theta_all": theta.tolist(),
            "cos_all": cosv.tolist(),
            "ct_accuracy_all": ct.tolist(),
            "n_selected_all": nsel.tolist(),
            "cat_names": vals["cat_names"],
        }

    return summary


# ---------------------------------------------------------------------------
# Page 1: summary table + Q68 bar chart + Q68 distribution histogram
# ---------------------------------------------------------------------------

def _page_summary(pdf, summary, n_cats):
    labels = list(summary.keys())
    q68_vals = [summary[l]["theta68_from_cos_deg"] for l in labels]

    fig = plt.figure(figsize=(13, 9))
    gs = fig.add_gridspec(2, 2, hspace=0.4, wspace=0.3)

    ax0 = fig.add_subplot(gs[0, :])
    ax0.axis("off")
    ax0.text(0.5, 0.98, "All-CAT Scenario Aggregate Report",
             ha="center", va="top", fontsize=18, weight="bold")
    ax0.text(0.5, 0.88, f"Processed CATs: {n_cats}",
             ha="center", va="top", fontsize=11)

    header = "Scenario                          Ncats   Q68(cos)   Mean(cos)   MedQ68(MCMC)   MeanCTacc   MeanNsel"
    lines = [header, "-" * len(header)]
    for label in labels:
        row = summary[label]
        lines.append(
            f"{label:<32} {row['n_cats']:>5d}   {_format_num(row['theta68_from_cos_deg']):>8}"
            f"   {_format_num(row['theta_mean_from_cos_deg']):>9}   {_format_num(row['q68_median_deg']):>12}"
            f"   {_format_num(row['ct_accuracy_mean'], 3):>9}   {_format_num(row['n_selected_mean'], 1):>8}"
        )
    ax0.text(0.02, 0.78, "\n".join(lines), ha="left", va="top",
             family="monospace", fontsize=9)

    ax1 = fig.add_subplot(gs[1, 0])
    colors = [_color(l, i) for i, l in enumerate(labels)]
    bars = ax1.bar(range(len(labels)), q68_vals, color=colors, alpha=0.85, edgecolor="black")
    ax1.set_title("Q68 from cos distribution by scenario")
    ax1.set_ylabel("Q68 [deg]")
    ax1.set_xticks(range(len(labels)))
    ax1.set_xticklabels(labels, rotation=28, ha="right", fontsize=8)
    ax1.grid(axis="y", alpha=0.25)
    for b, v in zip(bars, q68_vals):
        if np.isnan(v):
            continue
        ax1.text(b.get_x() + b.get_width() / 2, v + 0.3, f"{v:.1f}",
                 ha="center", va="bottom", fontsize=8)

    ax2 = fig.add_subplot(gs[1, 1])
    for i, label in enumerate(labels):
        vals = np.asarray(summary[label]["q68_all"], dtype=float)
        vals = vals[np.isfinite(vals)]
        if vals.size == 0:
            continue
        ax2.hist(vals, bins=30, histtype="step", linewidth=2,
                 color=_color(label, i), label=label)
    ax2.set_title("Q68(MCMC) distribution across CATs")
    ax2.set_xlabel("Q68 [deg]")
    ax2.set_ylabel("Counts")
    ax2.grid(True, alpha=0.25)
    ax2.legend(fontsize=7)

    fig.subplots_adjust(left=0.06, right=0.98, top=0.96, bottom=0.08)
    pdf.savefig(fig)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Page 2: per-scenario cos distribution (adaptive x range)
# ---------------------------------------------------------------------------

def _page_cos_distributions(pdf, summary, title_suffix="", x_range=None):
    labels = list(summary.keys())
    ncols = 2
    nrows = int(np.ceil(len(labels) / float(ncols))) if labels else 1
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(13, 4.8 * nrows))
    if not isinstance(axes, np.ndarray):
        axes = np.array([[axes]])
    elif axes.ndim == 1:
        axes = axes.reshape(-1, ncols)

    for i, label in enumerate(labels):
        r, c = divmod(i, ncols)
        ax = axes[r, c]
        vals = np.asarray(summary[label]["cos_all"], dtype=float)
        vals = vals[np.isfinite(vals)]
        color = _color(label, i)

        if vals.size == 0:
            ax.text(0.5, 0.5, "No valid entries", ha="center", va="center")
            ax.set_title(f"{label}\n(N=0)", fontsize=13, weight="bold")
            continue

        q68_cos = float(summary[label]["cos_q68_containment"])
        q68_deg = float(summary[label]["theta68_from_cos_deg"])
        mean_cos = float(summary[label]["cos_mean"])
        mean_deg = float(summary[label]["theta_mean_from_cos_deg"])

        if x_range is not None:
            xmin, xmax = x_range
        else:
            xmin = max(-1.0, float(np.nanmin(vals)) - 0.01)
            xmax = 1.0

        ax.hist(vals, bins=50, range=(xmin, xmax), alpha=0.75,
                color=color, edgecolor="#555555", linewidth=0.8)
        if xmin <= q68_cos <= xmax:
            ax.axvline(q68_cos, color="red", linestyle="--", linewidth=2.5,
                       label=f"68% quantile: {q68_cos:.4f} ({q68_deg:.1f}°)")
        if xmin <= mean_cos <= xmax:
            ax.axvline(mean_cos, color="blue", linestyle="-", linewidth=2.2,
                       label=f"Mean: {mean_cos:.4f} ({mean_deg:.1f}°)")
        ax.set_xlim(xmin, xmax)
        ax.set_xlabel("cos(θ_true − θ_reco)", fontsize=11, weight="bold")
        ax.set_ylabel("Count", fontsize=11, weight="bold")
        ax.set_title(f"{label}\n(N={vals.size})", fontsize=13, weight="bold")
        ax.grid(True, alpha=0.25)
        ax.legend(loc="upper left", fontsize=9)

    for j in range(len(labels), nrows * ncols):
        r, c = divmod(j, ncols)
        axes[r, c].axis("off")

    fig.suptitle(f"cos(θ_true − θ_reco) per scenario{title_suffix}",
                 fontsize=16, weight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    pdf.savefig(fig)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Page 4: distribution analysis — boxplot, CDF, violin, histogram overlay
# ---------------------------------------------------------------------------

def _page_distribution_analysis(pdf, summary):
    labels = list(summary.keys())
    colors = [_color(l, i) for i, l in enumerate(labels)]

    # Collect per-CAT Q68 arrays
    q68_arrays = []
    valid_labels, valid_colors = [], []
    for i, label in enumerate(labels):
        arr = np.asarray(summary[label]["q68_all"], dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            continue
        q68_arrays.append(arr)
        valid_labels.append(label)
        valid_colors.append(colors[i])

    if not q68_arrays:
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Per-CAT Q68(MCMC) Distribution Analysis", fontsize=16, weight="bold")

    # Boxplot
    ax = axes[0, 0]
    bp = ax.boxplot(q68_arrays, labels=valid_labels, patch_artist=True,
                    notch=False, showmeans=True, widths=0.6)
    for patch, color in zip(bp["boxes"], valid_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_ylabel("Q68 [deg]", fontsize=11)
    ax.set_title("Boxplot comparison", fontsize=12, weight="bold")
    ax.tick_params(axis="x", rotation=30, labelsize=8)
    ax.grid(axis="y", alpha=0.3)

    # Bar chart mean ± std
    ax = axes[0, 1]
    means = [np.mean(a) for a in q68_arrays]
    stds = [np.std(a) for a in q68_arrays]
    x_pos = np.arange(len(valid_labels))
    bars = ax.bar(x_pos, means, yerr=stds, capsize=5, alpha=0.8,
                  color=valid_colors, edgecolor="black", linewidth=1.2)
    for bar, mean in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                f"{mean:.1f}°", ha="center", va="bottom", fontsize=8, weight="bold")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(valid_labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Mean Q68 [deg]", fontsize=11)
    ax.set_title("Mean ± Std Dev", fontsize=12, weight="bold")
    ax.grid(axis="y", alpha=0.3)

    # CDF
    ax = axes[1, 0]
    for arr, label, color in zip(q68_arrays, valid_labels, valid_colors):
        sorted_arr = np.sort(arr)
        cdf = np.arange(1, len(sorted_arr) + 1) / len(sorted_arr) * 100
        ax.plot(sorted_arr, cdf, label=label, color=color, linewidth=2.2)
    ax.axhline(68, color="red", linestyle="--", alpha=0.6, linewidth=1.5, label="68% CL")
    ax.set_xlabel("Q68 [deg]", fontsize=11)
    ax.set_ylabel("Cumulative [%]", fontsize=11)
    ax.set_title("Cumulative distribution", fontsize=12, weight="bold")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(True, alpha=0.3)

    # Violin
    ax = axes[1, 1]
    parts = ax.violinplot(q68_arrays, positions=range(len(q68_arrays)),
                          showmeans=True, showmedians=True, widths=0.7)
    for pc, color in zip(parts["bodies"], valid_colors):
        pc.set_facecolor(color)
        pc.set_alpha(0.7)
    ax.set_xticks(range(len(valid_labels)))
    ax.set_xticklabels(valid_labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Q68 [deg]", fontsize=11)
    ax.set_title("Distribution shapes (violin)", fontsize=12, weight="bold")
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    pdf.savefig(fig)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Page 5: input data stats — n_selected distributions + CT accuracy
# ---------------------------------------------------------------------------

def _page_input_stats(pdf, summary):
    labels = list(summary.keys())
    colors = [_color(l, i) for i, l in enumerate(labels)]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Input Data Statistics per Scenario", fontsize=15, weight="bold")

    # n_selected distribution per scenario (overlapping histograms)
    ax = axes[0]
    for i, label in enumerate(labels):
        nsel = np.asarray(summary[label]["n_selected_all"], dtype=float)
        nsel = nsel[np.isfinite(nsel)]
        if nsel.size == 0:
            continue
        ax.hist(nsel, bins=20, alpha=0.5, color=_color(label, i),
                edgecolor="black", linewidth=0.5,
                label=f"{label} (μ={np.mean(nsel):.0f})")
    ax.set_xlabel("n_selected per CAT", fontsize=11)
    ax.set_ylabel("CATs", fontsize=11)
    ax.set_title("Selected events per CAT", fontsize=12, weight="bold")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

    # CT accuracy distribution (only for scenarios with CT)
    ax = axes[1]
    plotted = False
    for i, label in enumerate(labels):
        ct = np.asarray(summary[label]["ct_accuracy_all"], dtype=float)
        ct = ct[np.isfinite(ct)]
        if ct.size == 0:
            continue
        ax.hist(ct, bins=20, alpha=0.6, color=_color(label, i),
                edgecolor="black", linewidth=0.5,
                label=f"{label} (μ={np.mean(ct):.3f})")
        plotted = True
    if not plotted:
        ax.text(0.5, 0.5, "No CT accuracy data", ha="center", va="center",
                transform=ax.transAxes, fontsize=12)
    ax.set_xlabel("CT accuracy", fontsize=11)
    ax.set_ylabel("CATs", fontsize=11)
    ax.set_title("CT accuracy distribution", fontsize=12, weight="bold")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    fig.tight_layout(rect=[0, 0, 1, 0.94])
    pdf.savefig(fig)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main PDF builder
# ---------------------------------------------------------------------------

def _make_pdf(output_pdf: Path, summary: dict, n_cats: int):
    with matplotlib.backends.backend_pdf.PdfPages(output_pdf) as pdf:
        # Page 1: summary table + bar + Q68 histogram
        _page_summary(pdf, summary, n_cats)

        # Page 2: per-scenario cos distribution (adaptive range)
        _page_cos_distributions(pdf, summary)

        # Page 3: cos distribution full range (-1 to 1)
        _page_cos_distributions(pdf, summary,
                                title_suffix=" — full range [−1, 1]",
                                x_range=(-1.0, 1.0))

        # Page 4: distribution analysis (boxplot / CDF / violin / bar±std)
        _page_distribution_analysis(pdf, summary)

        # Page 5: input data stats (n_selected + CT accuracy distributions)
        _page_input_stats(pdf, summary)


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate per-CAT scenario reports into all-CAT summary")
    parser.add_argument("--input-root", required=True,
                        help="Root containing per-cat folders with scenario_cos_theta_report.json")
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
        raise RuntimeError(
            f"No valid scenario_cos_theta_report.json found under {input_root}")

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
