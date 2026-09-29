#!/usr/bin/env python3
"""Wrapper around combo_gridfit.py for the threshold scan.

Loads combo_gridfit.py from a FROZEN copy of python/ (given by --frozen, stripped
from argv before the rest is forwarded unchanged to combo_gridfit.main()), so
these condor jobs are immune to the concurrent edit of python/ana/burst_direction.py
in the live checkout.

The only behavioural change relative to the checked-in script: RULE_THR is
extended in memory (t010/t015/t020/t025/t030/t035/t040/t060/t070/t090 added) so
that arm specs with "sel": "t0NN" select CT score >= 0.NN, exactly the same
selection_mask() logic already used for t050 (>=0.50) and t080 (>=0.80). t050,
t080 and all are left untouched -- same dict entries, same values, same code
path. This stands in for a `--rule NAME:THRESHOLD` CLI flag that combo_gridfit.py
does not have; it is applied to an in-memory module object loaded from the
frozen files, so nothing on disk is modified.
"""
import importlib.util
import sys

argv = sys.argv[1:]
assert argv[0] == "--frozen", "expected --frozen <dir> as first argument"
frozen_dir = argv[1]
rest = argv[2:]

spec = importlib.util.spec_from_file_location("combo_gridfit_frozen", frozen_dir + "/ana/combo_gridfit.py")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

assert mod.RULE_THR == {"t050": 0.50, "t080": 0.80, "all": 0.0}, mod.RULE_THR
mod.RULE_THR.update({"t010": 0.10, "t015": 0.15, "t020": 0.20, "t025": 0.25,
                     "t030": 0.30, "t035": 0.35, "t040": 0.40, "t060": 0.60,
                     "t070": 0.70, "t090": 0.90})

sys.argv = ["combo_gridfit.py"] + rest
mod.main()
