#!/usr/bin/env python3
"""
Build the CC cosine-energy pdf table, pdf_CC(cos | E), for the mixture-ct scenario.

Same construction as data/cosine_energy_pdf.npz (ES, from
submodules/ml-pointing-tools/electron_direction/ana/comprehensive_ed_analysis.py::generate_cosine_energy_pdf):
  - clusters: three-plane-matched MAIN-TRACK clusters, selected exactly as
    python/lib/sample_loader.py does (match_id across X/U/V, is_main_track == 1)
  - directions: ED model (v58) run through python/app/ed_inference.py (identical preprocessing)
  - cos = reco electron direction . true NEUTRINO momentum direction (metadata cols 15:18)
  - energy axis = reconstructed cluster energy (metadata col 10), same binning as the ES table
  - raw histogram per energy bin, normalised to unit integral over cos in [-1, 1]

Extra keys stored for reference: the same histogram vs the true electron direction
(ED resolution only) and vs true particle energy.

Usage (heavy; run on condor):
  python3 python/ana/build_cc_cosine_pdf.py --cluster-folder <folder with X/U/V> \
      --ed-model <keras> --reference-pdf data/cosine_energy_pdf.npz \
      --work-dir <scratch on EOS> --out <npz> --png <png> --events-out <npz>
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

python_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(python_root))
sys.path.insert(0, str(python_root / "lib"))

from sample_loader import _load_samples_from_folder  # noqa: E402


def _normalize_rows(v):
    v = np.asarray(v, dtype=np.float64)
    n = np.linalg.norm(v, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return v / n


def build_table(cos, energies, energy_bins, n_cos_bins=100):
    edges = np.linspace(-1.0, 1.0, n_cos_bins + 1)
    centers = 0.5 * (edges[:-1] + edges[1:])
    width = edges[1] - edges[0]
    pdf = np.zeros((len(energy_bins), n_cos_bins))
    n_per_bin = []
    for i, (e_min, e_max) in enumerate(energy_bins):
        m = (energies >= e_min) & (energies < e_max)
        n_per_bin.append(int(m.sum()))
        if m.sum() > 0:
            counts, _ = np.histogram(cos[m], bins=edges)
            pdf[i] = counts / (counts.sum() * width)
    return pdf, edges, centers, np.asarray(n_per_bin)


def shape_summary(pdf, centers, energy_bins, n_per_bin, label):
    width = centers[1] - centers[0]
    lines = [f"--- {label}: per-energy-bin shape (density integrates to 1 over cos in [-1,1]; flat = 0.5) ---",
             f"{'E bin [MeV]':>12} {'N':>7} {'<cos>':>7} {'P(cos>0)':>9} {'max/min':>8} {'KL(pdf||flat)':>13} {'pdf(cos>0.9)':>12}"]
    for i, (e0, e1) in enumerate(energy_bins):
        row = pdf[i]
        if n_per_bin[i] == 0:
            lines.append(f"{f'{e0:.0f}-{e1:.0f}':>12} {0:>7}")
            continue
        mean_cos = float(np.sum(row * centers) * width)
        fwd = float(np.sum(row[centers > 0]) * width)
        pos = row[row > 0]
        ratio = float(pos.max() / pos.min()) if pos.size else float("nan")
        kl = float(np.sum(pos * np.log(pos / 0.5)) * width)
        hi = float(np.mean(row[centers > 0.9]))
        lines.append(f"{f'{e0:.0f}-{e1:.0f}':>12} {n_per_bin[i]:>7d} {mean_cos:>7.3f} {fwd:>9.3f} {ratio:>8.2f} {kl:>13.4f} {hi:>12.3f}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cluster-folder", default=None, help="folder with X/U/V subfolders of matched cluster images")
    ap.add_argument("--cluster-folders-glob", default=None,
                    help="glob matching several such folders (e.g. ES images of many burst cats); used instead of --cluster-folder")
    ap.add_argument("--file-pattern", default="*_matched_planeX.npz")
    ap.add_argument("--sample-type", default="CC", help="label used in logs / stored in the output (CC or ES)")
    ap.add_argument("--ed-model", required=True)
    ap.add_argument("--reference-pdf", required=True, help="ES table whose energy binning is reused")
    ap.add_argument("--work-dir", required=True, help="scratch dir for the temporary volumes npz (EOS)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--png", default=None)
    ap.add_argument("--events-out", default=None, help="per-cluster arrays (reco dir, truth, energies)")
    ap.add_argument("--max-events", type=int, default=10**9)
    ap.add_argument("--batch-size", type=int, default=64)
    args = ap.parse_args()

    t0 = time.time()
    ref = np.load(args.reference_pdf, allow_pickle=True)
    energy_bins = [tuple(map(float, b)) for b in np.asarray(ref["energy_bins"])]
    n_cos_bins = int(np.asarray(ref["cosine_bin_centers"]).shape[0])
    print(f"reference binning: {len(energy_bins)} energy bins, {n_cos_bins} cos bins")

    import glob as _glob
    if args.cluster_folders_glob:
        folders = sorted(_glob.glob(args.cluster_folders_glob))
    elif args.cluster_folder:
        folders = [args.cluster_folder]
    else:
        raise SystemExit("give --cluster-folder or --cluster-folders-glob")
    print(f"{len(folders)} cluster folder(s)")
    parts = []
    n_files = 0
    for folder in folders:
        try:
            part = _load_samples_from_folder(
                folder, args.max_events, args.file_pattern,
                sample_type=args.sample_type, verbose=(len(folders) == 1), load_all_planes=True, vol_folder=None,
            )
        except Exception as exc:  # a cat without matching files must not kill the whole build
            print(f"  skip {folder}: {exc}")
            continue
        if part["n_clusters"] == 0:
            continue
        parts.append(part)
        n_files += len(part["files_used"])
    if not parts:
        raise SystemExit("no clusters loaded")
    loaded = {
        "images": {k: np.concatenate([q["images"][k] for q in parts], axis=0) for k in ("X", "U", "V")},
        "metadata": np.concatenate([q["metadata"] for q in parts], axis=0),
        "files_used": [f for q in parts for f in q["files_used"]],
        "n_events": sum(q["n_events"] for q in parts),
    }
    del parts
    md = np.asarray(loaded["metadata"], dtype=np.float64)
    n = md.shape[0]
    print(f"loaded {n} three-plane-matched main-track clusters from {n_files} files "
          f"in {len(folders)} folder(s) in {time.time() - t0:.0f}s")
    if n == 0:
        raise SystemExit("no clusters loaded")
    print(f"  is_es values: {np.unique(md[:, 3])}, main-track: {np.unique(md[:, 2])}")

    work = Path(args.work_dir)
    work.mkdir(parents=True, exist_ok=True)
    volumes_npz = work / "cc_volumes_tmp.npz"
    selection_npz = work / "cc_selection_tmp.npz"
    ed_npz = work / "cc_ed_inference.npz"
    np.savez(volumes_npz, images_x=loaded["images"]["X"], images_u=loaded["images"]["U"],
             images_v=loaded["images"]["V"], metadata=md.astype(np.float32))
    np.savez_compressed(selection_npz, is_selected_cluster=np.ones(n, dtype=bool))
    del loaded
    print(f"wrote temp volumes {volumes_npz} ({volumes_npz.stat().st_size / 1e9:.2f} GB) at {time.time() - t0:.0f}s")

    ed_script = python_root / "app" / "ed_inference.py"
    env = dict(os.environ)
    env["INIT_DONE"] = "true"
    subprocess.run(["python3", str(ed_script), args.ed_model, str(volumes_npz), str(selection_npz),
                    "--out", str(ed_npz), "--batch-size", str(args.batch_size)], check=True, env=env)
    ed = np.load(ed_npz, allow_pickle=True)
    raw = np.asarray(ed["ed_raw"], dtype=np.float64)
    if raw.ndim == 3 and raw.shape[1] == 1:
        raw = raw.squeeze(1)
    idx = np.asarray(ed["cluster_idx"], dtype=np.int64)
    assert raw.shape == (n, 3) and np.array_equal(idx, np.arange(n)), (raw.shape, idx[:5])
    reco = _normalize_rows(raw)
    valid = np.isfinite(reco).all(axis=1) & (np.linalg.norm(raw, axis=1) > 0)
    print(f"ED inference done: {valid.sum()}/{n} valid directions at {time.time() - t0:.0f}s")
    for tmp in (volumes_npz, selection_npz):
        try:
            tmp.unlink()
        except OSError:
            pass

    nu_dir = _normalize_rows(md[:, 15:18])
    e_dir = _normalize_rows(md[:, 7:10])
    nu_valid = np.linalg.norm(md[:, 15:18], axis=1) > 0
    e_valid = np.linalg.norm(md[:, 7:10], axis=1) > 0
    cos_nu = np.sum(reco * nu_dir, axis=1)
    cos_e = np.sum(reco * e_dir, axis=1)
    cos_e_nu = np.sum(e_dir * nu_dir, axis=1)
    e_reco = md[:, 10]
    e_true = md[:, 11]

    sel = valid & nu_valid & (e_reco > 0) & (e_reco < 1000)
    pdf, edges, centers, n_per_bin = build_table(cos_nu[sel], e_reco[sel], energy_bins, n_cos_bins)
    sel_e = valid & e_valid & (e_reco > 0) & (e_reco < 1000)
    pdf_vs_e, _, _, n_e = build_table(cos_e[sel_e], e_reco[sel_e], energy_bins, n_cos_bins)
    sel_t = valid & nu_valid & (e_true > 0) & (e_true < 1000)
    pdf_true_e, _, _, n_t = build_table(cos_nu[sel_t], e_true[sel_t], energy_bins, n_cos_bins)
    pdf_kin, _, _, n_k = build_table(cos_e_nu[nu_valid & e_valid], e_reco[nu_valid & e_valid], energy_bins, n_cos_bins)

    summary = "\n".join([
        shape_summary(pdf, centers, energy_bins, n_per_bin, "pdf_CC(cos(reco, nu) | E_reco)  [MAIN TABLE]"),
        shape_summary(pdf_vs_e, centers, energy_bins, n_e, "cos(reco, true electron) | E_reco  [ED resolution on CC]"),
        shape_summary(pdf_kin, centers, energy_bins, n_k, "cos(true electron, nu) | E_reco  [CC kinematics]"),
    ])
    print(summary)
    print(f"overall: <cos(reco,nu)> = {cos_nu[sel].mean():.4f}, P(cos>0) = {(cos_nu[sel] > 0).mean():.3f}, "
          f"<cos(reco,e)> = {cos_e[sel_e].mean():.4f}, <cos(e,nu)> = {cos_e_nu[nu_valid & e_valid].mean():.4f}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        out,
        pdf_2d=pdf,
        cosine_bin_edges=edges,
        cosine_bin_centers=centers,
        energy_bins=np.asarray(energy_bins, dtype=np.int64) if all(float(b[0]).is_integer() and float(b[1]).is_integer() for b in energy_bins) else np.asarray(energy_bins),
        n_events_per_bin=n_per_bin,
        smoothing_method="Raw histogram (no smoothing)",
        truth_axis="reco ED direction . true neutrino momentum (metadata cols 15:18)",
        energy_axis="reconstructed cluster energy (metadata col 10)",
        source_folder=str(args.cluster_folders_glob or args.cluster_folder),
        sample_type=str(args.sample_type),
        ed_model=str(args.ed_model),
        n_clusters_total=int(n),
        n_clusters_used=int(sel.sum()),
        pdf_2d_vs_true_electron=pdf_vs_e,
        n_events_per_bin_vs_true_electron=n_e,
        pdf_2d_true_energy_axis=pdf_true_e,
        n_events_per_bin_true_energy_axis=n_t,
        pdf_2d_kinematics_e_nu=pdf_kin,
        shape_summary=summary,
    )
    print(f"saved {out}")

    if args.events_out:
        np.savez_compressed(
            args.events_out,
            reco_dirs=reco.astype(np.float32), valid=valid, true_nu_dirs=nu_dir.astype(np.float32),
            true_electron_dirs=e_dir.astype(np.float32), energy_reco=e_reco.astype(np.float32),
            energy_true=e_true.astype(np.float32), nu_energy=md[:, 14].astype(np.float32),
            event_number=md[:, 0].astype(np.int64), cos_nu=cos_nu.astype(np.float32),
            cos_e=cos_e.astype(np.float32), metadata=md.astype(np.float32),
        )
        print(f"saved per-cluster arrays {args.events_out}")

    if args.png:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        es_pdf = np.asarray(ref["pdf_2d"])
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        ax = axes[0]
        im = ax.imshow(pdf, aspect="auto", origin="lower", cmap="hot", extent=[-1, 1, 0, len(energy_bins)])
        ax.set_yticks(np.arange(len(energy_bins)) + 0.5)
        ax.set_yticklabels([f"{int(a)}-{int(b)}" for a, b in energy_bins], fontsize=7)
        ax.set_xlabel("cos(reco e dir, true nu dir)")
        ax.set_ylabel("E_reco bin [MeV]")
        ax.set_title("pdf_CC(cos | E)")
        plt.colorbar(im, ax=ax)
        ax = axes[1]
        for i in (1, 4, 8, 12, 16):
            if n_per_bin[i] > 0:
                ax.plot(centers, pdf[i], label=f"CC {int(energy_bins[i][0])}-{int(energy_bins[i][1])} MeV")
                ax.plot(centers, es_pdf[i], "--", alpha=0.6, label=f"ES same bin")
        ax.axhline(0.5, color="grey", ls=":", label="flat")
        ax.set_yscale("log")
        ax.set_xlabel("cos")
        ax.set_ylabel("density")
        ax.set_title("CC (solid) vs ES (dashed) rows")
        ax.legend(fontsize=6, ncol=2)
        ax.grid(alpha=0.3)
        ax = axes[2]
        width = centers[1] - centers[0]
        ec = [0.5 * (a + b) for a, b in energy_bins]
        ax.plot(ec, [np.sum(pdf[i] * centers) * width for i in range(len(energy_bins))], "o-", label="CC: <cos(reco, nu)>")
        ax.plot(ec, [np.sum(pdf_vs_e[i] * centers) * width for i in range(len(energy_bins))], "s-", label="CC: <cos(reco, true e)>")
        ax.plot(ec, [np.sum(pdf_kin[i] * centers) * width for i in range(len(energy_bins))], "^-", label="CC: <cos(true e, nu)>")
        ax.plot(ec, [np.sum(es_pdf[i] * centers) * width for i in range(len(energy_bins))], "d--", label="ES table: <cos>")
        ax.axhline(0, color="grey", ls=":")
        ax.set_xlabel("E_reco [MeV]")
        ax.set_ylabel("<cos>")
        ax.set_title("mean cosine vs energy")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(args.png, dpi=130)
        print(f"saved {args.png}")
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
