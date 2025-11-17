# Neutrino Pointing Performance Baselines

## KEY METRIC: 68th Percentile of Cosine Distribution

**The primary performance metric is the 68th percentile of cos(θ) where θ is the angle between reconstructed and true neutrino direction.**

Higher values = better (closer to 1.0 = perfect alignment)

---

## Reference Baseline Results (cat000035)

### 1. Physics Limit: Single Electron ES Scattering
- **Source**: True scattering angles from ROOT files (336k events, 48 categories)
- **Median cos(θ)**: ~0.991 (corresponds to ~8° median angle)
- **68th percentile cos(θ)**: ~0.975 (corresponds to ~13° angle)
- **Description**: Fundamental physics limit from electron scattering kinematics. Even perfect reconstruction cannot exceed this due to ES scattering angles.

### 2. MCMC with TRUE Electron Directions (Best Case Scenario)
- **Method**: MCMC optimization using TRUE electron momenta from metadata
- **Events**: 40 (cat000035)
- **Results**:
  - **Median cos(θ): 0.9971** (4.35° median angle)
  - **68th percentile cos(θ): 0.9980** ← **BEST CASE BASELINE**
  - **Mean cos(θ): 0.9861**
  - **Forward pointing: 100%**
- **Description**: Shows maximum achievable performance if electron directions were perfectly known. Better than single-electron physics limit because multiple electrons are combined with energy weighting.

### 3. Pure Energy-Weighted ED Predictions (ES-filtered, cat000020)
- **Method**: Energy-weighted average of ED model predictions on ES main track clusters only
- **Events**: 40
- **Results**:
  - **Median cos(θ): -0.389** (112.9° median angle)
  - **68th percentile cos(θ)**: ~-0.52 (estimated from 124° at 68th percentile angle)
  - **Forward pointing: 40%**
- **Description**: Current ED model performance. Systematic backward pointing indicates model predicts electron direction instead of neutrino direction.

### 4. MCMC with ED Model Predictions (ES-filtered, cat000020)
- **Method**: MCMC optimization using ED model predictions
- **Events**: 40
- **Results**:
  - **Median cos(θ): -0.395** (113.3° median angle)
  - **68th percentile cos(θ)**: ~-0.53 (estimated from 134° at 68th percentile angle)
  - **Forward pointing: 40%**
- **Description**: MCMC provides no improvement over simple energy-weighted average. The problem is the ED model, not the optimization method.

---

## Performance Summary Table

| Method | 68th %ile cos(θ) | Median cos(θ) | Median Angle | Status |
|--------|------------------|---------------|--------------|--------|
| **MCMC with TRUE e- dirs** | **0.9980** | 0.9971 | 4.35° | ✅ Best possible |
| Physics limit (single e-) | ~0.975 | ~0.991 | ~8° | ✅ Theoretical |
| Pure ED (ES-filtered) | ~-0.52 | -0.389 | 112.9° | ❌ Broken |
| MCMC + ED (ES-filtered) | ~-0.53 | -0.395 | 113.3° | ❌ Broken |

---

## Key Insights

1. **Best achievable performance**: cos(θ) 68% = 0.9980 (if electron directions were perfect)
2. **Current ED model**: cos(θ) 68% = ~-0.52 (systematic backward pointing)
3. **Gap to close**: Δcos(θ) ≈ 1.52 (from -0.52 to +0.9980)
4. **Root cause**: ED model trained on electron direction, not neutrino direction
5. **MCMC is not the issue**: Optimization works perfectly with true directions

---

## Next Steps

1. Test ED model predictions on multiple categories to confirm systematic behavior
2. Retrain ED model with neutrino_px/py/pz as labels
3. Target performance: cos(θ) 68% > 0.95 (accounting for detector resolution)
