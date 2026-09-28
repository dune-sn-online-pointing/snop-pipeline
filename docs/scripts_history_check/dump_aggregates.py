#!/usr/bin/env python3
"""Read-only: dump scenario-level summary numbers from archived aggregate JSONs."""
import json, sys, os, glob

def num(v):
    try: return float(v)
    except Exception: return None

def walk_scalars(d, prefix=''):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            p = f"{prefix}{k}"
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out[p] = v
            elif isinstance(v, str) and len(v) < 80:
                out[p] = v
            elif isinstance(v, dict):
                out.update(walk_scalars(v, p + '.'))
            elif isinstance(v, list):
                out[p] = f"<list n={len(v)}>"
    return out

for f in sys.argv[1:]:
    d = json.load(open(f))
    print("=" * 100)
    print("FILE:", f)
    print("  input_root:", d.get('input_root'), " n_cats:", d.get('n_cats'))
    scen = d.get('scenarios', {})
    for name, s in scen.items():
        print("-" * 90)
        print("  SCENARIO:", name)
        sc = walk_scalars(s)
        for k in sorted(sc):
            print(f"      {k} = {sc[k]}")
