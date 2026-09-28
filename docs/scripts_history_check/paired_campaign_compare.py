#!/usr/bin/env python3
"""Read-only: paired per-CAT comparison of the best-case scenario across campaigns.

Uses cat_names + cos_all stored in the aggregate JSONs, restricted to CATs
common to all campaigns, so the comparison is not confounded by which CATs
survived in each run.
"""
import json, sys, numpy as np

def load(path, label_match="Best case"):
    d = json.load(open(path))
    for name, s in d.get("scenarios", {}).items():
        if label_match.lower() in name.lower():
            return dict(zip(s["cat_names"], s["cos_all"])), name
    return {}, None

def theta68(cosvals):
    c = np.asarray(cosvals, dtype=float)
    c = c[np.isfinite(c)]
    return float(np.degrees(np.arccos(np.quantile(c, 0.32))))

def stats(cosvals):
    c = np.asarray(cosvals, dtype=float); c = c[np.isfinite(c)]
    th = np.degrees(np.arccos(np.clip(c, -1, 1)))
    return dict(n=len(c), t68=theta68(c), median=float(np.median(th)),
                mean=float(np.mean(th)), p90=float(np.quantile(th, 0.90)),
                p95=float(np.quantile(th, 0.95)), max=float(th.max()))

if __name__ == "__main__":
    label = "Best case"
    files = sys.argv[1:]
    maps = {}
    for f in files:
        tag = f.split("/")[-1]
        m, nm = load(f, label)
        if m:
            maps[tag] = m
    common = set.intersection(*[set(m) for m in maps.values()])
    print(f"Scenario matched on '{label}'. Campaigns: {len(maps)}. Common CATs: {len(common)}")
    common = sorted(common)
    print()
    hdr = f"{'campaign':<62} {'nAll':>5} {'t68All':>7} {'nCom':>5} {'t68Com':>7} {'medCom':>7} {'meanCom':>8} {'p90':>7} {'p95':>7} {'max':>7}"
    print(hdr); print("-" * len(hdr))
    for tag, m in maps.items():
        a = stats(list(m.values()))
        b = stats([m[c] for c in common])
        print(f"{tag:<62} {a['n']:>5} {a['t68']:>7.2f} {b['n']:>5} {b['t68']:>7.2f} {b['median']:>7.2f} {b['mean']:>8.2f} {b['p90']:>7.2f} {b['p95']:>7.2f} {b['max']:>7.2f}")
