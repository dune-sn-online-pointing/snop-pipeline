#!/usr/bin/env python3
"""Unit checks for the GENERATED-event budget in python/lib/sample_loader.py.

The loader used to count events as a set of bare event numbers (metadata column 0).
Event numbers restart at 1..40 in EVERY input file, so that set saturated at 40, the
target (330 ES / 3300 CC) was never reached and every file was loaded: every burst of
the v80 campaigns really contained 400 ES + up to 4000 CC generated events.

`event_budget_mode="generated"` (the new default) counts an event as
(file index in sorted order, event number), so

    ES  330 = files 1-8 complete + events 1..10 of file 9
    CC 3300 = files 1-82 complete + events 1..20 of file 83

Generated events that leave no 3-plane-matched cluster still consume the budget.

Run:  source scripts/init.sh && python3 test/test_event_budget.py
"""
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "python"))
sys.path.insert(0, str(REPO / "python" / "lib"))

from lib.sample_loader import load_and_select_samples, _load_samples_from_folder

# One of the 50 dev cats that still carry the FULL products (CC cluster images included).
CAT = "cat000623"
PRODUCTS = Path("/eos/user/e/evilla/dune/sn-tps/mixture_dev_samples") / CAT / \
    f"{CAT}_cluster_images_tick3_ch2_min2_tot3_e3p0"
N_ES, N_CC = 330, 3300
EVENTS_PER_FILE = 40

failures = []


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


def file_index_of_rows(product_dir, pattern):
    """Ground truth: (file index, event number) of every row the loader would emit,
    obtained by replaying the 3-plane match file by file (no budget)."""
    files = sorted((Path(product_dir) / "X").glob(pattern))
    out = []
    for fi, fp in enumerate(files):
        mx = np.load(fp, allow_pickle=True)["metadata"]
        mu = np.load(Path(product_dir) / "U" / fp.name.replace("planeX", "planeU"),
                     allow_pickle=True)["metadata"]
        mv = np.load(Path(product_dir) / "V" / fp.name.replace("planeX", "planeV"),
                     allow_pickle=True)["metadata"]

        def idx(m):
            return {int(v): i for i, v in enumerate(m[:, 13]) if m[i, 2] == 1 and v != -1}

        ix, iu, iv = idx(mx), idx(mu), idx(mv)
        for mid in sorted(set(ix) & set(iu) & set(iv)):
            out.append((fi, int(mx[ix[mid], 0]), mx[ix[mid]]))
    return out, len(files)


print(f"products: {PRODUCTS}")
assert PRODUCTS.is_dir(), f"missing dev products: {PRODUCTS}"

for tag, pattern, target, n_full, n_rest in (
    ("ES", "es_*_planeX.npz", N_ES, N_ES // EVENTS_PER_FILE, N_ES % EVENTS_PER_FILE),
    ("CC", "cc_*_planeX.npz", N_CC, N_CC // EVENTS_PER_FILE, N_CC % EVENTS_PER_FILE),
):
    print(f"\n=== {tag}: target {target} generated events "
          f"= {n_full} full files + first {n_rest} events of file {n_full + 1} ===")
    truth, n_files_total = file_index_of_rows(PRODUCTS, pattern)

    got = _load_samples_from_folder(
        str(PRODUCTS), target, pattern, sample_type=tag, load_all_planes=True,
        event_budget_mode="generated", events_per_file=EVENTS_PER_FILE)
    meta = got["metadata"]

    expect = [(fi, ev, m) for fi, ev, m in truth
              if fi < n_full or (fi == n_full and ev <= n_rest)]
    check(meta.shape[0] == len(expect),
          f"{tag}: {meta.shape[0]} rows loaded, {len(expect)} expected from the replay")
    if meta.shape[0] == len(expect) and meta.shape[0]:
        ref = np.array([m for _, _, m in expect], dtype=np.float32)
        check(np.array_equal(meta, ref), f"{tag}: metadata rows identical to the replay")

    # the structural assertions the user asked for, read off the loaded rows themselves
    fidx = np.array([fi for fi, _, _ in expect])
    evs = np.array([ev for _, ev, _ in expect])
    check(fidx.max() == n_full, f"{tag}: highest file index used is {fidx.max()} (= file {n_full + 1})")
    check(bool(np.all(evs[fidx == n_full] <= n_rest)),
          f"{tag}: file {n_full + 1} contributes only events <= {n_rest} "
          f"(max {evs[fidx == n_full].max() if np.any(fidx == n_full) else 'n/a'})")
    check(bool(np.all(evs[fidx < n_full] <= EVENTS_PER_FILE)),
          f"{tag}: complete files contribute events <= {EVENTS_PER_FILE}")
    check(got["n_files_budget"] == n_full + 1, f"{tag}: n_files_budget == {n_full + 1}")
    check(got["n_events_budget"] == target, f"{tag}: n_events_budget == {target}")
    n_budgeted_events = len({(fi, ev) for fi, ev, _ in expect})
    check(got["n_events"] == n_budgeted_events,
          f"{tag}: n_events == {n_budgeted_events} generated events that left a matched cluster "
          f"(of {target} budgeted)")

    # legacy mode must reproduce the OLD row set exactly: every file, every event
    legacy = _load_samples_from_folder(
        str(PRODUCTS), target, pattern, sample_type=tag, load_all_planes=True,
        event_budget_mode="legacy", events_per_file=EVENTS_PER_FILE)
    ref_all = np.array([m for _, _, m in truth], dtype=np.float32)
    check(legacy["metadata"].shape[0] == len(truth),
          f"{tag}: legacy loads all {len(truth)} rows (got {legacy['metadata'].shape[0]})")
    check(np.array_equal(legacy["metadata"], ref_all),
          f"{tag}: legacy metadata identical to the full replay")
    check(len(legacy["files_used"]) == n_files_total,
          f"{tag}: legacy used all {n_files_total} files")
    check(legacy["n_events"] == EVENTS_PER_FILE,
          f"{tag}: legacy event set saturates at {EVENTS_PER_FILE} (the defect) "
          f"- got {legacy['n_events']}")

print("\n=== top-level load_and_select_samples ===")
sel = load_and_select_samples(
    cc_folder=str(PRODUCTS), es_folder=str(PRODUCTS),
    n_cc_events=N_CC, n_es_events=N_ES,
    cc_file_pattern="cc_*_planeX.npz", es_file_pattern="es_*_planeX.npz",
    load_all_planes=True, shuffle=True, random_seed=42,
    event_budget_mode="generated", events_per_file=EVENTS_PER_FILE)
check(sel["n_cc_files_budget"] == 83 and sel["n_es_files_budget"] == 9,
      f"file budgets: CC {sel['n_cc_files_budget']} (83), ES {sel['n_es_files_budget']} (9)")
check(sel["event_budget_mode"] == "generated", "event_budget_mode reported in the result")
n_es_rows = int(np.sum(sel["metadata"][:, 3] == 1))
print(f"  rows: {sel['total_clusters']} total, {n_es_rows} ES, "
      f"{sel['total_clusters'] - n_es_rows} CC")

legacy_top = load_and_select_samples(
    cc_folder=str(PRODUCTS), es_folder=str(PRODUCTS),
    n_cc_events=N_CC, n_es_events=N_ES,
    cc_file_pattern="cc_*_planeX.npz", es_file_pattern="es_*_planeX.npz",
    load_all_planes=True, shuffle=True, random_seed=42,
    event_budget_mode="legacy", events_per_file=EVENTS_PER_FILE)
check(legacy_top["total_clusters"] > sel["total_clusters"],
      f"legacy loads more rows ({legacy_top['total_clusters']}) than the budget "
      f"({sel['total_clusters']})")

print("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} FAILURES:"))
for f in failures:
    print("  - " + f)
sys.exit(1 if failures else 0)
