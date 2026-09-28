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
