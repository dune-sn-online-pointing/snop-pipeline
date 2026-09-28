#!/usr/bin/env python3
"""Read-only: compare the best-case scenario definition across campaigns (cat000001)."""
import json, sys, os

ROOT = "/eos/user/e/evilla/dune/sn-tps"
CAMPAIGNS = sys.argv[1:] if len(sys.argv) > 1 else [
    "condor_scenarios_corrected", "condor_scenarios_v2", "condor_scenarios_v3",
    "condor_scenarios_v4", "condor_scenarios_v80final",
    "condor_scenarios_v80gauss_final", "condor_scenarios_v80t080_final",
    "condor_scenarios_v80t080_merged1000",
]

def flat(d, p=''):
    o = {}
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, dict): o.update(flat(v, p + k + '.'))
            elif isinstance(v, list): o[p+k] = f"<list n={len(v)}>"
            else: o[p+k] = v
    return o

for c in CAMPAIGNS:
    base = os.path.join(ROOT, c, "cat000001")
    print("=" * 95)
    print("CAMPAIGN:", c)
    cfg = os.path.join(base, "scenario_analysis_config.json")
    if os.path.exists(cfg):
        d = json.load(open(cfg))
        f = flat(d)
        for k in sorted(f): print(f"   CFG {k} = {f[k]}")
    else:
        print("   (no scenario_analysis_config.json)")
    rep = os.path.join(base, "scenario_cos_theta_report.json")
    if os.path.exists(rep):
        d = json.load(open(rep))
        print("   REPORT top-level keys:", list(d)[:20])
        scen = d.get("scenarios", d)
        if isinstance(scen, list):
            it = [(s.get("label", s.get("name", "?")), s) for s in scen]
        else:
            it = list(scen.items())
        for name, s in it:
            f = flat(s)
            keep = {k: v for k, v in f.items() if any(t in k.lower() for t in
                    ("label","name","selection","direction","min_energy","energy","n_sel","theta","cos","q68","prior","nsteps","nwalkers","stretch","kernel","pdf","seed","discard"))}
            print("   ---", name)
            for k in sorted(keep): print(f"        {k} = {keep[k]}")
