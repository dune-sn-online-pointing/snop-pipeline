"""End-to-end check of the CT volume lookup fix (2026-09-06).

Builds (vol_file, match_id) references exactly as sample_loader does (3-plane common
main-track match ids, volume file = cluster file name without '_matched'), runs
_predict_from_vol_refs with a dummy model whose "prediction" is the pixel sum of the
image it was handed, and checks that every reference was scored on the volume whose
metadata carries that match_id and the same event number. Also counts how many
references the old positional lookup would have sent to another event's image.

Run:  source scripts/init.sh && python3 test/test_ct_volume_lookup.py [cat_dir] [n_files]
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from lib.channel_tagger import _predict_from_vol_refs  # noqa: E402

cat_dir = Path(sys.argv[1] if len(sys.argv) > 1 else
               "/eos/user/e/evilla/dune/sn-tps/mixture_dev_samples/cat000623")
n_files = int(sys.argv[2]) if len(sys.argv) > 2 else 12
cat = cat_dir.name
clu = sorted(cat_dir.glob(f"{cat}_cluster_images_*"))[0]
vol = sorted(cat_dir.glob(f"{cat}_volume_images_*"))[0]

refs, expected_sum, expected_event, positional_sum = [], [], [], []
x_files = sorted((clu / "X").glob("*_planeX.npz"))
x_files = x_files[:n_files // 2] + x_files[-(n_files - n_files // 2):]  # some CC, some ES
for xf in x_files:
    uf = clu / "U" / xf.name.replace("planeX", "planeU")
    vf = clu / "V" / xf.name.replace("planeX", "planeV")
    if not (uf.exists() and vf.exists()):
        continue
    mx = np.load(xf, allow_pickle=True)["metadata"]
    mu = np.load(uf, allow_pickle=True)["metadata"]
    mv = np.load(vf, allow_pickle=True)["metadata"]
    ids = lambda m: {int(r[13]): i for i, r in enumerate(m) if r[2] == 1 and r[13] != -1}  # noqa: E731
    ix, iu, iv = ids(mx), ids(mu), ids(mv)
    common = sorted(set(ix) & set(iu) & set(iv))
    vol_file = vol / "X" / xf.name.replace("_matched", "")
    vd = np.load(vol_file, allow_pickle=True)
    vimgs, vmeta = vd["images"], vd["metadata"]
    id_to_pos = {}
    for pos, m in enumerate(vmeta):
        mid = int(m["main_cluster_match_id"])
        if mid >= 0 and mid not in id_to_pos:
            id_to_pos[mid] = pos
    for mid in common:
        pos = id_to_pos.get(mid)
        if pos is None:
            continue
        refs.append((str(vol_file), mid))
        expected_sum.append(float(np.asarray(vimgs[pos], dtype=np.float32).sum()))
        expected_event.append((int(mx[ix[mid], 0]), int(vmeta[pos]["event"])))
        positional_sum.append(float(np.asarray(vimgs[mid], dtype=np.float32).sum()) if mid < len(vimgs) else np.nan)


class DummyModel:
    def predict(self, batch, batch_size=32, verbose=0):
        s = batch.reshape(batch.shape[0], -1).sum(axis=1)
        return np.stack([s, s], axis=1)  # column 0 is read as "P(ES)"


scores = _predict_from_vol_refs(DummyModel(), refs, len(refs), verbose=False, preprocess_mode="raw")
expected_sum = np.array(expected_sum)
ok = np.isclose(scores, expected_sum, rtol=1e-5)
ev_ok = np.array([a == b for a, b in expected_event])
pos_wrong = ~np.isclose(np.array(positional_sum), expected_sum, rtol=1e-5)
print(f"refs: {len(refs)} from {len(x_files)} files")
print(f"fixed lookup scored the metadata-resolved volume: {ok.mean():.4f}; cluster event == volume event: {ev_ok.mean():.4f}")
print(f"old positional lookup would have used a different image for {pos_wrong.mean():.3f} of these refs")
assert ok.all() and ev_ok.all(), "CT volume lookup still wrong"
print("CT VOLUME LOOKUP OK")
