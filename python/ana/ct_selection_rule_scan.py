#!/usr/bin/env python3
"""
Offline scan of CHANNEL-TAGGER SELECTION RULES for the supernova burst pointing,
evaluated with the pipeline's own likelihood + sampler.

Motivation
----------
The v80 channel tagger (CT) is very inefficient for high-energy elastic-scattering
(ES) events: at score >= 0.80 only a few percent of the true ES above 10 MeV
survive, yet those are exactly the events that point best (the mean cosine of the
reco electron direction to the neutrino direction grows with energy). This script
asks, WITHOUT ANY RETRAINING, what a smarter cut on the EXISTING score buys, using
the real pointing metric.

Inputs are the kept per-event outputs of the scenario-7 dev run,
  <root>/<cat>/scenario_7_mixture_ct/pipeline_run_*/predictions/mixture_events.npz
which contain exactly the events the pipeline's scenario 3 sees (verified
bit-identical), with fields reco_dirs, energy, ct_score, p_es, is_es_true,
true_electron_dirs, true_nu_dirs, true_burst_dir.

For every selection rule and every cat we run burst_direction._run_emcee with the
pipeline's emcee configuration (128 walkers x 500 steps, 100 burn-in, uniform
prior, seed 42 -> repeatable) and the pure-ES cosine-energy pdf loaded through
burst_direction.load_pdf_interpolator (mode "clipped", the post-fix default),
weights = 1. Across cats:
    theta68 = degrees(arccos(quantile(cos(reco, truth), 0.32)))
plus the median per-cat angle and the fraction of cats above 30 deg, with a
bootstrap-over-bursts 68% interval on theta68 and a paired per-cat comparison
with the R0 baseline.

Nothing here touches the production code path: the module only IMPORTS from
ana.burst_direction and writes its own json/md.

Usage (diagnostics only, cheap, safe on a login node):
  python3 python/ana/ct_selection_rule_scan.py --input-root <root> --diagnostic-only \
      --out-json <json> --out-md <md>

Usage (emcee scan, meant for condor; --rules picks a group):
  python3 python/ana/ct_selection_rule_scan.py --input-root <root> \
      --pdf data/cosine_energy_pdf.npz --rules R0,R1 --resume \
      --out-json <json> --out-md <md>

Merging condor partials into the final report:
  python3 python/ana/ct_selection_rule_scan.py --input-root <root> \
      --merge '<dir>/ct_selection_rule_scan_part_*.json' \
      --out-json <json> --out-md <md>
"""
import argparse
import glob
import json
import sys
import time
from pathlib import Path

import numpy as np

python_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(python_root))

from ana.burst_direction import (  # noqa: E402
    _run_emcee,
    angular_error_deg,
    load_pdf_interpolator,
    normalize_vector,
)

# exactly what scenario_cos_theta_report hands to _run_emcee for scenario 3
EMCEE_CFG = {"nwalkers": 128, "nsteps": 500, "discard": 100, "random_seed": 42}

# diagnostic-table energy bins (MeV); last bin is open-ended
DIAG_EDGES = [3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 30.0, np.inf]
# R3 energy-flattening bins (start at the 5 MeV floor of the baseline)
R3_EDGES = [5.0, 7.0, 10.0, 15.0, 20.0, 30.0, np.inf]

BASE_SCORE = 0.80
BASE_EMIN = 5.0


# --------------------------------------------------------------------------- IO
def _latest_run(scenario_dir: Path):
    runs = sorted(Path(scenario_dir).glob("pipeline_run_*"))
    return runs[-1] if runs else None


def load_events(root: Path, scenario_name="scenario_7_mixture_ct", cats=None):
    """cat -> dict with the arrays we need (float64 / bool), sorted by cat name."""
    root = Path(root)
    out = {}
    for cat_dir in sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("cat")):
        if cats is not None and cat_dir.name not in cats:
            continue
        run = _latest_run(cat_dir / scenario_name)
        if run is None:
            continue
        f = run / "predictions" / "mixture_events.npz"
        if not f.exists():
            continue
        d = np.load(f, allow_pickle=True)
        ev = {
            "reco_dirs": np.asarray(d["reco_dirs"], dtype=np.float64),
            "energy": np.asarray(d["energy"], dtype=np.float64),
            "ct_score": np.asarray(d["ct_score"], dtype=np.float64),
            "is_es_true": np.asarray(d["is_es_true"], dtype=bool),
            "true_burst_dir": normalize_vector(np.asarray(d["true_burst_dir"], dtype=np.float64)),
        }
        if "true_nu_dirs" in d.files:
            ev["true_nu_dirs"] = np.asarray(d["true_nu_dirs"], dtype=np.float64)
        out[cat_dir.name] = ev
    return out


# -------------------------------------------------------------------- selections
def sel_global(score, energy, is_es, t, emin):
    return (score >= t) & (energy >= emin)


def sel_twoband(score, energy, is_es, edge, t_lo, t_hi, emin):
    t = np.where(energy < edge, t_lo, t_hi)
    return (score >= t) & (energy >= emin)


def sel_binned(score, energy, is_es, edges, thresholds, emin):
    """Per-energy-bin thresholds; events below edges[0] are rejected."""
    idx = np.digitize(energy, edges[1:-1], right=False)  # 0..len(thresholds)-1
    t = np.asarray(thresholds, dtype=np.float64)[np.clip(idx, 0, len(thresholds) - 1)]
    return (score >= t) & (energy >= max(emin, edges[0]))


def sel_ramp(score, energy, is_es, emin, s0=0.80, slope=0.02, floor=0.30):
    t = np.maximum(s0 - slope * (energy - emin), floor)
    return (score >= t) & (energy >= emin)


def sel_true_es(score, energy, is_es, emin):
    return is_es & (energy >= emin)


def sel_r0_es_only(score, energy, is_es, **_):
    return is_es & (score >= BASE_SCORE) & (energy >= BASE_EMIN)


# ------------------------------------------------------------ pooled diagnostics
def pooled_arrays(events):
    s = np.concatenate([ev["ct_score"] for ev in events.values()])
    e = np.concatenate([ev["energy"] for ev in events.values()])
    x = np.concatenate([ev["is_es_true"] for ev in events.values()])
    cos_burst = np.concatenate([
        np.clip(ev["reco_dirs"] @ ev["true_burst_dir"], -1.0, 1.0) for ev in events.values()
    ])
    return s, e, x, cos_burst


def diagnostic_table(events):
    s, e, x, cos_burst = pooled_arrays(events)
    rows = []
    for i in range(len(DIAG_EDGES) - 1):
        lo, hi = DIAG_EDGES[i], DIAG_EDGES[i + 1]
        m = (e >= lo) & (e < hi)
        es, cc = m & x, m & (~x)
        n_es, n_cc = int(es.sum()), int(cc.sum())
        p80 = m & (s >= 0.80)
        p50 = m & (s >= 0.50)
        rows.append({
            "e_lo": float(lo), "e_hi": (None if not np.isfinite(hi) else float(hi)),
            "n_es": n_es, "n_cc": n_cc,
            "es_eff_080": float((es & (s >= 0.80)).sum() / n_es) if n_es else float("nan"),
            "cc_acc_080": float((cc & (s >= 0.80)).sum() / n_cc) if n_cc else float("nan"),
            "es_eff_050": float((es & (s >= 0.50)).sum() / n_es) if n_es else float("nan"),
            "cc_acc_050": float((cc & (s >= 0.50)).sum() / n_cc) if n_cc else float("nan"),
            "es_frac_pass_080": float((p80 & x).sum() / p80.sum()) if p80.sum() else float("nan"),
            "es_frac_pass_050": float((p50 & x).sum() / p50.sum()) if p50.sum() else float("nan"),
            "n_pass_080": int(p80.sum()), "n_pass_050": int(p50.sum()),
            "mean_cos_es_burst": float(cos_burst[es].mean()) if n_es else float("nan"),
            "mean_cos_cc_burst": float(cos_burst[cc].mean()) if n_cc else float("nan"),
        })
    tot = {
        "n_es": int(x.sum()), "n_cc": int((~x).sum()), "n_all": int(x.size),
        "n_cats": len(events),
        "es_fraction": float(x.mean()),
    }
    return {"bins": rows, "totals": tot}


def derive_r3_thresholds(events):
    """Per-energy-bin thresholds from the POOLED sample (truth-based, exploration only)."""
    s, e, x, _ = pooled_arrays(events)
    base = (s >= BASE_SCORE) & (e >= BASE_EMIN)
    hi_e = e >= BASE_EMIN
    cc_hi, es_hi = hi_e & (~x), hi_e & x
    a0 = float((base & (~x)).sum() / cc_hi.sum())   # global CC acceptance among E>=5 CC
    eff0 = float((base & x).sum() / es_hi.sum())    # global ES efficiency among E>=5 ES

    def per_bin(target, truth_mask, label):
        ts = []
        for i in range(len(R3_EDGES) - 1):
            lo, hi = R3_EDGES[i], R3_EDGES[i + 1]
            m = truth_mask & (e >= lo) & (e < hi)
            if m.sum() < 20:
                ts.append(float(BASE_SCORE))
                continue
            # threshold whose pass fraction in this bin equals `target`
            t = float(np.quantile(s[m], 1.0 - min(max(target, 0.0), 1.0)))
            ts.append(float(np.clip(t, 0.0, 1.0)))
        return ts

    out = {
        "a0_cc_acceptance_E5": a0,
        "eff0_es_efficiency_E5": eff0,
        "edges": [float(v) if np.isfinite(v) else None for v in R3_EDGES],
        "flatCC_1x": per_bin(a0, (~x), "cc"),
        "flatCC_2x": per_bin(2.0 * a0, (~x), "cc"),
        "flatCC_0p5x": per_bin(0.5 * a0, (~x), "cc"),
        "flatES": per_bin(eff0, x, "es"),
    }
    # realised pass fractions with the derived thresholds (sanity)
    for key in ("flatCC_1x", "flatCC_2x", "flatCC_0p5x", "flatES"):
        m = sel_binned(s, e, x, R3_EDGES, out[key], BASE_EMIN)
        out[key + "_realised"] = {
            "cc_acc_E5": float((m & (~x)).sum() / cc_hi.sum()),
            "es_eff_E5": float((m & x).sum() / es_hi.sum()),
        }
    return out


# -------------------------------------------------------------------- rule table
def build_rules(r3):
    """List of dicts: id, group, label, fn(score, energy, is_es) -> bool mask."""
    R = []

    def add(rid, group, label, fn):
        R.append({"id": rid, "group": group, "label": label, "fn": fn})

    add("R0", "R0", "baseline: s>=0.80, E>=5",
        lambda s, e, x: sel_global(s, e, x, 0.80, 5.0))

    for t in (0.5, 0.6, 0.7, 0.9):
        add(f"R1_t{t:g}", "R1", f"global: s>={t:.2f}, E>=5",
            lambda s, e, x, t=t: sel_global(s, e, x, t, 5.0))

    # R1x: extra points of the global threshold scan, for the energy-reweighted
    # taggers (v83 / v82-X) whose useful operating point is not known a priori.
    # 0.50/0.60/0.70/0.90 are already in R1 and 0.80 is R0, so only the gaps are added.
    for t in (0.4, 0.55, 0.65, 0.75, 0.85):
        add(f"R1x_t{t:g}", "R1x", f"global: s>={t:.2f}, E>=5",
            lambda s, e, x, t=t: sel_global(s, e, x, t, 5.0))

    for t_hi in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7):
        add(f"R2_e10_t{t_hi:g}", "R2",
            f"two-band: s>=0.80 for 5<=E<10, s>={t_hi:.2f} for E>=10",
            lambda s, e, x, t=t_hi: sel_twoband(s, e, x, 10.0, 0.80, t, 5.0))
    for t_hi in (0.3, 0.5):
        add(f"R2_e15_t{t_hi:g}", "R2",
            f"two-band: s>=0.80 for 5<=E<15, s>={t_hi:.2f} for E>=15",
            lambda s, e, x, t=t_hi: sel_twoband(s, e, x, 15.0, 0.80, t, 5.0))

    r3_specs = [
        ("R3_flatCC_1x", "flatCC_1x", "flat CC acceptance = R0 level (1x)"),
        ("R3_flatCC_2x", "flatCC_2x", "flat CC acceptance = 2x R0 level"),
        ("R3_flatCC_0p5x", "flatCC_0p5x", "flat CC acceptance = 0.5x R0 level"),
        ("R3_flatES", "flatES", "flat ES efficiency = R0 level"),
    ]
    for rid, key, txt in r3_specs:
        ts = r3[key]
        add(rid, "R3", f"energy-flattened t(E), {txt}; t={['%.3f' % v for v in ts]}",
            lambda s, e, x, ts=ts: sel_binned(s, e, x, R3_EDGES, ts, 5.0))

    for t in (0.3, 0.5, 0.8):
        add(f"R4_e10_t{t:g}", "R4", f"high-E only: E>=10, s>={t:.2f}",
            lambda s, e, x, t=t: sel_global(s, e, x, t, 10.0))
    add("R4_e7_t0.5", "R4", "high-E only: E>=7, s>=0.50",
        lambda s, e, x: sel_global(s, e, x, 0.5, 7.0))

    add("R5_trueES_E5", "R5", "CEILING: true ES only, E>=5",
        lambda s, e, x: sel_true_es(s, e, x, 5.0))
    add("R5_trueES_E10", "R5", "CEILING: true ES only, E>=10",
        lambda s, e, x: sel_true_es(s, e, x, 10.0))
    add("R5_R0_esonly", "R5", "CEILING: R0 selection with the CC removed (true ES passing R0)",
        lambda s, e, x: sel_r0_es_only(s, e, x))

    add("R6_ramp", "R6", "ramp: t(E) = max(0.30, 0.80 - 0.02*(E-5)), E>=5",
        lambda s, e, x: sel_ramp(s, e, x, 5.0))

    # R6x: steeper-start ramps, for taggers whose scores sit higher overall
    add("R6x_ramp09_s02_f04", "R6x", "ramp: t(E) = max(0.40, 0.90 - 0.02*(E-5)), E>=5",
        lambda s, e, x: sel_ramp(s, e, x, 5.0, s0=0.90, slope=0.02, floor=0.40))
    add("R6x_ramp09_s015_f05", "R6x", "ramp: t(E) = max(0.50, 0.90 - 0.015*(E-5)), E>=5",
        lambda s, e, x: sel_ramp(s, e, x, 5.0, s0=0.90, slope=0.015, floor=0.50))

    return R


# ------------------------------------------------------------------------ engine
def run_rule_on_cat(ev, fn, pdf_interp):
    s = ev["ct_score"]
    e = ev["energy"]
    x = ev["is_es_true"]
    truth = ev["true_burst_dir"]
    mask = np.asarray(fn(s, e, x), dtype=bool)
    n_sel = int(mask.sum())
    row = {
        "n_sel": n_sel,
        "n_es_sel": int((mask & x).sum()),
        "n_cc_sel": int((mask & (~x)).sum()),
        "n_es_tot": int(x.sum()),
        "n_cc_tot": int((~x).sum()),
        "n_tot": int(x.size),
        "n_es_tot_e10": int((x & (e >= 10.0)).sum()),
        "n_es_sel_e10": int((mask & x & (e >= 10.0)).sum()),
    }
    if n_sel < 2:
        row.update({"theta_deg": float("nan"), "cos": float("nan"), "acceptance": float("nan")})
        return row
    dirs = ev["reco_dirs"][mask]
    energies = e[mask]
    weights = np.ones(n_sel, dtype=np.float64)
    t0 = time.time()
    res = _run_emcee(dirs, weights, energies, truth, EMCEE_CFG, pdf_interp)
    row["theta_deg"] = float(angular_error_deg(res["reco_dir"], truth))
    row["cos"] = float(np.clip(np.dot(res["reco_dir"], truth), -1.0, 1.0))
    row["acceptance"] = float(res["acceptance_fraction"])
    row["wall_s"] = float(time.time() - t0)
    return row


def aggregate_rule(per_cat, base_per_cat=None, n_boot=2000, boot_seed=12345):
    cats = sorted(per_cat)
    rows = [per_cat[c] for c in cats]
    cos = np.array([r["cos"] for r in rows], dtype=float)
    th = np.array([r["theta_deg"] for r in rows], dtype=float)
    ok = np.isfinite(cos) & np.isfinite(th)
    cos, th = cos[ok], th[ok]
    if cos.size == 0:
        return {"n_cats": 0}

    def t68(c):
        return float(np.degrees(np.arccos(np.clip(np.quantile(c, 0.32), -1.0, 1.0))))

    rng = np.random.default_rng(boot_seed)
    boot = np.array([t68(cos[rng.integers(0, cos.size, cos.size)]) for _ in range(n_boot)])

    def tot(k):
        return float(np.sum([r[k] for r in rows]))

    out = {
        "n_cats": int(cos.size),
        "theta68_deg": t68(cos),
        "theta68_lo68": float(np.percentile(boot, 16.0)),
        "theta68_hi68": float(np.percentile(boot, 84.0)),
        "theta_median_deg": float(np.median(th)),
        "theta_mean_deg": float(np.mean(th)),
        "frac_gt_30deg": float(np.mean(th > 30.0)),
        "n_sel_mean": float(np.mean([r["n_sel"] for r in rows])),
        "n_es_sel_mean": float(np.mean([r["n_es_sel"] for r in rows])),
        "n_cc_sel_mean": float(np.mean([r["n_cc_sel"] for r in rows])),
        "es_purity": tot("n_es_sel") / max(tot("n_sel"), 1.0),
        "es_eff": tot("n_es_sel") / max(tot("n_es_tot"), 1.0),
        "es_eff_e10": tot("n_es_sel_e10") / max(tot("n_es_tot_e10"), 1.0),
        "cc_acc": tot("n_cc_sel") / max(tot("n_cc_tot"), 1.0),
        "acceptance_mean": float(np.nanmean([r.get("acceptance", np.nan) for r in rows])),
        "wall_s_mean": float(np.nanmean([r.get("wall_s", np.nan) for r in rows])),
    }
    if base_per_cat:
        common = [c for c in cats if c in base_per_cat
                  and np.isfinite(per_cat[c]["theta_deg"])
                  and np.isfinite(base_per_cat[c]["theta_deg"])]
        if common:
            d = np.array([per_cat[c]["theta_deg"] - base_per_cat[c]["theta_deg"] for c in common])
            out.update({
                "paired_n": int(d.size),
                "paired_dtheta_median_deg": float(np.median(d)),
                "paired_dtheta_mean_deg": float(np.mean(d)),
                "paired_frac_better": float(np.mean(d < 0.0)),
            })
    return out


# ------------------------------------------------------------------------ report
def paired_theta68_bootstrap(per_cat, base_per_cat, n_boot=4000, boot_seed=7):
    """Bootstrap the DIFFERENCE in theta68 vs R0 resampling the SAME cats for both.

    This is the only fair significance statement here: the marginal 68% intervals of
    two rules evaluated on the same 50 bursts overlap almost completely even when the
    rules track each other closely, so they must not be read as independent errors.
    """
    cats = [c for c in sorted(per_cat)
            if c in base_per_cat
            and np.isfinite(per_cat[c]["cos"]) and np.isfinite(base_per_cat[c]["cos"])]
    if len(cats) < 5:
        return {}
    x = np.array([per_cat[c]["cos"] for c in cats])
    b = np.array([base_per_cat[c]["cos"] for c in cats])

    def t68(c):
        return float(np.degrees(np.arccos(np.clip(np.quantile(c, 0.32), -1.0, 1.0))))

    rng = np.random.default_rng(boot_seed)
    d = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, len(cats), len(cats))
        d[i] = t68(x[idx]) - t68(b[idx])
    return {
        "dtheta68_deg": t68(x) - t68(b),
        "dtheta68_lo68": float(np.percentile(d, 16.0)),
        "dtheta68_hi68": float(np.percentile(d, 84.0)),
        "p_improves": float(np.mean(d < 0.0)),
        "paired_boot_n_cats": len(cats),
    }


def _fmt(v, n=2):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "-"
    return f"{v:.{n}f}"


def write_report(store, out_json, out_md):
    out_json = Path(out_json)
    out_md = Path(out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    base = store.get("rules", {}).get("R0", {}).get("per_cat")
    aggs = {}
    for rid, blk in store.get("rules", {}).items():
        pc = blk.get("per_cat", {})
        if not pc:
            continue
        a = aggregate_rule(pc, base_per_cat=(None if rid == "R0" else base))
        a["label"] = blk.get("label", rid)
        a["group"] = blk.get("group", "")
        if base and rid != "R0" and a.get("n_cats", 0) > 0:
            a.update(paired_theta68_bootstrap(pc, base))
        aggs[rid] = a
    store["aggregate"] = aggs
    # A rule can select <2 events in EVERY burst (e.g. s>=0.80 on a tagger whose score
    # never reaches 0.80). Those have no theta at all; keep them out of the tables.
    degenerate = {k: v for k, v in aggs.items() if v.get("n_cats", 0) == 0}
    aggs = {k: v for k, v in aggs.items() if v.get("n_cats", 0) > 0}
    with open(out_json, "w") as f:
        json.dump(store, f, indent=1)

    L = []
    A = L.append
    A("# CT selection-rule scan for supernova burst pointing")
    A("")
    A("Offline re-evaluation on the kept per-event outputs of the scenario-7 dev run")
    A("(50 cats, cat000623-cat000672; these are bit-identical to what the pipeline's")
    A("scenario 3 sees). For every rule and every cat the selected events are handed to")
    A("`burst_direction._run_emcee` with the pipeline's own configuration")
    A(f"({EMCEE_CFG}) and the pure-ES cosine-energy pdf loaded through")
    A("`load_pdf_interpolator(mode='clipped')`, weights = 1. Nothing in the production")
    A("code path was modified.")
    A("")
    A("`theta68` = degrees(arccos(0.32-quantile of cos(reco_dir, true_burst_dir) over cats));")
    A("the bracket is a 68% bootstrap-over-bursts interval (2000 resamples of the 50 cats).")
    A("`ES eff`/`CC acc` are pooled over all 50 cats with the denominator = ALL true ES /")
    A("ALL true CC events in the files (no energy cut), so an E>=10 rule is capped at the")
    A("fraction of ES above 10 MeV. `dtheta vs R0` is the median of the per-cat differences.")
    A("")
    for line in (store.get("meta", {}).get("note") or "").splitlines():
        A(f"> {line}" if line.strip() else ">")
    if store.get("meta", {}).get("note"):
        A("")

    d = store.get("diagnostic")
    if d:
        t = d["totals"]
        A("## Diagnostic table (no emcee): where the information is, and where the CT loses it")
        A("")
        A(f"Pooled over {t['n_cats']} cats: {t['n_all']} events, {t['n_es']} true ES "
          f"({100*t['es_fraction']:.2f}%), {t['n_cc']} true CC.")
        A("`mean cos ES` is the mean cos(reco_dir, true_burst_dir) of the TRUE ES in the bin:")
        A("the raw pointing power of an event of that energy.")
        A("")
        A("| E bin (MeV) | N ES | N CC | ES eff @0.80 | CC acc @0.80 | ES eff @0.50 | CC acc @0.50 | ES frac of pass@0.80 | ES frac of pass@0.50 | mean cos ES | mean cos CC |")
        A("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for r in d["bins"]:
            lab = f"{r['e_lo']:g}-{r['e_hi']:g}" if r["e_hi"] else f"{r['e_lo']:g}+"
            A(f"| {lab} | {r['n_es']} | {r['n_cc']} | {_fmt(100*r['es_eff_080'],1)}% | "
              f"{_fmt(100*r['cc_acc_080'],2)}% | {_fmt(100*r['es_eff_050'],1)}% | "
              f"{_fmt(100*r['cc_acc_050'],2)}% | {_fmt(100*r['es_frac_pass_080'],1)}% | "
              f"{_fmt(100*r['es_frac_pass_050'],1)}% | {_fmt(r['mean_cos_es_burst'],3)} | "
              f"{_fmt(r['mean_cos_cc_burst'],3)} |")
        A("")

    r3 = store.get("r3_thresholds")
    if r3:
        A("## R3 derived per-bin thresholds")
        A("")
        A(f"Reference levels from R0 among E>=5 events: CC acceptance a0 = {100*r3['a0_cc_acceptance_E5']:.3f}%, "
          f"ES efficiency eff0 = {100*r3['eff0_es_efficiency_E5']:.2f}%.")
        A("Thresholds are score quantiles of the POOLED 50-cat truth sample. In deployment")
        A("they would have to be derived from the CT test set, not from the burst sample itself.")
        A("")
        edges = r3["edges"]
        labs = []
        for i in range(len(edges) - 1):
            labs.append(f"{edges[i]:g}-{edges[i+1]:g}" if edges[i + 1] else f"{edges[i]:g}+")
        A("| rule | " + " | ".join(labs) + " | realised CC acc (E>=5) | realised ES eff (E>=5) |")
        A("|---|" + "---:|" * (len(labs) + 2))
        for key, nice in (("flatCC_1x", "flat CC acc = a0"),
                          ("flatCC_2x", "flat CC acc = 2 a0"),
                          ("flatCC_0p5x", "flat CC acc = 0.5 a0"),
                          ("flatES", "flat ES eff = eff0")):
            rr = r3.get(key + "_realised", {})
            A(f"| {nice} | " + " | ".join(f"{v:.3f}" for v in r3[key]) +
              f" | {_fmt(100*rr.get('cc_acc_E5', float('nan')),3)}% | {_fmt(100*rr.get('es_eff_E5', float('nan')),2)}% |")
        A("")

    if aggs:
        A("## Rule table, sorted by theta68")
        A("")
        hdr = ("| rule | selection | theta68 [68% boot] | median theta | frac>30 | "
               "<n sel> | <n ES> | <n CC> | ES purity | ES eff | ES eff E>10 | CC acc | dtheta vs R0 |")
        A(hdr)
        A("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        order = sorted(aggs, key=lambda k: aggs[k].get("theta68_deg", 1e9))
        for rid in order:
            a = aggs[rid]
            dth = a.get("paired_dtheta_median_deg")
            note = "" if a.get("n_cats", 0) == 50 else f" (only {a.get('n_cats')}/50 cats usable)"
            A(f"| {rid} | {a['label']}{note} | **{_fmt(a['theta68_deg'])}** "
              f"[{_fmt(a['theta68_lo68'])}, {_fmt(a['theta68_hi68'])}] | "
              f"{_fmt(a['theta_median_deg'])} | {_fmt(a['frac_gt_30deg'],2)} | "
              f"{_fmt(a['n_sel_mean'],1)} | {_fmt(a['n_es_sel_mean'],1)} | {_fmt(a['n_cc_sel_mean'],1)} | "
              f"{_fmt(100*a['es_purity'],1)}% | {_fmt(100*a['es_eff'],1)}% | "
              f"{_fmt(100*a['es_eff_e10'],1)}% | {_fmt(100*a['cc_acc'],2)}% | "
              f"{'-' if dth is None else _fmt(dth)} |")
        A("")
        A("### Paired comparison with R0 (the only fair significance statement)")
        A("")
        A("The marginal bootstrap brackets above all overlap, because every rule is evaluated")
        A("on the SAME 50 bursts. Resampling those 50 bursts jointly and taking the DIFFERENCE")
        A("in theta68 removes the common burst-to-burst scatter. `P(improves)` is the fraction")
        A("of paired resamples in which the rule beats R0; 0.5 means indistinguishable.")
        A("")
        A("| rule | d(theta68) vs R0 | paired-boot 68% | P(improves) | median per-cat dtheta | frac of cats better |")
        A("|---|---:|---:|---:|---:|---:|")
        for rid in order:
            a = aggs[rid]
            if "dtheta68_deg" not in a:
                continue
            A(f"| {rid} | {a['dtheta68_deg']:+.2f} | "
              f"[{a['dtheta68_lo68']:+.2f}, {a['dtheta68_hi68']:+.2f}] | "
              f"{a['p_improves']:.2f} | {_fmt(a.get('paired_dtheta_median_deg'))} | "
              f"{_fmt(a.get('paired_frac_better'), 2)} |")
        A("")
        A("### By group (same numbers, grouped)")
        A("")
        for g in ("R0", "R1", "R2", "R3", "R4", "R5", "R6"):
            ids = [k for k in aggs if aggs[k].get("group") == g]
            if not ids:
                continue
            A(f"**{g}**")
            A("")
            A("| rule | selection | theta68 [68% boot] | median theta | frac>30 | <n sel> | ES purity | ES eff | ES eff E>10 | CC acc | dtheta vs R0 |")
            A("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
            for rid in sorted(ids, key=lambda k: aggs[k].get("theta68_deg", 1e9)):
                a = aggs[rid]
                dth = a.get("paired_dtheta_median_deg")
                A(f"| {rid} | {a['label']} | {_fmt(a['theta68_deg'])} "
                  f"[{_fmt(a['theta68_lo68'])}, {_fmt(a['theta68_hi68'])}] | "
                  f"{_fmt(a['theta_median_deg'])} | {_fmt(a['frac_gt_30deg'],2)} | "
                  f"{_fmt(a['n_sel_mean'],1)} | {_fmt(100*a['es_purity'],1)}% | "
                  f"{_fmt(100*a['es_eff'],1)}% | {_fmt(100*a['es_eff_e10'],1)}% | "
                  f"{_fmt(100*a['cc_acc'],2)}% | {'-' if dth is None else _fmt(dth)} |")
            A("")

    if degenerate:
        A("## Rules with no usable burst")
        A("")
        A("These selected fewer than 2 events in every one of the 50 bursts, so no direction")
        A("could be reconstructed. For a tagger whose score never reaches the threshold this")
        A("is the honest answer, not a failure.")
        A("")
        for rid in sorted(degenerate):
            A(f"- `{rid}` - {degenerate[rid].get('label', '')}")
        A("")

    if aggs and "R0" in aggs:
        A("## R5 ceilings: what the contamination costs vs what the missing ES cost")
        A("")
        A("| reference | theta68 [68% boot] | <n sel> | reading |")
        A("|---|---|---:|---|")
        rows = [
            ("R0", "the pipeline today"),
            ("R5_R0_esonly", "R0's own events with every CC removed -> the cost of the contamination R0 lets in"),
            ("R5_trueES_E10", "a perfect tagger keeping only E>=10 ES"),
            ("R5_trueES_E5", "a perfect tagger, E>=5 -> the ceiling of this likelihood on these bursts"),
        ]
        for rid, txt in rows:
            if rid not in aggs:
                continue
            a = aggs[rid]
            A(f"| {rid} | {_fmt(a['theta68_deg'])} [{_fmt(a['theta68_lo68'])}, {_fmt(a['theta68_hi68'])}] | "
              f"{_fmt(a['n_sel_mean'],1)} | {txt} |")
        A("")
        if all(k in aggs for k in ("R0", "R5_R0_esonly", "R5_trueES_E5")):
            cost_cc = aggs["R0"]["theta68_deg"] - aggs["R5_R0_esonly"]["theta68_deg"]
            cost_es = aggs["R5_R0_esonly"]["theta68_deg"] - aggs["R5_trueES_E5"]["theta68_deg"]
            bigger = "the CC contamination R0 admits" if cost_cc >= cost_es else "the ES R0 throws away"
            ratio = max(cost_cc, cost_es) / max(min(cost_cc, cost_es), 1e-9)
            A(f"Splitting the R0-to-ceiling gap of "
              f"{aggs['R0']['theta68_deg'] - aggs['R5_trueES_E5']['theta68_deg']:.2f} deg: about "
              f"{cost_cc:.2f} deg is the CC contamination R0 already admits, and about "
              f"{cost_es:.2f} deg is the ES that R0 throws away -- so {bigger} is the larger "
              f"of the two, by a factor of about {ratio:.1f}.")
            A("")

    with open(out_md, "w") as f:
        f.write("\n".join(L) + "\n")


# -------------------------------------------------------------------------- main
def merge_stores(pattern):
    merged = {"meta": {}, "rules": {}}
    files = sorted(glob.glob(pattern))
    for fp in files:
        try:
            st = json.load(open(fp))
        except Exception as e:
            print(f"skip {fp}: {e}")
            continue
        merged["meta"].setdefault("parts", []).append(str(fp))
        for k in ("diagnostic", "r3_thresholds"):
            if k in st and k not in merged:
                merged[k] = st[k]
        for k, v in st.get("meta", {}).items():
            merged["meta"].setdefault(k, v)
        for rid, blk in st.get("rules", {}).items():
            tgt = merged["rules"].setdefault(rid, {"label": blk.get("label", rid),
                                                   "group": blk.get("group", ""),
                                                   "per_cat": {}})
            tgt["label"] = blk.get("label", tgt["label"])
            tgt["group"] = blk.get("group", tgt["group"])
            tgt["per_cat"].update(blk.get("per_cat", {}))
    return merged


def _cos_map(store, rule_id):
    blk = store.get("rules", {}).get(rule_id)
    if not blk:
        return {}
    return {c: r["cos"] for c, r in blk["per_cat"].items() if np.isfinite(r.get("cos", np.nan))}


def _paired_vs(cos_a, cos_b, n_boot=4000, boot_seed=7):
    """theta68(a) - theta68(b), bootstrapping the cats they share.

    Valid across RUNS as well as across rules: every root here is the same 50 bursts
    with the same true directions, only the CT score (and hence the selection) differs.
    """
    cats = sorted(set(cos_a) & set(cos_b))
    if len(cats) < 5:
        return None
    a = np.array([cos_a[c] for c in cats])
    b = np.array([cos_b[c] for c in cats])

    def t68(c):
        return float(np.degrees(np.arccos(np.clip(np.quantile(c, 0.32), -1.0, 1.0))))

    rng = np.random.default_rng(boot_seed)
    d = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, len(cats), len(cats))
        d[i] = t68(a[idx]) - t68(b[idx])
    return {"n_cats": len(cats), "dtheta68_deg": t68(a) - t68(b),
            "lo68": float(np.percentile(d, 16.0)), "hi68": float(np.percentile(d, 84.0)),
            "p_improves": float(np.mean(d < 0.0))}


def run_compare(args):
    """Side-by-side of several finished scans (one json per run) + paired bootstrap."""
    runs = {}
    for item in args.compare.split(","):
        if "=" not in item:
            raise SystemExit(f"--compare entries must be label=path, got {item!r}")
        label, path = item.split("=", 1)
        runs[label.strip()] = json.load(open(path.strip()))
    ref_label, ref_rule = args.compare_ref.split(":")
    ref_label, ref_rule = ref_label.strip(), ref_rule.strip()
    if ref_label not in runs:
        raise SystemExit(f"--compare-ref label {ref_label!r} not among {list(runs)}")
    ref_cos = _cos_map(runs[ref_label], ref_rule)

    # make sure every run has an up-to-date aggregate block
    for st in runs.values():
        if "aggregate" not in st:
            base = st.get("rules", {}).get("R0", {}).get("per_cat")
            st["aggregate"] = {}
            for rid, blk in st.get("rules", {}).items():
                if not blk.get("per_cat"):
                    continue
                a = aggregate_rule(blk["per_cat"], base_per_cat=(None if rid == "R0" else base))
                a["label"] = blk.get("label", rid)
                st["aggregate"][rid] = a

    L = []
    A = L.append
    A("# Cross-run comparison of CT selection rules")
    A("")
    A("Every run below is the SAME 50 bursts (cat000623-cat000672) with the same true")
    A("directions and the same likelihood, sampler and pdf; only the CT score that drives")
    A("the selection differs. A paired bootstrap over those shared bursts is therefore")
    A("meaningful ACROSS runs as well as across rules, and is the only statement here that")
    A("is not swamped by burst-to-burst scatter.")
    A("")
    A(f"Reference for every paired number: **{ref_label} / {ref_rule}** "
      f"(theta68 = {runs[ref_label]['aggregate'][ref_rule]['theta68_deg']:.2f} deg).")
    A("")

    rule_ids = [r.strip() for r in args.compare_rules.split(",") if r.strip()] if args.compare_rules else None
    if rule_ids:
        A("## Side-by-side on the requested rules")
        A("")
        A("| rule | " + " | ".join(f"{lb} theta68" for lb in runs) + " |")
        A("|---|" + "---:|" * len(runs))
        for rid in rule_ids:
            cells = []
            for lb, st in runs.items():
                a = st.get("aggregate", {}).get(rid)
                cells.append("-" if not a or a.get("n_cats", 0) == 0 else
                             f"{a['theta68_deg']:.2f} [{a['theta68_lo68']:.2f}, {a['theta68_hi68']:.2f}]")
            A(f"| {rid} | " + " | ".join(cells) + " |")
        A("")
        A("| rule | " + " | ".join(f"{lb} \\<n sel\\> / ES purity / ES eff E>10" for lb in runs) + " |")
        A("|---|" + "---|" * len(runs))
        for rid in rule_ids:
            cells = []
            for lb, st in runs.items():
                a = st.get("aggregate", {}).get(rid)
                cells.append("-" if not a or a.get("n_cats", 0) == 0 else
                             f"{a['n_sel_mean']:.0f} / {100*a['es_purity']:.1f}% / {100*a['es_eff_e10']:.1f}%")
            A(f"| {rid} | " + " | ".join(cells) + " |")
        A("")

    A("## Best rule per run, paired against the reference")
    A("")
    A("| run | best rule | theta68 [68% boot] | d(theta68) vs ref | paired-boot 68% | P(beats ref) | \\<n sel\\> | ES purity |")
    A("|---|---|---|---:|---:|---:|---:|---:|")
    summary = {}
    for lb, st in runs.items():
        aggs = st.get("aggregate", {})
        # ceilings (R5_*) are truth-based, not deployable rules -> excluded from "best"
        cand = {k: v for k, v in aggs.items()
                if not k.startswith("R5_") and v.get("n_cats", 0) >= 45
                and "theta68_deg" in v}
        if not cand:
            continue
        best = min(cand, key=lambda k: cand[k]["theta68_deg"])
        a = cand[best]
        pb = _paired_vs(_cos_map(st, best), ref_cos)
        summary[lb] = {"best_rule": best, "theta68_deg": a["theta68_deg"], "paired_vs_ref": pb}
        A(f"| {lb} | {best} | {a['theta68_deg']:.2f} [{a['theta68_lo68']:.2f}, {a['theta68_hi68']:.2f}] | "
          f"{pb['dtheta68_deg']:+.2f} | [{pb['lo68']:+.2f}, {pb['hi68']:+.2f}] | {pb['p_improves']:.2f} | "
          f"{a['n_sel_mean']:.0f} | {100*a['es_purity']:.1f}% |")
    A("")

    A("## Every rule of every run, paired against the reference")
    A("")
    A("| run | rule | theta68 | d(theta68) vs ref | paired-boot 68% | P(beats ref) |")
    A("|---|---|---:|---:|---:|---:|")
    allrows = []
    for lb, st in runs.items():
        for rid, a in st.get("aggregate", {}).items():
            if a.get("n_cats", 0) < 45 or "theta68_deg" not in a:
                continue
            pb = _paired_vs(_cos_map(st, rid), ref_cos)
            if pb is None:
                continue
            allrows.append((a["theta68_deg"], lb, rid, a, pb))
    for th, lb, rid, a, pb in sorted(allrows):
        A(f"| {lb} | {rid} | {th:.2f} | {pb['dtheta68_deg']:+.2f} | "
          f"[{pb['lo68']:+.2f}, {pb['hi68']:+.2f}] | {pb['p_improves']:.2f} |")
    A("")

    Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_md, "w") as f:
        f.write("\n".join(L) + "\n")
    with open(args.out_json, "w") as f:
        json.dump({"reference": {"run": ref_label, "rule": ref_rule},
                   "summary": summary,
                   "rows": [{"run": lb, "rule": rid, "theta68_deg": th,
                             "paired_vs_ref": pb} for th, lb, rid, a, pb in sorted(allrows)]},
                  f, indent=1)
    print(f"saved {args.out_json} and {args.out_md}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input-root", default=None,
                    help="scenario output root (required except in --compare mode)")
    ap.add_argument("--scenario", default="scenario_7_mixture_ct")
    ap.add_argument("--pdf", default=None, help="pure-ES cosine-energy pdf (data/cosine_energy_pdf.npz)")
    ap.add_argument("--rules", default="all",
                    help="comma list of rule ids or group ids (R0,R1,...) or 'all'")
    ap.add_argument("--cats", default=None, help="comma list of cat names (default: all found)")
    ap.add_argument("--diagnostic-only", action="store_true")
    ap.add_argument("--merge", default=None, help="glob of partial jsons to merge into the report")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--note", default=None,
                    help="caveat text stored in meta and rendered as a blockquote in the md")
    ap.add_argument("--compare", default=None,
                    help="comma list of label=finished_scan.json to compare side by side")
    ap.add_argument("--compare-ref", default=None,
                    help="label:rule_id used as the reference for every paired bootstrap")
    ap.add_argument("--compare-rules", default=None,
                    help="comma list of rule ids for the side-by-side table")
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    args = ap.parse_args()

    if args.compare:
        if not args.compare_ref:
            raise SystemExit("--compare needs --compare-ref label:rule_id")
        run_compare(args)
        return

    if args.merge:
        store = merge_stores(args.merge)
        if args.note:
            store.setdefault("meta", {})["note"] = args.note
        write_report(store, args.out_json, args.out_md)
        n = {k: len(v["per_cat"]) for k, v in store["rules"].items()}
        print(f"merged {len(store['rules'])} rules: {n}")
        print(f"saved {args.out_json} and {args.out_md}")
        return

    if not args.input_root:
        raise SystemExit("--input-root is required")
    cats = set(c.strip() for c in args.cats.split(",")) if args.cats else None
    t0 = time.time()
    events = load_events(Path(args.input_root), args.scenario, cats)
    print(f"loaded {len(events)} cats in {time.time()-t0:.1f}s", flush=True)
    if not events:
        raise SystemExit("no events found")

    diag = diagnostic_table(events)
    r3 = derive_r3_thresholds(events)
    rules = build_rules(r3)

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    store = {}
    if args.resume and out_json.exists():
        try:
            store = json.load(open(out_json))
        except Exception as e:
            print(f"could not resume from {out_json}: {e}")
            store = {}
    store.setdefault("meta", {})
    store["meta"].update({
        "input_root": str(args.input_root), "scenario": args.scenario,
        "pdf": str(args.pdf), "emcee_cfg": EMCEE_CFG,
        "cats": sorted(events), "n_cats": len(events),
        "note": args.note,
        "diag_edges": [float(v) if np.isfinite(v) else None for v in DIAG_EDGES],
        "r3_edges": [float(v) if np.isfinite(v) else None for v in R3_EDGES],
    })
    store["diagnostic"] = diag
    store["r3_thresholds"] = r3
    store.setdefault("rules", {})

    if args.diagnostic_only:
        write_report(store, args.out_json, args.out_md)
        print(f"diagnostic only -> {args.out_json} / {args.out_md}")
        return

    pdf_interp = load_pdf_interpolator(args.pdf)
    if pdf_interp is None:
        raise SystemExit(f"could not load pdf interpolator from {args.pdf}")

    want = [w.strip() for w in args.rules.split(",") if w.strip()]
    if "all" in want:
        todo = rules
    else:
        todo = [r for r in rules if r["id"] in want or r["group"] in want]
    print(f"running {len(todo)} rules x {len(events)} cats: {[r['id'] for r in todo]}", flush=True)

    for r in todo:
        blk = store["rules"].setdefault(r["id"], {"label": r["label"], "group": r["group"],
                                                  "per_cat": {}})
        blk["label"], blk["group"] = r["label"], r["group"]
        done = 0
        for i, (cat, ev) in enumerate(sorted(events.items())):
            if cat in blk["per_cat"]:
                continue
            row = run_rule_on_cat(ev, r["fn"], pdf_interp)
            blk["per_cat"][cat] = row
            done += 1
            print(f"{r['id']} {cat}: n={row['n_sel']} nES={row['n_es_sel']} "
                  f"theta={row['theta_deg']:.2f} ({row.get('wall_s', float('nan')):.1f}s)", flush=True)
            if done % 10 == 0:
                with open(out_json, "w") as f:
                    json.dump(store, f, indent=1)
        with open(out_json, "w") as f:  # partial save after every rule
            json.dump(store, f, indent=1)
        print(f"--- finished {r['id']} ({time.time()-t0:.0f}s elapsed)", flush=True)

    write_report(store, args.out_json, args.out_md)
    print(f"saved {args.out_json} and {args.out_md}")


if __name__ == "__main__":
    main()
