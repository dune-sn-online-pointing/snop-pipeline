#!/usr/bin/env python3
"""
Batch ED runner for NPZ samples.

Runs ED inference directly on a folder/glob of NPZ files in one command,
without requiring prior CT pipeline artifacts.

Supported NPZ input layouts:
- `volumes` (preferred) or `images`: array with shape (N, ...)
- optional `cluster_energy`: array (N,)
- optional `true_direction`: array (N, 3)
- optional `metadata`: structured array used to derive tentative directions from
  fields `main_track_momentum_x/y/z` if present
- optional `tentative_dirs`: array (N,3)
"""

import argparse
import subprocess
from pathlib import Path
import tempfile
import glob
import numpy as np


def _resolve_inputs(input_glob: str):
    files = sorted(Path(p).resolve() for p in glob.glob(input_glob))
    if not files:
        raise FileNotFoundError(f"No files matched input glob: {input_glob}")
    return [f for f in files if f.is_file()]


def _load_sample(npz_path: Path):
    data = np.load(npz_path, allow_pickle=True)

    if 'volumes' in data:
        volumes = np.asarray(data['volumes'])
    elif 'images' in data:
        volumes = np.asarray(data['images'])
    else:
        raise KeyError(f"{npz_path} must contain `volumes` or `images`")

    if volumes.ndim < 3:
        raise ValueError(f"{npz_path} has invalid volume/image shape: {volumes.shape}")

    n_entries = volumes.shape[0]
    energies = np.asarray(data['cluster_energy']) if 'cluster_energy' in data else None
    true_direction = np.asarray(data['true_direction']) if 'true_direction' in data else None

    tentative_dirs = None
    if 'tentative_dirs' in data:
        tentative_dirs = np.asarray(data['tentative_dirs'])
    elif 'metadata' in data:
        metadata = data['metadata']
        if hasattr(metadata, 'dtype') and metadata.dtype.names:
            names = metadata.dtype.names
            needed = ('main_track_momentum_x', 'main_track_momentum_y', 'main_track_momentum_z')
            if all(name in names for name in needed):
                momentum = np.stack([
                    np.asarray(metadata['main_track_momentum_x'], dtype=np.float32),
                    np.asarray(metadata['main_track_momentum_y'], dtype=np.float32),
                    np.asarray(metadata['main_track_momentum_z'], dtype=np.float32),
                ], axis=1)
                norms = np.linalg.norm(momentum, axis=1, keepdims=True)
                norms[norms == 0] = 1.0
                tentative_dirs = momentum / norms

    if energies is not None and len(energies) != n_entries:
        energies = None

    if true_direction is not None and true_direction.shape[0] != n_entries:
        true_direction = None

    if tentative_dirs is not None and tentative_dirs.shape[0] != n_entries:
        tentative_dirs = None

    return volumes, energies, true_direction, tentative_dirs


def main():
    parser = argparse.ArgumentParser(description='Run ED inference in batch on NPZ files')
    parser.add_argument('ed_model', help='Path to ED Keras model')
    parser.add_argument('--input-glob', required=True,
                        help='Glob for NPZ inputs (e.g. "output/my_samples/*.npz")')
    parser.add_argument('--output-dir', default='output/ed_batch',
                        help='Directory where per-file ED outputs are written')
    parser.add_argument('--batch-size', type=int, default=32,
                        help='Batch size passed to ED inference')
    parser.add_argument('--run-mcmc', action='store_true',
                        help='Run ED MCMC after each ED inference output')
    parser.add_argument('--mcmc-steps', type=int, default=2000,
                        help='MCMC steps if --run-mcmc is enabled')
    parser.add_argument('--mcmc-proposal-scale', type=float, default=0.08,
                        help='MCMC proposal scale if --run-mcmc is enabled')
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    ed_inference_script = repo_root / 'python' / 'app' / 'ed_inference.py'
    ed_mcmc_script = repo_root / 'python' / 'app' / 'ed_mcmc.py'

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    npz_files = _resolve_inputs(args.input_glob)
    print(f"Found {len(npz_files)} NPZ files")

    for idx, input_npz in enumerate(npz_files, start=1):
        stem = input_npz.stem
        sample_out_dir = output_dir / stem
        sample_out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[{idx}/{len(npz_files)}] Processing: {input_npz}")

        volumes, energies, true_direction, tentative_dirs = _load_sample(input_npz)
        n_entries = volumes.shape[0]
        selected_mask = np.ones(n_entries, dtype=bool)

        with tempfile.TemporaryDirectory(prefix='ed_batch_') as tmpdir:
            tmpdir_path = Path(tmpdir)
            volumes_npz = tmpdir_path / 'volumes_for_ed.npz'
            selection_npz = tmpdir_path / 'selection_mask.npz'

            vol_payload = {'volumes': volumes}
            if energies is not None:
                vol_payload['cluster_energy'] = energies
            if true_direction is not None:
                vol_payload['true_direction'] = true_direction
            np.savez_compressed(volumes_npz, **vol_payload)

            sel_payload = {'is_selected_cluster': selected_mask}
            if tentative_dirs is not None:
                sel_payload['tentative_dirs'] = tentative_dirs
            np.savez_compressed(selection_npz, **sel_payload)

            ed_out = sample_out_dir / 'ed_inference.npz'
            ed_cmd = [
                'python3', str(ed_inference_script),
                str(args.ed_model),
                str(volumes_npz),
                str(selection_npz),
                '--out', str(ed_out),
                '--batch-size', str(args.batch_size),
            ]
            subprocess.run(ed_cmd, check=True)

            if args.run_mcmc:
                if tentative_dirs is None:
                    print('  Skipping MCMC (no tentative_dirs available in this input)')
                else:
                    mcmc_out = sample_out_dir / 'ed_mcmc_results.npz'
                    mcmc_cmd = [
                        'python3', str(ed_mcmc_script),
                        str(ed_out),
                        '--out', str(mcmc_out),
                        '--nsteps', str(args.mcmc_steps),
                        '--proposal-scale', str(args.mcmc_proposal_scale),
                    ]
                    subprocess.run(mcmc_cmd, check=True)

    print(f"\nBatch ED complete. Outputs in: {output_dir}")


if __name__ == '__main__':
    main()
