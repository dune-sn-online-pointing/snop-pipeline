#!/usr/bin/env python3
"""
Offline re-evaluation of the mixture-ct (scenario 7) likelihood on kept per-event outputs.

Reads, per cat, <root>/<cat>/scenario_7_mixture_ct/pipeline_run_*/predictions/mixture_events.npz
(written by scenario_cos_theta_report.py in mixture-ct mode: ALL loaded events with reco
direction, reco energy, raw CT score, truth flags, true nu/electron directions, true burst dir)
and recomputes the grid posterior for a list of variants:

  - pi: truth-based (run's own ES fraction) vs fixed
  - energy cut: none vs E > 5 MeV
  - CC pdf: measured table vs flat
  - CT threshold-free vs soft floor (drop events with score < s_min) / p floor
  - "scenario-3 likelihood with clipped lookup": pure-ES pdf on the scenario-3 selection
    (score >= 0.8 and E > 5 MeV, p_i = 1), same grid -> isolates the lookup fix from the mixture
  - "true tags": p_i = 1 for true ES, 0 otherwise (unit check against scenario 2)
  - "true ES only, clipped": scenario-2 selection with the pure-ES pdf on the grid

For every variant and cat: single-pass theta (posterior mean vs truth), MAP theta, HPD-68
radius, truth-in-HPD68 flag, sum of weights. Aggregates: 68% containment of theta across
cats (arccos of the 32% quantile of cos, as aggregate_scenario_reports.py), median theta,
fraction > 30 deg, coverage.

Usage:
  python3 python/ana/mixture_offline_variants.py --input-root <dev output base> \
      --pdf-es data/cosine_energy_pdf.npz --pdf-cc data/cosine_energy_pdf_cc.npz \
      --calibration data/ct_v80_calibration.npz --out-json <json> --out-md <md>

Additive second mode (--decompose): the (selection x sampler x lookup) 2x2, which
separates the two things that differ between in-pipeline scenario 3 and the
scenario-7 style offline re-evaluation -- the pdf lookup (the buggy
RegularGridInterpolator with fill_value=1e-10 outside the cos bin centres, vs the
clipped/floored mixture lookup) and the aggregator (the pipeline's own emcee vs
the exhaustive grid posterior).  Nothing above changes; the default run is
identical to before.

  # cheap: the two grid cells for both selections
  python3 python/ana/mixture_offline_variants.py ... --decompose --decompose-samplers grid
  # the emcee cells (one condor job per cell, see condor/mixture_dev/decomp_*.sub)
  python3 python/ana/mixture_offline_variants.py ... --decompose --decompose-samplers emcee \
      --decompose-selections sc3 --decompose-lookups hole --repeats 3 --resume
  # merge the per-cell jsons into the final table
  python3 python/ana/mixture_offline_variants.py ... --merge a.json,b.json,... \
      --reference-json ref.json --reference-per-cat-json ref_percat.json
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

python_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(python_root))

from ana.burst_direction import (  # noqa: E402
    angular_error_deg,
    calibrated_p_es,
    cc_map_lookup,
    fibonacci_sphere_grid,
    load_cc_direction_map,
    flat_pdf_table,
    grid_mixture_posterior,
    hpd_region_from_grid,
    load_ct_calibration,
    load_pdf_table,
    normalize_vector,
)


def smooth_table(table, k):
    """Moving-average smoothing (2k+1 bins, edge-padded) of each energy row, renormalised."""
    out = dict(table)
    pdf = np.asarray(table["pdf"], dtype=np.float64).copy()
    if k > 0:
        ker = np.ones(2 * k + 1) / (2 * k + 1)
        pdf = np.array([np.convolve(np.pad(r, (k, k), mode="edge"), ker, mode="valid") for r in pdf])
        w = table["cos_edges"][1:] - table["cos_edges"][:-1]
        pdf /= (pdf * w[None, :]).sum(axis=1, keepdims=True)
    out["pdf"] = pdf
    return out


def _latest_run(scenario_dir: Path):
    runs = sorted(scenario_dir.glob("pipeline_run_*"))
    return runs[-1] if runs else None


def load_events(root: Path, scenario_name="scenario_7_mixture_ct"):
    out = {}
    for cat_dir in sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("cat")):
        run = _latest_run(cat_dir / scenario_name)
        if run is None:
            continue
        f = run / "predictions" / "mixture_events.npz"
        if not f.exists():
            continue
        d = np.load(f, allow_pickle=True)
        out[cat_dir.name] = {k: d[k] for k in d.files}
    return out


VARIANTS = [
    # name, dict(sel: 'all'|'sc3'|'true_es', p: 'ct'|'truth'|'one', pi: 'truth'|float, emin: float, cc: 'table'|'flat', s_min: None|float, p_floor: float)
    ("mix: pi=truth, no E cut, CC table (scenario 7 as run)", dict(sel="all", p="ct", pi="truth", emin=0.0, cc="table")),
    ("mix: pi=0.09 fixed, no E cut, CC table",               dict(sel="all", p="ct", pi=0.09, emin=0.0, cc="table")),
    ("mix: pi=truth, E>5 MeV, CC table",                      dict(sel="all", p="ct", pi="truth", emin=5.0, cc="table")),
    ("mix: pi=0.09 fixed, E>5 MeV, CC table",                 dict(sel="all", p="ct", pi=0.09, emin=5.0, cc="table")),
    ("mix: pi=truth, no E cut, CC FLAT",                      dict(sel="all", p="ct", pi="truth", emin=0.0, cc="flat")),
    ("mix: pi=truth, E>5 MeV, CC FLAT",                       dict(sel="all", p="ct", pi="truth", emin=5.0, cc="flat")),
    ("mix: pi=truth, no E cut, CC table, soft floor s>=0.3",  dict(sel="all", p="ct", pi="truth", emin=0.0, cc="table", s_min=0.3)),
    ("mix: pi=truth, no E cut, CC table, soft floor s>=0.5",  dict(sel="all", p="ct", pi="truth", emin=0.0, cc="table", s_min=0.5)),
    ("mix: pi=truth, no E cut, CC table, p floor 0.02",       dict(sel="all", p="ct", pi="truth", emin=0.0, cc="table", p_floor=0.02)),
    ("mix: pi=0.5 (uncalibrated-like), no E cut, CC table",   dict(sel="all", p="ct", pi=0.5, emin=0.0, cc="table")),
    ("sc3 selection (s>=0.8, E>5), pure-ES pdf, clipped grid", dict(sel="sc3", p="one", pi="truth", emin=5.0, cc="table")),
    ("sc3 selection (s>=0.8, E>5), mixture weights, CC table", dict(sel="sc3", p="ct", pi="truth", emin=5.0, cc="table")),
    ("true tags in mixture (p=1 ES / 0 CC), no E cut",         dict(sel="all", p="truth", pi="truth", emin=0.0, cc="table")),
    ("true ES only (sc2 selection, E>3), pure-ES pdf, clipped grid", dict(sel="true_es", p="one", pi="truth", emin=3.0, cc="table")),
    # --- variants with the re-derived ES table vs the NEUTRINO axis (requires --pdf-es-alt) ---
    ("ESnu: mix pi=truth, no E cut, CC FLAT",                  dict(sel="all", p="ct", pi="truth", emin=0.0, cc="flat", es="alt")),
    ("ESnu: mix pi=truth, E>5 MeV, CC FLAT",                   dict(sel="all", p="ct", pi="truth", emin=5.0, cc="flat", es="alt")),
    ("ESnu: mix pi=0.09 fixed, no E cut, CC FLAT",             dict(sel="all", p="ct", pi=0.09, emin=0.0, cc="flat", es="alt")),
    ("ESnu: mix pi=truth, no E cut, CC table",                 dict(sel="all", p="ct", pi="truth", emin=0.0, cc="table", es="alt")),
    ("ESnu: mix pi=truth, no E cut, CC FLAT, soft floor s>=0.5", dict(sel="all", p="ct", pi="truth", emin=0.0, cc="flat", es="alt", s_min=0.5)),
    ("ESnu: sc3 selection (s>=0.8, E>5), pure-ES pdf, grid",   dict(sel="sc3", p="one", pi="truth", emin=5.0, cc="flat", es="alt")),
    ("ESnu: true tags in mixture (p=1/0), CC FLAT",            dict(sel="all", p="truth", pi="truth", emin=0.0, cc="flat", es="alt")),
    ("ESnu: true ES only (sc2 selection, E>3), pure-ES pdf, grid", dict(sel="true_es", p="one", pi="truth", emin=3.0, cc="flat", es="alt")),
    # --- CC component = detector-frame density map q(d) of CC reco directions (requires --cc-map) ---
    ("CCmap: mix pi=truth, no E cut, orig ES table",             dict(sel="all", p="ct", pi="truth", emin=0.0, cc="map")),
    ("CCmap: mix pi=0.09 fixed, no E cut, orig ES table",        dict(sel="all", p="ct", pi=0.09, emin=0.0, cc="map")),
    ("CCmap: mix pi=truth, E>5 MeV, orig ES table",              dict(sel="all", p="ct", pi="truth", emin=5.0, cc="map")),
    ("CCmap: mix pi=truth, no E cut, soft floor s>=0.5",         dict(sel="all", p="ct", pi="truth", emin=0.0, cc="map", s_min=0.5)),
    ("CCmap: mix pi=truth, no E cut, soft floor s>=0.8",         dict(sel="all", p="ct", pi="truth", emin=0.0, cc="map", s_min=0.8)),
    ("CCmap: sc3 selection (s>=0.8, E>5), mixture weights",      dict(sel="sc3", p="ct", pi="truth", emin=5.0, cc="map")),
    ("CCmap+ESnu: mix pi=truth, no E cut",                       dict(sel="all", p="ct", pi="truth", emin=0.0, cc="map", es="alt")),
    ("CCmap+ESnu: mix pi=truth, E>5 MeV",                        dict(sel="all", p="ct", pi="truth", emin=5.0, cc="map", es="alt")),
    ("CCmap+ESnu: mix pi=truth, no E cut, soft floor s>=0.5",    dict(sel="all", p="ct", pi="truth", emin=0.0, cc="map", es="alt", s_min=0.5)),
    ("CCmap+ESsmooth5: mix pi=truth, no E cut",                  dict(sel="all", p="ct", pi="truth", emin=0.0, cc="map", es_smooth=5)),
    ("ESsmooth5: true ES only (sc2 selection, E>3), pure-ES pdf", dict(sel="true_es", p="one", pi="truth", emin=3.0, cc="flat", es_smooth=5)),
    ("ESsmooth5: sc3 selection (s>=0.8, E>5), pure-ES pdf",      dict(sel="sc3", p="one", pi="truth", emin=5.0, cc="flat", es_smooth=5)),
    # --- reference: plain (weighted) vector sums, no likelihood ---
    ("REF: vector sum, weights = calibrated p (pi=truth)",     dict(sel="all", p="ct", pi="truth", emin=0.0, cc="flat", vecsum=True)),
    ("REF: vector sum, true ES only (E>3)",                     dict(sel="true_es", p="one", pi="truth", emin=3.0, cc="flat", vecsum=True)),
    ("REF: vector sum, sc3 selection (s>=0.8, E>5)",            dict(sel="sc3", p="one", pi="truth", emin=5.0, cc="flat", vecsum=True)),
]


def run_variant(ev, cfg, tables, calib, grid_n):
    dirs = np.asarray(ev["reco_dirs"], dtype=np.float64)
    energy = np.asarray(ev["energy"], dtype=np.float64)
    score = np.asarray(ev["ct_score"], dtype=np.float64)
    is_es = np.asarray(ev["is_es_true"], dtype=bool)
    truth = normalize_vector(np.asarray(ev["true_burst_dir"], dtype=np.float64))
    n_loaded = int(ev["n_loaded"]) if "n_loaded" in ev else dirs.shape[0]
    n_true_es_loaded = int(ev["n_true_es_loaded"]) if "n_true_es_loaded" in ev else int(is_es.sum())
    pi = n_true_es_loaded / max(n_loaded, 1) if cfg["pi"] == "truth" else float(cfg["pi"])
    pi = float(np.clip(pi, 1e-4, 1 - 1e-4))

    sel = np.ones(dirs.shape[0], dtype=bool)
    if cfg["sel"] == "sc3":
        sel &= (score >= 0.8)
    elif cfg["sel"] == "true_es":
        sel &= is_es
    if cfg["emin"] > 0:
        sel &= energy >= cfg["emin"]

    if cfg["p"] == "ct":
        p = calibrated_p_es(score, calib, pi)
        s_min = cfg.get("s_min")
        p_floor = float(cfg.get("p_floor", 0.0))
        if s_min is not None:
            p = np.where(score >= s_min, p, p_floor)
        if p_floor > 0:
            p = np.maximum(p, p_floor)
    elif cfg["p"] == "truth":
        p = is_es.astype(np.float64)
    else:
        p = np.ones(dirs.shape[0])

    pdf_cc = tables["cc"] if cfg["cc"] == "table" else tables["flat"]
    pdf_es = tables["es_alt"] if cfg.get("es") == "alt" else tables["es"]
    if pdf_es is None:
        return None
    if cfg.get("es_smooth"):
        pdf_es = smooth_table(pdf_es, int(cfg["es_smooth"]))
    cc_const = None
    if cfg["cc"] == "map":
        if tables.get("cc_map") is None:
            return None
        cc_const = cc_map_lookup(tables["cc_map"], dirs)
    d, e, pp = dirs[sel], energy[sel], p[sel]
    if d.shape[0] == 0:
        return None
    if cfg.get("vecsum"):
        v = normalize_vector(np.sum(d * pp[:, None], axis=0))
        if v is None:
            return None
        return {"theta_deg": angular_error_deg(v, truth), "map_theta_deg": float("nan"),
                "cos": float(np.clip(np.dot(v, truth), -1, 1)), "hpd68_radius_deg": float("nan"),
                "truth_in_hpd68": False, "n_used": int(d.shape[0]), "sum_p": float(np.sum(pp)),
                "n_true_es_used": int(np.sum(is_es[sel])), "pi": pi}
    grid, log_like, post = grid_mixture_posterior(d, e, pp, pdf_es, pdf_cc, grid_n=grid_n,
                                                  cc_const_per_event=None if cc_const is None else cc_const[sel])
    mean_dir = normalize_vector(np.sum(post[:, None] * grid, axis=0))
    map_dir = grid[int(np.argmax(post))]
    hpd = hpd_region_from_grid(post, 0.68)
    truth_idx = int(np.argmax(grid @ truth))
    return {
        "theta_deg": angular_error_deg(mean_dir, truth),
        "map_theta_deg": angular_error_deg(map_dir, truth),
        "cos": float(np.clip(np.dot(mean_dir, truth), -1, 1)),
        "hpd68_radius_deg": hpd["radius_deg"],
        "truth_in_hpd68": bool(hpd["members"][truth_idx]),
        "n_used": int(d.shape[0]),
        "sum_p": float(np.sum(pp)),
        "n_true_es_used": int(np.sum(is_es[sel])),
        "pi": pi,
    }


def aggregate(rows):
    th = np.array([r["theta_deg"] for r in rows], dtype=float)
    cos = np.array([r["cos"] for r in rows], dtype=float)
    return {
        "n_cats": int(len(rows)),
        "theta68_from_cos_deg": float(np.degrees(np.arccos(np.clip(np.quantile(cos, 0.32), -1, 1)))),
        "theta_median_deg": float(np.median(th)),
        "theta_mean_deg": float(np.mean(th)),
        "frac_gt_30deg": float(np.mean(th > 30.0)),
        "map_theta_median_deg": float(np.nanmedian([r["map_theta_deg"] for r in rows])),
        "hpd68_radius_median_deg": float(np.nanmedian([r["hpd68_radius_deg"] for r in rows])),
        "coverage68": float(np.mean([r["truth_in_hpd68"] for r in rows])),
        "n_used_mean": float(np.mean([r["n_used"] for r in rows])),
        "sum_p_mean": float(np.mean([r["sum_p"] for r in rows])),
        "pi_mean": float(np.mean([r["pi"] for r in rows])),
    }



# ===========================================================================
# Lookup x sampler decomposition (additive; nothing above this line changes)
# ===========================================================================
#
# Scenarios 1-6 evaluate the ES pdf through burst_direction.load_pdf_interpolator,
# a scipy RegularGridInterpolator over (energy bin centres, cos bin centres) with
# bounds_error=False and fill_value=1e-10.  The cos grid is the BIN CENTRES,
# [-0.99, +0.99], so any event whose cos to the trial direction exceeds 0.99 in
# absolute value (a ~8.1 deg cap around the event direction and around its
# antipode) is evaluated as 1e-10 -> log(1e-10) = -23.03, instead of the true
# (large) forward pdf value.  The scenario-7 mixture code instead CLIPS cos and
# energy into the table range and floors/renormalises the table.
#
# The four cells below separate the two changes:
#   A grid   + clipped     C emcee + clipped
#   B grid   + hole        D emcee + hole   (= the in-pipeline configuration)
# The lookup is the SAME callable in both samplers, so the only differences
# between cells are the two intended axes.

_HOLE_FILL = 1e-10


class PdfLookup:
    """Energy-cosine pdf lookup in one of the two pipeline conventions.

    mode="hole"    : RAW pdf_2d, bilinear on the (energy centre, cos centre) grid,
                     fill_value=1e-10 outside the grid in EITHER dimension, then
                     max(., 1e-10).  Byte-for-byte the behaviour of
                     burst_direction.load_pdf_interpolator(mode="hole") + _pdf_likelihood
                     (the pipeline default before 2026-09-04).
    mode="clipped" : table floored at pdf_floor and renormalised per energy row
                     (load_pdf_table), energy and cos CLIPPED into the centre
                     range, same bilinear interpolation.  The mixture convention.

    Both evaluate in linear pdf space (RegularGridInterpolator does), so the two
    cells differ only by the fill/clip and the floor.
    """

    def __init__(self, pdf_path, mode="clipped", pdf_floor=1e-4):
        data = np.load(pdf_path, allow_pickle=True)
        self.mode = mode
        self.path = str(pdf_path)
        raw = np.asarray(data["pdf_2d"], dtype=np.float64)
        self.e_centers = np.asarray(data["energy_bins"], dtype=np.float64).mean(axis=1)
        self.c_centers = np.asarray(data["cosine_bin_centers"], dtype=np.float64)
        if mode == "clipped":
            self.pdf = load_pdf_table(pdf_path, pdf_floor=pdf_floor)["pdf"]
        elif mode == "hole":
            self.pdf = raw
        else:
            raise ValueError(f"unknown lookup mode: {mode}")
        self.dc = self.c_centers[1] - self.c_centers[0]
        self.n_c = self.c_centers.shape[0]

    def rows(self, energies):
        """Per-event pdf row over the cos centres, linear in energy.

        Returns (rows (N, n_cos), out_of_range_energy (N,) bool)."""
        e = np.asarray(energies, dtype=np.float64)
        out_e = (e < self.e_centers[0]) | (e > self.e_centers[-1])
        ec = np.clip(e, self.e_centers[0], self.e_centers[-1])
        hi = np.clip(np.searchsorted(self.e_centers, ec, side="right"), 1, len(self.e_centers) - 1)
        lo = hi - 1
        denom = self.e_centers[hi] - self.e_centers[lo]
        frac = np.where(denom > 0, (ec - self.e_centers[lo]) / np.where(denom > 0, denom, 1.0), 0.0)
        rows = self.pdf[lo] * (1.0 - frac)[:, None] + self.pdf[hi] * frac[:, None]
        if self.mode == "clipped":
            out_e = np.zeros_like(out_e)
        return rows, out_e

    def eval(self, rows, out_e, cos_values):
        """Evaluate the per-event rows at cos_values (N, G) -> (N, G) pdf values."""
        c = np.asarray(cos_values, dtype=np.float64)
        out_c = (c < self.c_centers[0]) | (c > self.c_centers[-1])
        cc = np.clip(c, self.c_centers[0], self.c_centers[-1])
        t = (cc - self.c_centers[0]) / self.dc
        idx = np.clip(np.floor(t).astype(np.int64), 0, self.n_c - 2)
        fr = t - idx
        v0 = np.take_along_axis(rows, idx, axis=1)
        v1 = np.take_along_axis(rows, idx + 1, axis=1)
        v = v0 * (1.0 - fr) + v1 * fr
        if self.mode == "hole":
            v = np.where(out_c | out_e[:, None], _HOLE_FILL, v)
            v = np.maximum(v, _HOLE_FILL)
        else:
            v = np.maximum(v, 1e-300)
        return v

    def in_hole(self, energies, cos_values):
        """Boolean (N, G): would this (energy, cos) pair hit the fill value?"""
        e = np.asarray(energies, dtype=np.float64)
        out_e = (e < self.e_centers[0]) | (e > self.e_centers[-1])
        c = np.asarray(cos_values, dtype=np.float64)
        out_c = (c < self.c_centers[0]) | (c > self.c_centers[-1])
        return out_c | out_e[:, None]


class _EmceeInterpAdapter:
    """Wrap a PdfLookup so _run_emcee/_pdf_likelihood can call it like the
    RegularGridInterpolator: f(points) with points = [[E_i, cos_i], ...].

    The energy column is identical on every call (it is the fixed selected_energies
    array), so the per-event rows are built once and reused; the first call
    validates that assumption."""

    def __init__(self, lookup, energies):
        self.lookup = lookup
        self.energies = np.asarray(energies, dtype=np.float64)
        self.rows, self.out_e = lookup.rows(self.energies)
        self._checked = False

    def __call__(self, points):
        points = np.atleast_2d(np.asarray(points, dtype=np.float64))
        if not self._checked:
            if points.shape[0] != self.energies.shape[0] or not np.allclose(points[:, 0], self.energies):
                raise ValueError("energy column changed between calls; adapter assumption broken")
            self._checked = True
        return self.lookup.eval(self.rows, self.out_e, points[:, 1][:, None])[:, 0]


def grid_posterior_lookup(dirs, energies, lookup, grid_n=41253, chunk=2048):
    """Exact posterior on the Fibonacci grid using `lookup` (uniform prior, p_i = 1).

    log L(n) = sum_i log lookup(E_i, d_i . n)  -- the same likelihood the emcee
    sampler explores, evaluated exhaustively instead of sampled."""
    dirs = np.asarray(dirs, dtype=np.float64)
    rows, out_e = lookup.rows(energies)
    grid = fibonacci_sphere_grid(int(grid_n))
    log_like = np.empty(grid.shape[0], dtype=np.float64)
    for s in range(0, grid.shape[0], int(chunk)):
        g = grid[s:s + chunk]
        v = lookup.eval(rows, out_e, np.clip(dirs @ g.T, -1.0, 1.0))
        log_like[s:s + chunk] = np.sum(np.log(v), axis=0)
    post = np.exp(log_like - np.max(log_like))
    post /= np.sum(post)
    return grid, log_like, post


DECOMP_SELECTIONS = {
    # name: (predicate on (score, energy, is_es_true), label)
    "sc3": ("scenario-3 selection (CT score >= 0.80, E > 5 MeV)",
            lambda s, e, es: (s >= 0.8) & (e >= 5.0)),
    "sc2": ("scenario-2 selection (true ES, E > 3 MeV)",
            lambda s, e, es: es & (e >= 3.0)),
}


def _decomp_select(ev, sel_key):
    e = np.asarray(ev["energy"], dtype=np.float64)
    s = np.asarray(ev["ct_score"], dtype=np.float64)
    es = np.asarray(ev["is_es_true"], dtype=bool)
    mask = DECOMP_SELECTIONS[sel_key][1](s, e, es)
    return (np.asarray(ev["reco_dirs"], dtype=np.float64)[mask], e[mask], es[mask],
            normalize_vector(np.asarray(ev["true_burst_dir"], dtype=np.float64)))


def run_decomp_cell(ev, sel_key, sampler, lookup, grid_n, emcee_cfg, repeats, seed0):
    """One (selection, sampler, lookup) cell for one cat."""
    from ana.burst_direction import _run_emcee  # noqa: N813  (pipeline's own sampler)

    dirs, energy, is_es, truth = _decomp_select(ev, sel_key)
    if dirs.shape[0] == 0 or truth is None:
        return None
    base = {"n_used": int(dirs.shape[0]), "n_true_es_used": int(np.sum(is_es))}
    # hole reach at the TRUE direction (independent of sampler/lookup mode)
    cos_true = np.clip(dirs @ truth, -1.0, 1.0)
    base["frac_hole_at_truth"] = float(np.mean(np.abs(cos_true) > 0.99))
    base["frac_hole_forward_at_truth"] = float(np.mean(cos_true > 0.99))

    if sampler == "grid":
        grid, log_like, post = grid_posterior_lookup(dirs, energy, lookup, grid_n=grid_n)
        mean_dir = normalize_vector(np.sum(post[:, None] * grid, axis=0))
        map_dir = grid[int(np.argmax(post))]
        hpd = hpd_region_from_grid(post, 0.68)
        truth_idx = int(np.argmax(grid @ truth))
        # fraction of (event, trial direction) lookups in the hole over the whole grid
        base.update({
            "theta_deg": angular_error_deg(mean_dir, truth),
            "map_theta_deg": angular_error_deg(map_dir, truth),
            "cos": float(np.clip(np.dot(mean_dir, truth), -1.0, 1.0)),
            "hpd68_radius_deg": hpd["radius_deg"],
            "truth_in_hpd68": bool(hpd["members"][truth_idx]),
            "theta_repeats_deg": [angular_error_deg(mean_dir, truth)],
            "acceptance": float("nan"),
        })
        return base

    weights = np.ones(dirs.shape[0], dtype=np.float64)
    interp = _EmceeInterpAdapter(lookup, energy)
    thetas, coss, accs = [], [], []
    for r in range(int(repeats)):
        np.random.seed(int(seed0) + 1000 * r)  # emcee draws from the global RNG
        res = _run_emcee(dirs, weights, energy, truth, emcee_cfg, interp)
        thetas.append(angular_error_deg(res["reco_dir"], truth))
        coss.append(float(np.clip(np.dot(res["reco_dir"], truth), -1.0, 1.0)))
        accs.append(float(res["acceptance_fraction"]))
    base.update({
        "theta_deg": float(np.median(thetas)),
        "map_theta_deg": float("nan"),
        "cos": float(np.median(coss)),
        "hpd68_radius_deg": float("nan"),
        "truth_in_hpd68": False,
        "theta_repeats_deg": [float(t) for t in thetas],
        "cos_repeats": coss,
        "acceptance": float(np.mean(accs)),
    })
    return base


def aggregate_decomp(rows, cos_key="cos"):
    th = np.array([r["theta_deg"] for r in rows], dtype=float)
    cos = np.array([r[cos_key] for r in rows], dtype=float)
    out = {
        "n_cats": int(len(rows)),
        "theta68_from_cos_deg": float(np.degrees(np.arccos(np.clip(np.quantile(cos, 0.32), -1, 1)))),
        "theta_median_deg": float(np.median(th)),
        "theta_mean_deg": float(np.mean(th)),
        "frac_gt_30deg": float(np.mean(th > 30.0)),
        "n_used_mean": float(np.mean([r["n_used"] for r in rows])),
        "frac_hole_at_truth_mean": float(np.mean([r["frac_hole_at_truth"] for r in rows])),
        "frac_hole_forward_at_truth_mean": float(np.mean([r["frac_hole_forward_at_truth"] for r in rows])),
    }
    # per-repeat theta68, to expose the emcee Monte-Carlo noise
    nrep = min(len(r.get("cos_repeats", [])) for r in rows) if all("cos_repeats" in r for r in rows) else 0
    if nrep > 1:
        per = []
        for k in range(nrep):
            c = np.array([r["cos_repeats"][k] for r in rows], dtype=float)
            per.append(float(np.degrees(np.arccos(np.clip(np.quantile(c, 0.32), -1, 1)))))
        out["theta68_per_repeat_deg"] = per
        out["theta68_repeat_spread_deg"] = float(np.max(per) - np.min(per))
    return out


def verify_lookup(pdf_path, pdf_floor=1e-4, n=20000, seed=0):
    """Check PdfLookup(mode='hole') against the real load_pdf_interpolator."""
    from ana.burst_direction import load_pdf_interpolator
    interp = load_pdf_interpolator(pdf_path)
    if interp is None:
        return {"ok": False, "reason": "interpolator unavailable"}
    lk = PdfLookup(pdf_path, mode="hole", pdf_floor=pdf_floor)
    rng = np.random.default_rng(seed)
    e = rng.uniform(2.0, 65.0, n)
    c = rng.uniform(-1.0, 1.0, n)
    ref = np.maximum(interp(np.column_stack([e, c])), _HOLE_FILL)
    rows, out_e = lk.rows(e)
    got = lk.eval(rows, out_e, c[:, None])[:, 0]
    rel = np.abs(got - ref) / np.maximum(np.abs(ref), 1e-30)
    return {"ok": bool(np.max(rel) < 1e-9), "max_rel_diff": float(np.max(rel)), "n": int(n)}


def run_decomposition(args, events):
    emcee_cfg = {
        # exactly what scenario_cos_theta_report.main() hands to _run_emcee
        # (note: prior_type is NOT forwarded there, so the prior is "uniform")
        "nwalkers": 128, "nsteps": 500, "discard": 100,
        "prior_kappa": 25.0, "likelihood_kappa": 25.0,
        "random_seed": 42, "stretch_a": 2.0,
    }
    lookups = {m: PdfLookup(args.pdf_es, mode=m, pdf_floor=args.pdf_floor) for m in ("clipped", "hole")}
    sel_keys = [s.strip() for s in args.decompose_selections.split(",") if s.strip()]
    cells = []
    for sel_key in sel_keys:
        for sampler in [s.strip() for s in args.decompose_samplers.split(",") if s.strip()]:
            for lk in [l.strip() for l in args.decompose_lookups.split(",") if l.strip()]:
                cells.append((sel_key, sampler, lk))

    out_path = Path(args.out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    store = {}
    if args.resume and out_path.exists():
        store = json.load(open(out_path))
    store.setdefault("meta", {})
    store["meta"].update({
        "pdf_es": str(args.pdf_es), "pdf_floor": args.pdf_floor, "grid_n": args.grid_n,
        "emcee_cfg": emcee_cfg, "repeats": args.repeats, "seed0": args.seed0,
        "n_cats_available": len(events),
        "lookup_verification": verify_lookup(args.pdf_es, args.pdf_floor, n=4000),
    })
    store.setdefault("cells", {})

    for cat, ev in events.items():
        for sel_key, sampler, lkname in cells:
            key = f"{sel_key}|{sampler}|{lkname}"
            cell = store["cells"].setdefault(key, {})
            if cat in cell:
                continue
            r = run_decomp_cell(ev, sel_key, sampler, lookups[lkname], args.grid_n,
                                emcee_cfg, args.repeats if sampler == "emcee" else 1, args.seed0)
            if r is not None:
                cell[cat] = r
            print(f"{cat} {key}: theta={r['theta_deg'] if r else float('nan'):.2f} n={r['n_used'] if r else 0}", flush=True)
        with open(out_path, "w") as f:  # partial save after every cat
            json.dump(store, f, indent=1)

    write_decomposition_report(store, Path(args.out_json), Path(args.out_md))
    print(f"saved {args.out_json} and {args.out_md}")


def write_decomposition_report(store, out_json, out_md):
    aggs = {}
    for key, cell in store.get("cells", {}).items():
        rows = list(cell.values())
        if not rows:
            continue
        aggs[key] = aggregate_decomp(rows)
    store["aggregate"] = aggs
    with open(out_json, "w") as f:
        json.dump(store, f, indent=1)
    lines = [
        "# Lookup x sampler decomposition of the scenario-3 pointing resolution",
        "",
        "50 dev cats (cat000623-cat000672), same per-event inputs (reco directions and CT",
        "scores are bit-identical between the scenario-3 and scenario-7 pipeline runs).",
        "`hole` = burst_direction.load_pdf_interpolator (RegularGridInterpolator over the",
        "cos BIN CENTRES [-0.99, 0.99], fill_value=1e-10). `clipped` = the mixture-code",
        "lookup (table floored/renormalised, cos and energy clipped into range).",
        "`emcee` = the pipeline's own _run_emcee (128 walkers x 500 steps, 100 burn-in,",
        "uniform prior, stretch a=2.0); `grid` = exhaustive posterior on the 41253-point",
        "Fibonacci grid. theta68 = arccos of the 0.32 quantile of cos(reco, truth).",
        "",
        "| selection | sampler | lookup | Ncats | theta68 [deg] | median theta [deg] | frac > 30 deg | mean n_used | emcee theta68 spread [deg] |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for key in sorted(aggs):
        sel_key, sampler, lkname = key.split("|")
        a = aggs[key]
        spread = a.get("theta68_repeat_spread_deg")
        spread_s = "-" if spread is None else f"{spread:.2f} ({', '.join(f'{v:.2f}' for v in a['theta68_per_repeat_deg'])})"
        lines.append(f"| {DECOMP_SELECTIONS[sel_key][0]} | {sampler} | {lkname} | {a['n_cats']} | "
                     f"{a['theta68_from_cos_deg']:.2f} | {a['theta_median_deg']:.2f} | {a['frac_gt_30deg']:.2f} | "
                     f"{a['n_used_mean']:.0f} | {spread_s} |")
    ref = store.get("meta", {}).get("in_pipeline_reference", {})
    if ref:
        lines += ["", "In-pipeline reference (scenario reports of the same dev run, aggregated by",
                  "aggregate_scenario_reports.py -- emcee + hole lookup, i.e. cell D):", "",
                  "| scenario | Ncats | theta68 [deg] | median theta [deg] | frac > 30 deg | mean n_selected |",
                  "|---|---|---|---|---|---|"]
        for name, r in ref.items():
            lines.append(f"| {name} | {r['n_cats']} | {r['theta68_from_cos_deg']:.2f} | {r['theta_median_deg']:.2f} | "
                         f"{r['frac_gt_30deg']:.2f} | {r['n_selected_mean']:.0f} |")
    # reproduction check: cell D against the in-pipeline per-cat cos values
    percat = store.get("meta", {}).get("in_pipeline_per_cat", {})
    if percat:
        lines += ["", "## Does D reproduce the in-pipeline numbers?", "",
                  "emcee draws from the GLOBAL numpy RNG, so a pipeline run is one unreproducible",
                  "realisation; D is compared to it through independent repeats on the same cats.", "",
                  "| selection | Ncats matched | in-pipeline theta68 | D theta68 per repeat | per-cat |D - in-pipeline| mean | per-cat D repeat spread mean | in-pipeline theta68 bootstrap 68% CI |",
                  "|---|---|---|---|---|---|---|"]
        for sel_key in sorted(percat):
            cell = store["cells"].get(f"{sel_key}|emcee|hole", {})
            cats = [c for c in sorted(cell) if c in percat[sel_key]]
            if not cats:
                continue
            ip = np.array([percat[sel_key][c] for c in cats], dtype=float)
            mine = np.array([cell[c]["cos_repeats"] for c in cats], dtype=float)
            t68 = lambda c: float(np.degrees(np.arccos(np.clip(np.quantile(np.asarray(c), 0.32), -1, 1))))
            ip_th = np.degrees(np.arccos(np.clip(ip, -1, 1)))
            my_th = np.degrees(np.arccos(np.clip(mine, -1, 1)))
            rng = np.random.default_rng(0)
            bs = [t68(ip[rng.integers(0, len(cats), len(cats))]) for _ in range(4000)]
            lines.append(f"| {DECOMP_SELECTIONS[sel_key][0]} | {len(cats)} | {t68(ip):.2f} | "
                         f"{', '.join(f'{t68(mine[:, k]):.2f}' for k in range(mine.shape[1]))} | "
                         f"{np.abs(np.median(my_th, axis=1) - ip_th).mean():.2f} | "
                         f"{(my_th.max(1) - my_th.min(1)).mean():.2f} | "
                         f"[{np.quantile(bs, 0.16):.2f}, {np.quantile(bs, 0.84):.2f}] |")
    # attribution: how many degrees come from each axis
    lines += ["", "## Attribution", ""]
    for sel_key in sorted({k.split("|")[0] for k in aggs}):
        got = {(sm, lk): aggs.get(f"{sel_key}|{sm}|{lk}") for sm in ("grid", "emcee") for lk in ("clipped", "hole")}
        if not all(got.values()):
            continue
        t = {k: v["theta68_from_cos_deg"] for k, v in got.items()}
        lines += [
            f"**{DECOMP_SELECTIONS[sel_key][0]}** (theta68, deg; \"gain\" = reduction in theta68, positive is better)",
            "",
            f"- D emcee + hole    = {t[('emcee','hole')]:.2f}   (the in-pipeline configuration)",
            f"- C emcee + clipped = {t[('emcee','clipped')]:.2f}   lookup fix alone, sampler held at emcee: "
            f"gain {t[('emcee','hole')] - t[('emcee','clipped')]:+.2f}",
            f"- B grid  + hole    = {t[('grid','hole')]:.2f}   sampler change alone, lookup held buggy: "
            f"gain {t[('emcee','hole')] - t[('grid','hole')]:+.2f}",
            f"- A grid  + clipped = {t[('grid','clipped')]:.2f}   both: gain {t[('emcee','hole')] - t[('grid','clipped')]:+.2f}",
            f"- non-additivity (A - B - C + D) = "
            f"{t[('grid','clipped')] - t[('grid','hole')] - t[('emcee','clipped')] + t[('emcee','hole')]:+.2f}",
            "",
        ]
    lines += ["", "## Reach of the fill_value hole", "",
              "| selection | mean frac of events with |cos(d_i, truth)| > 0.99 | of which forward (cos > 0.99) |",
              "|---|---|---|"]
    best = {}
    for key, a in aggs.items():
        sel_key = key.split("|")[0]
        if sel_key not in best or a["n_cats"] > aggs[best[sel_key]]["n_cats"]:
            best[sel_key] = key
    for sel_key in sorted(best):
        a = aggs[best[sel_key]]
        lines.append(f"| {DECOMP_SELECTIONS[sel_key][0]} | {a['frac_hole_at_truth_mean']:.4f} | "
                     f"{a['frac_hole_forward_at_truth_mean']:.4f} |")
    mech = store.get("meta", {}).get("hole_mechanism", {})
    if mech:
        lines += ["", "Why the hole hurts: an event inside it contributes log(1e-10) = -23.0 instead of",
                  "the (large) forward pdf value, so the optimum of the buggy likelihood is the",
                  "direction that puts NO event in the hole -- which is not the true direction.", "",
                  "| selection | mean frac of events in the hole at truth | ... at the buggy-likelihood MAP | median MAP-truth angle [deg] | median logL(MAP) - logL(truth) [nats] |",
                  "|---|---|---|---|---|"]
        for sel_key in sorted(mech):
            m = mech[sel_key]
            lines.append(f"| {DECOMP_SELECTIONS[sel_key][0]} | {m['frac_events_in_hole_at_truth_mean']:.4f} | "
                         f"{m['frac_events_in_hole_at_buggy_MAP_mean']:.4f} | {m['buggy_MAP_theta_median_deg']:.2f} | "
                         f"{m['loglike_gain_MAP_over_truth_median_nats']:.1f} |")
    with open(out_md, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", required=True)
    ap.add_argument("--pdf-es", required=True)
    ap.add_argument("--pdf-cc", required=True)
    ap.add_argument("--pdf-es-alt", default=None, help="alternative ES table (e.g. vs the neutrino axis) for the ESnu variants")
    ap.add_argument("--cc-map", default=None, help="detector-frame CC reco-direction density map (build_cc_direction_map.py) for the CCmap variants")
    ap.add_argument("--calibration", required=True)
    ap.add_argument("--grid-n", type=int, default=41253)
    ap.add_argument("--pdf-floor", type=float, default=1e-4)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--only", default=None, help="comma-separated variant indices to run")
    # --- lookup x sampler decomposition (opt-in; leaves the variant scan above untouched) ---
    ap.add_argument("--decompose", action="store_true",
                    help="run the (selection x sampler x lookup) decomposition instead of VARIANTS")
    ap.add_argument("--decompose-selections", default="sc3,sc2")
    ap.add_argument("--decompose-samplers", default="grid,emcee")
    ap.add_argument("--decompose-lookups", default="clipped,hole")
    ap.add_argument("--repeats", type=int, default=3,
                    help="emcee repeats per cat (emcee draws from the GLOBAL numpy RNG, so it is not reproducible)")
    ap.add_argument("--seed0", type=int, default=20260904)
    ap.add_argument("--cats", default=None, help="comma-separated cat names to restrict to")
    ap.add_argument("--resume", action="store_true", help="reuse cells already present in --out-json")
    ap.add_argument("--report-only", action="store_true", help="only rebuild the md/json summary from --out-json")
    ap.add_argument("--merge", default=None, help="comma-separated decomposition jsons to merge into --out-json")
    ap.add_argument("--reference-json", default=None, help="in-pipeline reference numbers to quote in the report")
    ap.add_argument("--reference-per-cat-json", default=None,
                    help="{sel_key: {cat: cos_to_truth}} from the in-pipeline scenario reports, for the D reproduction check")
    args = ap.parse_args()

    if args.report_only or args.merge:
        store = json.load(open(args.out_json)) if Path(args.out_json).exists() and not args.merge else {}
        if args.merge:
            store = {"meta": {"merged_from": []}, "cells": {}}
            for src in [x.strip() for x in args.merge.split(",") if x.strip()]:
                part = json.load(open(src))
                store["meta"]["merged_from"].append(src)
                store["meta"].setdefault("parts", {})[src] = part.get("meta", {})
                for key, cell in part.get("cells", {}).items():
                    store["cells"].setdefault(key, {}).update(cell)
            if args.reference_json:
                store["meta"]["in_pipeline_reference"] = json.load(open(args.reference_json))
            if args.reference_per_cat_json:
                store["meta"]["in_pipeline_per_cat"] = json.load(open(args.reference_per_cat_json))
        write_decomposition_report(store, Path(args.out_json), Path(args.out_md))
        print(f"wrote {args.out_json} and {args.out_md}")
        return

    events = load_events(Path(args.input_root))
    if not events:
        raise SystemExit("no mixture_events.npz found")
    print(f"{len(events)} cats with per-event outputs")
    if args.cats:
        keep = {c.strip() for c in args.cats.split(",") if c.strip()}
        events = {k: v for k, v in events.items() if k in keep}
        print(f"restricted to {len(events)} cats")
    if args.decompose:
        run_decomposition(args, events)
        return
    tables = {
        "es": load_pdf_table(args.pdf_es, pdf_floor=args.pdf_floor),
        "cc": load_pdf_table(args.pdf_cc, pdf_floor=args.pdf_floor),
    }
    tables["flat"] = flat_pdf_table(tables["es"])
    tables["es_alt"] = load_pdf_table(args.pdf_es_alt, pdf_floor=args.pdf_floor) if args.pdf_es_alt else None
    tables["cc_map"] = load_cc_direction_map(args.cc_map) if args.cc_map else None
    calib = load_ct_calibration(args.calibration)

    which = list(range(len(VARIANTS)))
    if args.only:
        which = [int(x) for x in args.only.split(",")]
    results = {}
    for vi in which:
        name, cfg = VARIANTS[vi]
        rows = {}
        for cat, ev in events.items():
            r = run_variant(ev, cfg, tables, calib, args.grid_n)
            if r is not None:
                rows[cat] = r
        if not rows:
            print(f"[{vi:2d}] {name}: skipped (no inputs, e.g. missing --pdf-es-alt)")
            continue
        agg = aggregate(list(rows.values()))
        results[name] = {"config": cfg, "aggregate": agg, "per_cat": rows}
        print(f"[{vi:2d}] {name:<66} theta68={agg['theta68_from_cos_deg']:6.2f} med={agg['theta_median_deg']:6.2f} "
              f">30:{agg['frac_gt_30deg']:.2f} cov68={agg['coverage68']:.2f} hpd68={agg['hpd68_radius_median_deg']:5.2f} n={agg['n_used_mean']:.0f}", flush=True)
        Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out_json, "w") as f:
            json.dump(results, f, indent=1)

    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_json, "w") as f:
        json.dump(results, f, indent=1)
    lines = ["| variant | Ncats | theta68 (68% cont.) [deg] | median theta [deg] | frac > 30 deg | median MAP theta | median HPD68 radius [deg] | coverage68 | mean n_used | mean sum p |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for name, res in results.items():
        a = res["aggregate"]
        lines.append(f"| {name} | {a['n_cats']} | {a['theta68_from_cos_deg']:.2f} | {a['theta_median_deg']:.2f} | {a['frac_gt_30deg']:.2f} | "
                     f"{a['map_theta_median_deg']:.2f} | {a['hpd68_radius_median_deg']:.2f} | {a['coverage68']:.2f} | {a['n_used_mean']:.0f} | {a['sum_p_mean']:.0f} |")
    with open(args.out_md, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"saved {args.out_json} and {args.out_md}")


if __name__ == "__main__":
    main()
