#!/usr/bin/env python3
"""Plot the detector-frame reco-direction density R(d) that the acceptance term uses.

Left/middle: raw relative density of reconstructed directions (equal-area lon x sin(lat)
bins, normalised to sphere mean 1) for true CC and true ES events of the deployed selection
(CT v80 >= t, E > 5 MeV) on the table-building slice.  Right: the band-limited (l <= 6)
fit stored next to the ED model, which is what the likelihood evaluates.  Bottom: radial
profile against the angle to the nearest detector axis.

R/(4 pi) is the pdf per steradian of a reconstructed direction in the detector frame.
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ana.combo_acceptance import band_limited_density  # noqa: E402

AXES = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], float)


def lonlat(d):
    return np.degrees(np.arctan2(d[:, 1], d[:, 0])), np.degrees(np.arcsin(np.clip(d[:, 2], -1, 1)))


def raw_density(dirs, nlon=72, nlat=36):
    lon, lat = lonlat(dirs)
    h, xe, ye = np.histogram2d(lon, np.sin(np.radians(lat)), bins=[nlon, nlat],
                               range=[[-180, 180], [-1, 1]])
    return h / h.mean(), xe, ye


def nearest_axis_angle(d):
    return np.degrees(np.arccos(np.clip((d @ AXES.T).max(axis=1), -1, 1)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/"
                    "r3_rescan/slice_cache_673_900.npz")
    ap.add_argument("--acceptance", default="/eos/project-e/ep-nu/evilla/sn-online-pointing/neural-networks/"
                    "electron_direction/three_plane_v63_matchfix_ft58_20260921_132520/"
                    "reco_acceptance_r3_v63_l6_ct030.npz")
    ap.add_argument("--threshold", type=float, default=0.30)
    ap.add_argument("--min-energy", type=float, default=5.0)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    z = np.load(a.cache, allow_pickle=True)
    sel = (z["proba"] >= a.threshold) & (z["energy"] > a.min_energy)
    dirs = np.asarray(z["dirs"], float)
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    cc, es = dirs[sel & ~z["is_es"]], dirs[sel & z["is_es"]]
    acc = np.load(a.acceptance, allow_pickle=True)
    coeffs, lmax = np.asarray(acc["coeffs"], float), int(acc["lmax"])

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(16, 8.5))
    gs = fig.add_gridspec(2, 3, height_ratios=[1.15, 1.0])
    vmin, vmax = 0.0, 2.0
    cmap = "RdBu_r"

    def mollweide(ax, dens, xe, ye, title):
        lon = np.radians(xe)
        lat = np.arcsin(ye)
        m = ax.pcolormesh(lon, lat, dens.T, vmin=vmin, vmax=vmax, cmap=cmap, shading="flat",
                          rasterized=True)
        for v, lab in [((0, 0), "+x"), ((np.pi, 0), "-x"), ((np.pi / 2, 0), "+y"),
                       ((-np.pi / 2, 0), "-y"), ((0, np.pi / 2 - 0.02), "+z"), ((0, -np.pi / 2 + 0.02), "-z")]:
            ax.plot(v[0], v[1], "k+", ms=9, mew=1.5)
            ax.annotate(lab, v, xytext=(5, 4), textcoords="offset points", fontsize=9)
        ax.set_title(title, fontsize=11)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=7)
        return m

    dcc, xe, ye = raw_density(cc)
    des, _, _ = raw_density(es)
    ax1 = fig.add_subplot(gs[0, 0], projection="mollweide")
    mollweide(ax1, dcc, xe, ye, f"raw: true CC reco directions, N={len(cc):,}")
    ax2 = fig.add_subplot(gs[0, 1], projection="mollweide")
    mollweide(ax2, des, xe, ye, f"raw: true ES reco directions, N={len(es):,}")

    # fitted R on the same bin centres
    lonc = 0.5 * (xe[1:] + xe[:-1])
    latc = np.degrees(np.arcsin(0.5 * (ye[1:] + ye[:-1])))
    LON, LAT = np.meshgrid(np.radians(lonc), np.radians(latc), indexing="ij")
    grid = np.stack([np.cos(LAT) * np.cos(LON), np.cos(LAT) * np.sin(LON), np.sin(LAT)], axis=-1).reshape(-1, 3)
    rfit = band_limited_density(coeffs, grid, lmax)[0].reshape(len(lonc), len(latc))
    ax3 = fig.add_subplot(gs[0, 2], projection="mollweide")
    m = mollweide(ax3, rfit, xe, ye, f"deployed: R(d), real SH fit l<={lmax} of the CC map")
    cb = fig.colorbar(m, ax=[ax1, ax2, ax3], orientation="horizontal", fraction=0.04, pad=0.08, aspect=50)
    cb.set_label("relative density of reconstructed directions in the detector frame  (isotropic = 1;  pdf = R / 4pi)")

    # radial profiles
    ax4 = fig.add_subplot(gs[1, :])
    edges = np.arange(0, 56, 2.0)
    mid = 0.5 * (edges[1:] + edges[:-1])
    # expected isotropic fraction per shell from a fine uniform grid
    rng = np.random.default_rng(1)
    u = rng.normal(size=(2_000_000, 3)); u /= np.linalg.norm(u, axis=1, keepdims=True)
    iso, _ = np.histogram(nearest_axis_angle(u), bins=edges)
    iso = iso / iso.sum()
    for d, lab, c in [(cc, "true CC (raw)", "C3"), (es, "true ES (raw)", "C0")]:
        h, _ = np.histogram(nearest_axis_angle(d), bins=edges)
        h = h / h.sum()
        ax4.step(mid, h / iso, where="mid", label=lab, color=c, lw=1.8)
    ang_u = nearest_axis_angle(u[:400_000])
    r_u = band_limited_density(coeffs, u[:400_000], lmax)[0]
    prof = np.array([r_u[(ang_u >= lo) & (ang_u < hi)].mean() for lo, hi in zip(edges[:-1], edges[1:])])
    ax4.plot(mid, prof, "k-", lw=2.2, label=f"deployed fit R(d), l<={lmax}")
    ax4.axhline(1, color="grey", ls=":")
    ax4.set_xlabel("angle of the reconstructed direction to the nearest detector axis [deg]")
    ax4.set_ylabel("density / isotropic")
    ax4.set_xlim(0, 54.7)
    ax4.grid(True, alpha=0.3)
    ax4.legend(loc="upper right")
    fig.suptitle("Detector-frame reconstructed-direction density used by the acceptance term\n"
                 f"selection: CT v80 >= {a.threshold:.2f}, E > {a.min_energy:g} MeV, slice cats "
                 f"{int(acc['slice_cats'][0])}-{int(acc['slice_cats'][1])}, ED {acc['ed_model']}", fontsize=12, y=0.99)
    fig.subplots_adjust(hspace=0.35)
    fig.savefig(a.out, dpi=150, bbox_inches="tight")
    print("wrote", a.out)
    # numbers
    for d, lab in [(cc, "CC"), (es, "ES")]:
        ang = nearest_axis_angle(d)
        print(f"{lab}: frac within 10 deg of an axis {np.mean(ang < 10):.3f} (isotropic {np.mean(nearest_axis_angle(u) < 10):.3f}); "
              f"density ratio <10 deg / >40 deg = {(np.mean(ang < 10) / np.mean(nearest_axis_angle(u) < 10)) / (np.mean(ang > 40) / np.mean(nearest_axis_angle(u) > 40)):.2f}")
    print("fit R range", r_u.min().round(3), r_u.max().round(3), "mean", r_u.mean().round(4))


if __name__ == "__main__":
    main()
