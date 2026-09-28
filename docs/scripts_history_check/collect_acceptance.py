#!/usr/bin/env python3
"""Read-only: pull acceptance_fraction + best-case error from per-CAT scenario reports."""
import json, os, sys, glob
import numpy as np

ROOT = "/eos/user/e/evilla/dune/sn-tps"
for camp in sys.argv[1:]:
    rows = []
    for p in sorted(glob.glob(os.path.join(ROOT, camp, "cat*", "scenario_cos_theta_report.json")))[:400]:
        try:
            d = json.load(open(p))
        except Exception:
            continue
        sc = d.get("scenarios", [])
        it = sc if isinstance(sc, list) else list(sc.values())
        for s in it:
            if s.get("scenario", "").startswith("scenario_1"):
                rows.append((s.get("acceptance_fraction"), s.get("single_pass_theta_deg"),
                             s.get("q68_theta_deg"), s.get("forward_frac"), s.get("n_selected")))
                break
    if not rows:
        print(f"{camp}: no rows"); continue
    a = np.array([r[0] if r[0] is not None else np.nan for r in rows], float)
    t = np.array([r[1] if r[1] is not None else np.nan for r in rows], float)
    q = np.array([r[2] if r[2] is not None else np.nan for r in rows], float)
    f = np.array([r[3] if r[3] is not None else np.nan for r in rows], float)
    print(f"{camp:38s} n={len(rows):4d} accept med={np.nanmedian(a):.4f} "
          f"[{np.nanpercentile(a,5):.4f},{np.nanpercentile(a,95):.4f}]  "
          f"theta med={np.nanmedian(t):.3f} t68={np.degrees(np.arccos(np.quantile(np.cos(np.radians(t[np.isfinite(t)])),0.32))):.3f}  "
          f"q68 med={np.nanmedian(q):.2f}  fwd med={np.nanmedian(f):.4f}")
