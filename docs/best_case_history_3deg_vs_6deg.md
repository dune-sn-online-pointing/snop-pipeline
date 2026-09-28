# Best-case pointing: where the "~3 degrees" came from, and why today it is 6.06 deg

Historical investigation, 2026-09-03. Read-only: nothing outside this file and
`docs/scripts_history_check/` was created or modified.

**Code references below are to `HEAD` (`504fa8d`) as of 2026-09-03 ~17:00.**
While this note was being written, `python/ana/burst_direction.py`,
`scenario_cos_theta_report.py`, `aggregate_scenario_reports.py` and
`test/run_small_sample_pipeline.sh` were edited by someone else in the working
tree (new mixture-likelihood path, `build_cc_cosine_pdf.py`,
`build_ct_calibration.py`, `mixture_offline_variants.py`), so line numbers may
have shifted. The Section 6 finding is **unaffected and still live**: the new
mixture path clips its lookups correctly, but the working tree still carries
`fill_value=1e-10` (`burst_direction.py:42`) and states explicitly at
`burst_direction.py:554` that *"the emcee scenarios (1-6) keep their historical
RegularGridInterpolator behaviour"* — scenario 1 is the best case that produces
the 6.06 deg number.

Scope: the **best case** scenario only — true ES selection, **true electron
direction** per event, E_cluster > 3 MeV, ~239 events per burst, emcee posterior
mean, aggregated over bursts.

---

## 1. Short answer

There are **three separate effects**, and only one of them is a real change in
the analysis. In decreasing order of size:

| # | Effect | Size |
|---|--------|------|
| A | **Metric definition.** The old "68% quantile" was `arccos(np.percentile(cos, 68))`, which is the **32%** containment radius, not the 68%. On *today's* numbers that same formula gives **3.36 deg**, not 6.06 deg. | factor ~1.8 |
| B | **A real regression between Apr-29 and May-04 2026**, on identical inputs and (from `v80gauss` onwards) an identical emcee config: 68% containment went 4.54 deg -> 6.4 deg and has stayed there. Cause narrowed but **not fully pinned down** (Section 4.1). | +40% |
| C | **The whole scale, old and new, is wrong.** The likelihood PDF is evaluated out of bounds for exactly the events that sit closest to the truth, so the likelihood *repels* the estimator from the true direction. Confirmed end-to-end with the shipped code: the same six bursts give **0.65 deg** with a plain vector sum and **~5 deg** with the shipped emcee+pdf estimator. The statistical floor is **~0.95 deg** at N=239, and the pipeline itself reached **0.78 deg** in March 2026 with a plain weighted mean. | factor ~6-8 |

So the honest summary is: **the old number was not a fluke, and the new number
is not a bug fix.** The ~3 deg memory is real and traceable — it is the tech
note's 2.4 deg and the Apr-2026 campaigns' 2.60/2.63 deg, computed with a
quantile that reports the 32% containment while calling it 68%. Today's 6.06 deg
is a correctly-defined 68% containment of a **badly degraded estimator**. Both
numbers are a factor of several above what the data actually supports.

---

## 2. Metric glossary — the single most important table

All of these are computed from the *same* per-burst array `cos_all` (cosine
between the reconstructed burst direction and the true burst direction, one
value per burst). They are not interchangeable, and the historical numbers use
different ones.

| Name | Formula | What it means |
|------|---------|---------------|
| `theta68_from_cos_deg` | `degrees(arccos(quantile(cos, 0.32)))` | **68% containment radius** across bursts. 68% of bursts point at least this well. Current definition, `python/ana/aggregate_scenario_reports.py:105-106`. |
| tech-note "68% quantile" | `degrees(arccos(percentile(cos, 68)))` | **32% containment radius**. Only 32% of bursts point this well. `snop-pipeline/python/analysis/analyze_6scenarios_aggregate.py:267,403` |
| `theta_median_deg` | `median(degrees(arccos(cos)))` | median per-burst error |
| `theta_mean_deg` | `mean(degrees(arccos(cos)))` | mean per-burst error |
| `theta_mean_from_cos_deg` | `degrees(arccos(mean(cos)))` | angle of the mean cosine (tail-sensitive) |
| `q68_theta_deg` / `omega68_deg` | 68th percentile of the **within-burst MCMC posterior** | the *claimed* per-burst uncertainty, ~27 deg |
| `single_pass_theta_deg` | `angular_error(reco_dir, truth)` | **misnomer**: when emcee is enabled this is the *emcee posterior-mean* error, identical to `arccos(cos_to_truth)`. It is only the plain mean-vector error when emcee is off. `python/ana/burst_direction.py:484,505` |

Today's campaign under every convention (845 bursts, `scenario_aggregate_v80_t080_merged_926cats_20260903.json`):

| Q68 cont | median | mean | **Q32 cont = old "68% quantile"** | arccos(mean cos) | Q90 cont | Q95 cont |
|---|---|---|---|---|---|---|
| **6.06** | 4.55 | 5.17 | **3.36** | 6.02 | 9.25 | 10.69 |

**The 3-vs-6 gap is more than half explained by this row alone.**

---

## 3. Every historical number found

Direction definition is **true electron momentum, metadata cols 7:10**
throughout (cols 15:18 = true neutrino/burst direction, used only as truth).
The "used the true neutrino direction as the per-event direction by mistake"
hypothesis was checked and is **false** for every result below: the sub-degree
March-2026 numbers are reproduced from scratch in Section 5.3 using the
*electron* directions, and the column convention was settled by commit
`7abb8f3` on 2026-03-04 (Section 4).

### 3.1 Tech note (frozen from the pre-refactor `snop-pipeline`)

| Value | Date | Source | Scenario | N/burst | Method | Metric |
|---|---|---|---|---|---|---|
| **2.4 deg** | first written 2026-02-02, never updated | `snop-tech-notes/chapters/pipeline.tex:678`, figure `images/pointing_section/trueDir.png` | best case, true e- dir, true ES, E>3 MeV | ~325 ES generated | emcee 128x500, burn-in 100, **uniform prior** (`ln sin phi`), init +-10 deg around mean, stretch a=3.0, PDF likelihood | `arccos(percentile(cos,68))` on 567 cats — i.e. **32% containment** |
| 7.5 deg | same figure | `trueDir.png` legend | same | same | same | `arccos(mean cos)` |
| 8 deg | `pipeline.tex:696` | | perfect CT, reco dir | | | same 32%-containment convention |
| 7.7 deg | `pipeline.tex:697` | | perfect CT, reco dir, E>5 MeV | | | " |
| 8.5 deg | `pipeline.tex:698` | | perfect CT, **simple average** (no MCMC) | | | " |
| 18 deg | `pipeline.tex:701` | | full pipeline, CT threshold 0.80 | | | " |

The figure legend reads `68% quantile: 0.9991 (2.4 deg)` / `Mean: 0.9915
(7.5 deg)`. The generating code is
`snop-pipeline/python/analysis/analyze_6scenarios_aggregate.py:403`:
`q68 = np.percentile(cos_arr, 68)` then `arccos(q68)`. That is the 32%
containment. (The same repo's
`python/app/multiple_dir_res_studies.py:236` uses `0.32` correctly — the
convention was inconsistent between scripts.)

### 3.2 Refactor-pipeline campaigns

Best case only. `t68` = current 68% containment; `Q32` = the old tech-note
convention applied to the same data.

| Campaign | Run date | n cats | N/burst | prior | t68 | median | mean | **Q32** | per-burst q68 | Source |
|---|---|---|---|---|---|---|---|---|---|---|
| `aggregate_results_fixed_ed_corrected` | 2026-03-26 17:01 | 589 | **365** | **weighted mean + bootstrap, no MCMC** [1] | **0.78** | 0.61 | 0.64 | — | **0.99** | `previous-reports-20260824/repo-output/` |
| `aggregate_results_FINAL_MCMC_FIXED` | 2026-03-26 18:16 | 523 | 237 | emcee+pdf, first turned on | **21.23** | 18.89 | 20.46 | — | 26.9 | idem |
| `condor_scenarios_corrected` | 2026-04-28 | 527 | 237 | gaussian_around_mean, 10 deg | 4.84 | 3.77 | 4.53 | **2.63** | 26.7 | `previous-reports-20260824/eos-aggregates/` |
| `condor_scenarios_v2` | 2026-04-29 12:17 | 526 | 237 | gaussian_around_mean, 10 deg | **4.54** | 3.41 | 4.22 | **2.60** | 26.9 | idem |
| `condor_scenarios_v3` | 2026-04-29 16:28 | 526 | 237 | **uniform + random-sphere init** | 9.91 | 7.63 | 8.11 | 5.60 | 27.8 | idem |
| `condor_scenarios_v4` | 2026-05-04 | 527 | 237 | uniform + 45 deg init near mean | 6.23 | 4.60 | 5.25 | 3.29 | 27.0 | idem |
| `condor_scenarios_v80final` | 2026-07-10 | 164 | 237 | uniform | 6.61 | 4.86 | 5.55 | 3.71 | 27.0 | idem |
| `condor_scenarios_v80gauss_final` | 2026-07-11 | 339 | 237 | gaussian_around_mean, 10 deg | 6.41 | 4.93 | 5.41 | 3.68 | 27.0 | idem |
| `condor_scenarios_v80t080_final` | 2026-07-15 | 339 | 237 | gaussian_around_mean, 10 deg | 6.42 | 4.91 | 5.29 | 3.56 | 27.0 | idem |
| **`..._merged1000` (today)** | 2026-09-03 | 917 / 845 | **239** | gaussian_around_mean, 10 deg | **6.06** | 4.55 | 5.16 | **3.36** | 27.1 | `/eos/user/e/evilla/dune/sn-tps/condor_scenarios_v80t080_merged1000/` |

[1] The aggregate JSON of that era does not store `aggregation_method`, but the
per-cat backup from the same period
(`cat000400/scenario_cos_theta_report.json.backup_before_mcmc_fix`) records
`aggregation_method = "weighted-mean+bootstrap (emcee unavailable)"` and
`min_energy_mev = 0.0`, and the labels match (`Best Case (true e- dir, true
ES)`); the labels change to `True electron direction (true ES, true dir)` in
`FINAL_MCMC_FIXED`, written 75 minutes later. Its per-burst bootstrap width
(q68 = 0.99 deg) is also consistent with its across-burst containment
(0.78 deg), which an unconverged MCMC would not be. Independent confirmation:
the analytic mean-vector floor scaled to N = 365 is
`0.94 * sqrt(239/365) = 0.76 deg`, versus the 0.776 deg measured then.

The today campaign is a *merge*: for cats 1-621 the per-cat
`scenario_cos_theta_report.json` files still point at
`condor_scenarios_v80t080_final/.../pipeline_run_20260715_*` and are bit-for-bit
the July results; the rest are the new cats 623-1223. On the 164 cats common to
all campaigns the merged campaign therefore gives exactly `v80t080_final`'s
6.52 deg; the drop to 6.06 deg over 917 cats comes from the new cats being
slightly better, not from any analysis change.

Companion best-case-adjacent numbers today: perfect CT (reco dir) **11.05**,
perfect CT E>5 MeV **9.72**, full pipeline (CT v80 = 0.80, E>5 MeV) **18.33**,
weighted CT **30.06**.

Note that the tech note's **18 deg full pipeline agrees with today's 18.33 deg**
even though the metric conventions differ — a coincidence of the CT model
change (v52 -> v80) roughly cancelling the metric change. The truth-based
scenarios are the ones that moved.

### 3.3 Per-CAT snapshots preserved on EOS

`/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples/cat000400/`
still holds two backups of the per-cat report from before two fixes:

| File | Date | Best-case method | N | Best-case error |
|---|---|---|---|---|
| `scenario_cos_theta_report.json.backup_before_mcmc_fix` | 2026-03-12 19:52 | `weighted-mean+bootstrap (emcee unavailable)`, **min_energy 0.0** | 311 | **0.31 deg**, per-burst q68 = 0.85 deg |
| `scenario_cos_theta_report.json.backup_before_coordinate_fix` | 2026-03-26 18:01 | `emcee+pdf` | 221 | **18.70 deg**, per-burst q68 = 24.95 deg |

For reference, the same cat in the later campaigns: `corrected` 3.40, `v2`
3.00, `v4` 2.52, `v80t080` 3.79 deg. And the **plain mean-vector estimator on
the real cat000400 events (E>3 MeV, n=280) gives 0.395 deg** (Section 5).

### 3.4 Loose notes

`dune/notes-snop.txt` (March 2026) records the pre-refactor MCMC config as
"nwalkers 64, nsteps 2000, discard 400", and results
`simple_average_ct: 68% error = 60.44 deg` / `weighted_average_ct: 92.87 deg`.
The tech note instead documents 128 x 500 with 100 burn-in, which is what the
refactor pipeline uses.

---

## 4. Timeline of the code changes that moved the number

All in `refactor-snop-pipeline` unless stated.

| Commit | Date | What changed | Effect on the best case |
|---|---|---|---|
| `acd5239` | 2026-03-04 | "Use reconstructed directions for reco mode in burst aggregation" | reco path only |
| `7abb8f3` | 2026-03-04 | **"Revert incorrect burst-direction column remap"** — settles the convention: cols **7:10 = true electron momentum**, 15:18 = true burst direction. A short-lived variant had read 4:7 / 7:10. | fixed the direction columns |
| `621b24e` | 2026-03-25 17:15 | "MAJOR BREAKTHROUGH: Fix sample size issue" — `TEST_N_ES` 8 -> 35. Commit message records scenario 1 going 14.9 deg -> 3.6 deg on one cat. | large, statistical |
| `662879f` | 2026-03-25 17:40 | reverted ED model v57 -> v58 | reco path only |
| (no commit) | 2026-03-26 17:01 | `aggregate_results_fixed_ed_corrected`: **weighted mean + bootstrap**, 365 events/burst -> **0.78 deg** | the floor, reached |
| (no commit) | 2026-03-26 18:16 | `aggregate_results_FINAL_MCMC_FIXED`: emcee+pdf enabled -> **21.2 deg** | **the regression enters here** |
| `78813b3` | 2026-04-28 16:48 | "improve scenario reporting, burst direction, and multi-CAT aggregation" — **introduces** `cos_q68_containment = np.quantile(cos, 0.32)` and `theta68_from_cos_deg`, with the comment *"68% containment in angle space corresponds to the 32nd percentile in cos-space"*. The predecessor `45d7247` (2026-02-26) had no across-burst containment metric at all, only `q68_median_deg` (the per-burst posterior width). | **metric change A happens here** |
| `a6095eb` | 2026-04-29 10:54 | "expand aggregate report to 5 pages with consistent theta68 metrics" — promotes `theta68_from_cos_deg` to the headline number on every page (the plot legend still reads "68% quantile") | makes A visible |
| `90bfce2` | 2026-04-29 10:54 | `TEST_N_ES` 290 -> 330 per cat | ~237 -> ~239 selected after the 3 MeV cut |
| `ef60fdc` | 2026-04-29 11:11 | stretch `a` 3.0 -> configurable, default **2.0**; CT threshold 0.9; E>5 MeV for CT scenarios | acceptance 0.077 -> 0.089 |
| `c6fc8d1` | 2026-04-29 14:19 | CT model volume-image fix | CT scenarios only |
| `d00cde2` | 2026-04-30 17:08 | "Fix weighted-ct to use all events; **fix EMCEE init regression for best_case**" — uniform prior had been initialising walkers randomly on the sphere; now always init near the mean, 45 deg for uniform. Commit message: "best_case 4.5 deg -> 9.9 deg regression", cat000001 7.98 -> 5.0. | recovers most of the v3 regression |
| `1c797ab` | 2026-07-11 17:59 | "Restore gaussian_around_mean MCMC prior (thesis config); uniform had degraded non-CT pointing" | 6.61 -> 6.41, **does not recover 4.5** |
| `504fa8d` | 2026-07-15 | CT operating point 0.80 | full pipeline only |

**Events per burst.** `n_es_events` in `json/` went 5 -> **330** (with
`n_cc_events` 3300) at `2160399`, 2026-02-26, and the default was later bumped
to 350. In practice the condor campaigns are driven by the `TEST_N_ES`
environment variable, whose history is **8 -> 35** (`621b24e`, 2026-03-25)
**-> 290 -> 330** (`90bfce2`, 2026-04-29). After the E_cluster > 3 MeV cut this
gives the ~237 (pre-Apr-29) / ~239 (post) selected events seen in every
campaign. No campaign in the table above ran with 100 events per burst.

**Likelihood kernel.** The `-sum(angle^2)` kernel in
`burst_direction.py:_logpost` is only the fallback used when `pdf_path` is
`None`. Every campaign config sets
`pdf_path = data/cosine_energy_pdf.npz` and every per-cat report records
`aggregation_method = "emcee+pdf"`, so the PDF lookup was always in use once
emcee was enabled. The PDF file itself has not changed since 2026-03-19.

**Verified negative results for effect B (the 4.54 -> 6.4 step):**

* Event sets are **identical**. `n_selected_all` is bit-for-bit equal across
  `corrected`, `v2`, `v4` and `v80t080` on all 339 common cats
  (216, 260, 205, 213, 214, 253, ... for the first cats).
* The emcee config JSON is **identical** between `v2` (4.54) and
  `v80gauss_final` / `v80t080_final` (6.41 / 6.42): `nwalkers 128, nsteps 500,
  discard 100, prior gaussian_around_mean, prior_sigma_deg 10, seed 42,
  likelihood_kappa 25, same `data/cosine_energy_pdf.npz` (mtime 2026-03-19,
  unchanged), min_energy 3.0`.
* `git diff ef60fdc 504fa8d -- python/ana/burst_direction.py` touches only the
  `weighted-ct` mask and a **cosmetic reordering** of the walker
  initialisation; for `prior_type != "uniform"` the init sigma is
  `prior_sigma_rad` both before and after. `scenario_cos_theta_report.py` is
  unchanged. The other diffs (`sample_loader.py`, `pipeline.py`,
  `channel_tagger.py`) concern CT volume images only.
* Paired on the same 164 cats: `corrected` 5.01, `v2` 4.56, `v3` 9.73, `v4`
  6.98, `v80final` 6.61, `v80gauss` 6.94, `v80t080` 6.52, today 6.52. The whole
  distribution shifts (median 3.71 -> 4.99, p90 7.73 -> 9.62), not just a tail.
* The per-burst posterior width is unchanged (`q68` median 26.7 - 27.1 deg in
  every campaign), so it is the posterior *mean* that moves, not the posterior.
* Acceptance fractions were collected per campaign from the per-cat reports
  (`collect_acceptance.py`, first 400 cats each). They do not track the result:

  | campaign | median acceptance | t68 |
  |---|---|---|
  | `corrected` | 0.0767 | 4.93 |
  | `v2` | 0.0890 | 4.66 |
  | `v3` | 0.0859 | 9.48 |
  | `v4` | 0.0849 | 6.28 |
  | `v80final` | 0.0836 | 6.27 |
  | `v80gauss_final` | 0.0846 | 6.35 |
  | `v80t080_final` | 0.0843 | 6.30 |

  (`corrected` predates the stretch `a` 3.0 -> 2.0 change, hence its lower
  acceptance; every later campaign sits at 0.084-0.089 regardless of whether it
  gave 4.7 or 6.3 deg.)

### 4.1 The estimator is not reproducible run to run

`emcee.EnsembleSampler` is constructed without a `random_state`, so it draws
from the numpy **global** random stream and is *not* reproducible; the
`random_seed=42` in the config only fixes the walker *initialisation*. With
acceptance ~8.5% over 400 post-burn-in steps each walker accepts ~34 moves on a
posterior ~27 deg wide, so the chains are nowhere near converged.

`docs/scripts_history_check/emcee_noise_test.py` imports the **shipped**
`reconstruct_burst_direction()` and runs it repeatedly on identical inputs with
the production config (gaussian prior 10 deg, 128 walkers x 500 steps,
discard 100, the shipped PDF). Result on cats 400-405, true ES, true electron
direction, E>3 MeV:

```
mean-vector estimator (no MCMC): 68% cont = 0.648 deg   median 0.542   mean 0.576

emcee repetition 0: 68% cont = 5.203 deg  median 3.801  posterior q68 median 26.46  accept 0.098
emcee repetition 1: 68% cont = 4.774 deg  median 3.874  posterior q68 median 25.50  accept 0.087
emcee repetition 2: 68% cont = 5.545 deg  median 3.831  posterior q68 median 26.30  accept 0.090

per-cat spread over 3 independent runs on IDENTICAL inputs:
  mean per-cat std   = 0.878 deg
  max  per-cat std   = 1.878 deg
  mean per-cat range = 1.678 deg

  cat        rep0   rep1   rep2   | mean-vector
  cat000400  4.45   1.65   5.22   |  0.40
  cat000401  6.16   5.15   6.01   |  0.78
  cat000402  2.33   3.24   2.45   |  0.56
  cat000403  0.85   1.09   0.30   |  0.76
  cat000404  3.15   4.50   2.37   |  0.53
  cat000405  9.17   7.89   7.52   |  0.43
```

Two conclusions:

1. **Effect C is reproduced end-to-end with the shipped code.** The same six
   bursts give **0.65 deg** with a plain vector sum and **~5 deg** with the
   shipped emcee+pdf estimator. Nothing about the data changed; only the
   estimator.
2. **The per-burst run-to-run scatter is 0.88 deg (up to 1.88 deg)** on
   identical inputs — comparable to the entire statistical error of the
   measurement. Individual bursts move by 3.5 deg between runs (cat000400:
   4.45 / 1.65 / 5.22).

This is enough to make campaign-to-campaign comparison unreliable at the
per-burst level, but on 500+ bursts it does not by itself explain a *systematic*
4.54 -> 6.42 deg shift between two campaigns with identical inputs and config.
**Effect B is therefore only partly explained.** Everything under the analysis's
own control has been eliminated (inputs, config, code path); the leading
remaining hypothesis, **not confirmed here**, is an environment change on the
worker nodes between April and July — note that
`load_pdf_interpolator` itself prints *"Warning: scipy version may be
incompatible but will try to use it"* at import, and the whole pathology of
Section 6 lives in `RegularGridInterpolator`'s out-of-bounds handling, whose
behaviour has changed across scipy versions. Checking the LCG view / scipy
version recorded in the condor logs of `condor_scenarios_v2` versus
`condor_scenarios_v80t080_final` would settle it. Once the Section 6 fix is in,
the question largely stops mattering: both campaigns should land near 1 deg.

---

## 5. First-principles floor

Measured directly from the true ES kinematics in the cluster-image metadata of
**cats 400-420 only** — these are the CT v80 *training* cats
(`cat_roles.json`: `ct_v80_train = [400, 571]`, `val = [572,596]`,
`test = [597,621]`, `eval = [1,399] + [622,1223]`), so no evaluation cat is
touched. The quantity measured is generator-level physics (true electron
momentum vs true neutrino momentum) and is independent of any network.

Script: `docs/scripts_history_check/first_principles_floor.py`,
`docs/scripts_history_check/floor_mle_refined.py`.

### 5.1 The ES opening angle

6375 true-ES main-track clusters, plane X, E_cluster >= 3 MeV (the cut keeps
99.7% of them):

```
R  = <cos>    = 0.9727     -> mean opening angle 13.4 deg
S2 = <cos^2>  = 0.9469        median opening angle 10.3 deg
fraction with cos < 0        = 0.0000
```

Energy dependence (equal-count bins, cluster energy):

| E [MeV] | n | `<cos>` | mean opening angle |
|---|---|---|---|
| 3.0 - 4.8 | 417 | 0.9237 | 22.5 deg |
| 4.8 - 6.5 | 416 | 0.9536 | 17.5 deg |
| 6.5 - 8.4 | 416 | 0.9686 | 14.4 deg |
| 8.4 - 10.4 | 416 | 0.9784 | 11.9 deg |
| 10.4 - 12.5 | 417 | 0.9851 | 9.9 deg |
| 12.5 - 15.4 | 416 | 0.9889 | 8.5 deg |
| 15.4 - 20.0 | 416 | 0.9926 | 7.0 deg |
| 20.0 - 49.6 | 417 | 0.9959 | 5.2 deg |

ES is kinematically very forward — as it must be, since
`cos(theta_e) = ((E_nu + m_e)/E_nu) sqrt(T_e/(T_e + 2 m_e))`.

### 5.2 Floor vs N

Analytic (mean-vector): the transverse components of the mean vector have
variance `(1-S2)/(2N)`, so the 68% (2-D Rayleigh) containment is
`1.5096 * sqrt((1-S2)/(2N)) / R`. Toy MC draws N events from the measured
(cos, E) sample with uniform azimuth. The MLE column maximises
`sum log p(alpha_i | E_i)` with the *true* ES kinematic pdf, by Nelder-Mead
(not grid-limited).

| N | mean-vector analytic | mean-vector toy 68% | true-pdf MLE toy 68% |
|---|---|---|---|
| 50 | 2.05 | 2.01 | 1.13 |
| 100 | 1.45 | 1.54 | 0.62 |
| 150 | 1.18 | 1.13 | 0.43 |
| 200 | 1.02 | 1.05 | 0.35 |
| **239** | **0.94** | **0.96** | **0.33** |
| 300 | 0.84 | 0.79 | 0.28 |
| 330 | 0.80 | 0.74 | 0.29 |
| 400 | 0.72 | 0.64 | 0.23 |
| 500 | 0.65 | 0.65 | 0.21 |
| 1000 | 0.46 | 0.45 | 0.16 |

(The MLE beats the 1/sqrt(N) mean-vector scaling because the ES angular
distribution has a hard kinematic edge; the Fisher information is formally
divergent there, so the MLE row is a toy result, not an analytic bound.)

N needed for a **3.00 deg** 68% containment with the trivial mean-vector
estimator: **N = 23 events**. For 6.06 deg: **N = 6 events**.

### 5.3 Cross-check on real bursts (not a toy)

`docs/scripts_history_check/real_burst_meanvector.py`, cats 400-439, exactly
the best-case selection (true ES, main track, true electron direction,
E_cluster >= 3 MeV), plain normalised vector sum, compared to the burst's true
neutrino direction (verified to be identical for every event in a cat):

```
40 bursts, 305 events/burst on average
  all events:        68% containment = 0.826 deg   median 0.725   mean 0.710   max 1.368
  subsampled N=239:  68% containment = 1.053 deg   median 0.851   mean 0.870   max 1.734
```

This **matches the March-2026 pipeline result of 0.776 deg** (589 cats, 365
events/burst, weighted mean + bootstrap) essentially exactly, and matches the
toy floor of 0.94-0.96 deg at N=239.

**Conclusion: today's best case of 6.06 deg is a factor ~6 above the
statistical floor of ~0.95 deg. Neither 3 deg nor 6 deg is the floor. 3 deg
would require only ~23 events, not 239.**

---

## 6. What is actually wrong now: the likelihood PDF is evaluated out of bounds

`docs/scripts_history_check/likelihood_scan.py` re-implements the shipped
`load_pdf_interpolator` / `_pdf_likelihood`
(`python/ana/burst_direction.py:20-90`) and scans the log-likelihood as a
function of angular offset from the true burst direction, using the real
best-case inputs.

Two things are wrong at once.

**(i) The PDF is the reconstructed-direction PDF, used on true directions.**
`data/cosine_energy_pdf.npz` has `<cos>` between 0.17 and 0.68 depending on
energy bin, and 13-38% of its weight at `cos < 0` — that is the ED network's
resolution function. The true electron directions fed to the best case have
`<cos> = 0.973` and **zero** weight at `cos < 0`. In angle: the kernel's mean
opening angle is 50-80 deg, against 13.4 deg for the data it is applied to —
roughly 4-6x too broad. On its own this is only inefficient, not biased.

**(ii) The interpolator's cosine grid stops at 0.99, and everything beyond it
is assigned `fill_value = 1e-10`.**

```python
RegularGridInterpolator((energy_centers, cosine_bin_centers), pdf_2d,
                        method='linear', bounds_error=False, fill_value=1e-10)
```

`cosine_bin_centers` spans `[-0.99, +0.99]`. Any event whose cosine to the
trial direction exceeds 0.99 — i.e. **any event within 8.1 deg of the trial
direction** — is scored `log(1e-10) = -23.03` instead of the peak log-density
`~ +2.5`, a 25.5 penalty per event.

With true electron directions, **36.0% of the events are within 8.1 deg of the
truth** (3331 clusters, cats 400-410, E>3 MeV). The likelihood therefore has a
deep hole exactly at the right answer, and is maximised by moving *away* from
it:

| offset from truth [deg] | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 8 | 10 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|
| cat000400, shipped `logL` (rel.) | 0 | -72 | -7 | +37 | +69 | +207 | +359 | +667 | +990 | +1245 |
| cat000401 | 0 | -2 | +26 | +121 | +234 | +376 | +522 | +836 | +1180 | +1482 |
| cat000402 | 0 | +18 | +58 | +136 | +252 | +435 | +636 | +1079 | +1554 | +1936 |
| cat000403 | 0 | +7 | +48 | +130 | +253 | +377 | +485 | +803 | +1145 | +1447 |
| same, with the out-of-bounds hole removed (`logL*`, cat000400) | 0 | -1 | -2 | -4 | -7 | -11 | -16 | -28 | -43 | -62 |

The as-shipped likelihood **rises monotonically out to at least 25 deg** from
the truth on every cat tested. With the hole removed (cosine clipped into the
grid) the very same PDF peaks correctly at 0 deg offset.

This explains everything else that looks odd:

* **Why the answer is ~6 deg and not ~25 deg**: only the Gaussian prior around
  the mean electron direction (sigma = 10 deg) and the walker initialisation
  near that mean hold the sampler back. The result is the equilibrium of a
  tug-of-war between a correct prior and a repulsive likelihood — which is why
  it is so sensitive to prior/init/sampler details (Section 4, effect B).
* **Why `v3` gave 9.91 deg**: uniform prior + random-sphere init removed the
  prior's pull, and the repulsive likelihood took over.
* **Why the per-burst posterior is 27 deg wide** while the across-burst scatter
  is 6 deg: the posterior is not the posterior of the data. Compare March 2026,
  weighted mean + bootstrap: per-burst q68 = 0.99 deg, across-burst containment
  = 0.78 deg — consistent, i.e. correctly calibrated.
* **Why the true-direction scenarios regressed but the full pipeline did not**:
  reconstructed directions actually resemble the PDF, so far fewer of them land
  in the `cos > 0.99` hole. Measured: **36.0%** of true electron directions sit
  at `cos > 0.99` from the truth, versus a spectrum-weighted **6.4%** of the
  PDF's own weight (i.e. of reconstructed directions) — the pathology is ~5.6x
  weaker in the reco scenarios. The full pipeline's 18.3 deg today matches the
  tech note's 18 deg.

**The fix is one line** — give the interpolator `fill_value=None`
(extrapolate) or clip `cos_angles` into `[cosine_bin_centers[0],
cosine_bin_centers[-1]]` before the lookup — plus, separately, using a
kinematic PDF rather than the ED resolution PDF for the true-direction
scenarios. With the hole removed the best case should return to ~1 deg.

---

## 7. Conclusions

**Which number is right for which definition** (best case, ~239 events/burst,
true electron direction, E>3 MeV):

| Definition | Value | Provenance |
|---|---|---|
| 68% containment, current estimator | **6.06 deg** | today's 845-burst campaign — correct arithmetic, degraded estimator |
| 32% containment ("68% quantile" of cos), current estimator | **3.36 deg** | the same data under the tech note's formula — **this is the ~3 deg being remembered** |
| 32% containment, Apr-2026 campaigns | **2.60 / 2.63 deg** | `v2` / `corrected` |
| tech note as published | **2.4 deg** | `pipeline.tex:678`, 567 cats, pre-refactor code, same 32% convention |
| 68% containment, Apr-2026 campaigns | 4.54 / 4.84 deg | `v2` / `corrected` |
| 68% containment, plain weighted mean (March 2026 pipeline) | **0.78 deg** | `aggregate_results_fixed_ed_corrected.json`, 365 events/burst |
| 68% containment, statistical floor at N=239 | **~0.95 deg** | this note, measured + toy + real bursts |
| 68% containment, true-pdf MLE floor at N=239 | ~0.33 deg | toy |

**Was something wrong then?** Yes, but not in the direction assumed. The 2.4 deg
and 2.6 deg numbers used a quantile convention that reports the 32% containment
while calling it 68%. That made the *reported* number look ~1.8x better than the
same data under today's definition. The direction columns were correct
(cols 7:10, fixed by `7abb8f3` on 2026-03-04); the "neutrino direction used as
the per-event direction" hypothesis is ruled out — the sub-degree March-2026
results are reproduced here from scratch with the *electron* directions.

**Is something wrong now?** Yes, and it is bigger than the metric issue. The
best case is a factor ~6 above its own statistical floor because the PDF
likelihood is queried outside its cosine grid for exactly the events nearest
the truth, turning the likelihood into a repulsive one. Three independent
lines agree on the floor — the pipeline's own March-2026 weighted-mean result
(0.78 deg at N=365), the from-scratch mean-vector check on real bursts
(0.83 deg at N=305, 1.05 deg at N=239) and the toy (0.95 deg at N=239) — and all
of them disagree with every emcee+pdf campaign since 2026-03-26. Running the
shipped estimator here on six bursts whose vector-sum error is 0.65 deg returns
~5 deg, so the loss is entirely in the aggregation step.

One caveat worth stating plainly: **effect B is not fully explained.** Inputs,
config and the best-case code path are all verified identical between the
4.54 deg and 6.42 deg campaigns; sampler noise (0.88 deg per burst) accounts
for the per-burst scatter but not obviously for a systematic shift over 500
bursts. The leading unconfirmed hypothesis is a worker-node scipy/LCG change
affecting `RegularGridInterpolator` out-of-bounds handling — which is exactly
where the Section 6 pathology lives.

**Do they measure different things?** Partly. Put on the same convention the
comparison is: tech note **2.4 deg** vs today **3.36 deg** (both 32%
containment), or Apr-2026 **4.54 deg** vs today **6.06 deg** (both 68%
containment). So roughly half the remembered gap is the convention and the
other half is the real ~40% degradation of effect B — sitting on top of the
factor ~6 of effect C that has been there ever since emcee+pdf was switched on
on 2026-03-26.

**Recommended actions**

1. Fix the interpolator out-of-bounds handling in
   `python/ana/burst_direction.py::load_pdf_interpolator` and re-run the
   best-case and perfect-CT scenarios. Expect the best case near 1 deg.
2. Use a PDF appropriate to the direction being aggregated: the ES kinematic
   `p(cos|E)` for true directions, the ED resolution PDF for reconstructed ones.
3. Seed `emcee.EnsembleSampler` (pass a `random_state`) so campaigns are
   reproducible, and check convergence (acceptance is ~8%, ~34 accepted moves
   per walker).
4. Update `snop-tech-notes/chapters/pipeline.tex` and the plotting code in
   `snop-pipeline/python/analysis/analyze_*scenarios_aggregate.py` to use
   `np.percentile(cos, 32)`, and re-quote 2.4 -> the corresponding 68% number.
5. Sanity check going forward: the across-burst 68% containment and the median
   per-burst posterior q68 should agree to within a factor ~1.5. Today they are
   6.06 vs 27 deg — a 4.5x over-coverage that flags the problem on its own.
6. Always report the plain mean-vector result alongside the MCMC one. It is
   free, it is the correct estimator for a high-purity sample, and it would
   have caught this in March 2026. (The tech note already notes that simple
   averaging "performs nearly as well as MCMC" for high-purity ES samples —
   in fact it performs far better.)
7. To close out effect B: compare the scipy / LCG view recorded in the condor
   logs of `condor_scenarios_v2` (2026-04-29) against
   `condor_scenarios_v80t080_final` (2026-07-15).

---

## 8. Scripts

All new, all read-only, in `docs/scripts_history_check/`:

| Script | Purpose |
|---|---|
| `dump_aggregates.py` | dump every scalar in an aggregate JSON |
| `compare_scenario_configs.py` | per-cat `scenario_analysis_config.json` + report across campaigns |
| `paired_campaign_compare.py` | paired per-CAT comparison on the common cats |
| `collect_acceptance.py` | acceptance fraction / error / posterior width per campaign |
| `metric_conventions.py` | the same `cos_all` under every historical metric |
| `first_principles_floor.py` | measured ES kinematics + analytic and toy floor |
| `floor_mle_refined.py` | optimizer-based MLE floor (not grid-limited) |
| `real_burst_meanvector.py` | mean-vector estimator on real bursts, cats 400+ |
| `likelihood_scan.py` | the shipped likelihood vs offset from truth |
| `emcee_noise_test.py` | run-to-run scatter of the shipped emcee estimator |

Data read (never written): `previous-reports-20260824/{eos-aggregates,repo-output}`,
`/eos/user/e/evilla/dune/sn-tps/condor_scenarios_*`,
`/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples/cat0004xx`
(CT-training cats only), `snop-tech-notes/`, `snop-pipeline/`, and the
`refactor-snop-pipeline` git history.
