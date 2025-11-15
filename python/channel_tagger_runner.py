#!/usr/bin/env python3
"""
Run the channel tagger (CT) model on a set of volumes and save predictions.

Expected input:
 - volumes_npz: a .npz file that contains an array named `volumes`
   with shape (N, ...) matching the CT model input shape.
 - Optionally `y_true` (N,) with ground-truth labels (0/1) to evaluate metrics.

Output: writes a predictions .npz with arrays `y_pred_proba` and (if present) `y_true`.
"""

import argparse
from pathlib import Path
import numpy as np

try:
    import tensorflow as tf
except Exception:
    tf = None


def load_volumes(path):
    data = np.load(path)
    if 'volumes' not in data:
        raise KeyError('Input volumes .npz must contain an array named "volumes"')
    volumes = data['volumes']
    y_true = data.get('y_true')
    return volumes, y_true


def run_inference(model_path, volumes, batch_size=64):
    if tf is None:
        raise RuntimeError('TensorFlow not available in this environment')
    model = tf.keras.models.load_model(model_path)
    # Predict probabilities
    preds = model.predict(volumes, batch_size=batch_size)
    # If model returns logits or shape (N,1) try to squeeze
    preds = np.asarray(preds)
    if preds.ndim > 1 and preds.shape[1] == 1:
        preds = preds.squeeze(axis=1)
    return preds


def main():
    p = argparse.ArgumentParser()
    p.add_argument('model', help='Path to CT Keras model (SavedModel or .h5)')
    p.add_argument('volumes_npz', help='.npz file containing `volumes` array')
    p.add_argument('--out', default='results/ct_predictions.npz', help='Output .npz to write predictions')
    p.add_argument('--batch-size', type=int, default=64)
    args = p.parse_args()

    volumes, y_true = load_volumes(args.volumes_npz)
    print(f'Loaded volumes: shape={volumes.shape}')

    preds = run_inference(args.model, volumes, batch_size=args.batch_size)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    save_dict = {'y_pred_proba': preds}
    if y_true is not None:
        save_dict['y_true'] = y_true

    np.savez_compressed(out_path, **save_dict)
    print(f'Saved predictions to {out_path} (N={len(preds)})')


if __name__ == '__main__':
    main()
