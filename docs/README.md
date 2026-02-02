# Documentation Index

This directory contains documentation for the DUNE data selection pipeline project.

## Quick Navigation

### 📊 Analysis Documentation

- **[axis_aligned_analysis_notes.md](axis_aligned_analysis_notes.md)**  
  Important considerations for axis-aligned performance analysis. Discusses non-uniform angular distribution, statistical limitations, and why X-aligned performance appears better than expected.

- **[bias_vs_precision_in_emcee_reconstruction.md](bias_vs_precision_in_emcee_reconstruction.md)**  
  Analysis of bias vs precision in EMCEE reconstruction methods.

### 🗂️ Repository Structure

- **[REPOSITORY_STRUCTURE.md](REPOSITORY_STRUCTURE.md)**  
  Complete guide to repository organization, directory structure, and file locations.

- **[CLEANUP_SUMMARY.md](CLEANUP_SUMMARY.md)**  
  Summary of repository cleanup performed on Nov 21, 2025. Before/after comparison and changes made.

### 🛠️ Technical Guides

- **[CT_ED_MCMC_GUIDE.md](CT_ED_MCMC_GUIDE.md)**  
  Guide to Charge Tagging (CT), Electron Direction (ED), and MCMC analysis methods.

- **[DATA_CORRECTION_SUMMARY.md](DATA_CORRECTION_SUMMARY.md)**  
  Summary of data corrections and preprocessing steps.

- **[README_skymap_tool.md](../README_skymap_tool.md)**  
  Documentation for the skymap visualization tool.

### 📋 Project Planning

- **[DEPLOYMENT_PLAN.md](DEPLOYMENT_PLAN.md)**  
  Deployment and workflow planning documentation.

- **[cat_list.txt](cat_list.txt)**  
  List of categories being analyzed.

- **[cat_list_resubmit.txt](cat_list_resubmit.txt)**  
  Categories requiring resubmission.

### 📝 Analysis Reports

- **[cat000001_pipeline_report.md](cat000001_pipeline_report.md)**  
  Example pipeline report for a single category.

- **[electron_scattering_angle_analysis.md](electron_scattering_angle_analysis.md)**  
  Analysis of electron scattering angles.

## Important Notes

### For Analysis Results

If you're looking for **analysis results**:
- PDF reports → `../analysis_outputs/reports/`
- Figures → `../analysis_outputs/cat_examples/`
- Aggregated data → `../analysis_outputs/aggregated_data/`

### For Analysis Scripts

If you're looking for **analysis scripts**:
- Main scripts → `../scripts/analysis/`
- Python modules → `../python/`

### For Understanding Axis-Aligned Analysis

**Start here:** [axis_aligned_analysis_notes.md](axis_aligned_analysis_notes.md)

This explains why X-aligned neutrinos show better performance in the current analysis and what this actually means (spoiler: it's due to sample bias and low statistics, not detector performance).

## Recent Updates

**November 21, 2025:**
- ✅ Repository reorganized and cleaned
- ✅ Axis-aligned analysis documented with caveats
- ✅ Repository structure guide created
- ✅ Cleanup summary documented

## See Also

- Main project README: [../README.md](../README.md)
- Repository structure: [REPOSITORY_STRUCTURE.md](REPOSITORY_STRUCTURE.md)
- Analysis considerations: [axis_aligned_analysis_notes.md](axis_aligned_analysis_notes.md)

---

**For questions or updates to documentation, please update this index accordingly.**
