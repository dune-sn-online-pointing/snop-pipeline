#!/usr/bin/env python3
"""
Generate PDF report from ED inference NPZ output.
"""

import argparse
import importlib.util
import json
import os
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages

try:
    import mplhep as hep  # type: ignore
except Exception:
    hep = None


def _require_init_done():
    if os.environ.get("INIT_DONE", "").lower() != "true":
        raise RuntimeError("Environment not initialized. Run: source scripts/init.sh")


def _load_json_config(path):
    with open(path, "r") as f:
        return json.load(f)


def _resolve_config(args):
    cfg = {}
    if args.config:
        cfg = _load_json_config(args.config)
    ed_cfg = cfg.get("ed_inference", cfg)

    output_base = Path(os.environ.get("SNOP_OUTPUT_BASE", "output"))

    defaults = {
        "output_dir": str(output_base / "ed_inference"),
        "report_title": "ED Inference Report",
        "verbose": False,
    }

    resolved = {}
    for key, default_val in defaults.items():
        cli_val = getattr(args, key, None)
        cfg_val = ed_cfg.get(key)
        resolved[key] = cli_val if cli_val is not None else (cfg_val if cfg_val is not None else default_val)

    return resolved


def _compute_cos_angle(true_dirs: np.ndarray, reco_dirs: np.ndarray) -> np.ndarray:
    t = np.asarray(true_dirs, dtype=np.float32)
    r = np.asarray(reco_dirs, dtype=np.float32)

    t_norm = np.linalg.norm(t, axis=1, keepdims=True) + 1e-8
    r_norm = np.linalg.norm(r, axis=1, keepdims=True) + 1e-8
    t_u = t / t_norm
    r_u = r / r_norm

    dot = np.sum(t_u * r_u, axis=1)
    return np.clip(dot, -1.0, 1.0)



def _apply_plot_style():
    # Match reco_display style direction: CMS/HEP style, no grid, square pages.
    if hep is not None:
        plt.style.use(hep.style.CMS)

    plt.rcParams.update(
        {
            "figure.figsize": (8, 8),
            "axes.grid": False,
            "axes.grid.which": "both",
            "font.size": 12,
            "axes.titlesize": 14,
            "axes.labelsize": 13,
            "legend.fontsize": 9,
        }
    )


def _get_parula_cmap():
    # Try to reuse online-pointing-utils parula map.
    repo_root = Path(__file__).resolve().parents[2]
    style_py = repo_root / "online-pointing-utils" / "python" / "reco" / "style.py"
    if style_py.exists():
        try:
            spec = importlib.util.spec_from_file_location("opu_reco_style", str(style_py))
            if spec is not None and spec.loader is not None:
                # Prevent style.py from mutating global plotting style (notably TeX settings).
                _orig_style_use = plt.style.use
                plt.style.use = lambda *args, **kwargs: None
                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)
                    cmap = getattr(module, "parula_map", None)
                    if cmap is not None:
                        return cmap
                finally:
                    plt.style.use = _orig_style_use
        except Exception:
            pass
    return "viridis"


def _square_axes():
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.grid(False)
    ax.minorticks_off()
    return fig, ax


def _overlay_cos_percentile_lines(ax, e_true, cos_angle, e_range, n_bins=15):
    """Draw step-function 68% and 90% percentile lines on a cos(x) vs E(y) 2D histogram."""
    edges = np.linspace(e_range[0], e_range[1], n_bins + 1)
    p32_vals, p10_vals, bin_lo, bin_hi = [], [], [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (e_true >= lo) & (e_true < hi)
        if np.sum(sel) < 5:
            continue
        val = cos_angle[sel]
        p32_vals.append(float(np.percentile(val, 32)))
        p10_vals.append(float(np.percentile(val, 10)))
        bin_lo.append(lo)
        bin_hi.append(hi)

    if not p32_vals:
        return

    def _step_path(pvals, los, his):
        # Vertical segment per bin, horizontal jump at each boundary.
        # x = [p0, p0, p1, p1, ...], y = [lo0, hi0, hi0, hi1, hi1, hi2, ...]
        xs = [pvals[0], pvals[0]]
        ys = [los[0],   his[0]]
        for j in range(1, len(pvals)):
            if los[j] != his[j - 1]:          # gap: break line with NaN
                xs += [float("nan"), pvals[j], pvals[j]]
                ys += [float("nan"), los[j],   his[j]]
            else:
                xs += [pvals[j], pvals[j]]
                ys += [his[j - 1], his[j]]
        return xs, ys

    x32, y32 = _step_path(p32_vals, bin_lo, bin_hi)
    x10, y10 = _step_path(p10_vals, bin_lo, bin_hi)
    ax.plot(x32, y32, color="red", linewidth=3, linestyle="-",  label="68th percentile")
    ax.plot(x10, y10, color="red", linewidth=3, linestyle="--", label="90th percentile")
    ax.legend(fontsize=15, loc="upper left", bbox_to_anchor=(0.0, -0.08),
              ncol=2, borderaxespad=0)


def _add_short_colorbar(ax, mappable, label: str, shrink: float = 0.82):
    """Attach a vertical colorbar with configurable height."""
    cb = plt.colorbar(mappable, ax=ax, shrink=shrink, pad=0.02)
    cb.set_label(label)
    return cb


def _plot_overlay_residuals(pdf, e_true, cos_angle, title_suffix=""):
    energy_bins = [(0, 5), (5, 10), (10, 15), (15, np.inf)]

    fig, axs = plt.subplots(2, 2, figsize=(14, 12))
    sigma_centers = []
    sigma_vals = []
    sigma_halfwidths = []

    for ax, (lo, hi) in zip(axs.flatten(), energy_bins):
        if np.isfinite(hi):
            sel = (e_true >= lo) & (e_true < hi)
            bin_label = f"{lo}–{hi} MeV"
            hi_val = hi
        else:
            sel = e_true >= lo
            bin_label = f"E \u2265 {lo} MeV"
            hi_val = float(np.max(e_true)) if np.any(sel) else lo + 1

        n = int(np.sum(sel))
        if n < 5:
            ax.set_title(f"{bin_label}  (no data)")
            ax.axis("off")
            continue

        val = cos_angle[sel]
        median = float(np.median(val))
        p32 = float(np.percentile(val, 32))   # 68% of events have cos > p32
        p10 = float(np.percentile(val, 10))   # 90% of events have cos > p10

        ax.hist(val, bins=60, range=(-1.0, 1.0), density=True, alpha=0.7)
        ax.axvspan(p10, 1.0, alpha=0.15, color="steelblue", label=f"90% [{p10:.3f}, 1]")
        ax.axvspan(p32, 1.0, alpha=0.25, color="steelblue", label=f"68% [{p32:.3f}, 1]")
        ax.axvline(median, color="k", linestyle="--", linewidth=1.5, label=f"median = {median:.3f}")
        ax.set_xlim(-1.0, 1.0)
        ax.set_xlabel("cos(angle(true, reco))")
        ax.set_ylabel("Density")
        ax.set_title(f"{bin_label}  (n={n})")
        ax.legend(fontsize=9)
        ax.grid(False)
        ax.minorticks_off()

        sigma_centers.append(0.5 * (lo + hi_val))
        sigma_vals.append((1.0 - p32, 1.0 - p10))
        sigma_halfwidths.append(0.5 * (hi_val - lo))

    fig.suptitle(f"cos(angle) distributions by energy bin {title_suffix}".strip(), fontsize=14)
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

    if sigma_centers:
        res_1sigma = [v[0] for v in sigma_vals]
        res_2sigma = [v[1] for v in sigma_vals]
        fig, ax = _square_axes()
        ax.errorbar(
            sigma_centers, res_1sigma, xerr=sigma_halfwidths,
            fmt="o-", capsize=4, linewidth=1.5, label="1\u03c3 (68%)",
        )
        ax.errorbar(
            sigma_centers, res_2sigma, xerr=sigma_halfwidths,
            fmt="s--", capsize=4, linewidth=1.5, label="2\u03c3 (90%)",
        )
        ax.legend(fontsize=10)
        ax.set_xlabel("E-truth")
        ax.set_ylabel("1 \u2212 pN (resolution from cos=1)")
        ax.set_title(f"Per-Energy angular resolution {title_suffix}".strip())
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)


def _plot_adc_vs_energy_panels(
    pdf,
    e_true,
    values_by_plane,
    cmap,
    norm,
    page_title,
    y_label,
    bins=(60, 60),
    e_range=None,
):
    fig, axs = plt.subplots(2, 2, figsize=(12, 12))
    entries = [("U", values_by_plane["U"]), ("V", values_by_plane["V"]), ("X", values_by_plane["X"]), ("All", values_by_plane["All"])]

    for ax, (name, vals) in zip(axs.flatten(), entries):
        if e_range is None:
            yr = [float(np.min(vals)), float(np.max(vals))]
            xr = [float(np.min(e_true)), float(np.max(e_true))]
        else:
            xr = [float(e_range[0]), float(e_range[1])]
            yr = [float(np.min(vals)), float(np.max(vals))]
        h = ax.hist2d(
            e_true,
            vals,
            bins=bins,
            range=[xr, yr],
            cmap=cmap,
            norm=norm,
        )
        ax.set_title(name)
        ax.set_xlabel("E-truth")
        ax.set_ylabel(y_label)
        ax.set_box_aspect(1)
        ax.grid(False)
        ax.minorticks_off()
        _add_short_colorbar(ax, h[3], "Counts (log scale)", shrink=0.74)

    fig.suptitle(page_title, fontsize=14)
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def make_report(
    input_npz: Path,
    output_pdf: Path,
    title: str = "ED Inference Report",
    verbose: bool = False,
):
    data = np.load(input_npz, allow_pickle=True)
    reco = np.asarray(data["predicted_directions"], dtype=np.float32)
    true = np.asarray(data["true_directions"], dtype=np.float32)
    e_true = np.asarray(data["true_energy"], dtype=np.float32)
    x_adc = np.asarray(data["x_deposited_charge"], dtype=np.float32)
    total_adc_all = np.asarray(data["total_adc_all"], dtype=np.float32) if "total_adc_all" in data else x_adc.copy()
    u_total_adc = np.asarray(data["u_total_adc"], dtype=np.float32) if "u_total_adc" in data else x_adc.copy()
    v_total_adc = np.asarray(data["v_total_adc"], dtype=np.float32) if "v_total_adc" in data else x_adc.copy()
    x_total_adc = np.asarray(data["x_total_adc"], dtype=np.float32) if "x_total_adc" in data else x_adc.copy()
    if "peak_adc_all" in data:
        peak_adc_all = np.asarray(data["peak_adc_all"], dtype=np.float32)
    elif "x_peak_adc" in data:
        peak_adc_all = np.asarray(data["x_peak_adc"], dtype=np.float32)
    else:
        # Legacy fallback: use X total as proxy so report still renders.
        peak_adc_all = x_adc.copy()
    u_peak_adc = np.asarray(data["u_peak_adc"], dtype=np.float32) if "u_peak_adc" in data else peak_adc_all.copy()
    v_peak_adc = np.asarray(data["v_peak_adc"], dtype=np.float32) if "v_peak_adc" in data else peak_adc_all.copy()
    x_peak_adc = np.asarray(data["x_peak_adc"], dtype=np.float32) if "x_peak_adc" in data else peak_adc_all.copy()
    if peak_adc_all.shape[0] != e_true.shape[0]:
        peak_adc_all = x_adc.copy()

    valid = (
        np.isfinite(reco).all(axis=1)
        & np.isfinite(true).all(axis=1)
        & np.isfinite(e_true)
        & np.isfinite(u_total_adc)
        & np.isfinite(v_total_adc)
        & np.isfinite(x_total_adc)
        & np.isfinite(total_adc_all)
        & np.isfinite(u_peak_adc)
        & np.isfinite(v_peak_adc)
        & np.isfinite(x_peak_adc)
        & np.isfinite(peak_adc_all)
    )
    reco = reco[valid]
    true = true[valid]
    e_true = e_true[valid]
    x_adc = x_adc[valid]
    u_total_adc = u_total_adc[valid]
    v_total_adc = v_total_adc[valid]
    x_total_adc = x_total_adc[valid]
    total_adc_all = total_adc_all[valid]
    u_peak_adc = u_peak_adc[valid]
    v_peak_adc = v_peak_adc[valid]
    x_peak_adc = x_peak_adc[valid]
    peak_adc_all = peak_adc_all[valid]

    cos_angle = _compute_cos_angle(true, reco)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    if verbose:
        print(f"[INFO] Input NPZ: {input_npz}")
        print(f"[INFO] Total samples: {len(valid)}")
        print(f"[INFO] Valid samples: {np.sum(valid)}")

    _apply_plot_style()
    parula_cmap = _get_parula_cmap()
    log_norm = mcolors.LogNorm(vmin=1)

    with PdfPages(output_pdf) as pdf:
        fig, ax = _square_axes()
        ax.axis("off")
        txt = (
            f"{title}\n\n"
            f"Input: {input_npz}\n"
            f"Valid samples: {len(e_true)}\n"
            f"Mean cos(angle): {np.mean(cos_angle):.4f}\n"
            f"Median cos(angle): {np.median(cos_angle):.4f}\n"
            f"16/84 percentiles: {np.percentile(cos_angle, 16):.4f} / {np.percentile(cos_angle, 84):.4f}\n"
        )
        ax.text(0.03, 0.95, txt, va="top", ha="left", family="monospace")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        _plot_adc_vs_energy_panels(
            pdf,
            e_true=e_true,
            values_by_plane={
                "U": u_total_adc,
                "V": v_total_adc,
                "X": x_total_adc,
                "All": total_adc_all,
            },
            cmap=parula_cmap,
            norm=log_norm,
            page_title="2D Histograms: Total ADC vs E-truth (U, V, X, All)",
            y_label="Total ADC",
            bins=(40, 40),
            e_range=None,
        )

        _plot_adc_vs_energy_panels(
            pdf,
            e_true=e_true,
            values_by_plane={
                "U": u_peak_adc,
                "V": v_peak_adc,
                "X": x_peak_adc,
                "All": peak_adc_all,
            },
            cmap=parula_cmap,
            norm=log_norm,
            page_title="2D Histograms: Peak ADC vs E-truth (U, V, X, All)",
            y_label="Peak ADC",
            bins=(40, 40),
            e_range=None,
        )

        fig, ax = _square_axes()
        h = ax.hist2d(
            cos_angle,
            e_true,
            bins=(40, 40),
            range=[[-1.0, 1.0], [np.min(e_true), np.max(e_true)]],
            cmap=parula_cmap,
            norm=log_norm,
        )
        ax.set_box_aspect(1)
        _add_short_colorbar(ax, h[3], "Counts (log scale)", shrink=0.84)
        _overlay_cos_percentile_lines(ax, e_true, cos_angle, e_range=[np.min(e_true), np.max(e_true)])
        ax.set_xlabel("cos(angle(true, reco))")
        ax.set_ylabel("E-truth")
        ax.set_title("2D Histogram: cos(angle) vs E-truth")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # True-vs-reco direction correlation (per Cartesian component).
        fig, axs = plt.subplots(1, 3, figsize=(18, 6))
        comp_labels = ["x", "y", "z"]
        for i, ax in enumerate(axs):
            h = ax.hist2d(
                true[:, i],
                reco[:, i],
                bins=(25, 25),
                range=[[-1.0, 1.0], [-1.0, 1.0]],
                cmap=parula_cmap,
            )
            ax.plot([-1, 1], [-1, 1], "r--", linewidth=1.2)
            ax.set_xlabel(f"True dir {comp_labels[i]}")
            ax.set_ylabel(f"Reco dir {comp_labels[i]}")
            ax.set_title(f"Direction Correlation ({comp_labels[i]})")
            ax.set_box_aspect(1)
            ax.grid(False)
            ax.minorticks_off()
            _add_short_colorbar(ax, h[3], "Counts", shrink=0.74)
        fig.suptitle("True vs Reco Direction Correlation", fontsize=14)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        _plot_overlay_residuals(
            pdf,
            e_true=e_true,
            cos_angle=cos_angle,
            title_suffix="(+/-1 sigma band)",
        )

        # Additional capped-energy pages: E_true <= 15 MeV, with finer binning.
        cap_mask = e_true <= 15.0
        if np.sum(cap_mask) >= 20:
            e_cap = e_true[cap_mask]
            u_total_cap = u_total_adc[cap_mask]
            v_total_cap = v_total_adc[cap_mask]
            x_total_cap = x_total_adc[cap_mask]
            adc_cap = total_adc_all[cap_mask]
            u_peak_cap = u_peak_adc[cap_mask]
            v_peak_cap = v_peak_adc[cap_mask]
            x_peak_cap = x_peak_adc[cap_mask]
            peak_cap = peak_adc_all[cap_mask]
            cos_cap = cos_angle[cap_mask]

            _plot_adc_vs_energy_panels(
                pdf,
                e_true=e_cap,
                values_by_plane={
                    "U": u_total_cap,
                    "V": v_total_cap,
                    "X": x_total_cap,
                    "All": adc_cap,
                },
                cmap=parula_cmap,
                norm=log_norm,
                page_title="2D Histograms (E <= 15 MeV): Total ADC vs E-truth (U, V, X, All)",
                y_label="Total ADC",
                bins=(30, 30),
                e_range=(0.0, 15.0),
            )

            _plot_adc_vs_energy_panels(
                pdf,
                e_true=e_cap,
                values_by_plane={
                    "U": u_peak_cap,
                    "V": v_peak_cap,
                    "X": x_peak_cap,
                    "All": peak_cap,
                },
                cmap=parula_cmap,
                norm=log_norm,
                page_title="2D Histograms (E <= 15 MeV): Peak ADC vs E-truth (U, V, X, All)",
                y_label="Peak ADC",
                bins=(30, 30),
                e_range=(0.0, 15.0),
            )

            fig, ax = _square_axes()
            h = ax.hist2d(
                cos_cap,
                e_cap,
                bins=(30, 30),
                range=[[-1.0, 1.0], [0.0, 15.0]],
                cmap=parula_cmap,
                norm=log_norm,
            )
            ax.set_box_aspect(1)
            _add_short_colorbar(ax, h[3], "Counts (log scale)", shrink=0.84)
            _overlay_cos_percentile_lines(ax, e_cap, cos_cap, e_range=[0.0, 15.0])
            ax.set_xlabel("cos(angle(true, reco))")
            ax.set_ylabel("E-truth")
            ax.set_title("2D Histogram (E <= 15 MeV): cos(angle) vs E-truth")
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)

            true_cap = true[cap_mask]
            reco_cap = reco[cap_mask]
            fig, axs = plt.subplots(1, 3, figsize=(18, 6))
            for i, ax in enumerate(axs):
                h = ax.hist2d(
                    true_cap[:, i],
                    reco_cap[:, i],
                    bins=(25, 25),
                    range=[[-1.0, 1.0], [-1.0, 1.0]],
                    cmap=parula_cmap,
                )
                ax.plot([-1, 1], [-1, 1], "r--", linewidth=1.2)
                ax.set_xlabel(f"True dir {comp_labels[i]}")
                ax.set_ylabel(f"Reco dir {comp_labels[i]}")
                ax.set_title(f"Direction Correlation ({comp_labels[i]})")
                ax.set_box_aspect(1)
                ax.grid(False)
                ax.minorticks_off()
                _add_short_colorbar(ax, h[3], "Counts", shrink=0.74)
            fig.suptitle("True vs Reco Direction Correlation (E \u2264 15 MeV)", fontsize=14)
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)


    print(f"Saved PDF report: {output_pdf}")


def main():
    _require_init_done()

    parser = argparse.ArgumentParser(description="Generate ED inference PDF report")
    parser.add_argument("-j", "--json", "--config", dest="config", default=None,
                        help="JSON config file (supports top-level keys or ed_inference.*)")
    parser.add_argument("-i", "--input-npz", dest="input_npz", default=None,
                        help="Input NPZ path (overrides JSON output_dir)")
    parser.add_argument("-o", "--output-pdf", dest="output_pdf", default=None,
                        help="Output PDF path")
    parser.add_argument("--title", dest="report_title", default=None, help="Report title")
    parser.add_argument("--verbose", dest="verbose", action="store_true", default=None)
    args = parser.parse_args()

    if not args.config and not args.input_npz:
        raise ValueError("Provide either -j/--json or -i/--input-npz.")

    cfg = _resolve_config(args)

    if args.input_npz:
        input_npz = Path(args.input_npz)
    else:
        input_npz = Path(cfg["output_dir"]).resolve() / "ed_predictions.npz"

    if not input_npz.exists():
        raise FileNotFoundError(f"Input NPZ not found: {input_npz}")

    if args.output_pdf:
        output_pdf = Path(args.output_pdf)
    else:
        output_pdf = input_npz.with_name(input_npz.stem + "_report.pdf")

    make_report(
        input_npz=input_npz,
        output_pdf=output_pdf,
        title=cfg["report_title"],
        verbose=bool(cfg["verbose"]),
    )


if __name__ == "__main__":
    main()
