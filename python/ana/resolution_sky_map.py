#!/usr/bin/env python3
"""Pointing resolution over the sky, in the DETECTOR frame, for the deployed configuration.

Deployed: scenario_8_full_pipeline_acc_t030 (CT v80 >= 0.30, E > 5 MeV, grid-mixture likelihood
with the detector-acceptance term, grid posterior mean), replayed on the r3 campaign
(`pipeline-campaign/v63_matchfix_1000_acc_t030/<cat>/scenario_cos_theta_report.json`).
Before: the campaign's own scenario_3_full_pipeline (CT v80 >= 0.80, emcee) from the r3 reports.

The TRUE burst direction of every cat is not in those jsons; it is rebuilt exactly as the
pipeline does (`_resolve_direction_inputs`: mean of the normalised neutrino momenta, metadata
columns 15-17, of the loaded clusters) from `volumes.npz` inside each cat's slim tar (read in
memory, nothing extracted) and cached in <out>/true_burst_dirs_1000.npz.  Cross-checked against
pole_dependence/pole_refit.npz (722 cats).

Cells are EQUAL-AREA "igloo" cells: bands in sin(latitude) whose heights are proportional to
their number of longitude cells.  Longitude = atan2(y, x), latitude = asin(z).  Schemes put
the +-z axes at the centres of the polar caps and the +-x/+-y axes at the centres of the four
cells of the equatorial band.  The burst directions of the campaign are random (not a lattice),
so the counts of equal-area cells fluctuate like Poisson; the schemes are the finest of that
family whose every cell holds >= 30 bursts.  Octant map: (|x|, |y|, |z|), 8x statistics,
triangular band pattern 1,3,5,7(,9) in |z| (equal area), drawn in a Lambert azimuthal
equal-area projection centred on the body diagonal (1,1,1)/sqrt3 so the three axes sit at
the corners of the spherical triangle and the coordinate planes on its sides.

theta68 = degrees(arccos(quantile(cos_to_truth, 0.32))) per cell, 68% bootstrap interval over the
cats of the cell (2000 resamples), median of the per-cat angle, N.

Cat sets: evaluation 2-399 + 901-1224 (722); "all" = the 1000 campaign cats (1-399, 623-1224
without 701) minus cat000001 (reduced CC statistics, flagged in the campaign) = 999, which
INCLUDES the 50 dev cats (623-672) and the 227 slice cats (673-900, in-sample for the tables).
Cats 400-621 are never read.

Usage:
  python3 python/ana/resolution_sky_map.py [--out <dir>] [--n-boot 2000]
"""
import argparse
import matplotlib.patheffects as pe
import io
import json
import tarfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402
from matplotlib.patches import Polygon  # noqa: E402

PC = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-campaign")
R3 = PC / "v63_matchfix_1000"
DEPLOYED = PC / "v63_matchfix_1000_acc_t030"
OUT_DEFAULT = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/combo_study/"
                   "resolution_maps")
POLE_REFIT = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/combo_study/"
                  "pole_dependence/pole_refit.npz")
SC_DEPLOYED = "scenario_8_full_pipeline_acc_t030"
SC_BEFORE = "scenario_3_full_pipeline"

CAMPAIGN_CATS = [n for n in list(range(1, 400)) + list(range(623, 1225)) if n != 701]
EVAL = [(2, 399), (901, 1224)]

# equal-area igloo schemes: number of longitude cells per sin(lat) band, north -> south
SCHEME_722 = [1, 5, 4, 5, 1]            # 16 cells
SCHEME_ALL = [1, 5, 4, 5, 1]            # same 16 cells (user choice 2026-10-01)
OCT_722 = [1, 3, 5, 7]                  # 16 cells in the octant
OCT_ALL = [1, 3, 5, 7, 9]               # 25 cells
AXIS_BINS = [(0.0, 15.0), (15.0, 35.0), (35.0, 54.75)]
MAP_ROT_DEG = 45.0   # Mollweide frame spans true longitude [-135, 225]: the 4-cell band (edges
                     # +-45, +-135) and the 5-cell bands (edges -135 + 72 k) end exactly on the frame


def disp_lon(lon):
    """true longitude -> display longitude (deg) of the rotated Mollweide frame"""
    return ((np.asarray(lon, dtype=float) - MAP_ROT_DEG + 180.0) % 360.0) - 180.0

AXES = {"+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0),
        "+z": (0, 0, 1), "-z": (0, 0, -1)}


def in_ranges(n, ranges):
    return any(lo <= n <= hi for lo, hi in ranges)


# ----------------------------------------------------------------------------- inputs
def true_burst_dirs(cache):
    if cache.is_file():
        z = np.load(cache)
        return dict(zip(z["cats"].astype(int).tolist(), z["truth"]))
    cats, truth = [], []
    for n in CAMPAIGN_CATS:
        tar = R3 / f"cat{n:06d}" / f"cat{n:06d}_scenarios_slim.tar"
        with tarfile.open(tar) as tf:
            names = sorted(x for x in tf.getnames()
                           if x.startswith(SC_BEFORE + "/") and x.endswith("volume_images/volumes.npz"))
            m = np.load(io.BytesIO(tf.extractfile(names[-1]).read()))["metadata"].astype(np.float64)
        v = m[:, 15:18]
        v = v[np.linalg.norm(v, axis=1) > 0]
        u = v / np.linalg.norm(v, axis=1, keepdims=True)
        mu = u.mean(axis=0)
        cats.append(n)
        truth.append(mu / np.linalg.norm(mu))
    np.savez(cache, cats=np.array(cats), truth=np.array(truth))
    return dict(zip(cats, truth))


def load_cos(root, scenario):
    out = {}
    for n in CAMPAIGN_CATS:
        f = root / f"cat{n:06d}" / "scenario_cos_theta_report.json"
        if not f.is_file():
            continue
        for s in json.loads(f.read_text()).get("scenarios", []):
            if s.get("scenario") == scenario and s.get("cos_to_truth") is not None \
                    and np.isfinite(s["cos_to_truth"]):
                out[n] = {"cos": float(s["cos_to_truth"]), "n_selected": int(s.get("n_selected", 0))}
    return out


# ----------------------------------------------------------------------------- statistics
def theta68(cos):
    return float(np.degrees(np.arccos(np.clip(np.quantile(np.asarray(cos), 0.32), -1, 1))))


def cell_stats(cos, rng, n_boot):
    cos = np.asarray(cos, dtype=np.float64)
    th = np.degrees(np.arccos(np.clip(cos, -1, 1)))
    t68 = theta68(cos)
    boots = np.array([theta68(cos[rng.integers(0, cos.size, cos.size)]) for _ in range(n_boot)])
    lo, hi = np.percentile(boots, [16, 84])
    return {"N": int(cos.size), "theta68": t68, "theta68_lo": float(lo), "theta68_hi": float(hi),
            "theta68_err": float(0.5 * (hi - lo)), "median": float(np.median(th)),
            "frac_gt30": float(np.mean(th > 30))}


# ----------------------------------------------------------------------------- cells
def igloo_edges(bands, zmin=-1.0):
    n = sum(bands)
    return [1.0 - (1.0 - zmin) * c / n for c in np.concatenate([[0], np.cumsum(bands)])]


def igloo_assign(dirs, bands):
    """Full-sky equal-area cells; longitude cells centred on lon 0 (so +x, +y, -x, -y sit at
    cell centres in a band of 4).  Returns cell index per dir and the cell geometry list."""
    z = dirs[:, 2]
    lon = np.degrees(np.arctan2(dirs[:, 1], dirs[:, 0]))
    edges = igloo_edges(bands)
    cell = np.full(len(dirs), -1)
    geo, k = [], 0
    for b, nb in enumerate(bands):
        hi, lo = edges[b], edges[b + 1]
        inb = (z <= hi) & ((z > lo) if b < len(bands) - 1 else (z >= lo))
        w = 360.0 / nb
        c0 = 0.0 if nb == 4 else 45.0   # axes at the centres of the 4-cell band; other bands
        #                                 start at the map frame (true lon -135) -> no cut cells
        idx = np.floor(((lon - c0 + w / 2) % 360) / w).astype(int) % nb
        cell[inb] = k + idx[inb]
        for j in range(nb):
            c = c0 + j * w  # centre longitude
            geo.append({"band": b, "lon_lo": c - w / 2, "lon_hi": c + w / 2, "lon_c": c,
                        "z_lo": lo, "z_hi": hi, "full_ring": nb == 1})
        k += nb
    return cell, geo


def octant_assign(adirs, bands):
    z = adirs[:, 2]
    lon = np.degrees(np.arctan2(adirs[:, 1], adirs[:, 0]))  # 0..90
    edges = igloo_edges(bands, zmin=0.0)
    cell = np.full(len(adirs), -1)
    geo, k = [], 0
    for b, nb in enumerate(bands):
        hi, lo = edges[b], edges[b + 1]
        inb = (z <= hi) & ((z > lo) if b < len(bands) - 1 else (z >= lo))
        w = 90.0 / nb
        idx = np.minimum((lon / w).astype(int), nb - 1)
        cell[inb] = k + idx[inb]
        for j in range(nb):
            geo.append({"band": b, "lon_lo": j * w, "lon_hi": (j + 1) * w, "lon_c": (j + 0.5) * w,
                        "z_lo": lo, "z_hi": hi, "full_ring": False})
        k += nb
    return cell, geo


def axis_angle(dirs):
    c = np.abs(dirs).max(axis=1)
    return np.degrees(np.arccos(np.clip(c, -1, 1)))


PERM = {}


def perm_test(cell, cos, ncell, rng, n_perm=2000):
    """Permutation test of direction independence: rms of the per-cell theta68 with the cats'
    errors shuffled across the cells (cell sizes kept), vs the observed rms."""
    def rms(cc):
        t = np.array([theta68(cc[cell == k]) for k in range(ncell)])
        return float(t.std())
    obs = rms(cos)
    null = np.array([rms(rng.permutation(cos)) for _ in range(n_perm)])
    return {"rms_obs": obs, "rms_null_mean": float(null.mean()), "rms_null_std": float(null.std()),
            "p_value": float((1 + np.sum(null >= obs)) / (1 + n_perm)), "n_perm": n_perm}


def build_map(cats, truth, cosd, assign, bands, rng, n_boot, key=None):
    dirs = np.array([truth[c] for c in cats])
    cell, geo = assign(dirs, bands)
    cos = np.array([cosd[c]["cos"] for c in cats])
    if key is not None:
        PERM[key] = perm_test(cell, cos, len(geo), rng)
    cells = []
    for k, g in enumerate(geo):
        m = cell == k
        st = cell_stats(cos[m], rng, n_boot)
        cells.append({"cell": k, **g, **st,
                      "lat_lo": float(np.degrees(np.arcsin(g["z_lo"]))),
                      "lat_hi": float(np.degrees(np.arcsin(g["z_hi"])))})
    return cells


# ----------------------------------------------------------------------------- drawing
def _cell_outline(g, npts=60):
    lons = np.linspace(g["lon_lo"], g["lon_hi"], npts)   # already display longitudes
    lat_lo = np.degrees(np.arcsin(g["z_lo"]))
    lat_hi = np.degrees(np.arcsin(g["z_hi"]))
    top = np.column_stack([lons, np.full(npts, lat_hi)])
    bot = np.column_stack([lons[::-1], np.full(npts, lat_lo)])
    return np.vstack([top, bot])


def _wrap_pieces(g):
    """Split a cell crossing lon = +-180 into the pieces drawable on a Mollweide axis."""
    lo, hi = g["lon_lo"], g["lon_hi"]
    if g["full_ring"]:
        return [dict(g, lon_lo=-180.0, lon_hi=180.0)]
    pieces = []
    for shift in (-360.0, 0.0, 360.0):
        a, b = max(lo + shift, -180.0), min(hi + shift, 180.0)
        if b > a:
            pieces.append(dict(g, lon_lo=a, lon_hi=b))
    return pieces


def draw_mollweide(ax, cells, norm, cmap, title, fontsize=7):
    ax.grid(False)
    for c in cells:
        col = cmap(norm(c["theta68"]))
        cd = dict(c)
        if not c["full_ring"]:
            lo, hi = disp_lon(c["lon_lo"]), disp_lon(c["lon_hi"])
            if hi <= lo:          # numerical wrap at the frame edge
                hi += 360.0
            cd.update(lon_lo=lo, lon_hi=hi)
        for p in _wrap_pieces(cd):
            xy = np.radians(_cell_outline(p))
            ax.add_patch(Polygon(xy, closed=True, facecolor=col, edgecolor="white", lw=0.8))
        lat_c = np.degrees(np.arcsin(0.5 * (c["z_lo"] + c["z_hi"])))
        if c["full_ring"]:
            la, lb = np.degrees(np.arcsin(c["z_lo"])), np.degrees(np.arcsin(c["z_hi"]))
            lat_c = la + 0.45 * (lb - la) if lb > 89 else lb - 0.45 * (lb - la)
            lon_c = 0.0
        else:
            lon_c = float(disp_lon(c["lon_c"]))
            if c["z_lo"] < 0 < c["z_hi"]:
                lat_c = -7.0  # below the axis name of the equatorial cells
        dark = norm(c["theta68"]) > 0.55
        ax.text(np.radians(lon_c), np.radians(lat_c),
                f"{c['theta68']:.1f}$\\pm${c['theta68_err']:.1f}\nN={c['N']}",
                ha="center", va="center", fontsize=fontsize, color="white",
                path_effects=[pe.withStroke(linewidth=1.6, foreground="black")])
    # no axis names inside the cells (user choice 2026-10-01): the title states where the axes are
    ax.set_xticks(np.radians([-120, -60, 0, 60, 120]))
    ax.set_xticklabels([])
    ax.set_yticks(np.radians([-60, -30, 0, 30, 60]))
    ax.tick_params(labelsize=7)
    ax.set_title(title + "\n(detector frame: +x at the centre of the middle equatorial cell, +y one cell to "
                 "its right, -x and -y beyond; +z / -z = the polar caps; cell text: "
                 "$\\theta_{68}\\pm$68% bootstrap [deg], N bursts)", fontsize=9.5, pad=14)


def lambert_octant(v):
    """Lambert azimuthal equal-area projection centred on (1,1,1)/sqrt3; +z up."""
    c = np.array([1.0, 1.0, 1.0]) / np.sqrt(3.0)
    e_up = np.array([-1.0, -1.0, 2.0]) / np.sqrt(6.0)
    e_right = np.cross(e_up, c)
    v = np.atleast_2d(v)
    k = np.sqrt(2.0 / (1.0 + v @ c))
    return np.column_stack([k * (v @ e_right), k * (v @ e_up)])


def _octant_outline(g, npts=40):
    lons = np.radians(np.linspace(g["lon_lo"], g["lon_hi"], npts))
    pts = []
    for z, ls in ((g["z_hi"], lons), (g["z_lo"], lons[::-1])):
        r = np.sqrt(max(0.0, 1 - z * z))
        pts.append(np.column_stack([r * np.cos(ls), r * np.sin(ls), np.full(npts, z)]))
    return lambert_octant(np.vstack(pts))


def draw_octant(ax, cells, norm, cmap, title):
    for c in cells:
        ax.add_patch(Polygon(_octant_outline(c), closed=True, facecolor=cmap(norm(c["theta68"])),
                             edgecolor="white", lw=0.8))
        zc = 0.5 * (c["z_lo"] + c["z_hi"])
        if c["band"] == 0:
            zc = c["z_lo"] + 0.35 * (c["z_hi"] - c["z_lo"])
        r = np.sqrt(1 - zc * zc)
        lc = np.radians(c["lon_c"])
        xy = lambert_octant(np.array([r * np.cos(lc), r * np.sin(lc), zc]))[0]
        dark = norm(c["theta68"]) > 0.55
        ax.text(xy[0], xy[1], f"{c['theta68']:.1f}$\\pm${c['theta68_err']:.1f}\nN={c['N']}",
                ha="center", va="center", fontsize=6.3, color="white",
                path_effects=[pe.withStroke(linewidth=1.6, foreground="black")])
    for name, v in (("|x|", (1, 0, 0)), ("|y|", (0, 1, 0)), ("|z|", (0, 0, 1))):
        xy = lambert_octant(np.array(v, dtype=float))[0]
        ax.annotate(name + " axis", xy, textcoords="offset points",
                    xytext=(0, 10) if name == "|z|" else ((-14, -12) if name == "|x|" else (14, -12)),
                    ha="center", fontsize=9, fontweight="bold")
    ax.set_aspect("equal")
    ax.set_xlim(-0.95, 0.95)
    ax.set_ylim(-0.7, 1.0)
    ax.axis("off")
    ax.set_title(title, fontsize=10)


# ----------------------------------------------------------------------------- tables
def md_cells(cells, octant=False):
    head = ("| cell | lon range [deg] | lat range [deg] | N | theta68 [deg] (68% boot) | median | "
            "frac>30 |\n|---|---|---|---|---|---|---|\n")
    lines = []
    for c in cells:
        lon = "all" if c["full_ring"] else f"{c['lon_lo']:.0f} .. {c['lon_hi']:.0f}"
        lines.append(f"| {c['cell']} | {lon} | {c['lat_lo']:.1f} .. {c['lat_hi']:.1f} | {c['N']} | "
                     f"**{c['theta68']:.2f}** [{c['theta68_lo']:.2f}, {c['theta68_hi']:.2f}] | "
                     f"{c['median']:.2f} | {c['frac_gt30']:.3f} |")
    return head + "\n".join(lines) + "\n"


def summary_line(cells):
    t = np.array([c["theta68"] for c in cells])
    n = np.array([c["N"] for c in cells])
    return (f"{len(cells)} cells, N per cell {n.min()}-{n.max()}; theta68 per cell "
            f"{t.min():.2f}-{t.max():.2f} deg (max/min {t.max() / t.min():.2f}), "
            f"rms spread {t.std():.2f} deg")


def chi2_flat(cells, overall):
    """chi2 of the cells against the overall theta68 using the bootstrap half-widths."""
    t = np.array([c["theta68"] for c in cells])
    e = np.array([c["theta68_err"] for c in cells])
    chi2 = float(np.sum(((t - overall) / e) ** 2))
    from scipy.stats import chi2 as C2
    return chi2, len(cells), float(C2.sf(chi2, len(cells) - 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=12345)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    truth = true_burst_dirs(out / "true_burst_dirs_1000.npz")
    # cross-check against the pole study's truth (722 cats)
    xchk = None
    if POLE_REFIT.is_file():
        z = np.load(POLE_REFIT)
        dev = [np.degrees(np.arccos(np.clip(np.dot(truth[int(c)], t), -1, 1)))
               for c, t in zip(z["cats"], z["truth"])]
        xchk = {"n": len(dev), "max_dev_deg": float(np.max(dev))}
    dep = load_cos(DEPLOYED, SC_DEPLOYED)
    bef = load_cos(R3, SC_BEFORE)
    eval_cats = [n for n in CAMPAIGN_CATS if in_ranges(n, EVAL) and n in dep]
    all_cats = [n for n in CAMPAIGN_CATS if n != 1 and n in dep]
    eval_bef = [n for n in eval_cats if n in bef]
    assert len(eval_cats) == 722, len(eval_cats)
    assert len(eval_bef) == 722, len(eval_bef)
    assert not any(400 <= n <= 621 for n in all_cats)

    overall = {
        "deployed_722": cell_stats([dep[c]["cos"] for c in eval_cats], rng, args.n_boot),
        "deployed_all": cell_stats([dep[c]["cos"] for c in all_cats], rng, args.n_boot),
        "before_722": cell_stats([bef[c]["cos"] for c in eval_bef], rng, args.n_boot),
    }
    maps = {
        "full_722": build_map(eval_cats, truth, dep, igloo_assign, SCHEME_722, rng, args.n_boot, key="full_722"),
        "full_all": build_map(all_cats, truth, dep, igloo_assign, SCHEME_ALL, rng, args.n_boot, key="full_all"),
        "before_full_722": build_map(eval_bef, truth, bef, igloo_assign, SCHEME_722, rng,
                                     args.n_boot, key="before_full_722"),
    }
    absT = {c: np.abs(truth[c]) for c in CAMPAIGN_CATS}
    maps["octant_722"] = build_map(eval_cats, absT, dep, octant_assign, OCT_722, rng, args.n_boot, key="octant_722")
    maps["octant_all"] = build_map(all_cats, absT, dep, octant_assign, OCT_ALL, rng, args.n_boot, key="octant_all")
    maps["before_octant_722"] = build_map(eval_bef, absT, bef, octant_assign, OCT_722, rng,
                                          args.n_boot, key="before_octant_722")

    # 1D profile vs angle to the nearest axis
    prof = {}
    for key, cats, src in (("deployed_722", eval_cats, dep), ("deployed_all", all_cats, dep),
                           ("before_722", eval_bef, bef)):
        ang = axis_angle(np.array([truth[c] for c in cats]))
        cos = np.array([src[c]["cos"] for c in cats])
        rows = []
        for lo, hi in AXIS_BINS:
            m = (ang >= lo) & (ang < hi)
            rows.append({"bin": [lo, hi], "mean_axis_angle": float(ang[m].mean()),
                         **cell_stats(cos[m], rng, args.n_boot)})
        prof[key] = rows

    # ------------------------------------------------------------------ figures
    cmap = plt.get_cmap("viridis")
    all_t = [c["theta68"] for k in maps for c in maps[k]]
    vmin, vmax = np.floor(min(all_t)), np.ceil(max(all_t))
    norm_common = Normalize(vmin=vmin, vmax=vmax)
    dep_t = [c["theta68"] for k in ("full_722", "full_all", "octant_722", "octant_all")
             for c in maps[k]]
    norm_dep = Normalize(vmin=np.floor(min(dep_t)), vmax=np.ceil(max(dep_t)))

    def cbar(fig, ax, norm, label=r"$\theta_{68}$ [deg]"):
        sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
        cb = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.05, pad=0.08, aspect=40)
        cb.set_label(label)

    dep_lab = "deployed (CT v80 $\\geq$ 0.30, E > 5 MeV, mixture + acceptance, grid mean)"
    for key, fname, title in (
            ("full_722", "sky_resolution_map_722.png",
             f"Pointing resolution vs true burst direction (detector frame), 722 evaluation cats\n"
             f"{dep_lab}; overall $\\theta_{{68}}$ = {overall['deployed_722']['theta68']:.2f}$^\\circ$"
             "\nlongitude = atan2(y,x) (0 at +x, +90 at +y), latitude = asin(z)"),
            ("full_all", "sky_resolution_map_1000.png",
             f"Same, all campaign cats (999: 722 eval + 50 dev + 227 slice [in-sample]; cat 1 flagged)\n"
             f"{dep_lab}; overall $\\theta_{{68}}$ = {overall['deployed_all']['theta68']:.2f}$^\\circ$")):
        fig = plt.figure(figsize=(11, 6.6))
        ax = fig.add_subplot(111, projection="mollweide")
        draw_mollweide(ax, maps[key], norm_dep, cmap, title, fontsize=7.5)
        cbar(fig, ax, norm_dep, r"$\theta_{68}$ per cell [deg]  (text: $\theta_{68}\pm$68% bootstrap, N bursts)")
        fig.savefig(out / fname, dpi=150, bbox_inches="tight")
        plt.close(fig)

    fig, axs = plt.subplots(1, 2, figsize=(13, 6.2))
    draw_octant(axs[0], maps["octant_722"], norm_dep, cmap,
                f"sign-folded (|x|,|y|,|z|), 722 eval cats, {len(maps['octant_722'])} cells")
    draw_octant(axs[1], maps["octant_all"], norm_dep, cmap,
                f"sign-folded, 999 cats (incl. dev + slice), {len(maps['octant_all'])} cells")
    fig.suptitle("Deployed configuration: resolution relative to the detector axes and coordinate "
                 "planes\n(Lambert equal-area projection centred on (1,1,1)/$\\sqrt{3}$; equal-area "
                 "cells; text $\\theta_{68}\\pm$68% bootstrap [deg], N)", fontsize=10)
    cbar(fig, axs, norm_dep)
    fig.savefig(out / "sky_resolution_folded.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig = plt.figure(figsize=(16, 6.2))
    for i, (key, lab, ok) in enumerate((
            ("before_full_722", "BEFORE: scenario_3_full_pipeline (CT v80 $\\geq$ 0.80, emcee)",
             "before_722"),
            ("full_722", "AFTER: scenario_8 deployed (CT $\\geq$ 0.30, mixture + acceptance)",
             "deployed_722"))):
        ax = fig.add_subplot(1, 2, i + 1, projection="mollweide")
        draw_mollweide(ax, maps[key], norm_common, cmap,
                       f"{lab}\n722 eval cats, overall $\\theta_{{68}}$ = {overall[ok]['theta68']:.2f}$^\\circ$",
                       fontsize=6.5)
    cbar(fig, fig.axes, norm_common, r"$\theta_{68}$ per cell [deg] (common scale)")
    fig.savefig(out / "sky_resolution_before_after.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.6))
    for key, lab, col, mk, dx in (("before_722", "before (scenario 3), 722 eval", "#888888", "s", -0.8),
                                  ("deployed_722", "deployed (scenario 8), 722 eval", "#1f77b4", "o", 0.0),
                                  ("deployed_all", "deployed, 999 cats (incl. dev + slice)", "#d62728", "^", 0.8)):
        x = np.array([r["mean_axis_angle"] for r in prof[key]]) + dx
        y = np.array([r["theta68"] for r in prof[key]])
        lo = y - np.array([r["theta68_lo"] for r in prof[key]])
        hi = np.array([r["theta68_hi"] for r in prof[key]]) - y
        ns = "/".join(str(r["N"]) for r in prof[key])
        ax.errorbar(x, y, yerr=[lo, hi], xerr=None, fmt=mk + "-", color=col, capsize=3,
                    label=f"{lab} (N = {ns})")
    for lo, hi in AXIS_BINS[1:]:
        ax.axvline(lo, color="k", lw=0.5, ls=":")
    ax.set_xlabel("angle between the true burst direction and the nearest detector axis [deg]\n"
                  "(bins 0-15, 15-35, 35-54.7; points at the mean angle of the bin)")
    ax.set_ylabel(r"$\theta_{68}$ [deg] (68% bootstrap)")
    ax.set_xlim(0, 55)
    ax.set_ylim(0, None)
    ax.legend(fontsize=8)
    ax.set_title("Resolution vs direction relative to the detector axes", fontsize=10)
    fig.savefig(out / "resolution_axis_profile.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # ------------------------------------------------------------------ tables
    flat = {k: chi2_flat(v, overall["before_722" if k.startswith("before") else
                                    ("deployed_all" if k.endswith("all") else "deployed_722")]["theta68"])
            for k, v in maps.items()}
    payload = {"overall": overall, "maps": maps, "axis_profile": prof,
               "schemes": {"full_722": SCHEME_722, "full_all": SCHEME_ALL, "octant_722": OCT_722,
                           "octant_all": OCT_ALL, "axis_bins": AXIS_BINS},
               "flatness_chi2": {k: {"chi2": v[0], "ncells": v[1], "p_value": v[2]}
                                 for k, v in flat.items()},
               "permutation_test": PERM,
               "truth_crosscheck_vs_pole_refit": xchk,
               "n_boot": args.n_boot, "seed": args.seed,
               "cats": {"eval": eval_cats, "all": all_cats}}
    (out / "resolution_maps.json").write_text(json.dumps(payload, indent=1) + "\n")

    L = []
    L.append("# Pointing resolution over the sky (detector frame), deployed configuration\n")
    L.append("*Generated by `python/ana/resolution_sky_map.py`.  Deployed = "
             "`scenario_8_full_pipeline_acc_t030` (CT v80 >= 0.30, E > 5 MeV, grid-mixture "
             "likelihood with the acceptance term, grid posterior mean) replayed on the r3 campaign "
             "(`pipeline-campaign/v63_matchfix_1000_acc_t030`).  Before = the campaign's "
             "`scenario_3_full_pipeline` (CT v80 >= 0.80, emcee) from the r3 reports.*\n")
    L.append("## Definitions\n")
    L.append("* theta68 = degrees(arccos(quantile(cos(reco, true burst), 0.32))) over the cats of the "
             f"cell; 68% interval from {args.n_boot} bootstrap resamples of those cats (the `+-` in the "
             "figures is half its width); median = median per-cat angle; frac>30 = fraction of cats "
             "with an error above 30 deg.")
    L.append("* True burst direction = the pipeline's own definition (mean normalised neutrino "
             "momentum of the loaded clusters, `volumes.npz` columns 15-17), read from each cat's "
             "slim tar in memory; it agrees with `pole_dependence/pole_refit.npz` to "
             f"{xchk['max_dev_deg']:.1e} deg on its {xchk['n']} cats." if xchk else "")
    L.append("* Longitude = atan2(y, x), latitude = asin(z), detector frame.  Cells are equal-area "
             "'igloo' cells: bands in sin(lat) whose heights are proportional to their number of "
             "longitude cells, the +-z axes at the centres of the polar caps and +x, +y, -x, -y at the "
             "centres of the four cells of the equatorial band.")
    L.append("* **Why fewer cells than 18-20 / ~33.**  The campaign's burst directions are random "
             "isotropic (not a lattice), so equal-area cell counts fluctuate like Poisson (722 cats in "
             "18 equal cells: 26-55 per cell).  Requiring >= 30 in EVERY cell, the finest equal-area "
             f"scheme of this family is {sum(SCHEME_722)} cells on 722 cats (`{SCHEME_722}`, "
             f"axes at cell centres) and {sum(SCHEME_ALL)} on 999 cats (`{SCHEME_ALL}`); 33 cells on "
             "999 cats would leave cells with ~18 bursts.  The octant maps use the triangular pattern "
             f"`{OCT_722}` ({sum(OCT_722)} cells, 722) and `{OCT_ALL}` ({sum(OCT_ALL)} cells, 999).")
    L.append("* Cat sets: 722 evaluation cats (2-399, 901-1224) = the headline.  '999 cats' = the 1000 "
             "campaign cats minus cat000001 (reduced CC statistics, flagged in the campaign); it "
             "INCLUDES the 50 dev cats (623-672) and the 227 slice cats (673-900), which are "
             "in-sample for the ES table / calibration / acceptance (their in-sample bias on theta68 "
             "is 0.04 deg: 7.20 vs 7.24).  Cats 400-621 are never read.\n")

    L.append("## Overall\n")
    L.append("| set | N | theta68 (68% boot) | median | frac>30 |\n|---|---|---|---|---|")
    for k, lab in (("deployed_722", "deployed, 722 eval"), ("deployed_all", "deployed, 999 (incl. dev+slice)"),
                   ("before_722", "before (scenario 3), 722 eval")):
        o = overall[k]
        L.append(f"| {lab} | {o['N']} | **{o['theta68']:.2f}** [{o['theta68_lo']:.2f}, "
                 f"{o['theta68_hi']:.2f}] | {o['median']:.2f} | {o['frac_gt30']:.3f} |")
    L.append("")
    L.append("Flatness test: chi2 of the per-cell theta68 against the overall value of the same set, "
             "with the bootstrap half-widths as errors (cells are disjoint, so independent):\n")
    L.append("| map | cells | chi2 | p (ndf = cells-1) |\n|---|---|---|---|")
    for k, v in flat.items():
        L.append(f"| {k} | {v[1]} | {v[0]:.1f} | {v[2]:.3g} |")
    L.append("")
    L.append("The bootstrap of a quantile on 30-60 cats is only approximate, so the robust test is a "
             "permutation test: the per-cat errors are shuffled across the cells (cell sizes kept) and "
             "the rms of the per-cell theta68 is compared with the observed one:\n")
    L.append("| map | rms of cell theta68, observed [deg] | same, shuffled (mean +- std) | p |\n|---|---|---|---|")
    for k, v in PERM.items():
        L.append(f"| {k} | {v['rms_obs']:.2f} | {v['rms_null_mean']:.2f} +- {v['rms_null_std']:.2f} | "
                 f"{v['p_value']:.2g} |")
    L.append("")

    for key, title, fig_ in (
            ("full_722", "(a) Full sky, 722 evaluation cats -- deployed", "sky_resolution_map_722.png"),
            ("full_all", "(b) Full sky, 999 cats INCLUDING dev and slice cats -- deployed",
             "sky_resolution_map_1000.png"),
            ("before_full_722", "(a') Full sky, 722 evaluation cats -- BEFORE (scenario 3)",
             "sky_resolution_before_after.png (left)"),
            ("octant_722", "(c) Sign-folded octant (|x|,|y|,|z|), 722 evaluation cats -- deployed",
             "sky_resolution_folded.png (left)"),
            ("octant_all", "(c) Sign-folded octant, 999 cats incl. dev + slice -- deployed",
             "sky_resolution_folded.png (right)"),
            ("before_octant_722", "(c') Sign-folded octant, 722 eval cats -- BEFORE (scenario 3), "
             "table only", "-")):
        L.append(f"## {title}\n")
        L.append(f"Figure: `{fig_}`.  {summary_line(maps[key])}.\n")
        if key.startswith("octant") or key.startswith("before_octant"):
            L.append("Longitude here is atan2(|y|, |x|) in 0-90 and latitude asin(|z|) in 0-90: "
                     "band 0 is the cap around the |z| axis; the last band touches the z = 0 plane, "
                     "its first cell holds the |x| axis and its last cell the |y| axis.\n")
        L.append(md_cells(maps[key]))

    L.append("## (d) Profile vs angle to the nearest of the six axes\n")
    L.append("Figure: `resolution_axis_profile.png`.\n")
    L.append("| set | 0-15 deg | 15-35 deg | 35-54.7 deg |\n|---|---|---|---|")
    for k, lab in (("deployed_722", "deployed, 722 eval"), ("deployed_all", "deployed, 999 incl. dev+slice"),
                   ("before_722", "before (scenario 3), 722 eval")):
        cells = [f"{r['theta68']:.2f} [{r['theta68_lo']:.2f}, {r['theta68_hi']:.2f}], med "
                 f"{r['median']:.2f}, N={r['N']}" for r in prof[k]]
        L.append(f"| {lab} | " + " | ".join(cells) + " |")
    L.append("")
    (out / "resolution_maps.md").write_text("\n".join(x for x in L if x is not None) + "\n")
    print(f"wrote {out}")
    for k in ("deployed_722", "deployed_all", "before_722"):
        print(k, json.dumps({kk: round(v, 3) if isinstance(v, float) else v
                             for kk, v in overall[k].items()}))
    for k, v in maps.items():
        print(k, summary_line(v), "chi2=%.1f p=%.3g" % (flat[k][0], flat[k][2]), PERM.get(k))
    for k, rows in prof.items():
        print(k, [(r["bin"], round(r["theta68"], 2), round(r["theta68_err"], 2), r["N"]) for r in rows])


if __name__ == "__main__":
    main()
