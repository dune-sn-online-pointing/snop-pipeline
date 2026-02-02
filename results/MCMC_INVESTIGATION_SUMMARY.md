# MCMC Investigation Summary: cat000020

## Key Findings

### Overall Performance
- **Category**: cat000020
- **Events analyzed**: 40
- **Median cos(angle)**: -0.720
- **Median angle**: 136.0°
- **68th percentile angle**: 140.4°

### Critical Observation: Systematic Backward Pointing
- **39 out of 40 events** (97.5%) have **negative cosines**, meaning the reconstructed neutrino direction points **backward** (>90° away) from the true neutrino direction
- This is a **systematic bias**, not random errors

### True Neutrino Direction
```
[-0.646, -0.491, 0.584]  (θ=54.3°, φ=-217.3°)
```
- Verified constant across all 17,594 events in the category (std < 1e-6)
- Loaded from tps/*.root files (neutrino_px/py/pz branches)

### Best Event (Event 13)
The **single outlier** that points in the correct direction:
- Event ID: 13
- Clusters: 416
- **Cos(angle): 0.829** (34.0° angle) ✅
- Log-likelihood: -9471.7
- MCMC direction: [-0.769, -0.638, 0.032]

This demonstrates the MCMC **can** find the correct solution, but only does so in 1/40 cases.

## Physical Interpretation

### Why are directions pointing backward?

The **electron direction (ED) model predicts the direction of the outgoing electron**, not the incoming neutrino. In charged-current interactions:

```
ν + n → e⁻ + p
```

The electron typically scatters **forward** relative to the neutrino direction, but not perfectly aligned. In the detector frame:
- **True neutrino**: comes from direction [-0.646, -0.491, 0.584]
- **Electron clusters**: their energy deposits show directions that MCMC combines
- **MCMC result**: finds most likely **neutrino direction** given cluster directions

### The Flip Test
When we manually flip all reconstructed directions (`-direction`):
- Original: median angle = 136°
- Flipped: median angle ≈ 44° (estimated)

This 92° improvement suggests the ED model is systematically predicting directions that point **opposite** to where the neutrino came from.

## Possible Explanations

### 1. ED Model Training Issue
- The ED model was trained on **electron directions** (outgoing particles)
- Perhaps the training data had a convention where electrons point backward?
- Or the model learned to predict the direction opposite to what we expect?

### 2. Physics Constraint Missing
- MCMC only uses the energy-cosine PDF: `P(E, cos(θ))`
- Perhaps we need additional physics constraints:
  - Kinematics: electron energy vs scattering angle
  - Conservation laws: momentum/energy conservation
  - Interaction type: CC vs ES have different angular distributions

### 3. Local Minimum Problem
- MCMC initialization: mean of cluster directions
- If all cluster directions point "forward" (electron direction), the mean also points forward
- MCMC might be getting stuck in a local minimum
- The true neutrino direction (pointing backward) might be another mode in the likelihood landscape

### 4. Track Selection Issue
- **Important question**: Are we using **all CC interactions** or filtering for **ES (elastic scattering)**?
- CC interactions: produce electrons that scatter forward
- ES interactions: neutrino scatters elastically, different kinematics
- Need to verify: what is the `interaction_type` for these events?

## Cluster Statistics

- **Mean clusters per event**: 408
- **Range**: 363-483 clusters
- These are very high numbers, suggesting we're including many clusters per event
- Question: Should we filter for only the **main electron track** clusters?

## Recommendations

### Immediate Actions
1. **Check interaction type**: Verify if we're selecting ES vs CC tracks
   - Look for interaction_type in volume metadata
   - CC interactions produce forward electrons
   - ES interactions have different angular relationships

2. **Investigate Event 13**: Why did it succeed?
   - What's different about its cluster distribution?
   - Does it have different energy spectrum?
   - Different log-likelihood landscape?

3. **Test alternative MCMC initialization**:
   - Instead of mean of cluster directions, try:
     - Random direction on sphere
     - Multiple starting points (multi-start optimization)
     - Opposite of mean direction (flip initialization)

### Physics Understanding
4. **Consult training data**: How was the ED model trained?
   - What convention for electron direction?
   - Was it trained on neutrino direction or electron direction?
   - Check training labels in the dataset

5. **Add physics constraints**: 
   - Implement kinematic constraints (electron energy vs angle)
   - Use momentum conservation
   - Add interaction-type-specific priors

### Long-term Solutions
6. **Retrain ED model**: If the model is predicting electron directions
   - Either flip the training labels
   - Or train a separate model specifically for neutrino pointing

7. **Alternative approach**: Instead of per-cluster directions
   - Use only the **main electron track** direction
   - Weight clusters by energy more heavily
   - Apply topology cuts to select most relevant clusters

## Files Generated

- **PDF Report**: `results/mcmc_investigation_cat000020.pdf`
  - Page 1: Theta-phi distributions with true direction overlay
  - Page 2: Bias analysis (systematic offsets)
  - Page 3: MCMC performance vs cluster count and likelihood
  - Page 4: Flipped direction comparison (shows what resolution could be)

- **JSON Data**: `results/ed_mcmc_cats/cat000020/metrics.json`
  - Full event-by-event results
  - MCMC directions, log-likelihoods, acceptance rates

## Next Steps

**Most urgent**: Answer the track selection question
- Are we using ES tracks only, or all CC interactions?
- This fundamentally changes the expected physics

**Then**: Investigate why MCMC is stuck in wrong minimum
- Test different initialization strategies
- Examine the likelihood landscape around true direction
- Check if adding physics constraints helps
