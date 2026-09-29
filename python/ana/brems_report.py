#!/usr/bin/env python3
"""Diagnostic tables for the brems / purity-conditioning study (markdown on stdout).

Input: the per-event table from `brems_collect.py`.  Read-only.

Sections
  1  energy mis-assignment for CT-selected true ES (E_true vs E_reco, secondary energy)
  2  pointing quality inside a reco-energy bin vs true energy / secondaries
  3  purity vs topology and vs CT score at fixed reco energy
  4  CT efficiency for ES with and without brems companions
  5  the CC component: flat versus the burst axis, and in the detector frame

Usage: python3 python/ana/brems_report.py --collect <npz> [--collect2 <npz> --label2 eval]
"""
import argparse
import sys
from pathlib import Path

import numpy as np

EB = [(5, 6), (6, 8), (8, 10), (10, 12), (12, 14), (14, 25)]
CT_MIN, E_MIN = 0.80, 5.0


def load(path):
    z = np.load(path, allow_pickle=True)
    A = np.asarray(z["table"], dtype=np.float64)
    C = {c: A[:, i] for i, c in enumerate(list(z["cols"]))}
    return C, np.asarray(z["cats"])


def q(x, p):
    return float(np.nanquantile(x, p)) if np.isfinite(x).any() else float("nan")


def sem(x):
    x = x[np.isfinite(x)]
    return float(x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 1 else float("nan")


def anis(d):
    """Detector-frame anisotropy of unit vectors d: (|R|, 1/sqrt(N), mean vec, tensor eigs)."""
    n = len(d)
    if n < 10:
        return np.nan, np.nan, np.full(3, np.nan), np.full(3, np.nan)
    R = d.mean(axis=0)
    T = (d[:, :, None] * d[:, None, :]).mean(axis=0)
    eig = np.sort(np.linalg.eigvalsh(T))[::-1]
    return float(np.linalg.norm(R)), 1.0 / np.sqrt(n), R, eig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", required=True)
    ap.add_argument("--collect2", default=None)
    ap.add_argument("--label", default="slice 673-900")
    ap.add_argument("--label2", default="eval")
    args = ap.parse_args()

    C, cats = load(args.collect)
    sel = (C["ct"] >= CT_MIN) & (C["e_reco"] >= E_MIN)
    es = C["is_es"] == 1
    Ses, Scc = sel & es, sel & ~es
    print(f"# brems study diagnostics -- {args.label}: {len(cats)} cats, "
          f"{int(sel.sum())} selected events ({sel.sum()/len(cats):.1f}/burst), "
          f"purity {Ses.sum()/sel.sum():.4f}\n")

    esec = np.nan_to_num(C["e_sec_es"], nan=0.0)
    nsec = C["n_sec_es"]
    eprime = C["e_reco"] + esec
    fsec = np.where(eprime > 0, esec / eprime, 0.0)

    # ---------------------------------------------------------------- 1
    print("## 1. Energy mis-assignment of CT-selected true ES\n")
    print("| E_reco [MeV] | N | med E_true | med (E_true-E_reco) | q10 | q90 | "
          "frac E_reco<0.8 E_true | <n_sec> | frac n_sec>0 | med E_sec [MeV] | "
          "<E_sec/E'> | med (E_true-E') |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for lo, hi in EB:
        m = Ses & (C["e_reco"] >= lo) & (C["e_reco"] < hi)
        if m.sum() < 5:
            continue
        dE = C["e_true"][m] - C["e_reco"][m]
        dE2 = C["e_true"][m] - eprime[m]
        ns = nsec[m]
        ok = np.isfinite(ns)
        print(f"| {lo}-{hi} | {int(m.sum())} | {np.median(C['e_true'][m]):.2f} | "
              f"{np.median(dE):+.2f} | {q(dE,0.1):+.2f} | {q(dE,0.9):+.2f} | "
              f"{np.mean(C['e_reco'][m] < 0.8*C['e_true'][m]):.3f} | "
              f"{np.nanmean(ns):.3f} | {np.mean(ns[ok] > 0) if ok.any() else np.nan:.3f} | "
              f"{np.median(esec[m][esec[m]>0]) if (esec[m]>0).any() else 0:.2f} | "
              f"{np.mean(fsec[m]):.3f} | {np.median(dE2):+.2f} |")

    # ---------------------------------------------------------------- 2
    print("\n## 2. Pointing quality inside a reco-energy bin\n")
    print("### 2a. split by true energy (terciles of E_true within the reco bin)\n")
    print("| E_reco [MeV] | N | <cos> all | T1 E_true range | <cos> T1 | T2 | <cos> T2 | "
          "T3 | <cos> T3 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for lo, hi in EB:
        m = Ses & (C["e_reco"] >= lo) & (C["e_reco"] < hi)
        if m.sum() < 60:
            continue
        et, cb = C["e_true"][m], C["cos_burst"][m]
        e1, e2 = np.quantile(et, [1/3, 2/3])
        g = [et < e1, (et >= e1) & (et < e2), et >= e2]
        cells = []
        for gg, rng in zip(g, [f"<{e1:.1f}", f"{e1:.1f}-{e2:.1f}", f">{e2:.1f}"]):
            cells += [rng, f"{cb[gg].mean():.3f}+-{sem(cb[gg]):.3f}"]
        print(f"| {lo}-{hi} | {int(m.sum())} | {cb.mean():.3f} | " + " | ".join(cells) + " |")

    print("\n### 2b. split by presence of secondary MARLEY clusters (brems companions)\n")
    print("| E_reco [MeV] | N(n_sec=0) | <cos> | N(n_sec>=1) | <cos> | delta | "
          "<E_true> clean | <E_true> brems |")
    print("|---|---|---|---|---|---|---|---|")
    for lo, hi in EB:
        m = Ses & (C["e_reco"] >= lo) & (C["e_reco"] < hi) & np.isfinite(nsec)
        a, b = m & (nsec == 0), m & (nsec >= 1)
        if a.sum() < 20:
            continue
        ca, cb = C["cos_burst"][a], C["cos_burst"][b]
        d = (cb.mean() - ca.mean()) if b.sum() > 3 else np.nan
        print(f"| {lo}-{hi} | {int(a.sum())} | {ca.mean():.3f}+-{sem(ca):.3f} | {int(b.sum())} | "
              f"{cb.mean():.3f}+-{sem(cb):.3f} | {d:+.3f} | "
              f"{C['e_true'][a].mean():.2f} | {C['e_true'][b].mean():.2f} |")

    print("\n### 2c. split by n_marley_clusters in the volume (available for ES and CC)\n")
    print("| E_reco [MeV] | N(n_mar=1) | <cos> ES | N(n_mar>=2) | <cos> ES | delta |")
    print("|---|---|---|---|---|---|")
    nm = C["n_marley_vol"]
    for lo, hi in EB:
        m = Ses & (C["e_reco"] >= lo) & (C["e_reco"] < hi) & np.isfinite(nm)
        a, b = m & (nm == 1), m & (nm >= 2)
        if a.sum() < 20:
            continue
        ca, cb = C["cos_burst"][a], C["cos_burst"][b]
        print(f"| {lo}-{hi} | {int(a.sum())} | {ca.mean():.3f}+-{sem(ca):.3f} | {int(b.sum())} | "
              f"{cb.mean():.3f}+-{sem(cb):.3f} | "
              f"{(cb.mean()-ca.mean()) if b.sum()>3 else np.nan:+.3f} |")

    # ---------------------------------------------------------------- 3
    print("\n## 3. Purity at fixed reco energy\n")
    print("### 3a. f vs n_marley_clusters in the volume\n")
    print("| E_reco [MeV] | N | f all | N(n_mar=1) | f | N(n_mar=2) | f | N(n_mar>=3) | f |")
    print("|---|---|---|---|---|---|---|---|---|")
    for lo, hi in EB:
        m = sel & (C["e_reco"] >= lo) & (C["e_reco"] < hi) & np.isfinite(nm)
        if m.sum() < 50:
            continue
        cells = []
        for cond in (nm == 1, nm == 2, nm >= 3):
            mm = m & cond
            f = (mm & es).sum() / max(mm.sum(), 1)
            cells += [f"{int(mm.sum())}", f"{f:.3f}+-{np.sqrt(f*(1-f)/max(mm.sum(),1)):.3f}"]
        fa = (m & es).sum() / m.sum()
        print(f"| {lo}-{hi} | {int(m.sum())} | {fa:.3f} | " + " | ".join(cells) + " |")

    print("\n### 3b. f vs CT score, per reco-energy bin\n")
    sedges = [0.80, 0.8196, 0.8383, 0.8566, 0.8746, 1.0001]   # quintiles of the selected sample
    hdr = " | ".join(f"[{sedges[i]:.2f},{sedges[i+1]:.2f})" for i in range(len(sedges)-1))
    print(f"| E_reco [MeV] | N | f all | {hdr} |")
    print("|---|---|---|" + "---|" * (len(sedges) - 1))
    for lo, hi in EB:
        m = sel & (C["e_reco"] >= lo) & (C["e_reco"] < hi)
        if m.sum() < 50:
            continue
        cells = []
        for i in range(len(sedges) - 1):
            mm = m & (C["ct"] >= sedges[i]) & (C["ct"] < sedges[i+1])
            f = (mm & es).sum() / max(mm.sum(), 1)
            cells.append(f"{f:.3f} (n={int(mm.sum())})" if mm.sum() >= 20 else f"- (n={int(mm.sum())})")
        print(f"| {lo}-{hi} | {int(m.sum())} | {(m&es).sum()/m.sum():.3f} | " + " | ".join(cells) + " |")
    for i in range(len(sedges) - 1):
        mm = sel & (C["ct"] >= sedges[i]) & (C["ct"] < sedges[i+1])
        print(f"* score [{sedges[i]:.2f},{sedges[i+1]:.2f}): n={int(mm.sum())}, "
              f"f={(mm&es).sum()/max(mm.sum(),1):.4f}, "
              f"<cos> ES {C['cos_burst'][mm&es].mean():.3f}, CC {C['cos_burst'][mm&~es].mean():+.3f}")

    # ---------------------------------------------------------------- 4
    print("\n## 4. CT efficiency for true ES with and without brems companions\n")
    print("| E_reco [MeV] | N(n_sec=0) | eff@0.80 | N(n_sec>=1) | eff@0.80 | ratio |")
    print("|---|---|---|---|---|---|")
    for lo, hi in EB:
        m = es & (C["e_reco"] >= lo) & (C["e_reco"] < hi) & np.isfinite(nsec)
        a, b = m & (nsec == 0), m & (nsec >= 1)
        if a.sum() < 20:
            continue
        ea = (C["ct"][a] >= CT_MIN).mean()
        eb = (C["ct"][b] >= CT_MIN).mean() if b.sum() > 5 else np.nan
        print(f"| {lo}-{hi} | {int(a.sum())} | {ea:.3f} | {int(b.sum())} | {eb:.3f} | "
              f"{eb/ea if ea > 0 else np.nan:.2f} |")

    # ---------------------------------------------------------------- 5
    print("\n## 5. The CC component\n")
    for label, path in [(args.label, args.collect)] + \
                       ([(args.label2, args.collect2)] if args.collect2 else []):
        CC, cc_cats = load(path) if path != args.collect else (C, cats)
        s = (CC["ct"] >= CT_MIN) & (CC["e_reco"] >= E_MIN)
        e2 = CC["is_es"] == 1
        print(f"\n### 5a. {label}: <cos to burst> of CT-selected events per reco-E bin\n")
        print("| E_reco [MeV] | N_CC | <cos> CC | +-  | N_ES | <cos> ES | N_rad(non-MARLEY) | <cos> |")
        print("|---|---|---|---|---|---|---|---|")
        for lo, hi in EB:
            mc = s & ~e2 & (CC["e_reco"] >= lo) & (CC["e_reco"] < hi)
            me = s & e2 & (CC["e_reco"] >= lo) & (CC["e_reco"] < hi)
            mr = mc & (CC["is_marley"] == 0)
            if mc.sum() < 20:
                continue
            print(f"| {lo}-{hi} | {int(mc.sum())} | {CC['cos_burst'][mc].mean():+.4f} | "
                  f"{sem(CC['cos_burst'][mc]):.4f} | {int(me.sum())} | "
                  f"{CC['cos_burst'][me].mean():.4f} | {int(mr.sum())} | "
                  f"{CC['cos_burst'][mr].mean() if mr.sum()>5 else np.nan:+.4f} |")
        allcc = s & ~e2
        print(f"* all selected CC: N={int(allcc.sum())}, <cos to burst> = "
              f"{CC['cos_burst'][allcc].mean():+.4f} +- {sem(CC['cos_burst'][allcc]):.4f}")

        print(f"\n### 5b. {label}: detector-frame anisotropy of the selected reco directions\n")
        print("| class | E_reco [MeV] | N | \\|<d>\\| | 1/sqrt(N) | <d> (x,y,z) | "
              "tensor eigenvalues |")
        print("|---|---|---|---|---|---|---|")
        for cls, mcls in (("CC", ~e2), ("ES", e2)):
            for lo, hi in [(5, 8), (8, 12), (12, 25), (5, 25)]:
                m = s & mcls & (CC["e_reco"] >= lo) & (CC["e_reco"] < hi)
                if m.sum() < 50:
                    continue
                d = np.column_stack([CC["dx"][m], CC["dy"][m], CC["dz"][m]])
                R, iso, Rv, eig = anis(d)
                print(f"| {cls} | {lo}-{hi} | {int(m.sum())} | {R:.4f} | {iso:.4f} | "
                      f"({Rv[0]:+.3f},{Rv[1]:+.3f},{Rv[2]:+.3f}) | "
                      f"{eig[0]:.3f}/{eig[1]:.3f}/{eig[2]:.3f} |")


if __name__ == "__main__":
    main()
