# EMCEE Reconstruction: Bias vs Precision

## Executive Summary

**EMCEE produces high-precision directional reconstructions that can have large systematic bias from the true neutrino direction.** The 68% credible interval (ω₆₈) measures MCMC statistical convergence, not reconstruction accuracy. With poor input data (e.g., incorrect channel tagging), EMCEE will confidently converge to the wrong direction.

## Key Findings

### Evidence from cat000072

| Scenario | Angular Error (Bias) | ω₆₈ (Precision) | Bias/Precision Ratio |
|----------|----------------------|-----------------|---------------------|
| **Perfect CT** | 1.61° | 0.33° | **4.9×** |
| **Full Pipeline** | 106.54° | 1.71° | **62.3×** |

### Interpretation

1. **Perfect CT scenario:**
   - EMCEE converges with ±0.33° precision
   - Around a direction that is 1.61° away from truth
   - Bias is ~5× larger than statistical uncertainty

2. **Full Pipeline scenario:**
   - EMCEE converges with ±1.71° precision  
   - Around a direction that is **106° away from truth** (nearly opposite!)
   - Bias is ~62× larger than statistical uncertainty

## What These Metrics Mean

### ω₆₈ (68% Credible Interval Radius)
- **Measures:** MCMC statistical convergence around the best-fit direction
- **Interpretation:** How tightly the posterior distribution clusters
- **Does NOT measure:** Distance from true direction
- **Analogy:** How tightly grouped your shots are on a target

### Angular Error (Bias)
- **Measures:** Systematic offset from true neutrino direction
- **Interpretation:** How wrong the reconstruction is
- **Depends on:** Input data quality (electron selection, channel tagging)
- **Analogy:** How far your shot group is from the bullseye

## The Precision vs Accuracy Problem

EMCEE demonstrates the classic **"precise but inaccurate"** pattern:

```
         Precision (ω₆₈)          Accuracy (Angular Error)
Perfect CT:    0.33° ✓            1.61° (good)
Full Pipeline: 1.71° ✓            106.54° (terrible)
```

This is like a rifleman who consistently hits the same spot on the target, but that spot is far from the bullseye. The shot grouping is tight (good precision), but the grouping is centered on the wrong location (poor accuracy).

## Physical Interpretation

### Why Does This Happen?

1. **Electron Scattering:** Individual electrons scatter at various angles from the true neutrino direction due to:
   - Multiple scattering in the detector
   - Nuclear recoil effects
   - Electromagnetic shower development
   - Measurement uncertainties

2. **EMCEE's Task:** Find the most likely parent neutrino direction given the observed electron distribution

3. **The Problem:** 
   - With **perfect channel tagging** → EMCEE sees mostly correct electrons → converges near truth
   - With **poor channel tagging** → EMCEE sees many wrong particles (CC events, backgrounds) → converges to wrong direction
   - In both cases, EMCEE converges precisely (small ω₆₈), but accuracy depends entirely on input quality

### Skymap Evidence

The electron skymap visualizations clearly show:
- Individual electrons scattered across large angular regions (tens of degrees)
- EMCEE best-fit can be significantly offset from the true direction
- The 68% credible interval (orange circle) is small and centered on the best-fit
- This credible interval does NOT necessarily contain the true direction

## Implications for Analysis

### 1. ω₆₈ Should NOT Be Used Alone
- Small ω₆₈ ≠ good reconstruction
- ω₆₈ only indicates MCMC convergence quality
- Must compare to true direction (angular error) to assess accuracy

### 2. Channel Tagging Quality is Critical
The degradation from Perfect CT to Full Pipeline:
- Angular error worsens by **66×** (1.61° → 106.54°)
- Precision worsens by only **5×** (0.33° → 1.71°)
- **Poor channel tagging causes massive systematic bias, not just larger uncertainties**

### 3. Statistical vs Systematic Uncertainty
The bias/precision ratio reveals the dominant error source:
- **Bias/Precision = 5×** (Perfect CT): Systematic bias dominates, but manageable
- **Bias/Precision = 62×** (Full Pipeline): Systematic bias completely dominates

For the full pipeline, improving MCMC convergence (reducing ω₆₈) would have negligible impact on overall reconstruction quality. The problem is **systematic, not statistical**.

## Comparison to Other Scenarios

Looking at aggregate statistics across all 567 cats (68% quantile):

| Scenario | Angular Error (68% Q) | Notes |
|----------|----------------------|-------|
| **Best Case** | 6.73° | True electrons, optimal baseline |
| **Perfect CT** | 19.69° | Still good with perfect ES/ED separation |
| **Full Pipeline** | 54.09° | 275% degradation from Perfect CT |

Even with perfect channel tagging, inherent electron scattering causes ~20° median errors. The full pipeline's channel tagging errors add another ~34° of systematic bias on top of this.

## Recommendations

### For Analysis
1. **Always report both metrics:**
   - ω₆₈ for statistical quality assessment
   - Angular error for physics performance
   
2. **Focus optimization efforts on:**
   - Channel tagging improvement (reduces bias)
   - Electron energy thresholds (removes low-quality electrons)
   - Not MCMC tuning (precision is already good)

### For Presentation
1. Clearly distinguish precision (ω₆₈) from accuracy (angular error)
2. Use "systematic bias" terminology for angular error
3. Show skymap visualizations to illustrate the precision/accuracy distinction
4. Emphasize that small ω₆₈ does not imply good reconstruction

## Technical Notes

### Two Reconstruction Methods

**CRITICAL:** The analysis uses TWO different reconstruction algorithms:

1. **EMCEE Method** (used for main analysis):
   - Affine Invariant MCMC Ensemble sampler
   - Stores only summary statistics (best-fit, ω₆₈, acceptance fraction)
   - Better performance: 1.61° for cat000072
   - **No posterior chain saved**

2. **Regular MCMC Method** (older implementation):
   - Different MCMC algorithm
   - Stores full posterior chain (10,001 samples)
   - Worse performance: 19.04° for cat000072
   - Used for visualization purposes only

**For cat000072 comparison:**
- EMCEE best-fit: (0.588, 0.779, 0.219) → 1.61° error
- Regular best-fit: (0.456, 0.730, 0.508) → 19.04° error
- Angular difference between methods: **18.52°**

The two methods converge to DIFFERENT directions because they use different likelihood formulations or priors.

### EMCEE Algorithm Behavior
EMCEE explores the posterior distribution:
```
P(θ | data) ∝ P(data | θ) × P(θ)
```

Where:
- θ = neutrino direction parameters
- data = observed electron directions and energies
- P(data | θ) = likelihood of observing these electrons from direction θ

**Key insight:** If the input data includes wrong particles, the likelihood function itself is biased, and EMCEE will correctly sample from this biased posterior. The problem is upstream in data selection, not in MCMC convergence.

### Credible Interval Interpretation
The ω₆₈ represents the angular radius within which 68% of the posterior probability mass lies. This is analogous to a 1σ confidence interval in frequentist statistics, but:
- It's conditioned on the observed data
- It assumes the likelihood model is correct
- It does NOT account for systematic biases in the input data

## Conclusions

1. **EMCEE performs exactly as designed:** It finds high-precision best-fit directions given the input electron data

2. **The problem is data quality, not MCMC convergence:** Poor channel tagging introduces systematic bias that no amount of MCMC tuning can fix

3. **Precision ≠ Accuracy:** Small credible intervals (ω₆₈) indicate good MCMC convergence but say nothing about distance from truth

4. **Channel tagging is the critical bottleneck:** Improving CT accuracy from current ~40% to perfect would reduce angular errors by ~175% (from 54° to 20°)

5. **Visualization is essential:** Skymap plots clearly reveal the distinction between precision (tight posterior) and accuracy (proximity to truth)

---

*Document created: November 21, 2025*  
*Analysis based on: 567 cats, 6 reconstruction scenarios, cat000072 case study*
