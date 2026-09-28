#!/usr/bin/env python3
"""
Build a calibration map P(ES | CT score, class prior) for a channel-tagging model
from its held-out balanced test set (test_predictions.npz written by the CT trainer).

Model:
  s = P(ES) softmax index 0 (labels: ES=0, CC=1)
  On the BALANCED test set (pi=0.5) an isotonic regression of 1[ES] on s gives
  p50(s) = P(ES | s, pi=0.5). The class-conditional likelihood ratio is then
      LR(s) = f_ES(s) / f_CC(s) = p50 / (1 - p50)
  and for an arbitrary class prior pi:
      P(ES | s, pi) = pi LR / (pi LR + 1 - pi)
  Also stores smoothed class-conditional histograms f_ES(s), f_CC(s) for reference.

Output npz keys:
  s_grid, lr_grid, p_es_balanced_grid, hist_edges, f_es_hist, f_cc_hist,
  n_es, n_cc, source, method, reliability_bin_centers, reliability_frac_es, reliability_n

Usage:
  python3 python/ana/build_ct_calibration.py \
      --test-npz .../ct_volume_v80_.../test_predictions.npz \
      --out data/ct_v80_calibration.npz --png data/ct_v80_calibration.png
"""
import argparse
from pathlib import Path

import numpy as np


def isotonic_fit(s, y, y_min=1e-3, y_max=1 - 1e-3):
    """Pool-adjacent-violators, increasing fit of y on s (no sklearn dependency)."""
    order = np.argsort(s, kind="stable")
    s_sorted = s[order]
    y_sorted = y[order].astype(np.float64)
    # blocks: (sum_y, n, s_min, s_max)
    vals, wts, lo, hi = [], [], [], []
    for si, yi in zip(s_sorted, y_sorted):
        vals.append(yi)
        wts.append(1.0)
        lo.append(si)
        hi.append(si)
        while len(vals) > 1 and vals[-2] > vals[-1]:
            v = (vals[-2] * wts[-2] + vals[-1] * wts[-1]) / (wts[-2] + wts[-1])
            w = wts[-2] + wts[-1]
            l, h = lo[-2], hi[-1]
            vals.pop(); wts.pop(); lo.pop(); hi.pop()
            vals[-1], wts[-1], lo[-1], hi[-1] = v, w, l, h
    centers = np.array([(a + b) / 2 for a, b in zip(lo, hi)])
    fitted = np.clip(np.array(vals), y_min, y_max)
    return centers, fitted, np.array(wts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-npz", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--png", default=None)
    ap.add_argument("--n-grid", type=int, default=401)
    ap.add_argument("--hist-bins", type=int, default=40)
    args = ap.parse_args()

    d = np.load(args.test_npz, allow_pickle=True)
    pred = np.asarray(d["predictions"], dtype=np.float64)
    labels = np.asarray(d["true_labels"]).astype(int)
    s = pred[:, 0] if pred.ndim == 2 else pred.ravel()  # P(ES): softmax index 0
    is_es = labels == 0
    n_es, n_cc = int(is_es.sum()), int((~is_es).sum())
    print(f"test set: n_ES={n_es} n_CC={n_cc} (balanced prior pi_test={n_es/(n_es+n_cc):.3f})")

    # isotonic P(ES | s) at the test-set prior
    pi_test = n_es / (n_es + n_cc)
    centers, fitted, wts = isotonic_fit(s, is_es.astype(float))
    s_grid = np.linspace(0.0, 1.0, args.n_grid)
    p_test_grid = np.interp(s_grid, centers, fitted, left=fitted[0], right=fitted[-1])
    # convert to a prior-free likelihood ratio: p = pi LR / (pi LR + 1 - pi)
    lr_grid = (p_test_grid / (1.0 - p_test_grid)) * ((1.0 - pi_test) / pi_test)
    lr_grid = np.clip(lr_grid, 1e-3, 1e3)
    p_es_balanced_grid = lr_grid / (lr_grid + 1.0)

    # class-conditional histogram densities (reference / plotting)
    edges = np.linspace(0.0, 1.0, args.hist_bins + 1)
    f_es_hist, _ = np.histogram(s[is_es], bins=edges, density=True)
    f_cc_hist, _ = np.histogram(s[~is_es], bins=edges, density=True)

    # reliability (binned empirical ES fraction on the test set)
    rel_edges = np.linspace(0.0, 1.0, 21)
    idx = np.clip(np.digitize(s, rel_edges) - 1, 0, 19)
    rel_n = np.bincount(idx, minlength=20)
    rel_es = np.bincount(idx, weights=is_es.astype(float), minlength=20)
    rel_frac = np.where(rel_n > 0, rel_es / np.maximum(rel_n, 1), np.nan)
    rel_centers = 0.5 * (rel_edges[:-1] + rel_edges[1:])

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        out,
        s_grid=s_grid,
        lr_grid=lr_grid,
        p_es_balanced_grid=p_es_balanced_grid,
        hist_edges=edges,
        f_es_hist=f_es_hist,
        f_cc_hist=f_cc_hist,
        n_es=n_es,
        n_cc=n_cc,
        pi_test=pi_test,
        source=str(args.test_npz),
        method="isotonic P(ES|s) on balanced test set -> LR=f_ES/f_CC; p(ES|s,pi)=pi LR/(pi LR+1-pi)",
        reliability_bin_centers=rel_centers,
        reliability_frac_es=rel_frac,
        reliability_n=rel_n,
    )
    print(f"saved {out}")

    # summary numbers
    for pi in (0.5, 0.09):
        p = pi * lr_grid / (pi * lr_grid + 1 - pi)
        for sv in (0.5, 0.8, 0.9):
            print(f"  pi={pi:.2f}: P(ES|s={sv:.1f}) = {np.interp(sv, s_grid, p):.3f}")
    print(f"  LR(s) at s=0.2/0.5/0.8/0.9: " + ", ".join(f"{np.interp(v, s_grid, lr_grid):.2f}" for v in (0.2, 0.5, 0.8, 0.9)))

    if args.png:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))
        ax = axes[0]
        c = 0.5 * (edges[:-1] + edges[1:])
        ax.step(c, f_es_hist, where="mid", label=f"ES (n={n_es})", color="#2a9d8f", lw=2)
        ax.step(c, f_cc_hist, where="mid", label=f"CC (n={n_cc})", color="#e76f51", lw=2)
        ax.set_xlabel("CT score s = P(ES)")
        ax.set_ylabel("density")
        ax.set_title("class-conditional score densities (test set)")
        ax.legend()
        ax.grid(alpha=0.3)
        ax = axes[1]
        ax.plot(rel_centers, rel_frac, "o", color="black", label="binned ES fraction (test)")
        ax.plot(s_grid, p_test_grid, "-", color="#264653", lw=2, label="isotonic fit")
        ax.plot([0, 1], [0, 1], "--", color="grey", lw=1)
        ax.set_xlabel("CT score s")
        ax.set_ylabel("P(ES | s)  at pi=%.2f" % pi_test)
        ax.set_title("reliability")
        ax.legend()
        ax.grid(alpha=0.3)
        ax = axes[2]
        for pi, col in ((0.5, "#264653"), (0.2, "#2a9d8f"), (0.09, "#e9c46a"), (0.05, "#e76f51")):
            p = pi * lr_grid / (pi * lr_grid + 1 - pi)
            ax.plot(s_grid, p, lw=2, color=col, label=f"pi={pi}")
        ax.axvline(0.8, color="grey", ls=":", label="scenario-3 threshold")
        ax.set_xlabel("CT score s")
        ax.set_ylabel("calibrated P(ES | s, pi)")
        ax.set_title("prior-adjusted calibration")
        ax.legend()
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(args.png, dpi=130)
        print(f"saved {args.png}")


if __name__ == "__main__":
    main()
