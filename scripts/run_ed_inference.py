#!/usr/bin/env python3
"""
Run ED model inference from cluster-image NPZ files.

Expected JSON schema (example):
{
  "ed_inference": {
    "cluster_images_dir": "/path/to/cluster_images",
    "ed_model": "/path/to/model.keras",
    "output_dir": "output/ed_inference",
    "batch_size": 512,
    "input_order": "XUV",
    "match_by_match_id": true,
    "filter_es_interaction": false,
    "filter_main_track": false,
    "generate_report": false,
    "report_title": "ED Inference Report"
  }
}

Top-level keys are also accepted as a fallback.
Output NPZ (ed_predictions.npz) placed in output_dir includes:
  - predicted_directions: (N, 3)
  - true_directions: (N, 3) from metadata momentum (cols 7:10)
  - true_energy: (N,) from metadata (prefers col 11)
  - x_deposited_charge: (N,) ADC sum from X image
  - u_total_adc, v_total_adc, x_total_adc: (N,) per-plane ADC sums
  - u_peak_adc, v_peak_adc, x_peak_adc: (N,) per-plane peak ADC
  - total_adc_all: (N,) sum of U+V+X ADC
  - peak_adc_all: (N,) max peak ADC across U,V,X
  - metadata_x: original X metadata
"""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

import numpy as np
import tensorflow as tf


def _require_init_done():
    if os.environ.get("INIT_DONE", "").lower() != "true":
        raise RuntimeError("Environment not initialized. Run: source scripts/init.sh")


def _load_json_config(path):
    with open(path, "r") as f:
        return json.load(f)


def _resolve_config(args):
    cfg = {}
    if args.config:
        cfg = _load_json_config(args.config)
    ed_cfg = cfg.get("ed_inference", cfg)

    output_base = Path(os.environ.get("SNOP_OUTPUT_BASE", "output"))

    defaults = {
        "cluster_images_dir": None,
        "ed_model": None,
        "output_dir": str(output_base / "ed_inference"),
        "batch_size": 512,
        "input_order": None,
        "match_by_match_id": True,
        "filter_es_interaction": False,
        "filter_main_track": False,
        "generate_report": False,
        "report_title": "ED Inference Report",
    }

    resolved = {}
    for key, default_val in defaults.items():
        cli_val = getattr(args, key, None)
        cfg_val = ed_cfg.get(key)
        resolved[key] = cli_val if cli_val is not None else (cfg_val if cfg_val is not None else default_val)

    missing = [k for k in ("cluster_images_dir", "ed_model") if not resolved.get(k)]
    if missing:
        raise ValueError(f"Missing required ed_inference config keys: {', '.join(missing)}")

    return resolved


def _as_float(value, default=np.nan):
    try:
        return float(value)
    except Exception:
        return float(default)


def _meta_get(meta, key=None, idx=None, default=np.nan):
    if isinstance(meta, dict):
        if key is None:
            return default
        return meta.get(key, default)

    if idx is None:
        return default

    try:
        return meta[idx]
    except Exception:
        return default


def _extract_true_direction(meta):
    # Cluster-image metadata convention uses cols 7:10 (true_mom_x/y/z).
    # Keep legacy dict keys for compatibility.
    px = _meta_get(meta, key="true_mom_x", idx=7, default=np.nan)
    if not np.isfinite(_as_float(px)):
        px = _meta_get(meta, key="main_track_momentum_x", idx=7, default=np.nan)
    py = _meta_get(meta, key="true_mom_y", idx=8, default=np.nan)
    if not np.isfinite(_as_float(py)):
        py = _meta_get(meta, key="main_track_momentum_y", idx=8, default=np.nan)
    pz = _meta_get(meta, key="true_mom_z", idx=9, default=np.nan)
    if not np.isfinite(_as_float(pz)):
        pz = _meta_get(meta, key="main_track_momentum_z", idx=9, default=np.nan)

    vec = np.array([_as_float(px), _as_float(py), _as_float(pz)], dtype=np.float32)
    norm = float(np.linalg.norm(vec))
    if not np.isfinite(norm) or norm < 1e-8:
        return np.array([np.nan, np.nan, np.nan], dtype=np.float32)
    return vec / norm


def _extract_true_energy(meta):
    if isinstance(meta, dict):
        for key in ("true_particle_energy", "particle_energy", "cluster_energy"):
            if key in meta:
                return _as_float(meta[key])
        return np.nan

    e11 = _as_float(_meta_get(meta, idx=11, default=np.nan))
    if np.isfinite(e11):
        return e11
    return _as_float(_meta_get(meta, idx=10, default=np.nan))


def _extract_x_charge(x_image):
    return float(np.sum(np.asarray(x_image, dtype=np.float32)))


def _plane_total_adc(img):
    return float(np.sum(np.asarray(img, dtype=np.float32)))


def _plane_peak_adc(img):
    arr = np.asarray(img, dtype=np.float32)
    if arr.size == 0:
        return float("nan")
    return float(np.max(arr))


def _parse_input_order(value):
    if value is None:
        return ("X", "U", "V")
    s = str(value).upper().replace(",", "").replace(" ", "")
    if len(s) != 3 or set(s) != {"X", "U", "V"}:
        raise ValueError(
            f"Invalid input_order='{value}'. Use a permutation of XUV (e.g. XUV, UVX)."
        )
    return tuple(s)


def _infer_input_order_from_model(model):
    """
    Infer plane input order from model input tensor names.
    Falls back to UVX if names are ambiguous.
    """
    inferred = []
    for t in model.inputs:
        name = str(getattr(t, "name", "")).lower()
        tokens = [tok for tok in re.split(r"[^a-z0-9]+", name) if tok]
        plane = None
        for tok in tokens:
            if tok in {"u", "v", "x"}:
                plane = tok.upper()
                break
        if plane is None:
            for p in ("u", "v", "x"):
                if f"plane_{p}" in name or f"{p}_input" in name:
                    plane = p.upper()
                    break
        if plane is None:
            return ("U", "V", "X")
        inferred.append(plane)

    if len(inferred) == 3 and set(inferred) == {"U", "V", "X"}:
        return tuple(inferred)
    return ("U", "V", "X")


def _row_index_by_match_id(metadata):
    if not isinstance(metadata, np.ndarray) or metadata.ndim != 2 or metadata.shape[1] <= 13:
        return None
    out = {}
    for i, mid in enumerate(metadata[:, 13]):
        try:
            m = int(mid)
        except Exception:
            continue
        if m < 0:
            continue
        # Keep first occurrence to preserve deterministic order.
        if m not in out:
            out[m] = i
    return out


def _build_filter_mask(metadata_x, filter_es_interaction=False, filter_main_track=False):
    n = len(metadata_x)
    mask = np.ones(n, dtype=bool)
    if not isinstance(metadata_x, np.ndarray) or metadata_x.ndim != 2:
        return mask

    if filter_es_interaction and metadata_x.shape[1] > 3:
        mask &= metadata_x[:, 3].astype(np.float32) > 0.5
    if filter_main_track and metadata_x.shape[1] > 2:
        mask &= metadata_x[:, 2].astype(np.float32) > 0.5
    return mask


def _iter_triplets(
    input_dir: Path,
    match_by_match_id=True,
    filter_es_interaction=False,
    filter_main_track=False,
):
    x_dir = input_dir / "X"
    u_dir = input_dir / "U"
    v_dir = input_dir / "V"

    for d in (u_dir, v_dir, x_dir):
        if not d.exists():
            raise FileNotFoundError(f"Missing directory: {d}")

    x_files = sorted(x_dir.glob("*_planeX.npz"))
    if not x_files:
        raise FileNotFoundError(f"No *_planeX.npz files found in {x_dir}")

    found = False

    for x_file in x_files:
        base = x_file.name[:-11]  # remove "_planeX.npz"
        u_file = u_dir / f"{base}_planeU.npz"
        v_file = v_dir / f"{base}_planeV.npz"
        if not u_file.exists() or not v_file.exists():
            continue

        xd = np.load(x_file, allow_pickle=True)
        ud = np.load(u_file, allow_pickle=True)
        vd = np.load(v_file, allow_pickle=True)

        if "images" not in xd or "images" not in ud or "images" not in vd:
            continue

        x_images = np.asarray(xd["images"])
        u_images = np.asarray(ud["images"])
        v_images = np.asarray(vd["images"])

        meta_x = np.asarray(xd["metadata"]) if "metadata" in xd else None
        meta_u = np.asarray(ud["metadata"]) if "metadata" in ud else None
        meta_v = np.asarray(vd["metadata"]) if "metadata" in vd else None

        aligned = False
        if match_by_match_id and meta_x is not None and meta_u is not None and meta_v is not None:
            ix = _row_index_by_match_id(meta_x)
            iu = _row_index_by_match_id(meta_u)
            iv = _row_index_by_match_id(meta_v)
            if ix and iu and iv:
                common_ids = sorted(set(ix) & set(iu) & set(iv))
                if common_ids:
                    x_sel = np.array([ix[mid] for mid in common_ids], dtype=int)
                    u_sel = np.array([iu[mid] for mid in common_ids], dtype=int)
                    v_sel = np.array([iv[mid] for mid in common_ids], dtype=int)
                    x_images = x_images[x_sel]
                    u_images = u_images[u_sel]
                    v_images = v_images[v_sel]
                    meta_x = meta_x[x_sel]
                    aligned = True

        if not aligned:
            n = min(len(x_images), len(u_images), len(v_images))
            if n <= 0:
                continue
            x_images = x_images[:n]
            u_images = u_images[:n]
            v_images = v_images[:n]
            if meta_x is not None:
                meta_x = meta_x[:n]
            else:
                meta_x = np.array([{} for _ in range(n)], dtype=object)

        mask = _build_filter_mask(
            meta_x,
            filter_es_interaction=filter_es_interaction,
            filter_main_track=filter_main_track,
        )
        if not np.any(mask):
            continue

        found = True
        yield u_images[mask], v_images[mask], x_images[mask], meta_x[mask]

    if not found:
        raise RuntimeError("No matched U/V/X samples found.")


def _ensure_channel_dim(arr):
    if arr.ndim == 3:
        return arr[..., np.newaxis]
    return arr


def _to_predicted_directions(pred):
    if isinstance(pred, dict):
        pred = next(iter(pred.values()))
    if isinstance(pred, (list, tuple)):
        pred = pred[0]

    arr = np.asarray(pred, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    if arr.ndim > 2:
        arr = arr.reshape(arr.shape[0], -1)

    if arr.shape[1] == 3:
        dirs = arr
    elif arr.shape[1] == 2:
        theta = arr[:, 0]
        phi = arr[:, 1]
        dirs = np.column_stack(
            [
                np.sin(theta) * np.cos(phi),
                np.sin(theta) * np.sin(phi),
                np.cos(theta),
            ]
        ).astype(np.float32)
    else:
        raise ValueError(
            f"Unsupported ED model output shape {arr.shape}. "
            "Expected (N,3) (xyz) or (N,2) (theta,phi)."
        )

    norms = np.linalg.norm(dirs, axis=1, keepdims=True) + 1e-8
    return dirs / norms


def run_inference(cfg: dict, output_npz: Path):
    input_dir = Path(cfg["cluster_images_dir"])
    model_path = Path(cfg["ed_model"])
    batch_size = int(cfg["batch_size"])
    input_order_cfg = cfg.get("input_order")
    match_by_match_id = bool(cfg["match_by_match_id"])
    filter_es_interaction = bool(cfg["filter_es_interaction"])
    filter_main_track = bool(cfg["filter_main_track"])

    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    print(f"Preparing streaming inference from: {input_dir}")
    print(f"Loading model: {model_path}")
    model = tf.keras.models.load_model(model_path, compile=False)

    if input_order_cfg is None:
        input_order = _infer_input_order_from_model(model)
        print(
            "No input_order in JSON; inferred from model inputs: "
            f"{''.join(input_order)}"
        )
    else:
        input_order = _parse_input_order(input_order_cfg)
        print(f"Using input_order from JSON: {''.join(input_order)}")

    predicted_dirs_chunks = []
    true_dirs_list = []
    true_energy_list = []
    x_charge_list = []
    u_total_adc_list = []
    v_total_adc_list = []
    x_total_adc_list = []
    u_peak_adc_list = []
    v_peak_adc_list = []
    x_peak_adc_list = []
    metadata_x_list = []
    total_samples = 0

    print(
        "Running inference in streaming mode "
        f"(input_order={''.join(input_order)}, match_by_match_id={match_by_match_id}, "
        f"filter_es_interaction={filter_es_interaction}, filter_main_track={filter_main_track})..."
    )
    for u_images, v_images, x_images, metadata_x in _iter_triplets(
        input_dir,
        match_by_match_id=match_by_match_id,
        filter_es_interaction=filter_es_interaction,
        filter_main_track=filter_main_track,
    ):
        n_chunk = len(x_images)
        u_images = _ensure_channel_dim(np.asarray(u_images, dtype=np.float32))
        v_images = _ensure_channel_dim(np.asarray(v_images, dtype=np.float32))
        x_images = _ensure_channel_dim(np.asarray(x_images, dtype=np.float32))

        for i0 in range(0, n_chunk, batch_size):
            i1 = min(i0 + batch_size, n_chunk)
            u_b = u_images[i0:i1]
            v_b = v_images[i0:i1]
            x_b = x_images[i0:i1]
            m_b = metadata_x[i0:i1]

            plane_batches = {"U": u_b, "V": v_b, "X": x_b}
            model_inputs = [plane_batches[k] for k in input_order]
            pred_raw = model.predict(model_inputs, batch_size=len(u_b), verbose=0)
            pred_dirs = _to_predicted_directions(pred_raw)
            predicted_dirs_chunks.append(pred_dirs)

            for m, u_img, v_img, x_img in zip(m_b, u_b, v_b, x_b):
                true_dirs_list.append(_extract_true_direction(m))
                true_energy_list.append(_extract_true_energy(m))
                x_charge = _extract_x_charge(x_img)
                x_charge_list.append(x_charge)

                u_total = _plane_total_adc(u_img)
                v_total = _plane_total_adc(v_img)
                x_total = _plane_total_adc(x_img)
                u_peak = _plane_peak_adc(u_img)
                v_peak = _plane_peak_adc(v_img)
                x_peak = _plane_peak_adc(x_img)

                u_total_adc_list.append(u_total)
                v_total_adc_list.append(v_total)
                x_total_adc_list.append(x_total)
                u_peak_adc_list.append(u_peak)
                v_peak_adc_list.append(v_peak)
                x_peak_adc_list.append(x_peak)
                metadata_x_list.append(m)

            total_samples += (i1 - i0)
            if total_samples % (10 * batch_size) == 0:
                print(f"Processed {total_samples} samples")

    if not predicted_dirs_chunks:
        raise RuntimeError("No samples were processed.")

    predicted_dirs = np.concatenate(predicted_dirs_chunks, axis=0)
    true_dirs = np.asarray(true_dirs_list, dtype=np.float32)
    true_energy = np.asarray(true_energy_list, dtype=np.float32)
    x_charge = np.asarray(x_charge_list, dtype=np.float32)
    u_total_adc = np.asarray(u_total_adc_list, dtype=np.float32)
    v_total_adc = np.asarray(v_total_adc_list, dtype=np.float32)
    x_total_adc = np.asarray(x_total_adc_list, dtype=np.float32)
    u_peak_adc = np.asarray(u_peak_adc_list, dtype=np.float32)
    v_peak_adc = np.asarray(v_peak_adc_list, dtype=np.float32)
    x_peak_adc = np.asarray(x_peak_adc_list, dtype=np.float32)
    total_adc_all = u_total_adc + v_total_adc + x_total_adc
    peak_adc_all = np.maximum(np.maximum(u_peak_adc, v_peak_adc), x_peak_adc)
    metadata_x = np.asarray(metadata_x_list, dtype=object)

    output_npz.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        output_npz,
        predicted_directions=predicted_dirs,
        true_directions=true_dirs,
        true_energy=true_energy,
        x_deposited_charge=x_charge,
        u_total_adc=u_total_adc,
        v_total_adc=v_total_adc,
        x_total_adc=x_total_adc,
        u_peak_adc=u_peak_adc,
        v_peak_adc=v_peak_adc,
        x_peak_adc=x_peak_adc,
        total_adc_all=total_adc_all,
        peak_adc_all=peak_adc_all,
        metadata_x=metadata_x,
    )
    print(f"Saved predictions to: {output_npz}")


def main():
    _require_init_done()

    parser = argparse.ArgumentParser(description="Run ED model inference from cluster-image NPZ files")
    parser.add_argument("-j", "--json", "--config", dest="config", default=None,
                        help="JSON config file (supports top-level keys or ed_inference.*)")
    parser.add_argument("--cluster-images-dir", dest="cluster_images_dir", default=None)
    parser.add_argument("--ed-model", dest="ed_model", default=None)
    parser.add_argument("--output-dir", dest="output_dir", default=None)
    parser.add_argument("--batch-size", dest="batch_size", type=int, default=None)
    parser.add_argument("--input-order", dest="input_order", default=None)
    parser.add_argument("--match-by-match-id", dest="match_by_match_id", action="store_true", default=None)
    parser.add_argument("--no-match-by-match-id", dest="match_by_match_id", action="store_false")
    parser.add_argument("--filter-es-interaction", dest="filter_es_interaction", action="store_true", default=None)
    parser.add_argument("--filter-main-track", dest="filter_main_track", action="store_true", default=None)
    parser.add_argument("--generate-report", dest="generate_report", action="store_true", default=None)
    parser.add_argument("--no-generate-report", dest="generate_report", action="store_false")
    parser.add_argument("--report-title", dest="report_title", default=None)
    args = parser.parse_args()

    cfg = _resolve_config(args)

    output_dir = Path(cfg["output_dir"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_npz = output_dir / "ed_predictions.npz"

    run_inference(cfg, output_npz)

    if cfg["generate_report"]:
        analyze_script = Path(__file__).resolve().parent / "analyze_ed_inference.py"
        report_cmd = [
            "python3", str(analyze_script),
            "--input-npz", str(output_npz),
            "--title", str(cfg["report_title"]),
        ]
        if args.config:
            report_cmd += ["-j", args.config]
        subprocess.run(report_cmd, check=True)

    print(f"\nED inference output directory: {output_dir}")


if __name__ == "__main__":
    main()
