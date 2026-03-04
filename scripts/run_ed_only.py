#!/usr/bin/env python3
"""Run ED-only inference (and optional MCMC) from a JSON config."""

import argparse
import glob
import json
import os
import subprocess
import tempfile
from pathlib import Path
import sys
from typing import Optional

import numpy as np


def _load_json_config(path):
    with open(path, "r") as f:
        return json.load(f)


def _resolve_config(args):
    cfg = {}
    if args.config:
        cfg = _load_json_config(args.config)
    ed_cfg = cfg.get("ed_only", cfg)

    output_base = Path(os.environ.get("SNOP_OUTPUT_BASE", "output"))

    defaults = {
        "ed_model": None,
        "volumes_npz": None,
        "selection_npz": None,
        "input_folder": None,
        "input_glob": "*.npz",
        "output_dir": str(output_base / "ed_only"),
        "batch_size": 32,
        "run_mcmc": True,
        "mcmc_steps": 2000,
        "mcmc_proposal_scale": 0.08,
        "generate_report": True,
        "report_pdf": None,
    }

    resolved = {}
    for key, default_val in defaults.items():
        cli_val = getattr(args, key)
        cfg_val = ed_cfg.get(key)
        resolved[key] = cli_val if cli_val is not None else (cfg_val if cfg_val is not None else default_val)

    required = ["ed_model"]
    missing = [k for k in required if not resolved.get(k)]
    if missing:
        raise ValueError(f"Missing required ED config keys: {', '.join(missing)}")

    if not resolved.get("volumes_npz") and not resolved.get("input_folder"):
        raise ValueError("Provide either volumes_npz (single file) or input_folder (folder mode)")

    return resolved


def _resolve_input_files(cfg):
    single = cfg.get("volumes_npz")
    if single:
        single_path = Path(single).resolve()
        if not single_path.is_file():
            raise FileNotFoundError(f"volumes_npz not found: {single_path}")
        return [single_path], True

    input_folder = Path(cfg["input_folder"]).resolve()
    if not input_folder.is_dir():
        raise NotADirectoryError(f"input_folder not found: {input_folder}")

    pattern = str(input_folder / cfg.get("input_glob", "*.npz"))
    files = sorted(Path(p).resolve() for p in glob.glob(pattern))
    files = [p for p in files if p.is_file()]
    if not files:
        raise FileNotFoundError(f"No NPZ files matched: {pattern}")

    valid_inputs = []
    for path in files:
        try:
            payload = np.load(path, allow_pickle=True)
            if "volumes" in payload or "images" in payload:
                valid_inputs.append(path)
        except Exception:
            continue

    if not valid_inputs:
        raise FileNotFoundError(f"No ED input NPZ files with `volumes`/`images` matched: {pattern}")

    return valid_inputs, False


def _load_sample_for_selection(npz_path: Path):
    data = np.load(npz_path, allow_pickle=True)

    if "volumes" in data:
        volumes = np.asarray(data["volumes"])
    elif "images" in data:
        volumes = np.asarray(data["images"])
    else:
        raise KeyError(f"{npz_path} must contain `volumes` or `images`")

    if volumes.ndim < 3:
        raise ValueError(f"{npz_path} has invalid volume/image shape: {volumes.shape}")

    n_entries = int(volumes.shape[0])
    tentative_dirs = None

    if "tentative_dirs" in data:
        tentative_dirs = np.asarray(data["tentative_dirs"])
    elif "metadata" in data:
        metadata = data["metadata"]
        if hasattr(metadata, "dtype") and metadata.dtype.names:
            names = metadata.dtype.names
            needed = ("main_track_momentum_x", "main_track_momentum_y", "main_track_momentum_z")
            if all(name in names for name in needed):
                momentum = np.stack([
                    np.asarray(metadata["main_track_momentum_x"], dtype=np.float32),
                    np.asarray(metadata["main_track_momentum_y"], dtype=np.float32),
                    np.asarray(metadata["main_track_momentum_z"], dtype=np.float32),
                ], axis=1)
                norms = np.linalg.norm(momentum, axis=1, keepdims=True)
                norms[norms == 0] = 1.0
                tentative_dirs = momentum / norms
    elif "true_direction" in data:
        true_direction = np.asarray(data["true_direction"])
        if true_direction.shape[0] == n_entries and true_direction.shape[1] == 3:
            tentative_dirs = true_direction

    if tentative_dirs is not None and tentative_dirs.shape[0] != n_entries:
        tentative_dirs = None

    return n_entries, tentative_dirs


def _build_selection_npz(npz_path: Path, explicit_selection_npz: Optional[Path]):
    if explicit_selection_npz is not None:
        if not explicit_selection_npz.is_file():
            raise FileNotFoundError(f"selection_npz not found: {explicit_selection_npz}")
        return explicit_selection_npz, True

    n_entries, tentative_dirs = _load_sample_for_selection(npz_path)
    selected_mask = np.ones(n_entries, dtype=bool)

    tmpdir = tempfile.TemporaryDirectory(prefix="ed_unified_")
    selection_path = Path(tmpdir.name) / "selection_mask.npz"
    payload = {"is_selected_cluster": selected_mask}
    if tentative_dirs is not None:
        payload["tentative_dirs"] = tentative_dirs
    np.savez_compressed(selection_path, **payload)
    return selection_path, False, tmpdir


def main():
    parser = argparse.ArgumentParser(description="Run ED-only workflow from JSON config")
    parser.add_argument("-j", "--json", "--config", dest="config", default=None,
                        help="JSON config file (supports top-level keys or ed_only.*)")
    parser.add_argument("--ed-model", dest="ed_model", default=None)
    parser.add_argument("--volumes-npz", dest="volumes_npz", default=None)
    parser.add_argument("--selection-npz", dest="selection_npz", default=None)
    parser.add_argument("--input-folder", dest="input_folder", default=None,
                        help="Folder containing NPZ inputs (used when volumes_npz is not set)")
    parser.add_argument("--input-glob", dest="input_glob", default=None,
                        help="Glob pattern inside input_folder (default: *.npz)")
    parser.add_argument("--output-dir", dest="output_dir", default=None)
    parser.add_argument("--batch-size", dest="batch_size", type=int, default=None)
    parser.add_argument("--run-mcmc", dest="run_mcmc", action="store_true", default=None)
    parser.add_argument("--no-mcmc", dest="run_mcmc", action="store_false")
    parser.add_argument("--mcmc-steps", dest="mcmc_steps", type=int, default=None)
    parser.add_argument("--mcmc-proposal-scale", dest="mcmc_proposal_scale", type=float, default=None)
    parser.add_argument("--report-pdf", dest="report_pdf", default=None)
    parser.add_argument("--generate-report", dest="generate_report", action="store_true", default=None)
    parser.add_argument("--no-generate-report", dest="generate_report", action="store_false")
    args = parser.parse_args()

    cfg = _resolve_config(args)

    repo_root = Path(__file__).resolve().parents[1]
    ed_inference = repo_root / "python" / "app" / "ed_inference.py"
    ed_mcmc = repo_root / "python" / "app" / "ed_mcmc.py"

    output_dir = Path(cfg["output_dir"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    input_files, is_single_mode = _resolve_input_files(cfg)
    print(f"Resolved {len(input_files)} input file(s)")

    python_root = repo_root / "python"
    if str(python_root) not in sys.path:
        sys.path.insert(0, str(python_root))
    from ana.report_generator import generate_ed_only_report

    explicit_selection_npz = Path(cfg["selection_npz"]).resolve() if cfg.get("selection_npz") and is_single_mode else None

    for idx, input_file in enumerate(input_files, start=1):
        sample_name = input_file.stem
        sample_out_dir = output_dir if is_single_mode else (output_dir / sample_name)
        sample_out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[{idx}/{len(input_files)}] ED input: {input_file}")

        selection_info = _build_selection_npz(input_file, explicit_selection_npz)
        if len(selection_info) == 3:
            selection_npz_path, selection_is_explicit, temp_selection_holder = selection_info
        else:
            selection_npz_path, selection_is_explicit = selection_info
            temp_selection_holder = None

        if not selection_is_explicit:
            print("  selection_npz not provided: auto-generated mask from input NPZ")

        ed_out = sample_out_dir / "ed_inference.npz"
        ed_cmd = [
            "python3", str(ed_inference),
            str(cfg["ed_model"]),
            str(input_file),
            str(selection_npz_path),
            "--out", str(ed_out),
            "--batch-size", str(cfg["batch_size"]),
        ]
        subprocess.run(ed_cmd, check=True)

        mcmc_out = sample_out_dir / "ed_mcmc_results.npz"
        run_mcmc = bool(cfg["run_mcmc"])
        if run_mcmc:
            ed_payload = np.load(ed_out, allow_pickle=True)
            if "tentative_dirs" not in ed_payload:
                print("  Skipping MCMC: no tentative_dirs available in ED inference output")
                run_mcmc = False

        if run_mcmc:
            mcmc_cmd = [
                "python3", str(ed_mcmc),
                str(ed_out),
                "--out", str(mcmc_out),
                "--nsteps", str(cfg["mcmc_steps"]),
                "--proposal-scale", str(cfg["mcmc_proposal_scale"]),
            ]
            subprocess.run(mcmc_cmd, check=True)

        if cfg["generate_report"]:
            if args.report_pdf is not None and is_single_mode:
                report_pdf = Path(args.report_pdf).resolve()
            elif args.output_dir is not None or not is_single_mode:
                report_pdf = sample_out_dir / "ed_only_report.pdf"
            elif cfg.get("report_pdf") and is_single_mode:
                report_pdf = Path(cfg["report_pdf"]).resolve()
            else:
                report_pdf = sample_out_dir / "ed_only_report.pdf"

            report_path = generate_ed_only_report(
                ed_inference_npz=ed_out,
                ed_mcmc_npz=mcmc_out if run_mcmc else None,
                output_path=report_pdf,
                verbose=True,
            )
            print(f"  ED-only report: {report_path}")

        if temp_selection_holder is not None:
            temp_selection_holder.cleanup()

    print(f"\nED-only output directory: {output_dir}")


if __name__ == "__main__":
    main()
