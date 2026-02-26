#!/usr/bin/env python3
"""Run ED-only inference (and optional MCMC) from a JSON config."""

import argparse
import json
import os
import subprocess
from pathlib import Path


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
        "output_dir": str(output_base / "ed_only"),
        "batch_size": 32,
        "run_mcmc": True,
        "mcmc_steps": 2000,
        "mcmc_proposal_scale": 0.08,
    }

    resolved = {}
    for key, default_val in defaults.items():
        cli_val = getattr(args, key)
        cfg_val = ed_cfg.get(key)
        resolved[key] = cli_val if cli_val is not None else (cfg_val if cfg_val is not None else default_val)

    required = ["ed_model", "volumes_npz", "selection_npz"]
    missing = [k for k in required if not resolved.get(k)]
    if missing:
        raise ValueError(f"Missing required ED config keys: {', '.join(missing)}")

    return resolved


def main():
    parser = argparse.ArgumentParser(description="Run ED-only workflow from JSON config")
    parser.add_argument("-j", "--json", "--config", dest="config", default=None,
                        help="JSON config file (supports top-level keys or ed_only.*)")
    parser.add_argument("--ed-model", dest="ed_model", default=None)
    parser.add_argument("--volumes-npz", dest="volumes_npz", default=None)
    parser.add_argument("--selection-npz", dest="selection_npz", default=None)
    parser.add_argument("--output-dir", dest="output_dir", default=None)
    parser.add_argument("--batch-size", dest="batch_size", type=int, default=None)
    parser.add_argument("--run-mcmc", dest="run_mcmc", action="store_true", default=None)
    parser.add_argument("--mcmc-steps", dest="mcmc_steps", type=int, default=None)
    parser.add_argument("--mcmc-proposal-scale", dest="mcmc_proposal_scale", type=float, default=None)
    args = parser.parse_args()

    cfg = _resolve_config(args)

    repo_root = Path(__file__).resolve().parents[1]
    ed_inference = repo_root / "python" / "app" / "ed_inference.py"
    ed_mcmc = repo_root / "python" / "app" / "ed_mcmc.py"

    output_dir = Path(cfg["output_dir"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    ed_out = output_dir / "ed_inference.npz"
    ed_cmd = [
        "python3", str(ed_inference),
        str(cfg["ed_model"]),
        str(cfg["volumes_npz"]),
        str(cfg["selection_npz"]),
        "--out", str(ed_out),
        "--batch-size", str(cfg["batch_size"]),
    ]
    subprocess.run(ed_cmd, check=True)

    if cfg["run_mcmc"]:
        mcmc_out = output_dir / "ed_mcmc_results.npz"
        mcmc_cmd = [
            "python3", str(ed_mcmc),
            str(ed_out),
            "--out", str(mcmc_out),
            "--nsteps", str(cfg["mcmc_steps"]),
            "--proposal-scale", str(cfg["mcmc_proposal_scale"]),
        ]
        subprocess.run(mcmc_cmd, check=True)

    print(f"ED-only output directory: {output_dir}")


if __name__ == "__main__":
    main()
