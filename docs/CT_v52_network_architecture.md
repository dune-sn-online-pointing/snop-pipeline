# CT Volume v52 Network Architecture

**Model:** `ct_volume_v52_batch_reload`  
**Task:** Channel Tagging (ES vs CC classification)  
**Plane:** X  
**Training Date:** November 16, 2025

## Network Architecture Flowchart

```
INPUT: Volume Image (3D cluster representation)
  |
  ↓
┌─────────────────────────────────────────────────────────┐
│ CONVOLUTIONAL BLOCK 1                                   │
│  • Conv3D: 28 filters, kernel=3×3×3                     │
│  • Activation: ReLU                                     │
│  • Batch Normalization                                  │
│  • MaxPooling3D: pool_size=(2,2,2)                      │
└─────────────────────────────────────────────────────────┘
  |
  ↓
┌─────────────────────────────────────────────────────────┐
│ CONVOLUTIONAL BLOCK 2                                   │
│  • Conv3D: 28 filters, kernel=3×3×3                     │
│  • Activation: ReLU                                     │
│  • Batch Normalization                                  │
│  • MaxPooling3D: pool_size=(2,2,2)                      │
└─────────────────────────────────────────────────────────┘
  |
  ↓
┌─────────────────────────────────────────────────────────┐
│ CONVOLUTIONAL BLOCK 3                                   │
│  • Conv3D: 29 filters, kernel=3×3×3                     │
│  • Activation: ReLU                                     │
│  • Batch Normalization                                  │
│  • MaxPooling3D: pool_size=(2,2,2)                      │
└─────────────────────────────────────────────────────────┘
  |
  ↓
┌─────────────────────────────────────────────────────────┐
│ CONVOLUTIONAL BLOCK 4                                   │
│  • Conv3D: 47 filters, kernel=3×3×3                     │
│  • Activation: ReLU                                     │
│  • Batch Normalization                                  │
│  • MaxPooling3D: pool_size=(2,2,2)                      │
└─────────────────────────────────────────────────────────┘
  |
  ↓
┌─────────────────────────────────────────────────────────┐
│ CONVOLUTIONAL BLOCK 5                                   │
│  • Conv3D: 48 filters, kernel=3×3×3                     │
│  • Activation: ReLU                                     │
│  • Batch Normalization                                  │
│  • MaxPooling3D: pool_size=(2,2,2)                      │
└─────────────────────────────────────────────────────────┘
  |
  ↓
┌─────────────────────────────────────────────────────────┐
│ CONVOLUTIONAL BLOCK 6                                   │
│  • Conv3D: 48 filters, kernel=3×3×3                     │
│  • Activation: ReLU                                     │
│  • Batch Normalization                                  │
│  • MaxPooling3D: pool_size=(2,2,2)                      │
└─────────────────────────────────────────────────────────┘
  |
  ↓
┌─────────────────────────────────────────────────────────┐
│ FLATTEN                                                 │
│  Convert 3D feature maps to 1D vector                   │
└─────────────────────────────────────────────────────────┘
  |
  ↓
┌─────────────────────────────────────────────────────────┐
│ DENSE LAYER 1                                           │
│  • Units: 96                                            │
│  • Activation: ReLU                                     │
│  • Dropout: 0.3                                         │
└─────────────────────────────────────────────────────────┘
  |
  ↓
┌─────────────────────────────────────────────────────────┐
│ DENSE LAYER 2                                           │
│  • Units: 32                                            │
│  • Activation: ReLU                                     │
│  • Dropout: 0.3                                         │
└─────────────────────────────────────────────────────────┘
  |
  ↓
┌─────────────────────────────────────────────────────────┐
│ OUTPUT LAYER                                            │
│  • Units: 1 (binary classification)                     │
│  • Activation: Sigmoid                                  │
│  • Output: P(ES) ∈ [0, 1]                              │
└─────────────────────────────────────────────────────────┘
  |
  ↓
OUTPUT: ES probability (0 = CC, 1 = ES)
```

## Architecture Summary

### Convolutional Layers
- **6 Conv3D blocks** with increasing filter complexity
- Filter progression: 28 → 28 → 29 → 47 → 48 → 48
- All kernels: 3×3×3
- Each block includes:
  - Conv3D
  - ReLU activation
  - Batch Normalization
  - MaxPooling3D (2×2×2)

### Fully Connected Layers
- **2 Dense layers**: 96 → 32 units
- Dropout rate: 0.3 (30%) for regularization
- ReLU activations

### Output
- **Binary classification**: Sigmoid activation
- Predicts P(Electron Scattering)

## Training Configuration

| Parameter | Value |
|-----------|-------|
| Batch size | 32 |
| Epochs | 50 |
| Learning rate | 0.001 |
| Max samples per class | 50,000 |
| Optimizer | Adam (default) |
| Loss function | Binary Cross-Entropy |

## Data

- **ES directory:** `/eos/home-e/evilla/dune/sn-tps/prod_es/es_production_volume_images_tick3_ch2_min2_tot3_e2p0`
- **CC directory:** `/eos/home-e/evilla/dune/sn-tps/prod_cc/cc_production_volume_images_tick3_ch2_min2_tot3_e2p0`
- **Plane:** X (collection plane)
- **Image parameters:**
  - tick: 3
  - ch: 2
  - min: 2
  - tot: 3
  - Energy threshold: 2.0 MeV

## Key Features

1. **Deep architecture**: 6 convolutional blocks for hierarchical feature extraction
2. **3D convolutions**: Captures spatial structure of clusters in 3D space
3. **Batch normalization**: Stabilizes training and improves convergence
4. **Dropout regularization**: Prevents overfitting (30% dropout rate)
5. **Progressive filters**: Gradually increases feature complexity (28→48 filters)

## Performance

See comprehensive analysis report:
`/eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/ct_volume_v52_batch_reload_comprehensive_analysis.pdf`

---

**Note:** This is the production model used in the EMCEE direction reconstruction pipeline for the Perfect CT scenario.
