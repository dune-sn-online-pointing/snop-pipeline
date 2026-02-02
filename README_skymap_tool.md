# Electron Burst Skymap Visualization Tool

## Overview

`plot_electron_skymap.py` is a standalone tool to visualize electron burst directions from supernova neutrino events. It creates dual sky maps showing:

1. **Full-sky view** (Mollweide projection): All electron directions across the entire sky
2. **Zoomed view** (Gnomonic projection): Electrons within a cone around the true neutrino direction

## Features

- Loads EMCEE reconstruction results (best-fit direction, angular error, credible intervals)
- Extracts **individual electron directions** from cluster metadata (not just the final aggregate)
- Shows true neutrino direction, EMCEE best-fit, and all electron scatter points
- Configurable zoom angle for detailed inspection
- Dark blue/yellow color scheme for clear visualization

## Why this tool?

The electron directions come from two different data sources:
- **EMCEE summary files**: Only store final best-fit direction (1 direction per cat)
- **Cluster image metadata**: Store all individual electron directions (hundreds to thousands)

This tool combines both sources to show how individual electrons scatter relative to the true and reconstructed neutrino directions.

## Usage

### Basic usage (Perfect CT scenario, cat000072):
```bash
python3 plot_electron_skymap.py cat000072
```

### With options:
```bash
# Different scenario
python3 plot_electron_skymap.py cat000072 --scenario full_pipeline

# Larger zoom angle (default: 30°)
python3 plot_electron_skymap.py cat000072 --zoom 90

# Custom output filename
python3 plot_electron_skymap.py cat000072 --output my_burst.png

# Different data path
python3 plot_electron_skymap.py cat000072 --base-path /path/to/data
```

### Available scenarios:
- `best_case` - Best Case (True e⁻)
- `perfect_ct` - Perfect CT (ES + ED) **[default]**
- `full_pipeline` - Full Pipeline (CT + ED)
- `weighted_ct` - Weighted CT
- `perfect_ct_e_gt_10mev` - Perfect CT (E>10 MeV)
- `perfect_ct_e_gt_5mev` - Perfect CT (E>5 MeV)

## Examples

### Example 1: Best reconstruction
```bash
python3 plot_electron_skymap.py cat000072 --zoom 90
# Output: Angular error: 1.61°, ω₆₈: 0.33°, 1276 electrons
```

### Example 2: Full pipeline comparison
```bash
python3 plot_electron_skymap.py cat000072 --scenario full_pipeline --zoom 90
# Output: Angular error: 106.54°, ω₆₈: 1.71°, 1276 electrons
```

### Example 3: Multiple cats
```bash
for cat in cat000072 cat000051 cat000103; do
    python3 plot_electron_skymap.py $cat --zoom 90 --output ${cat}_skymap.png
done
```

## Output

The tool generates a PNG file with:

**Left panel (Mollweide projection):**
- Full sky view with all electrons (yellow points)
- True neutrino direction (red star)
- EMCEE best-fit (yellow star with black outline)

**Right panel (Gnomonic projection):**
- Zoomed tangent plane centered on true direction
- True direction at origin (red star)
- EMCEE best-fit with 68% credible interval circle (yellow)
- Electrons within zoom cone
- Angular scale circles (5°, 10°, 15°, 20°, 25°, 30°...)

## Data Structure

The tool expects:
```
/eos/project-e/ep-nu/evilla/sn-pointing/
├── cat000072/
│   ├── pipeline/
│   │   └── cat000072_scenario_perfect_ct_emcee.npz
│   └── cat000072_cluster_images_tick3_ch2_min2_tot3_e3p0/
│       ├── 0/
│       │   ├── es_*.npz  (electron metadata with px, py, pz)
│       │   └── cc_*.npz
│       └── ...
├── cat000073/
...
```

## Technical Details

### Electron Direction Extraction
Electron directions are extracted from cluster metadata NPZ files:
- Files: `cat*/cat*_cluster_images_tick3_ch2_min2_tot3_e3p0/*/es_*.npz`
- Metadata shape: (N, 18) array with columns:
  - [0-7]: id, tick, ch, plane, energy, x, y, z
  - **[8-10]: px, py, pz (direction components)** ← Extracted
  - [11-17]: Additional metadata

### EMCEE Data
EMCEE files contain:
- `{scenario}_emcee_best_dir_x/y/z`: Best-fit direction (Cartesian)
- `{scenario}_emcee_true_nu_px/py/pz`: True neutrino direction
- `{scenario}_emcee_angular_error_deg`: Angular separation
- `{scenario}_emcee_omega_68`: 68% credible interval radius (degrees)

### Coordinate System
- X, Y, Z: Detector coordinate system
- Theta (θ): Polar angle from +Z axis
- Phi (φ): Azimuthal angle in X-Y plane

## Performance

- Loads 1000+ electron directions in < 1 second
- Generates publication-quality 300 DPI images
- Handles full 4π sky visualization

## Integration

This is a **standalone tool** - it can be used independently or integrated into larger analysis pipelines. It doesn't modify any data files or depend on the main aggregate analysis scripts.
