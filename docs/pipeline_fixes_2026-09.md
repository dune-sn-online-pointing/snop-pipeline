# Pointing-pipeline fixes, September 2026

Reference sample: 50 development bursts (cats 623-672), regenerated products under
`/eos/user/e/evilla/dune/sn-tps/mixture_dev_samples`, CT v80 at threshold 0.80, ED v58.
Metric: theta68 = 68% containment of the angle between the reconstructed and true burst
direction across bursts (arccos of the 0.32 quantile of the cosine). All comparisons are
paired on the same bursts; intervals are bootstrap-over-bursts 68%.
Cats 400-621 (network training) are never used for evaluation.

## Reference numbers: 1000 bursts at the correct composition (2026-09-21)

A seventh defect surfaced after the rerun below: the sample loader never enforced its
330 ES / 3300 CC event targets. It counted distinct event numbers, which restart at 1..40
in every file, so the counter saturated at 40 and every file was always loaded: all bursts
evaluated until now contained 400 generated ES and about 3940 generated CC events. The
loader now counts GENERATED events by (file, event number): a burst is the first 330
generated ES and the first 3300 generated CC events, before any cut
(`sample_selection.event_budget_mode`: `generated` (default) | `legacy`;
`test/test_event_budget.py`). The campaign was re-evaluated offline from its kept
per-event outputs (`python/ana/budget_replay.py`; file index of every row recovered for
1000/1000 cats; with the budget off the replay reproduces n_selected exactly for 360/360
cat-scenario pairs and the fitted direction bit-exactly for 231/360, the rest within one
MCMC realisation, at most 0.12 deg, a residual whose origin in the archived fits is not
understood).

| scenario | old campaign | fixed code, all events | fixed code, 330 + 3300 |
|---|---|---|---|
| 1 best case (true ES, true directions) | 5.98 | 0.75 | 0.80 |
| 2 perfect CT (true ES, reco directions) | 11.03 | 10.11 | 10.36 |
| 3 full pipeline (CT >= 0.80, E > 5 MeV) | 18.40 | 16.48 | 17.75 |
| 4 weighted CT (all events, P(ES) weight) | 29.97 | 20.48 | 20.87 |
| 5 perfect CT, E > 10 MeV | 9.67 | 10.03 | 10.12 |
| 6 perfect CT, E > 5 MeV | 10.37 | 9.88 | 10.20 |

Per burst the correct composition gives 330 generated -> 197 matched ES and 3298 generated
-> 2056 matched CC events (all-events: 400 -> 239 and 3942 -> 2457). The right-hand column
is the reference from now on; full pipeline 17.75 deg is +1.27 [+0.88, +1.49] against the
all-events rerun and -0.65 [-1.24, -0.12] against the old campaign, whose inflated bursts
had hidden part of its own defects. cat000001 (only 1480 generated CC events) is included
and flagged `reduced_cc_statistics`; its scenarios 3 and 4 are not comparable. Files:
`/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-campaign/v80_fixed_1000_budget330/`.
The official aggregator must be run with `--no-min-selected` at this composition, since its
200-event true-ES filter would otherwise drop half of the bursts.

## The 999-burst campaign rerun, all generated events (2026-09-21)

All evaluation bursts (cats 2-399 and 623-1224; cat 1 has too few CC tpstreams left to be
reproduced) were regenerated from their tpstreams and run through the fixed pipeline.
Paired against the 2026-09-03 campaign on the same bursts:

| scenario | old campaign | fixed code | difference |
|---|---|---|---|
| 1 best case (true ES, true directions) | 5.98 | 0.75 | -5.23 [-5.37, -5.07] |
| 2 perfect CT (true ES, reco directions) | 11.04 | 10.11 | -0.93 [-1.24, -0.60] |
| 3 full pipeline (CT >= 0.80, E > 5 MeV) | 18.41 | 16.49 | -1.92 [-2.41, -1.38] |
| 4 weighted CT (all events, P(ES) weight) | 29.99 | 20.48 | -9.51 [-10.09, -8.94] |
| 5 perfect CT, E > 10 MeV | 9.67 | 10.05 | +0.38 [+0.16, +0.59] |
| 6 perfect CT, E > 5 MeV | 10.37 | 9.88 | -0.49 [-0.73, -0.25] |

Both production eras agree (cats 2-399: full pipeline 17.93 -> 16.31; cats 623-1224:
18.89 -> 16.76). Files: `/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-campaign/v80_fixed_1000/`
(`scenario_aggregate_v80_fixed_999cats_20260921.{pdf,json}`,
`paired_vs_old_campaign_999cats.md`, `_cats1to399.md`, `_cats623up.md`; per-cat reports
plus one tar of per-event outputs per cat). Campaign tooling and QC records:
`refactor-online-utils/condor/evilla/campaign_r2/`. The official aggregator's event-count
filter (200 for true-ES selections) removes scenario 5 entirely, since E > 10 MeV leaves
about 115 events per burst; the paired tables above apply no such filter.

The full-pipeline gain on 999 bursts (-1.9 deg) is about half of what the 50 development
bursts showed (-4.0, interval [-5.9, -0.7]); the development sample was on the favourable
side of its own interval.

## Before and after on the 50 development bursts

| scenario | campaign code | all fixes | difference |
|---|---|---|---|
| 1 best case (true ES, true directions) | 6.11 | 0.74 | -5.37 [-5.92, -4.67] |
| 2 perfect CT (true ES, reco directions) | 12.50 | 12.75 | +0.24 [-1.15, +1.51] |
| 3 full pipeline (CT >= 0.80, E > 5 MeV) | 20.04 | 16.01 | -4.03 [-5.89, -0.73] |
| 4 weighted CT (all events, P(ES) weight) | 26.12 | 21.99 | -4.13 [-5.52, -1.09] |
| 5 perfect CT, E > 10 MeV | 12.08 | 13.47 | +1.39 [-0.23, +2.19] |
| 6 perfect CT, E > 5 MeV | 12.27 | 12.10 | -0.17 [-0.71, +1.26] |

Outputs: campaign code `condor_scenarios_v80_mixture_dev` (user EOS), final
`/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/v80_final_dev`
(`paired_vs_campaign_code_50cats.md`). The 1000-burst campaign numbers of 2026-09-03
(full pipeline 18.4, best case 6.1, perfect CT 11.0) were produced with the campaign code
and are superseded once the campaign is rerun.

Scenarios 2, 5 and 6 (true ES, reconstructed directions) come out slightly worse after
the fixes, by +0.5, +1.1 and +0.9 deg on 81 regenerated cats of the 2026-09 campaign
(`pipeline-dev/product_effect_scratch/product_effect_cats1to82.md`). That is not a
regression: on identical events the old lookup's likelihood maximum sits ~20 deg from the
truth (a grid start under the old lookup gives 19.6 deg for E > 10 MeV), and the old
numbers survived only because the unconverged sampler stayed near its weighted-mean start.
For a pure sample that accidental estimator is close to a mean-vector fit and happens to
do well; the fixed code reports the actual posterior mean. The product regeneration itself
changes nothing (product effect 0.0 +- 0.2 deg, 93% of matched clusters bit-identical).

The remaining budget on these bursts is now legible: 0.7 deg (true directions) to 12.8
deg (reconstructed directions) is the electron-direction network; 12.8 to 16.0 deg is
channel tagging, and of that 3.5 deg is the CC contamination admitted at the working
point and only 0.6 deg the ES discarded (corrected rule scan, below).

## The fixes, in the order they were found

All in `refactor-snop-pipeline`, uncommitted; each has a test under `test/`.

1. **pdf lookup hole** (`python/ana/burst_direction.py`, `load_pdf_interpolator`). The
   RegularGridInterpolator spanned only the cosine bin centres [-0.99, 0.99] and returned
   1e-10 outside, so any event within ~8 deg of the trial direction scored log(1e-10). The
   likelihood maximum was wherever no event fell in the hole, 17 deg from the truth,
   beating the truth by 73 nats. Emcee's failure to converge on that surface is what kept
   the old numbers as good as they were. Fix: floor and renormalise the table, clip queries
   into the bin-centre range (mode `clipped`, default); old behaviour under
   `"pdf_lookup": "hole"`. Decomposition (`lookup_sampler_decomposition.md`): the fix
   alone is worth 2.7 deg on the deployed selection, the sampler choice 0.4.
   Test: `test/test_pdf_lookup_fix.py`.
2. **Unseeded emcee** (`_run_emcee`). `random_seed` only seeded the walker start; the
   sampler drew from the global numpy state, so one burst refit gave 2.8 to 7.5 deg. Fix:
   `sampler.random_state` seeded. Results are now bit-repeatable.
3. **CT scored the wrong image** (`python/lib/channel_tagger.py`). The lazy loader used the
   cluster's `match_id` as a positional index into the volume file, but volumes with an
   unmatched main cluster are stored too, so position and id disagree for 27-34% of volumes.
   About a third of events were scored on another event's image. Fix: resolve through the
   file's `main_cluster_match_id` metadata. No pointing change on this simulation (volume
   files are class-pure so the wrong image had the right class), but it invalidated every
   per-event use of the score. Test: `test/test_ct_volume_lookup.py`.
4. **Scenario-4 weights never reached the likelihood** (`_pdf_likelihood`). The weighted
   scenario was an unweighted fit of all events. Fix: sum of w log pdf; ones for the hard
   selections. 23.8 -> 21.0 deg. Test: `test/test_weighted_likelihood.py`.
5. **Prior setting dropped** (`python/ana/scenario_cos_theta_report.py`). The config asked
   for a 10-deg Gaussian prior around the weighted mean; the report script never forwarded
   it, so every campaign ran with the uniform prior. Now forwarded. Measured: the Gaussian
   prior helps only the true-direction case and costs +1.7 deg on the deployed selection
   (the weighted mean of a contaminated sample is off), so the uniform prior is kept
   explicitly in `json/base_config_prior_uniform.json`.
6. **Walker start** (`_run_emcee`, `init_mode`). The uniform-prior fit started 128 walkers
   45 deg wide around the weighted mean; 500 steps never collapse that onto a 0.5-deg
   posterior (chain length made no difference: 1.52/1.46/1.43 deg for 500/1500/3000
   steps), while any fixed narrow start hurts the contaminated case. Fix: seed the walkers
   at the maximum of the likelihood on a 4000-point equal-area grid, with a width set to
   the 68% radius of the grid posterior (clipped to 5-45 deg). Best case 1.52 -> 0.72 on
   real bursts, deployed selection unchanged (16.3 -> 16.2). Legacy under
   `"init_mode": "mean"`. Test: `test/test_grid_seeded_init.py`.
7. **Per-event outputs** are now kept (`PRUNE_SCENARIO_OUTPUTS=2`, 2.5 MB per burst) so
   every selection or likelihood variant can be evaluated offline without rerunning the
   networks; and `submit_cat_range.sh` passes `SCENARIO_NAMES` and `PRODUCT_SUFFIX`.

In `refactor-online-utils`: `python/lib/utils.py` no longer drops the last file of a cat
when `max_files=-1`; the 3-plane matcher partner rule, V+X routing and `match_type` are
fixed (`docs/three_plane_matching_fix_validation.md`, see below).

## What was tried on channel tagging, and why v80 at 0.80 stays

Corrected rule scan on the deployed selection (`pipeline-dev/*/ct_selection_rule_scan.md`):
no threshold policy on the v80 scores beats the 0.80 cut (best: an energy ramp, -0.5 deg,
P = 0.63). Energy-reweighted retrains v82-X, v83, v84 double the "ES pointing information
kept" proxy on the test set but are 3.3-3.7 deg worse in the pipeline at their best
operating points (P(beats v80) = 0.01-0.02): they flatten ES efficiency and CC acceptance
alike, i.e. they lower the effective threshold without improving separation (conditional
AUC unchanged). Three planes add ~0.01 conditional AUC and nothing on pointing. The
radiological mask helps ~0.01 only as an inference-time transform. The mixture likelihood
over all events (scenario 7) loses to the cut because reconstructed CC directions are
anisotropic in the detector frame. The bottleneck is purity at the working point, i.e.
separation at fixed energy, which none of these change.

## Matcher fix: right, but not yet usable for pointing

The most-energetic-partner rule raises the 3-plane match fraction of ES main tracks from
74.8 to 83.8% (all above 5 MeV, +42 points above 30 MeV) and adds 12% ES events per
burst, but the new events have split induction images the ED v58 network never saw and
its directions on them are worse in every energy bin: perfect CT 12.7 -> 13.8 deg, full
pipeline flat (the CT discards them anyway). A truth-free quality cut
min(E_U, E_V)/E_X >= 0.5 restores 11.7 deg on pure-ES selections but does nothing for the
deployed one. Path forward: retrain the ED on matcher-fixed products
(`pipeline-dev/v80_allfix_matchfix_dev/ed_on_matchfix_diagnosis.md`).

## Open decisions

- Rerun the 1000-burst campaign with the fixed code. CC cluster images were pruned from
  every campaign cat, so this needs the products regenerated (about 6 jobs and 3.5
  CPU-hours per cat, inode-limited batches of ~150 cats on the project area).
- ED retrain on matcher-fixed products (needs the ES training pool rebuilt with the new
  matcher), which is the only lever left that raises the ceiling as well as the deployed
  number.
- Commit the changes.

## Acceptance term deployed (2026-09-29)

The combined-likelihood study
(`/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/combo_study/combo_study.md`) showed
that the r3 re-scan's detector-frame CC map and the brems study's ES acceptance normalisation are
one effect seen twice, and that the consistent form of the mixture needs no CC map and no new
per-event lookup — only 49 stored numbers. That form is now in the pipeline.

**The model.** For a selected event `i` with ES probability `p_i`, reco direction `d_i` and reco
energy `E_i`,

    L(n) = prod_i [ p_i pdf_ES(cos(d_i,n) | E_i) / Z_i(n) + (1 - p_i)/2 ]
    Z_i(n) = sum_{l<=6} lambda_l^(i) R_l(n),   R_l(n) = sum_m c_lm Y_lm(n)

`lambda_l^(i)` is the Legendre moment of the ES table row of `E_i` (derived at load time, not
stored) and `R_l(n)` the l-band of the detector-frame reco-direction acceptance `R(d)`, 49 real
spherical-harmonic coefficients measured on the TRUE-CC reco directions of the table-building
slice (cats 673-900) at the deployed selection. The CC component stays flat: `R(d_i)` multiplies
both components of the consistent common-acceptance model and cancels exactly, so the whole
correction is `-sum_i log Z_i(n)` and the CC direction map is not needed
(combo_study.md section 3.1, verified there to 1.7e-12 in the log-likelihood).

**Code** (`python/ana/burst_direction.py`):

| what | where |
|---|---|
| `load_reco_acceptance(path)`, `acceptance_moments(table, energies, lmax)`, `Z_FLOOR = 1e-3` | new module-level helpers; `real_sh`/`multipole_bands`/`legendre_moments_of_rows` are imported from `ana.combo_acceptance` (with a fallback for the top-level import style) |
| `-sum_i w_i log Z_i(n)` term | `_pdf_likelihood(..., acceptance=None, acceptance_moments=None)` |
| pass-through and grid-seeded init on the same surface | `_run_emcee(..., acceptance=None, acceptance_moments=None)` |
| moments computed once per fit, before the sampler | `reconstruct_burst_direction(..., acceptance_path=None)` |
| second branch (no premixed row: the ES normalisation depends on `n`) | `grid_mixture_posterior(..., acceptance=None)` |
| loader + extras (`acceptance_path`, `acceptance_lmax`) | `reconstruct_burst_direction_grid_mixture(..., acceptance_path=None)` |
| opt-in hard CT cut for `mixture-ct` | `select_electrons_from_run` via `mixture.ct_hard_cut` |

Plumbing: `python/ana/scenario_cos_theta_report.py` reads `reporting.acceptance_path` (or
`reporting.mixture.acceptance_path`) and forwards it to BOTH reconstruct functions and into the
report json; `test/run_small_sample_pipeline.sh` copies the catalog key `acceptance_path` into
`reporting`, exactly as it already does for `pdf_path`. **With no acceptance file every existing
result is bit-identical** — verified, not asserted (below).

**Files.** Next to the v63 ED model
(`.../electron_direction/three_plane_v63_matchfix_ft58_20260921_132520/`):

* `reco_acceptance_r3_v63_l6.npz` — NEW, 8.5 kB: `coeffs` (49 float64), `lmax = 6` and provenance
  (source `combo_study/tables/combo_slice_t050_full.npz : coeffs_cc`, slice cats 673-900 / 227
  cats, selection CT v80 >= 0.50 and E > 5 MeV, class true CC, N = 115 776 events, date).
  Band-limited `R` over the sphere 0.0898-1.9126, mean 1.000000, never floored.
* `reco_acceptance_r3_v63_l6_ct030.npz` — NEW, 8.8 kB: the same at the DEPLOYABLE working point
  (source `combo_study/threshold_scan/tables/combo_slice_t030_full.npz : coeffs_cc`, CT v80 >= 0.30,
  N = 265 549 true-CC events). `R` 0.0782-1.8860, mean 1.000000, never floored.
* `cosine_energy_pdf_es_burstaxis_ct030_r3.npz` — NEW, 35 kB: the burst-axis ES likelihood table of
  the t = 0.30 selection, in exactly the deployed layout of
  `cosine_energy_pdf_es_burstaxis_ct050_r3.npz` (same keys, shapes and dtypes; verified by loading
  both through `load_pdf_table`, same binning, rows integrating to 1 to 2e-16), `pdf_2d` copied
  bit-for-bit from the scan's table. 15 of 18 energy rows measured.
* `..._provenance.json` for each new acceptance file, repeating the rebuild rule.
* unchanged and reused by BOTH arms: `ct_v80_calibration_r3slice_e5.npz` with `pi_fixed` 0.068421
  — `P(ES | CT score)` and the class prior are measured over the whole score range and are
  threshold independent. `cosine_energy_pdf_es_burstaxis_ct050_r3.npz` is unchanged.
  `cc_reco_direction_map_r3_v63.npz` is no longer needed by the recommended model — it stays a
  diagnostic.

**The ES table and R always travel together.** They are both properties of one selection: a
t = 0.30 `R` with the t = 0.50 table (or the reverse) is a misspecified model. The two arms below
differ in exactly three things — the hard cut, the ES table, the acceptance — and in nothing else.

**Config keys.** Two new catalogs, both = the six scenarios of
`json/six_scenarios_v63_mixture.json` byte-identical (scenario 3 is the unchanged regression
reference) plus the acceptance arms:

* `json/seven_scenarios_v63_acceptance.json` — `scenario_7_full_pipeline_acc`, t = 0.50.
* `json/eight_scenarios_v63_acceptance.json` — `scenario_7_full_pipeline_acc_t050` (the same entry,
  explicit name) and **`scenario_8_full_pipeline_acc_t030`, the deployable arm**. The seven-scenario
  catalog is kept as it is because a campaign was running against it.

```
"report_selection_mode": "mixture-ct", "report_min_energy_mev": 5.0,
"channel_tagger_enabled": true, "channel_tagger_threshold": 0.3,
"pdf_path":        ".../cosine_energy_pdf_es_burstaxis_ct030_r3.npz",
"acceptance_path": ".../reco_acceptance_r3_v63_l6_ct030.npz",
"mixture": { "calibration_path": ".../ct_v80_calibration_r3slice_e5.npz",
             "pdf_es_path": ".../cosine_energy_pdf_es_burstaxis_ct030_r3.npz",
             "cc_pdf_mode": "flat", "pi_mode": "fixed", "pi_fixed": 0.068421,
             "ct_source": "ct", "ct_hard_cut": 0.3,
             "acceptance_path": ".../reco_acceptance_r3_v63_l6_ct030.npz",
             "grid_n": 12000, "pdf_floor": 0.0001 }
```

`acceptance_path` is the one new likelihood key; `ct_hard_cut` is the one new selection key
(`mixture-ct` used to keep every event). A hard cut and the existing `s_min` soft floor give the
same posterior — a `p_i = 0` event contributes only the trial-direction-independent `log q_CC` —
verified to 0.0 deg with and without the term; the cut just keeps `n_selected`, the reported purity
and the cost of the fit honest. `grid_n` 12000 is the grid of the offline arms, so the pipeline
numbers are directly comparable with them (41253 moves theta68 by < 0.05 deg, combo_study.md
section 2.1). Nothing about the selection, the tables or the acceptance is hard-coded anywhere:
`python/ana/replay_scenario_from_slim.py --resolved-only` prints what a catalog entry resolves to,
so moving the working point again is a catalog edit plus a new output root.

**Tests.** `test/test_acceptance_term.py` (new, `source scripts/init.sh && python3
test/test_acceptance_term.py`); `test_pdf_lookup_fix.py`, `test_weighted_likelihood.py`,
`test_grid_seeded_init.py`, `test_ct_volume_lookup.py` and `test_event_budget.py` all still pass
unchanged.

`test/test_acceptance_term.py`, all checks passing in 324 s:

1. **Bit-identity.** On two real bursts (dev cats 623/624 of the campaign, 633 and 697 selected
   events) the patched module with `acceptance_path=None` reproduces the *unpatched* module's
   posterior mean, theta, omega68, the weighted log-likelihood at 3 trial directions and the grid
   log-likelihood at 3 grid nodes -- `np.array_equal`, not `allclose`. The references were produced
   with the pre-edit file and are embedded in the test.
2. **Normalisation.** `Z_i(n)` from the 49 coefficients against a brute-force 2e6-point Fibonacci
   integration of `2 <R(d) m_i(d.n)>_sphere`: max relative difference **8.1e-4** (< 1e-3). Doing the
   per-bin Legendre integrals exactly instead of by the midpoint rule drops it to **1.5e-4**, i.e.
   the residual is the midpoint quadrature inside `legendre_moments_of_rows`, not the model.
   `lambda_0 = 1` to 1.1e-15 and, with `R = 1` (monopole only), `Z = 1` to 8.9e-16. Band-limited
   `R` over the sphere: 0.090-1.913, mean 1.000000, the 0.05 floor never reached. `ct_hard_cut` and
   the existing `s_min` soft floor give identical posteriors (0.0 deg), with and without the term.
3. **Grid path.** On 5 evaluation cats the production `reconstruct_burst_direction_grid_mixture`
   with the acceptance reproduces the offline arm `CMB2_t050_accCC_ccl6` per cat to
   **max 8.1e-6 deg**, `n_selected` identical 5/5; the same check on the t = 0.30 products against
   `CMB2_t030_accCC_ccl6` gives **max 8.5e-6 deg**, 5/5. Swapping the offline purity convention for
   the deployed one (`ct_v80_calibration_r3slice_e5.npz` interpolates the likelihood ratio, the
   offline code interpolated `P(ES|s)`) moves it by 0.006 deg mean / 0.019 deg max: the two agree to
   8e-17 at the 50 score bin centres and by up to 0.007 in `p_i` between them.
4. **emcee path.** `Z_i(n)` is identical in the two code paths at the same direction (2e-16), and
   with the term the sampler reproduces the exact grid posterior mean *of its own likelihood* to
   max 2.1 / mean 1.1 deg, no worse than without it (2.8 / 1.6): the term does not spoil
   convergence. **But the emcee path is a different statistical model and must not be used as a
   substitute for the mixture.** `_pdf_likelihood` is the weighted pseudo-likelihood
   `sum_i w_i log pdf_ES(cos_i)`, which has no flat-CC floor, so a contaminated event pointing away
   from `n` costs `w_i log(pdf_floor)` instead of `log((1-p_i)/2)`; its own exact posterior mean sits
   9.5-32.6 deg from the mixture's -- already 1.5-8.2 deg away before any acceptance. The deployed
   fitter for this model is the grid. The emcee implementation is there for pure-ES selections and
   for premixed tables (the brems form), not for the recommended per-event mixture. combo_study.md
   section 9 listed "the emcee confirmation" as a prerequisite; the honest answer is that the emcee
   path cannot express a per-event mixture at all, and the grid is the production fitter for this
   scenario.

**Numbers.** **50 development bursts, FULL pipeline on HTCondor** (`pipeline-dev/combo_validation_dev`
for t = 0.50 and `..._t030` for t = 0.30, samples `mixture_dev_samples` with
`PRODUCT_SUFFIX=_matchfix`, CT v80, ED v63, 330 ES + 3300 CC, `PRUNE_SCENARIO_OUTPUTS=2`,
2 x 10 jobs of 5 cats):

| scenario | n/burst | theta68 | median | mean | frac>30 | coverage |
|---|---|---|---|---|---|---|
| 3 full pipeline (CT >= 0.80, deployed, emcee) | 145 | 15.44 | 12.11 | 14.57 | 0.060 | 0.95 |
| 7 + acceptance, t = 0.50 (grid mixture) | 638 | 7.74 | 6.87 | 6.90 | 0.000 | 0.76 |
| **8 + acceptance, t = 0.30 (DEPLOYABLE)** | 1337 | 7.87 | 6.46 | 6.66 | 0.000 | 0.87 |

paired against scenario 3 on the same 50 bursts:
t = 0.50 **-7.70 deg** [-12.44, -6.06] 68%
[-15.09, -4.63] 95%, paired mean -7.66 +- 1.22,
median -5.62, 86% improved;
t = 0.30 **-7.58 deg** [-12.70, -5.95] 68%
[-15.14, -4.27] 95%, paired mean -7.91 +- 1.29,
median -5.54, 80% improved.
t = 0.30 against t = 0.50 on these 50 bursts: +0.12 deg
[-0.70, +0.72], paired mean -0.25 +- 0.31
(58% of bursts improved) -- 50 bursts cannot arbitrate a 0.7 deg
difference, the 722-cat numbers below can.

*Scenario-3 regression.* Same products, same networks, same selection as the earlier v63 +
`_matchfix` dev runs: `n_selected` identical on 50/50 bursts against R4 and
50/50 against R6, so the selection and the inference chain are untouched. The fitted
directions differ only because those runs used a different likelihood table for scenario 3
(R4 = ED v63's own kinematic table, theta68 17.27, paired mean dtheta +0.55 +- 0.44;
R6 = the deployed table, 15.20, +1.49 +- 0.48; this catalog = the global-f
CC-mixture table, 15.44), not because of this change: the code path with no acceptance file is
bit-identical (test 1).

*Against the offline references, on the dev bursts.* t = 0.50: pipeline 7.74 vs offline
8.57; t = 0.30: pipeline 7.87 vs offline 7.99. These are **not** the same
events -- the offline study read the campaign's `..._e3p0_r3` products, this run the
`..._e3p0_matchfix` products of `mixture_dev_samples`, so the 330/3300 draw and every reco direction
differ (638 vs 641 selected events per burst at t = 0.50, `n_selected` identical on only
3/50 bursts, mean per-burst |dtheta| 2.06 deg). The per-burst closure with the
offline study is demonstrated instead on the campaign's own inputs: mean |dtheta| =
0.0150 deg (t = 0.50) and 0.0176 deg (t = 0.30) on the same 50 bursts.

**1000-burst campaign, production analysis stage on the stored per-event predictions**
(`pipeline-campaign/v63_matchfix_1000_acc{,_t030}`, `python/ana/replay_scenario_from_slim.py`,
40 + 20 condor jobs, 0 failures; full report in
`v63_matchfix_1000_acc/acceptance_scenario_1000cats.md`). The campaign cats no longer hold the CC
cluster images, so the ED/CT outputs stored in the slim tars are re-fitted rather than re-inferred;
the per-event inputs are exactly the campaign's.

| arm | 722 EVAL (headline) | median | frac>30 | cov | n/burst | 50 dev | 227 slice (in sample) | vs campaign sc3 (15.83) |
|---|---|---|---|---|---|---|---|---|
| campaign scenario 3 (deployed) | 15.83 | 12.41 | 0.057 | - | 147 | 14.27 | 15.49 | - |
| + acceptance, t = 0.50 | 7.98 | 5.96 | 0.000 | 0.87 | 643 | 8.57 | 7.72 | -7.85 [-8.37, -7.37] |
| **+ acceptance, t = 0.30 (DEPLOYABLE)** | **7.24** | **5.52** | **0.000** | 0.87 | 1340 | 7.99 | 7.20 | **-8.59** [-9.12, -8.11] |

On the 722 evaluation cats the deployable arm gives paired mean
-7.88 +- 0.33 deg, paired median
-6.46 deg, 86.3% of bursts improved and
frac > 30 deg 0.057 -> 0.000
(95% interval [-9.68, -7.69]).
(The r3 re-scan's own baseline, 14.68, was measured with the *rebuilt* mixture table
`cosine_energy_pdf_mixture_ctsel_global_flatcc.npz`; the campaign actually ran the older
`cosine_energy_pdf_mixture_global_flatcc.npz` and gives 15.83. Against 14.68 the gains
are -6.70 deg at t = 0.50 and -7.44 deg at t = 0.30.)

Per-burst closure with the offline arms on the campaign's inputs: mean |dtheta| =
0.0122 deg (t = 0.50, max 0.182) and
0.0104 deg (t = 0.30, max 0.212) over the 722 cats,
theta68 7.985 vs 7.994 (study quotes 7.99) and
7.241 vs 7.236 (scan quotes 7.24), `n_selected` identical on
721/722 and 721/722 (the one exception is a cluster exactly on the
5 MeV boundary: the pipeline cuts `E >= 5`, the offline code `E > 5`). Era splits 8.02 / 7.96
(t = 0.50, offline 8.05 / 7.90) and 7.58 / 7.02 (t = 0.30, offline 7.59 / 7.02); the
direction-dependence bins reproduce to <= 0.06 deg. The residual is the purity convention of the
deployed calibration (it interpolates the likelihood ratio, the offline code interpolated
`P(ES|s)`; identical to 8e-17 at the 50 score bin centres, up to 0.007 in `p_i` between them), not
the code.

**Two caveats from the independent review** (`combo_study/pole_dependence/pole_dependence.md`,
which re-derived `Z` from Funk-Hecke and reproduced the stored per-cat results to 1e-13 deg):

* **Near a detector axis the term costs instead of gaining, and that is expected.** Binned by the
  true burst's angle to the nearest of the six detector axes, theta68 goes 5.59 -> 6.42 deg inside
  10 deg (30 cats, ~5% of the sky; paired +0.80 +- 0.58 deg, 1.4 sigma) and improves by 1.5 to 10.5
  deg beyond; break-even is 10-12 deg from an axis. Both the closure MC (model exactly true) and a
  migration-mechanism MC predict exactly this, because the *uncorrected* estimator is biased towards
  the axes by 3-8 deg, so for a burst that really points at one its bias points at the truth. The
  corrected estimator is unbiased -- excess radial bias <= 1.8 deg everywhere and still slightly
  *towards* the axis inside 30 deg, so it does **not** push near-pole bursts away -- with a nearly
  direction-independent theta68 of 6.4-8.4 deg. **A "within ~10-12 deg of a detector axis" flag in
  the alert is cheap and honest**, and is the right way to carry this.
* **The mechanism is probably migration, not a multiplicative acceptance.** The real ES data reject
  the pure-acceptance model: the residual span of the burst-axis `<cos>` against pole angle is 0.063
  in data against 0.017 in the acceptance MC and 0.054 in the migration MC; the reco-to-truth rms in
  cos degrades from 0.507 to 0.568 as the burst turns towards an axis, which a thinning cannot do;
  and the *true*-electron `<cos>` is flat to 3e-4. The pile-up on the axes is directions dragged
  towards them with degraded resolution, not an excess of normally reconstructed events. Under that
  mechanism the term still helps almost as much (break-even 12 deg instead of 10.5, at most +0.9 deg
  push away from an axis, against the -3 to -9 deg pull of doing nothing), so this is a caveat, not
  a reason to hold the deployment -- but the principled next model is a direction-dependent ES
  kernel (a transfer function), which would need no `Z` term at all. `l > 6` and per-energy `R` are
  the wrong follow-ups.

**What is still open.** The 50 dev bursts cannot separate t = 0.30 from t = 0.50 (+0.12 +- 0.7 deg
there against -0.74 on 722 held-out cats), so the working point rests on the 722-cat scan. The
scan's plateau is 0.25-0.35 and was extended below 0.30; if it moves again, the threshold, the ES
table and the acceptance move together, which is a catalog edit and a new output root, not a code
change.

**The rebuild rule.** Everything R-related is a property of the ED model, the CT model and the
selection, not of the physics.

* **The acceptance coefficients and the burst-axis ES likelihood table must ALWAYS be rebuilt
  together**, because both are measured on one selection: the electron-direction model retrained,
  the CT model changed, the CT threshold moved, or the energy cut moved — all four invalidate both.
  Moving the working point from 0.50 to 0.30 in this very section is the worked example.
* **The `P(ES | CT score)` calibration and `pi_fixed` are threshold independent** — they are
  measured over the whole score range — so they survive a threshold move and were reused unchanged
  by both arms here. They must be rebuilt when the CT model or the score definition changes, or when
  the slice used to measure them changes.
* **The rotated-R null control must be re-run every time R is rebuilt**, because a mis-measured R is
  worse than none: on its own baseline it turns a -6.7 deg gain into a +2.8 deg loss. A deployed R
  that does not match the deployed ED/CT/selection is the one failure mode of this change, and the
  null is the only test that catches it.

`python/ana/combo_tables.py` writes the provenance json (slice, selection, class, N, multipole rms
against the statistical noise floor) for exactly this purpose, and both
`reco_acceptance_r3_v63_l6{,_ct030}_provenance.json` repeat the rule next to the product, including
which ES table each one must be used with.
