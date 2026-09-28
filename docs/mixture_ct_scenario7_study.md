# Scenario 7: mixture likelihood over all CT events (dev study)

Date: 2026-09-04. Dev sample: 50 cats (623-672), regenerated products under
`/eos/user/e/evilla/dune/sn-tps/mixture_dev_samples`, reports under
`/eos/user/e/evilla/dune/sn-tps/condor_scenarios_v80_mixture_dev`.
Cats 400-621 (CT/ED training) are never used. Scenarios 1-6 code paths are untouched:
the mixture branch is guarded by a new `mixture_cfg` kwarg and a new scenario type
`mixture-ct` in `json/seven_scenarios_v80_mixture.json`.

## Idea

Instead of cutting on the CT score and treating survivors as pure ES, keep every event and
give it a calibrated probability of being ES, then evaluate a two-component likelihood

    L(d) = prod_i [ p_i * pdf_ES(cos_i(d) | E_i) + (1 - p_i) * pdf_CC(cos_i(d) | E_i) ]

with p_i = P(ES | CT score, prior pi) from an isotonic calibration of CT v80 on its test set,
and pi the true ES fraction of the burst (~0.09). The posterior is evaluated on a Fibonacci
sphere grid, which also yields a truth-free HPD-68 credible region.

## Result: it does not beat the cut-based scenario 3

48 cats common to all scenarios, same products, same bursts.

| scenario | theta68 [deg] | median theta | frac > 30 deg | mean n_selected |
|---|---|---|---|---|
| 1 best case (true ES, true dir) | 6.35 | 4.67 | 0.00 | 238 |
| 2 perfect CT (true ES, reco dir) | 12.49 | 10.52 | 0.00 | 238 |
| 3 full pipeline (CT >= 0.80, E > 5) | 18.46 | 14.79 | 0.08 | 187 |
| 4 weighted CT (50 cats) | 26.12 | 20.17 | 0.18 | 2727 |
| 7 mixture CT | 24.56 | 19.87 | 0.15 | 2731 |

The mixture beats the old weighted-CT scenario 4 but loses to scenario 3 by ~6 deg.
On the same cats the previous campaign gives 6.19 / 13.14 / 19.06, so the regenerated
products reproduce the campaign to within the emcee and background-draw noise.

## Why it loses

1. **The CC component is not isotropic.** Reconstructed CC directions pile up along the
   detector y axis: 2.2-2.3x the isotropic density at +-y, 0.97x at +x
   (inertia eigenvalues 0.309 / 0.331 / 0.361). True CC kinematics are flat
   (`<cos(e_true, nu)> = -0.009`, KL to flat at Poisson-noise level), so this is a
   reconstruction artefact, not physics. A flat `pdf_CC` is therefore the wrong model,
   and the wrongness is coherent across ~2500 events per burst.
2. **CC dominates the weight budget.** Per burst the calibrated probabilities sum to
   ~72 for ES and ~225 for CC. Even at p ~ 0.08 each, 2500 CC events outvote 240 ES events,
   so the residual CC anisotropy sets the MAP. In cat 623 the MAP sits at +y and
   logL(truth) - logL(MAP) = -28.
3. **The posterior collapses.** Median HPD-68 radius is 0.80 deg while the actual error is
   ~20 deg, and coverage of the truth-free 68% region is 0.00 across all 50 cats. Treating
   thousands of weakly-informative events as independent makes the likelihood absurdly
   overconfident. Any future truth-free uncertainty must be calibrated, not read off this
   posterior.

Replacing the flat CC pdf with the measured detector-frame CC direction map ("CCmap")
recovers most of the loss (24.6 -> 17.8 deg), and adding a soft CT floor on top reaches
15.5 deg, i.e. parity with the cut-based approach, not an improvement.

## Offline variant scan (50 cats, grid posterior, clipped lookup)

| variant | theta68 [deg] | median | frac > 30 |
|---|---|---|---|
| mixture, flat CC pdf, pi = truth | 26.35 | 20.83 | 0.18 |
| mixture, measured CC table | 23.94 | 19.57 | 0.14 |
| mixture, CC direction map | 17.81 | 13.09 | 0.06 |
| mixture, CC map + soft CT floor (score >= 0.5) | 15.48 | 12.39 | 0.04 |
| mixture on scenario-3 selection, CC map weights | 15.25 | 12.19 | 0.02 |
| scenario-3 selection, pure-ES pdf | 15.78 | 12.64 | 0.00 |
| scenario-2 selection (true ES), pure-ES pdf | 12.76 | 8.95 | 0.00 |
| true tags in the mixture (p = 1 ES / 0 CC), all events | 12.22 | 9.71 | 0.00 |
| vector sum, true ES only | 15.13 | 12.39 | 0.00 |
| vector sum, scenario-3 selection | 19.86 | 16.94 | 0.10 |

Three things follow. Perfect tags in the mixture (12.22) land on perfect CT (12.49), so the
mixture has no headroom above a perfect cut: tag quality, not the estimator, is the ceiling.
The likelihood beats a plain vector sum by ~2.4 deg on the same events. And a fixed
pi = 0.09 performs the same as the true pi, so the burst-level ES fraction does not need to
be known.

## Resolved: the scenario-3 gain is the lookup, not the sampler

The offline scenario-3 row (15.78) differed from the in-pipeline scenario 3 (20.04) in two
ways at once, clipped lookup versus the `fill_value = 1e-10` hole, and dense grid versus
emcee. The 2x2 was run on the same 50 cats
(`lookup_sampler_decomposition.{json,md}` in the dev output dir, opt-in `--decompose` mode of
`mixture_offline_variants.py`, emcee cells calling the pipeline's own `_run_emcee`).

theta68 [deg], scenario-3 selection (score >= 0.80, E > 5 MeV), mean n = 186:

| | lookup = hole | lookup = clipped |
|---|---|---|
| emcee | 18.90 | 16.24 |
| grid | 19.04 | 15.79 |

theta68 [deg], scenario-2 selection (true ES, E > 3 MeV), mean n = 236:

| | lookup = hole | lookup = clipped |
|---|---|---|
| emcee | 12.28 | 12.72 |
| grid | 22.27 | 12.74 |

For the scenario-3 selection the lookup fix alone buys 2.7 deg at fixed sampler, while the
sampler swap buys nothing at fixed lookup (-0.1 deg) and only 0.45 deg once the lookup is
fixed. So clipping cos into the table range recovers almost all of the improvement, and
scenarios 1-6 can stay on emcee.

The scenario-2 cells do not decompose (non-additivity -10 deg) and are the more instructive
half. At fixed emcee the fix does nothing; at fixed buggy lookup the exhaustive grid is
catastrophically worse. Emcee never converges to the optimum of the buggy likelihood, and for
a pure-ES sample its 45-deg-wide initialisation around the weighted mean already sits near the
truth, so non-convergence accidentally hides the bug. The grid does find that optimum, 17.7
deg from truth.

That is the sharpest statement of the bug's shape. Only 2.06% of (event, trial-direction)
lookups fall in the hole when the trial direction is the truth, but at the buggy likelihood's
own MAP the in-hole fraction is 0.0000. An in-hole event costs 23 nats, so the maximum is
simply the direction that dodges every event's 8.1-deg cap. It beats the truth by 73 nats
(scenario 3) and 181 nats (scenario 2). The likelihood is not noisy, it is pointed the wrong
way, and only a non-converging sampler is keeping the current numbers honest.

Two side findings. `_run_emcee` is not reproducible: `random_seed` seeds the walker start
positions through `default_rng`, but `emcee.EnsembleSampler` is constructed without a random
state and draws from the unseeded global numpy stream, so one cat re-run gave theta between
2.8 and 7.5 deg. The published in-pipeline 20.04 is one realisation of a 19.0 +- 0.3
distribution, and the bootstrap-over-cats 68% interval on it is [17.44, 21.98]. Separately,
the hole is purely on the cos axis: no event energy ever leaves the table range.

## ES pdf axis check

On 11800 true-ES dev events the tabulated ES pdf matches both the neutrino axis and the true
electron axis about equally (mean absolute difference in `<cos>` per energy bin: 0.045 and
0.043), because ES kinematic smearing is negligible (`<cos(e, nu)> = 0.972`). The table is
15-20% sharper than the e3p0 sample below 12 MeV, which slightly over-weights low-energy
events.

## Recommendation

Do not promote scenario 7 as specified. It is worth keeping in the catalog as a diagnostic,
since it is the cheapest way to test tagging and pdf changes on all events at once. If a
mixture form is ever adopted it needs the measured CC direction map, a soft CT floor, and a
calibrated (not likelihood-derived) uncertainty.

## Fix applied and validated in the pipeline (2026-09-04)

`load_pdf_interpolator` now defaults to the clipped lookup (floored, renormalised table,
energy and cosine clipped into the bin-centre range); the old lookup is kept as
`mode="hole"` and can be selected per run with `"pdf_lookup": "hole"` in the emcee config.
`_run_emcee` now seeds the sampler's own random state, so results are repeatable.
Regression test: `test/test_pdf_lookup_fix.py`.

The six scenarios were rerun with the fix on the same 50 dev cats
(`condor_scenarios_v80t080_fixlookup_dev`, paired comparison in
`paired_vs_hole_50cats.md`, per-cat theta68 from the single-pass direction, bootstrap 68%
interval on the paired difference):

| scenario | hole | clipped + seeded | difference |
|---|---|---|---|
| 1 best case (true ES, true dir) | 6.11 | 2.78 | -3.33 [-4.14, -2.71] |
| 2 perfect CT (true ES, reco dir) | 12.50 | 12.75 | +0.25 [-0.89, +1.39] |
| 3 full pipeline (CT >= 0.80, E > 5) | 20.04 | 16.14 | -3.90 [-5.41, -1.40] |
| 4 weighted CT | 26.12 | 23.04 | -3.08 [-4.69, +0.80] |
| 5 perfect CT, E > 10 | 12.08 | 13.04 | +0.96 [-0.16, +2.44] |
| 6 perfect CT, E > 5 | 12.27 | 12.14 | -0.14 [-0.82, +1.28] |

The in-pipeline numbers agree with the offline decomposition (16.24 and 12.72 for the
scenario-3 and scenario-2 selections). The best case, which uses true directions and had 36%
of its events inside the hole at the truth, drops to 2.8 deg (median 1.2 deg): this is the
historical "~3 deg" figure, and it was real. Scenarios 2, 5 and 6 do not move, as predicted:
emcee's non-convergence was already hiding the bug for pure-ES samples with reconstructed
directions.

The per-burst posterior width is now meaningful. The median truth-referenced q68 of the
emcee posterior went from 27.3 to 2.1 deg (best case), 29.3 to 11.5 (perfect CT) and 33.3
to 16.2 (full pipeline), i.e. it now matches the across-burst 68% containment instead of
over-covering by a factor 2 to 5.

Remaining budget on these 50 cats: 2.8 deg (true directions) to 12.7 deg (reconstructed
directions) is the electron-direction network; 12.7 to 16.1 deg is channel tagging.
