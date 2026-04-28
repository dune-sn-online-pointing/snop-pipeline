#!/usr/bin/env python3
"""
Run the ED model on clusters selected by the pipeline selection stage.

This script expects three inputs:
 - `volumes_npz`: .npz with `volumes` array shaped (N, ...), one volume per cluster.
 - `selection_npz`: .npz with a boolean mask `is_selected_cluster` (N,) and a `tentative_dirs` array
    shaped (N,3) or (M,3) aligned to the selected clusters. If `tentative_dirs` isn't found,
    the script will still run ED but will not include tentative directions.
 - `ed_model`: path to a Keras/TensorFlow ED model.

Output: a .npz file with arrays for the selected clusters: `cluster_idx`, `energy` (if present),
and `ed_output_*` raw arrays produced by the model. The exact keys depend on the model's output.
"""

import argparse
from pathlib import Path
import numpy as np
import os

try:
    import tensorflow as tf
except Exception:
    tf = None


def _require_init_done():
    if os.environ.get('INIT_DONE', '').lower() != 'true':
        raise RuntimeError('Environment not initialized. Run: source scripts/init.sh')


def main():
    _require_init_done()

    p = argparse.ArgumentParser()
    p.add_argument('ed_model', help='Path to ED Keras model')
    p.add_argument('volumes_npz', help='.npz file containing `volumes` and optional `cluster_energy`')
    p.add_argument('selection_npz', help='.npz file containing `is_selected_cluster` boolean mask and optionally `tentative_dirs`')
    p.add_argument('--out', default=None)
    p.add_argument('--batch-size', type=int, default=32)
    args = p.parse_args()

    if tf is None:
        raise RuntimeError('TensorFlow not available in this environment')

    vols_data = np.load(args.volumes_npz, allow_pickle=True)

    # Check for 3-plane mode
    three_plane_mode = ('images_x' in vols_data and 'images_u' in vols_data and 'images_v' in vols_data)

    if three_plane_mode:
        volumes_x = vols_data['images_x']
        volumes_u = vols_data['images_u']
        volumes_v = vols_data['images_v']
        n_total = len(volumes_x)
        print(f"Loaded 3-plane volumes: X={volumes_x.shape}, U={volumes_u.shape}, V={volumes_v.shape}")
    elif 'volumes' in vols_data:
        volumes = vols_data['volumes']
        n_total = len(volumes)
    elif 'images' in vols_data:
        volumes = vols_data['images']
        n_total = len(volumes)
    else:
        raise KeyError('volumes_npz must contain `volumes`, `images`, or 3-plane arrays (images_x, images_u, images_v)')
    energies = vols_data.get('cluster_energy')

    selection_data = np.load(args.selection_npz, allow_pickle=True)
    if 'is_selected_cluster' in selection_data:
        selected_mask = np.asarray(selection_data['is_selected_cluster'], dtype=bool)
    else:
        raise KeyError('selection_npz must contain boolean mask `is_selected_cluster`')

    tentative_dirs = selection_data.get('tentative_dirs')

    if n_total != selected_mask.shape[0]:
        raise ValueError('volumes and selection mask must have the same length')

    selected_idx = np.where(selected_mask)[0]
    print(f'Found {len(selected_idx)} selected clusters')

    # load model
    model = tf.keras.models.load_model(args.ed_model, compile=False)
    n_model_inputs = len(model.inputs) if hasattr(model, 'inputs') else 1

    # Get expected input shape
    expected_input = model.inputs[0].shape if hasattr(model, 'inputs') and model.inputs else None
    exp_h, exp_w, exp_c = None, None, None
    if expected_input is not None and len(expected_input) >= 4:
        exp_h = expected_input[1]
        exp_w = expected_input[2]
        exp_c = expected_input[3] if len(expected_input) > 3 else 1

    def preprocess_plane(plane_volumes, selected_idx):
        """Preprocess a single plane's volumes."""
        selected = plane_volumes[selected_idx]
        if selected.dtype == object:
            selected = np.stack(
                [np.asarray(v, dtype=np.float32) for v in selected],
                axis=0,
            )
        else:
            selected = np.asarray(selected, dtype=np.float32)

        # Add channel dim if needed
        if selected.ndim == 3:
            selected = selected[..., np.newaxis]

        # Resize if needed
        if exp_h is not None and exp_w is not None:
            if selected.shape[1] != int(exp_h) or selected.shape[2] != int(exp_w):
                selected = tf.image.resize(
                    selected,
                    (int(exp_h), int(exp_w)),
                    method='bilinear',
                ).numpy()

        # Adjust channels if needed
        if exp_c is not None and int(exp_c) != selected.shape[-1]:
            if int(exp_c) == 1:
                selected = selected[..., :1]
            else:
                selected = np.repeat(selected[..., :1], int(exp_c), axis=-1)

        return selected

    if three_plane_mode and n_model_inputs == 3:
        # Proper 3-plane processing: pass U, V, X as separate inputs
        # IMPORTANT: Order must be [U, V, X] to match how the model was trained
        selected_x = preprocess_plane(volumes_x, selected_idx)
        selected_u = preprocess_plane(volumes_u, selected_idx)
        selected_v = preprocess_plane(volumes_v, selected_idx)
        print(f"3-plane inference: U={selected_u.shape}, V={selected_v.shape}, X={selected_x.shape}")

        preds = model.predict(
            [selected_u, selected_v, selected_x],  # Order: U, V, X (matches original training)
            batch_size=args.batch_size,
        )
    elif n_model_inputs == 3:
        # Single plane but model expects 3 inputs - pass same plane 3 times (legacy fallback, not ideal)
        print("WARNING: Model expects 3 inputs but only single-plane data available. Using same plane for all inputs.")
        selected_volumes = preprocess_plane(volumes, selected_idx)
        preds = model.predict(
            [selected_volumes, selected_volumes, selected_volumes],
            batch_size=args.batch_size,
        )
    else:
        # Single plane, single input model
        selected_volumes = preprocess_plane(volumes, selected_idx)
        preds = model.predict(selected_volumes, batch_size=args.batch_size)

    # Normalize preds to numpy array
    preds = np.asarray(preds)

    out = {
        'cluster_idx': selected_idx,
        'ed_raw': preds,
    }
    if energies is not None:
        out['energy'] = energies[selected_idx]
    if tentative_dirs is not None:
        # tentative_dirs might be full-length array, align to selected_idx
        if tentative_dirs.shape[0] == volumes.shape[0]:
            out['tentative_dirs'] = tentative_dirs[selected_idx]
        else:
            # assume tentative_dirs already aligned to selected
            out['tentative_dirs'] = tentative_dirs
    
    # Pass through true direction if available
    true_dir = vols_data.get('true_direction')
    if true_dir is not None:
        if true_dir.shape[0] == volumes.shape[0]:
            out['true_direction'] = true_dir[selected_idx]
        else:
            out['true_direction'] = true_dir

    out_default = Path(os.environ.get('SNOP_OUTPUT_BASE', 'output')) / 'ed_inference.npz'
    out_path = Path(args.out) if args.out else out_default
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_path, **out)
    print(f'Saved ED inference for selected clusters to {out_path}')


if __name__ == '__main__':
    main()
