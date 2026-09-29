#!/usr/bin/env python3
"""
ct_threshold_table.py

Purity / efficiency scan for the DUNE supernova-pointing channel tagger (CT v80).

Reads the per-event slice cache produced by the r3_rescan campaign
(scenario_3_full_pipeline, cats 673-900) and, for a grid of CT-v80 score
thresholds, computes:

  - ES efficiency  = selected ES / all ES candidates passing the energy cut
  - CC efficiency  = selected CC / all CC candidates passing the energy cut
  - CC rejection   = 1 - CC efficiency
  - purity         = selected ES / (selected ES + selected CC)
  - selected ES / CC / total per burst (normalised to the 227 cats in the cache)

The main table applies the pipeline's E > 5 MeV cut; a secondary section
reproduces the same table with no energy cut. A breakdown in reco-energy
bins (5-10, 10-20, 20-30, >30 MeV) is produced at t=0.50 and t=0.80, plus
the ROC AUC of the CT v80 score for ES vs CC (E>5 sample), and two
diagnostic plots.

Read-only w.r.t. the input cache; all outputs go to a dedicated EOS
directory. Pure numpy/matplotlib, no ML libraries needed -- cheap on
~660k events.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INPUT_NPZ = Path(
    "/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/r3_rescan/"
    "slice_cache_673_900.npz"
)
OUTDIR = Path(
    "/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/combo_study/"
    "ct_threshold_scan"
)

ENERGY_CUT_MEV = 5.0
N_CATS = 227  # number of burst realisations (cats 673-900) in this cache

# Generated (thrown) events per burst, upstream of clustering / 3-plane
# matching / the CT stage -- for context only, NOT used as a denominator
# anywhere in this table (see note in the markdown output).
ES_GENERATED_PER_BURST = 330
CC_GENERATED_PER_BURST = 3300

THRESHOLDS = [round(t, 2) for t in np.arange(0.0, 0.951, 0.05)]
HIGHLIGHT_THRESHOLDS = [0.50, 0.80]

ENERGY_BINS = [
    ("5-10 MeV", 5.0, 10.0),
    ("10-20 MeV", 10.0, 20.0),
    ("20-30 MeV", 20.0, 30.0),
    (">30 MeV", 30.0, np.inf),
]


# ---------------------------------------------------------------------------
# Core computations
# ---------------------------------------------------------------------------


def compute_row(proba: np.ndarray, is_es: np.ndarray, threshold: float, n_cats: int) -> dict:
    """Efficiency/purity numbers for a single score threshold."""
    is_es = is_es.astype(bool)
    sel = proba >= threshold

    es_total = int(is_es.sum())
    cc_total = int((~is_es).sum())

    es_sel = int(np.sum(sel & is_es))
    cc_sel = int(np.sum(sel & ~is_es))
    total_sel = es_sel + cc_sel

    es_eff = es_sel / es_total if es_total > 0 else float("nan")
    cc_eff = cc_sel / cc_total if cc_total > 0 else float("nan")
    cc_rej = 1.0 - cc_eff if not np.isnan(cc_eff) else float("nan")
    purity = es_sel / total_sel if total_sel > 0 else float("nan")

    return dict(
        threshold=threshold,
        es_total=es_total,
        cc_total=cc_total,
        es_efficiency=es_eff,
        cc_efficiency=cc_eff,
        cc_rejection=cc_rej,
        purity=purity,
        es_selected=es_sel,
        cc_selected=cc_sel,
        total_selected=total_sel,
        es_per_burst=es_sel / n_cats,
        cc_per_burst=cc_sel / n_cats,
        total_per_burst=total_sel / n_cats,
    )


def compute_table(proba: np.ndarray, is_es: np.ndarray, thresholds, n_cats: int) -> list:
    return [compute_row(proba, is_es, t, n_cats) for t in thresholds]


def compute_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """ROC AUC via a single sort + cumulative-sum sweep (no sklearn needed)."""
    labels = labels.astype(np.float64)
    order = np.argsort(-scores, kind="mergesort")
    labels_sorted = labels[order]

    n_pos = labels_sorted.sum()
    n_neg = len(labels_sorted) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")

    tps = np.cumsum(labels_sorted)
    fps = np.cumsum(1.0 - labels_sorted)

    tpr = np.concatenate(([0.0], tps / n_pos, [1.0]))
    fpr = np.concatenate(([0.0], fps / n_neg, [1.0]))

    return float(np.trapz(tpr, fpr))


def energy_bin_mask(energy: np.ndarray, lo: float, hi: float) -> np.ndarray:
    if np.isinf(hi):
        return energy >= lo
    return (energy >= lo) & (energy < hi)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def fmt(x, nd=3):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    return f"{x:.{nd}f}"


def table_to_markdown(rows: list, highlight=None) -> str:
    highlight = highlight or []
    header = (
        "| t | ES eff | CC eff | CC rej | Purity | ES sel | CC sel | Total sel | "
        "ES/burst | CC/burst | Total/burst |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    lines = []
    for r in rows:
        is_hl = any(abs(r["threshold"] - h) < 1e-9 for h in highlight)
        t_str = f"**{r['threshold']:.2f}**" if is_hl else f"{r['threshold']:.2f}"
        line = (
            f"| {t_str} | {fmt(r['es_efficiency'])} | {fmt(r['cc_efficiency'])} | "
            f"{fmt(r['cc_rejection'])} | {fmt(r['purity'])} | {r['es_selected']} | "
            f"{r['cc_selected']} | {r['total_selected']} | {fmt(r['es_per_burst'])} | "
            f"{fmt(r['cc_per_burst'])} | {fmt(r['total_per_burst'])} |"
        )
        lines.append(line)
    return header + "\n".join(lines) + "\n"


def energy_table_to_markdown(energy_rows: dict) -> str:
    header = (
        "| Energy bin | t | ES eff | CC eff | Purity | ES sel | CC sel | "
        "ES/burst | CC/burst | Total/burst |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
    )
    lines = []
    for bin_name, t_rows in energy_rows.items():
        for t, r in t_rows.items():
            lines.append(
                f"| {bin_name} | {t:.2f} | {fmt(r['es_efficiency'])} | "
                f"{fmt(r['cc_efficiency'])} | {fmt(r['purity'])} | {r['es_selected']} | "
                f"{r['cc_selected']} | {fmt(r['es_per_burst'])} | {fmt(r['cc_per_burst'])} | "
                f"{fmt(r['total_per_burst'])} |"
            )
    return header + "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading {INPUT_NPZ} ...")
    d = np.load(INPUT_NPZ, allow_pickle=True)

    energy = d["energy"].astype(np.float64)
    proba = d["proba"].astype(np.float64)
    is_es = d["is_es"].astype(bool)
    cat = d["cat"]
    cats = d["cats"]
    n_cats_in_file = int(d["n_cats"])
    campaign = str(d["campaign"])
    scenario = str(d["scenario"])
    per_cat = json.loads(str(d["per_cat"]))

    n_events = len(energy)
    n_es = int(is_es.sum())
    n_cc = int((~is_es).sum())
    n_below_cut = int(np.sum(energy <= ENERGY_CUT_MEV))
    per_cat_keys = sorted(set().union(*(v.keys() for v in per_cat.values())))

    diag = dict(
        campaign=campaign,
        scenario=scenario,
        n_cats_in_file=n_cats_in_file,
        n_cats_used=N_CATS,
        n_events_total=n_events,
        n_es_total=n_es,
        n_cc_total=n_cc,
        energy_min=float(energy.min()),
        energy_max=float(energy.max()),
        n_events_at_or_below_5MeV=n_below_cut,
        energy_cut_already_applied=bool(n_below_cut == 0),
        per_cat_json_keys=per_cat_keys,
        proba_min=float(proba.min()),
        proba_max=float(proba.max()),
    )

    print("--- Diagnostics ---")
    for k, v in diag.items():
        print(f"  {k}: {v}")
    print("--------------------")

    # -----------------------------------------------------------------
    # Main sample: E > 5 MeV cut (the pipeline's energy cut)
    # -----------------------------------------------------------------
    mask_cut = energy > ENERGY_CUT_MEV
    proba_cut = proba[mask_cut]
    is_es_cut = is_es[mask_cut]
    energy_cut = energy[mask_cut]

    main_table = compute_table(proba_cut, is_es_cut, THRESHOLDS, N_CATS)

    # -----------------------------------------------------------------
    # Secondary sample: no energy cut
    # -----------------------------------------------------------------
    nocut_table = compute_table(proba, is_es, THRESHOLDS, N_CATS)

    # -----------------------------------------------------------------
    # Energy-binned table at t = 0.50 and 0.80 (on the E>5 sample; bins
    # below start at 5 MeV so this is automatically consistent)
    # -----------------------------------------------------------------
    energy_binned = {}
    for bin_name, lo, hi in ENERGY_BINS:
        bmask = energy_bin_mask(energy_cut, lo, hi)
        p_bin = proba_cut[bmask]
        es_bin = is_es_cut[bmask]
        energy_binned[bin_name] = {
            t: compute_row(p_bin, es_bin, t, N_CATS) for t in HIGHLIGHT_THRESHOLDS
        }

    # Full threshold scan per energy bin, for the ES-efficiency-vs-energy plot
    energy_scan = {}
    for bin_name, lo, hi in ENERGY_BINS:
        bmask = energy_bin_mask(energy_cut, lo, hi)
        p_bin = proba_cut[bmask]
        es_bin = is_es_cut[bmask]
        energy_scan[bin_name] = compute_table(p_bin, es_bin, THRESHOLDS, N_CATS)

    # -----------------------------------------------------------------
    # ROC AUC (E > 5 MeV sample)
    # -----------------------------------------------------------------
    auc = compute_auc(proba_cut, is_es_cut)
    print(f"ROC AUC (ES vs CC, E>{ENERGY_CUT_MEV} MeV): {auc:.4f}")

    # -----------------------------------------------------------------
    # Write CSV (main table, with energy cut)
    # -----------------------------------------------------------------
    csv_path = OUTDIR / "ct_threshold_table.csv"
    fieldnames = list(main_table[0].keys())
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in main_table:
            writer.writerow(row)
    print(f"Wrote {csv_path}")

    # -----------------------------------------------------------------
    # Write JSON (everything)
    # -----------------------------------------------------------------
    json_path = OUTDIR / "ct_threshold_table.json"
    json_payload = dict(
        diagnostics=diag,
        energy_cut_mev=ENERGY_CUT_MEV,
        n_cats=N_CATS,
        es_generated_per_burst=ES_GENERATED_PER_BURST,
        cc_generated_per_burst=CC_GENERATED_PER_BURST,
        thresholds=THRESHOLDS,
        highlight_thresholds=HIGHLIGHT_THRESHOLDS,
        main_table_with_energy_cut=main_table,
        secondary_table_no_energy_cut=nocut_table,
        energy_bins=[b[0] for b in ENERGY_BINS],
        energy_binned_table=energy_binned,
        roc_auc_es_vs_cc_energy_cut=auc,
    )

    def _default(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, float) and np.isnan(o):
            return None
        return str(o)

    with open(json_path, "w") as f:
        json.dump(json_payload, f, indent=2, default=_default)
    print(f"Wrote {json_path}")

    # -----------------------------------------------------------------
    # Write markdown
    # -----------------------------------------------------------------
    md_path = OUTDIR / "ct_threshold_table.md"
    md = []
    md.append("# CT v80 threshold scan: purity / efficiency table\n")
    md.append(
        f"Input: `{INPUT_NPZ}`\n\n"
        f"Campaign: `{campaign}`  \n"
        f"Scenario: `{scenario}`  \n"
        f"Cats: {n_cats_in_file} (673-900)\n"
    )
    md.append("\n## Diagnostics\n")
    md.append(f"- Total events in cache: {n_events}\n")
    md.append(f"- ES (truth) events: {n_es}\n")
    md.append(f"- CC (truth) events: {n_cc}\n")
    md.append(f"- Reco energy range: {energy.min():.3f} - {energy.max():.3f} MeV\n")
    md.append(
        f"- Events at or below {ENERGY_CUT_MEV} MeV: {n_below_cut} "
        f"-> the E > {ENERGY_CUT_MEV} MeV cut is **not** pre-applied in this cache, "
        "so it is applied here for the main table.\n"
    )
    md.append(f"- CT v80 score (proba) range: {proba.min():.4f} - {proba.max():.4f}\n")
    md.append(f"- `per_cat` JSON per-cat keys: {per_cat_keys}\n")
    md.append(
        "\n**Note on per-burst normalisation:** each simulated burst generates "
        f"{ES_GENERATED_PER_BURST} ES + {CC_GENERATED_PER_BURST} CC events "
        "(thrown/generated level). The events in this cache, and hence the "
        "'per burst' columns below (selected counts / 227 cats), are **not** "
        "normalised to those generated numbers: they are the events that "
        "already reached the CT stage, i.e. survived clustering, three-plane "
        "matching, and (for the main table) the reco-energy cut. On average "
        f"only ~{n_es / n_cats_in_file:.0f} true-ES events per cat reach the CT "
        f"stage (of the {ES_GENERATED_PER_BURST} generated), so the per-burst "
        "figures below should be read as 'selected per burst among CT-stage "
        "candidates', not as an overall generation-to-selection efficiency.\n"
    )

    md.append(f"\n## Main table (E > {ENERGY_CUT_MEV} MeV cut applied)\n")
    md.append(
        f"ES candidates passing the energy cut: {main_table[0]['es_total']}  \n"
        f"CC candidates passing the energy cut: {main_table[0]['cc_total']}\n\n"
    )
    md.append(
        "Selection is `proba >= t` (high score = ES-like). Thresholds t = 0.50 and "
        "t = 0.80 are highlighted in bold.\n\n"
    )
    md.append(table_to_markdown(main_table, highlight=HIGHLIGHT_THRESHOLDS))

    md.append(f"\n## Secondary table (no energy cut)\n")
    md.append(
        f"ES candidates (no cut): {nocut_table[0]['es_total']}  \n"
        f"CC candidates (no cut): {nocut_table[0]['cc_total']}\n\n"
    )
    md.append(table_to_markdown(nocut_table, highlight=HIGHLIGHT_THRESHOLDS))

    md.append("\n## Energy-binned table at t = 0.50 and t = 0.80\n")
    md.append(f"(E > {ENERGY_CUT_MEV} MeV sample, split by reco energy bin)\n\n")
    md.append(energy_table_to_markdown(energy_binned))

    md.append("\n## ROC AUC\n")
    md.append(
        f"ROC AUC of the CT v80 score for ES vs CC, on the E > {ENERGY_CUT_MEV} MeV "
        f"sample: **{auc:.4f}**\n"
    )

    md.append("\n## Plots\n")
    md.append("- `ct_threshold_scan.png`: efficiency/purity and per-burst rates vs threshold\n")
    md.append("- `ct_threshold_scan_energy.png`: ES efficiency vs threshold, by energy bin\n")

    with open(md_path, "w") as f:
        f.write("".join(md))
    print(f"Wrote {md_path}")

    # -----------------------------------------------------------------
    # Plot 1: ct_threshold_scan.png (two panels)
    # -----------------------------------------------------------------
    t_arr = np.array([r["threshold"] for r in main_table])
    es_eff_arr = np.array([r["es_efficiency"] for r in main_table])
    cc_eff_arr = np.array([r["cc_efficiency"] for r in main_table])
    purity_arr = np.array([r["purity"] for r in main_table])
    es_pb_arr = np.array([r["es_per_burst"] for r in main_table])
    cc_pb_arr = np.array([r["cc_per_burst"] for r in main_table])

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    ax = axes[0]
    ax.plot(t_arr, es_eff_arr, marker="o", ms=3, label="ES efficiency", color="tab:blue")
    ax.plot(t_arr, cc_eff_arr, marker="o", ms=3, label="CC efficiency", color="tab:red")
    ax.plot(t_arr, purity_arr, marker="o", ms=3, label="Purity", color="tab:green")
    for hv in HIGHLIGHT_THRESHOLDS:
        ax.axvline(hv, color="gray", ls="--", lw=1, alpha=0.7)
    ax.set_xlabel("CT v80 score threshold")
    ax.set_ylabel("Fraction")
    ax.set_title(f"CT v80 selection (E > {ENERGY_CUT_MEV} MeV)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.grid(alpha=0.3)
    ax.legend(loc="best", fontsize=9)

    ax = axes[1]
    ax.plot(t_arr, es_pb_arr, marker="o", ms=3, label="Selected ES / burst", color="tab:blue")
    ax.plot(t_arr, cc_pb_arr, marker="o", ms=3, label="Selected CC / burst", color="tab:red")
    for hv in HIGHLIGHT_THRESHOLDS:
        ax.axvline(hv, color="gray", ls="--", lw=1, alpha=0.7)
    ax.set_yscale("log")
    ax.set_xlabel("CT v80 score threshold")
    ax.set_ylabel("Selected events per burst (log scale)")
    ax.set_title("Selected rate per burst (227 cats)")
    ax.set_xlim(0, 1)
    ax.grid(alpha=0.3, which="both")
    ax.legend(loc="best", fontsize=9)

    fig.tight_layout()
    plot1_path = OUTDIR / "ct_threshold_scan.png"
    fig.savefig(plot1_path, dpi=150)
    plt.close(fig)
    print(f"Wrote {plot1_path}")

    # -----------------------------------------------------------------
    # Plot 2: ct_threshold_scan_energy.png
    # -----------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(7, 5.5))
    colors = ["tab:blue", "tab:orange", "tab:green", "tab:purple"]
    for (bin_name, _, _), color in zip(ENERGY_BINS, colors):
        rows = energy_scan[bin_name]
        t_b = np.array([r["threshold"] for r in rows])
        eff_b = np.array([r["es_efficiency"] for r in rows])
        ax.plot(t_b, eff_b, marker="o", ms=3, label=bin_name, color=color)
    for hv in HIGHLIGHT_THRESHOLDS:
        ax.axvline(hv, color="gray", ls="--", lw=1, alpha=0.7)
    ax.set_xlabel("CT v80 score threshold")
    ax.set_ylabel("ES efficiency")
    ax.set_title(f"ES efficiency vs threshold by energy bin (E > {ENERGY_CUT_MEV} MeV)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.grid(alpha=0.3)
    ax.legend(loc="best", fontsize=9, title="Reco energy")

    fig.tight_layout()
    plot2_path = OUTDIR / "ct_threshold_scan_energy.png"
    fig.savefig(plot2_path, dpi=150)
    plt.close(fig)
    print(f"Wrote {plot2_path}")

    print("Done.")


if __name__ == "__main__":
    main()
