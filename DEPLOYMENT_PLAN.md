# SN Pointing Pipeline - Full Deployment Plan

## Current Status
✅ Scenario 1-2: Working with improved MCMC  
⏳ Scenario 3-5: Running on Condor with CT weighting

## Phase 1: Validation (Before Full Processing)

### 1.1 MCMC Validation
- [x] Implement proper MCMC convergence (50 inits + 10k chain)
- [x] Adaptive proposal scaling
- [ ] Verify chain convergence diagnostics
- [ ] Check acceptance rates are reasonable (20-50%)
- [ ] Validate log-likelihood calculations

### 1.2 Metrics Storage
Need to save per-category:
```
/eos/project-e/ep-nu/evilla/sn-pointing/cat00000X/pipeline/
├── scenario_1_best_case.npz
├── scenario_2_perfect_ct.npz
├── scenario_3_full_pipeline.npz
├── scenario_4_weighted_linear.npz
├── scenario_5_weighted_squared.npz
└── intermediate_data/
    ├── clusters_es_selected.npz
    ├── clusters_3mev_cut.npz
    ├── ct_predictions.npz
    └── ed_predictions.npz
```

Each scenario file should contain:
- `reconstructed_direction`: [x, y, z]
- `true_nu_direction`: [x, y, z]
- `angular_error_deg`: float
- `cos_theta`: cos(angle) for 68% quantile
- `n_clusters_total`: int
- `n_clusters_used`: int (after all cuts)
- `cluster_indices_used`: array of indices
- `mcmc_chain_directions`: [N, 3] full chain
- `mcmc_chain_log_likes`: [N] full chain
- `cluster_energies`: array
- `cluster_directions`: [N, 3] directions used
- `ct_weights`: array (for scenarios 4-5, None for others)

###1.3 Efficiency Tracking
Per scenario, track:
- Initial clusters (all main tracks)
- After ES selection (S2-S5)
- After 3 MeV cut
- After CT threshold (S3-S5)
- Final MCMC input

## Phase 2: Aggregation Tools

### 2.1 Per-Cat Processing
Adapt `run_cat000001_full_analysis.py` to:
- Save to `/eos/.../catXXXXXX/pipeline/` not workspace
- Save intermediate data for reprocessing
- Include all required metrics

### 2.2 Multi-Cat Aggregation
Use/adapt `aggregate_sn_results.py` to:
- Load all cats from `/eos/.../cat*/pipeline/`
- Compute cos(θ) distribution across all events
- Calculate 68% quantile of cos(θ)
- Average efficiencies across cats
- Break down by inclination category

### 2.3 Inclination Categories
Define based on true neutrino direction:
- **Z-like**: |cos(θ_z)| > 0.7 (mostly vertical)
- **X-like**: |cos(θ_x)| > 0.7 (along beam)
- **Y-like**: |cos(θ_y)| > 0.7 (perpendicular)

Where cos(θ_i) = |ν_i / |ν||

### 2.4 Final Report
Use/adapt `generate_sn_report.py` to create:
1. Overall performance (all cats)
   - 68% quantile cos(θ)
   - Mean angular error
   - Efficiency summary
   
2. By inclination
   - X-like performance
   - Y-like performance  
   - Z-like performance

3. Per-scenario comparison (S1-S5)

## Phase 3: Batch Submission

### 3.1 Condor Template
Create submission script for all cats:
- One job per cat per scenario
- Or one job per cat, runs all scenarios
- Proper resource requests (32GB, GPU)
- Save directly to EOS

### 3.2 Monitoring
- Track job status
- Check for failures
- Validate outputs exist

## Phase 4: Post-Processing
- Run aggregation across all cats
- Generate final PDF report
- Validate results make physical sense

## Next Steps
1. Wait for S3-S5 to finish for cat000001
2. Validate MCMC convergence
3. Update script to save to EOS with proper structure
4. Test on cat000001 + cat000002
5. If validated, submit all 100 cats
