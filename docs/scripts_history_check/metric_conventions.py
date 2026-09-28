#!/usr/bin/env python3
"""Read-only: the same per-burst results under every metric convention that has
been used historically, so the 'which number is right' question can be settled.
"""
import json, sys
import numpy as np

def rows(path, match="Best case"):
    d = json.load(open(path))
    for name, s in d.get("scenarios", {}).items():
        if match.lower() in name.lower() or "true electron direction" in name.lower() or "best case" in name.lower():
            c = np.asarray(s["cos_all"], float); c = c[np.isfinite(c)]
            return name, c, float(np.mean(s["n_selected_all"]))
    return None, None, None

hdr = (f"{'campaign':<34} {'n':>4} {'<N>':>5} | {'Q68cont':>8} {'median':>7} {'mean':>7} "
       f"{'Q32cont':>8} {'acos(q68cos)':>12} {'acos(<cos>)':>11} {'Q90cont':>8} {'Q95cont':>8}")
print(hdr); print("-" * len(hdr))
for p in sys.argv[1:]:
    name, c, N = rows(p)
    if c is None:
        print(f"{p.split('/')[-1][:34]:<34}  -- no matching scenario --"); continue
    th = np.degrees(np.arccos(np.clip(c, -1, 1)))
    def cont(q):  # q-containment radius of the angle
        return float(np.degrees(np.arccos(np.quantile(c, 1 - q))))
    tag = p.split("/")[-1].replace("scenario_aggregate", "").replace("condor_scenarios_", "")[:34]
    print(f"{tag:<34} {len(c):>4} {N:>5.0f} | {cont(0.68):>8.2f} {np.median(th):>7.2f} {th.mean():>7.2f} "
          f"{cont(0.32):>8.2f} {np.degrees(np.arccos(np.quantile(c,0.68))):>12.2f} "
          f"{np.degrees(np.arccos(c.mean())):>11.2f} {cont(0.90):>8.2f} {cont(0.95):>8.2f}")
print()
print("Q68cont  = 68% containment radius = arccos(32nd percentile of cos)  <-- current definition")
print("acos(q68cos) = arccos(68th percentile of cos) = 32% containment radius <-- tech-note figure definition")
