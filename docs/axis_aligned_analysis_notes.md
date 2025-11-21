# Axis-Aligned Performance Analysis - Important Considerations

**Date:** November 21, 2025  
**Analysis:** EMCEE 6-Scenario Aggregate Results

## Summary

The axis-aligned analysis in the aggregate report shows performance metrics for neutrinos aligned with the X, Y, and Z detector axes. This document discusses important considerations when interpreting these results.

## Key Findings

### Observed Performance Pattern
In the current analysis (Perfect CT scenario), the results show:
- **X-aligned neutrinos appear to have better angular resolution**
- This is **surprising** given DUNE detector geometry expectations

### Expected Detector Performance (DUNE Geometry)

Based on DUNE detector geometry:

1. **X-axis (Drift Direction):**
   - Perpendicular to wire planes
   - **Expected: WORST performance**
   - Limited spatial resolution in drift direction
   - Timing information less precise than wire hit positions

2. **Y-axis (Vertical Direction):**
   - Perpendicular to beam
   - **Expected: MEDIUM performance**
   - Good spatial resolution from wire planes

3. **Z-axis (Beam Direction):**
   - Parallel to wire planes, perpendicular to collection wires
   - **Expected: BEST performance**
   - Optimal geometry for reconstruction
   - Best spatial resolution

## Potential Explanations for Observed Results

### 1. Non-Uniform Angular Distribution of True Neutrino Directions

**Evidence:**
Analysis of true neutrino directions from sample of cats shows:
- |PX|/norm: **0.559** (X component dominant)
- |PY|/norm: **0.477** (Y component)
- |PZ|/norm: **0.443** (Z component smallest)

**Expected for uniform distribution:** 0.577 (= √(1/3))

**Interpretation:**
- The supernova simulation appears to have neutrinos preferentially directed along the X-axis
- This could be due to:
  - Specific supernova location in simulation geometry
  - Selection effects in event generation
  - Coordinate system convention in simulation

**Impact on Analysis:**
When true neutrinos are already more aligned with a particular axis:
- Less angular spread to reconstruct
- Appears to show "better" performance
- **Not indicative of actual detector capability**

### 2. Low Statistics

**Current Sample:**
- Analysis performed on ~39-72 cats (varies by scenario)
- Single neutrino per cat
- Small sample size for axis-aligned selections (±30° cone captures ~13% of sphere)

**Statistical Considerations:**
- With ~10-15 events per axis category, statistical fluctuations can be significant
- Need larger samples for robust axis-dependent performance claims
- Consider statistical uncertainties in comparisons

### 3. Coordinate System Verification

**Important:** The analysis assumes:
- px, py, pz in data correspond to X, Y, Z detector coordinates
- X = drift, Y = vertical, Z = beam direction (standard DUNE convention)

**Action Items:**
- ✓ Verify coordinate system definitions in simulation
- ✓ Confirm axis labels match detector geometry
- ✓ Check for any coordinate transformations in data pipeline

## Recommendations

### For Current Analysis

1. **Add Statistical Uncertainties:**
   - Report sample sizes for each axis category
   - Include error bars or confidence intervals
   - Consider bootstrap or resampling methods

2. **Report Angular Distribution:**
   - Include plot showing true neutrino direction distribution
   - Make non-uniformity explicit in results
   - Consider weighting by solid angle

3. **Expand Sample:**
   - Increase number of cats analyzed
   - Aim for >50 events per axis category
   - More robust statistical conclusions

### For Future Work

1. **Uniform Angular Sampling:**
   - Generate events with uniform angular distribution
   - Enables fair comparison of detector performance by direction
   - Standard approach for detector acceptance studies

2. **Detailed Geometry Study:**
   - Full 2D analysis (θ, φ) instead of axis-aligned bins
   - Map performance as function of neutrino direction
   - Identify any geometric biases or blind spots

3. **Systematic Studies:**
   - Energy dependence of directional performance
   - Impact of different cluster selection criteria
   - Validation against known detector systematics

## Caveats and Disclaimers

⚠️ **Important Caveats:**

1. **Statistical Limitations:**
   - Small sample sizes in axis-aligned categories
   - Results may be dominated by statistical fluctuations
   - Not sufficient to make definitive claims about detector performance

2. **Sample Bias:**
   - True neutrino directions not uniformly distributed
   - X-bias in current sample may explain apparent better performance
   - Results should not be interpreted as fundamental detector properties

3. **Interpretation:**
   - Do not conclude that DUNE performs better for X-aligned neutrinos
   - Results primarily reflect input distribution characteristics
   - Need controlled study with uniform sampling for detector capability assessment

## Conclusion

The apparent better performance for X-aligned neutrinos is likely due to:
1. **Non-uniform angular distribution** in the input sample (X-bias observed)
2. **Low statistics** in axis-aligned subsamples
3. Possibly **statistical fluctuations**

**The results should NOT be interpreted as indicating better detector performance for X-aligned neutrinos**, as this contradicts expected detector geometry effects.

### Recommended Actions:
- [x] Document these considerations
- [ ] Add statistical uncertainties to plots
- [ ] Include true direction distribution plot in report
- [ ] Consider rerunning with uniform angular distribution
- [ ] Increase sample size for robust conclusions

---

**Note:** This document should be updated as more data becomes available and additional studies are performed.
