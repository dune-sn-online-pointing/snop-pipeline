#!/usr/bin/env python3
"""Offline burst-direction fits for the induction-threshold study.

Three event sets per cat, all built on top of the deployed R4 per-event products
(scenario_4_weighted_ct rows of the v63/matchfix dev run: one row per loaded cluster,
CC 3300 + ES 330 generated-event budget):

  ref     the R4 rows as they are (clustering e3p0 in all views)
  ind25   ref + the ES events recovered by X=3.0 / induction=2.5 MeV
  ind20   ref + the ES events recovered by X=3.0 / induction=2.0 MeV

The recovered rows carry their own ED v63 direction (run on the new three-plane cluster
images) and their own CT v80 score (run on the unchanged X volume image of the same
event), produced by induction_threshold_infer.py.

Scenarios use the pipeline's own select_electrons_from_run + reconstruct_burst_direction
with the ed_r3_eval.py emcee settings.
"""
import argparse, json, os, shutil, sys, tempfile, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "python"))
sys.path.insert(0, os.path.join(REPO, "python", "lib"))
sys.path.insert(0, HERE)

from ana.burst_direction import select_electrons_from_run, reconstruct_burst_direction  # noqa: E402

R4 = ("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/ed_retrain/"
      "R4_v63_ownpdf_matchfix")
SCEN_TAR = "scenario_4_weighted_ct"


def read_cat(cat, r4=R4):
    """The R4 scenario-4 rows (one per loaded cluster) with their CT v80 score and
    ED v63 direction, in the seed-42 shuffled order the pipeline used."""
    import io, tarfile
    tp = f"{r4}/cat{cat:06d}/cat{cat:06d}_scenarios.tar"
    with tarfile.open(tp) as t:
        names = [n for n in t.getnames() if n.startswith(SCEN_TAR) and n.endswith(".npz")]

        def load(tag):
            n = [x for x in names if tag in x][0]
            return np.load(io.BytesIO(t.extractfile(n).read()), allow_pickle=True)
        md = load("volumes.npz")["metadata"]
        cp = load("channel_predictions")
        rd = load("reco_directions")
    return dict(md=md, proba=np.asarray(cp["y_pred_proba"], float),
                dirs=np.asarray(rd["reco_dirs"], float),
                has=np.asarray(rd["has_reco"], bool))

V63 = ("/eos/project-e/ep-nu/evilla/sn-online-pointing/neural-networks/electron_direction/"
       "three_plane_v63_matchfix_ft58_20260921_132520")
SCENARIOS = {
    "s2_perfect_ct_e3": dict(selection_mode="true-es", direction_mode="reco",
                             min_energy=3.0, ct_threshold=None,
                             pdf=f"{V63}/cosine_energy_pdf.npz"),
    "s6_perfect_ct_e5": dict(selection_mode="true-es", direction_mode="reco",
                             min_energy=5.0, ct_threshold=None,
                             pdf=f"{V63}/cosine_energy_pdf.npz"),
    "deployed_ct080_e5": dict(selection_mode="predicted-es", direction_mode="reco",
                              min_energy=5.0, ct_threshold=0.80,
                              pdf=f"{V63}/cosine_energy_pdf_mixture_ctsel_global_flatcc.npz"),
}
EMCEE_CFG = {"enabled": True, "nwalkers": 128, "nsteps": 500, "discard": 100,
             "prior_type": "uniform", "prior_sigma_deg": 10.0,
             "likelihood_kappa": 25.0, "random_seed": 42}


def write_run_dir(dest, md, dirs, has, proba):
    os.makedirs(os.path.join(dest, "volume_images"), exist_ok=True)
    os.makedirs(os.path.join(dest, "predictions"), exist_ok=True)
    np.savez(os.path.join(dest, "volume_images", "volumes.npz"), metadata=md)
    np.savez(os.path.join(dest, "predictions", "reco_directions.npz"),
             reco_dirs=dirs, has_reco=has)
    np.savez(os.path.join(dest, "predictions", "channel_predictions.npz"),
             y_true=md[:, 3].astype(np.int64),
             y_pred=(proba >= 0.5).astype(np.int64),
             y_pred_proba=proba.astype(np.float32))
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cats", default="623-672")
    ap.add_argument("--infer-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.cats.split("-"))

    # merge the per-range inference outputs
    rec = {}
    for sfx in ("indcut25", "indcut20"):
        rec[sfx] = {}
        for f in sorted(os.listdir(a.infer_dir)):
            if f.startswith(f"infer_{sfx}_") and f.endswith(".npz"):
                p = np.load(os.path.join(a.infer_dir, f), allow_pickle=True)["payload"][0]
                rec[sfx].update({k: v for k, v in p.items() if v is not None})

    res = {}
    scratch = tempfile.mkdtemp(prefix="indcut_fit_")
    t0 = time.time()
    try:
        for cat in range(lo, hi + 1):
            d = read_cat(cat)
            base = (d["md"], d["dirs"], np.ones(len(d["md"]), bool), d["proba"])
            sets = {"ref": base}
            for sfx, tag in (("indcut25", "ind25"), ("indcut20", "ind20")):
                r = rec[sfx].get(cat)
                if r is None:
                    continue
                sets[tag] = (np.concatenate([base[0], r["md"]]),
                             np.concatenate([base[1], r["dirs"]]),
                             np.concatenate([base[2], np.ones(len(r["md"]), bool)]),
                             np.concatenate([base[3], r["proba"]]))
            res[cat] = {}
            for tag, (md, dirs, has, proba) in sets.items():
                work = os.path.join(scratch, f"cat{cat:06d}_{tag}")
                write_run_dir(work, md.astype(np.float32), dirs, has, proba)
                for sname, st in SCENARIOS.items():
                    sel = select_electrons_from_run(
                        __import__("pathlib").Path(work),
                        selection_mode=st["selection_mode"],
                        direction_mode=st["direction_mode"],
                        min_energy_mev=st["min_energy"],
                        ct_threshold=st["ct_threshold"])
                    fr = reconstruct_burst_direction(
                        selected_dirs=sel["selected_dirs"],
                        selected_weights=sel["selected_weights"],
                        selected_energies=sel["selected_energy"],
                        true_burst_dir=sel["true_burst_dir"],
                        use_emcee=True, emcee_cfg=EMCEE_CFG, pdf_path=st["pdf"])
                    cos = (float(np.clip(np.dot(fr["reco_dir"], sel["true_burst_dir"]), -1, 1))
                           if fr["reco_dir"] is not None else float("nan"))
                    th = fr["theta_samples_deg"]
                    res[cat][(tag, sname)] = dict(
                        cos=cos, n_sel=int(sel["n_selected"]),
                        q68=float(np.quantile(th, 0.68)) if th.size else float("nan"),
                        single_pass=float(fr["single_pass_theta_deg"]))
                shutil.rmtree(work, ignore_errors=True)
            print(f"cat{cat:06d} done  ({time.time()-t0:.0f}s)  "
                  + "  ".join(f"{t}/{s}:n={res[cat][(t,s)]['n_sel']}"
                              for (t, s) in res[cat] if s == "deployed_ct080_e5"), flush=True)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    np.savez_compressed(a.out, payload=np.array([res], dtype=object))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
