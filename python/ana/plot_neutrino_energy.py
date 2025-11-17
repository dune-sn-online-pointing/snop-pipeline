#!/usr/bin/env python3
"""Aggregate neutrino energies across CAT datasets and draw a histogram."""

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Set, Tuple

import matplotlib.pyplot as plt
import numpy as np
import uproot


def discover_categories(base_path: Path, limit: int) -> List[Path]:
    """Return up to ``limit`` CAT directories sorted lexicographically."""
    cats = sorted(p for p in base_path.glob("cat[0-9][0-9][0-9][0-9][0-9][0-9]") if p.is_dir())
    if not cats:
        raise FileNotFoundError(f"No CAT directories found under {base_path}")
    if limit > 0:
        cats = cats[:limit]
    return cats


def find_dataset_dir(cat_dir: Path, dataset_type: str) -> Path:
    """Locate the directory containing cluster or matched ROOT files."""
    suffix = "clusters" if dataset_type == "clusters" else "matched_clusters"
    matches = sorted(p for p in cat_dir.glob(f"{cat_dir.name}_{suffix}_*") if p.is_dir())
    if not matches:
        raise FileNotFoundError(f"No {suffix} directory found in {cat_dir}")
    return matches[0]


def iter_root_files(dataset_dir: Path) -> Iterable[Path]:
    """Yield ROOT files containing cluster information (both CC and ES)."""
    yield from sorted(dataset_dir.glob("*.root"))


def extract_energies(
    file_obj,
    file_path: Path,
    tree_prefix: str,
    plane: str,
    seen_keys: Set[Tuple[str, str, int]],
    cat_name: str,
    min_energy: float,
) -> List[float]:
    """Read event-wise neutrino energies from a ROOT file, deduplicated."""
    interaction = "es" if file_path.stem.startswith("es_") else "cc"
    tree_name = f"{tree_prefix}/clusters_tree_{plane.upper()};1"
    if tree_name not in file_obj:
        print(f"[WARN] Missing {tree_name} in {file_path}", file=sys.stderr)
        return []

    try:
        tree = file_obj[tree_name]
    except Exception as exc:  # pragma: no cover
        print(f"[WARN] Failed to load {tree_name} in {file_path}: {exc}", file=sys.stderr)
        return []

    arrays = tree.arrays(["event", "true_neutrino_energy"], library="np")
    events = arrays["event"].astype(np.int64)
    energies = arrays["true_neutrino_energy"].astype(np.float64)

    collected: List[float] = []
    # Deduplicate per event within this file to avoid per-cluster repeats
    unique_events, indices = np.unique(events, return_index=True)

    for event_id, idx in zip(unique_events, indices):
        energy = energies[idx]
        if energy < min_energy:
            continue
        key = (cat_name, interaction, int(event_id))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        collected.append(float(energy))

    return collected


def build_histogram(energies: np.ndarray, bins: int, output_path: Path, title: str) -> None:
    """Plot and save histogram for the provided energy samples."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(energies, bins=bins, color="#1f77b4", alpha=0.8, edgecolor="black")
    ax.set_xlabel("True neutrino energy [MeV]")
    ax.set_ylabel("Number of events")
    ax.set_title(title)
    ax.grid(True, alpha=0.2)

    stats = (
        f"Events: {len(energies)}\n"
        f"Mean: {np.mean(energies):.1f} MeV\n"
        f"Median: {np.median(energies):.1f} MeV\n"
        f"Min/Max: {np.min(energies):.1f} / {np.max(energies):.1f} MeV"
    )
    ax.text(
        0.02,
        0.98,
        stats,
        transform=ax.transAxes,
        ha="left",
        va="top",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
    )

    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot neutrino energies from CAT cluster ROOT files")
    parser.add_argument(
        "--root-base",
        default="/eos/project-e/ep-nu/public/sn-pointing",
        help="Base directory containing cat* folders",
    )
    parser.add_argument(
        "--n-cats",
        type=int,
        default=100,
        help="Number of CAT directories to aggregate (sorted lexicographically)",
    )
    parser.add_argument(
        "--plane",
        choices=["U", "V", "X"],
        default="X",
        help="TPC plane to read from each ROOT file",
    )
    parser.add_argument(
        "--bins",
        type=int,
        default=60,
        help="Number of histogram bins",
    )
    parser.add_argument(
        "--dataset-type",
        choices=["clusters", "matched"],
        default="clusters",
        help="Which CAT directory to read from (clusters vs matched)",
    )
    parser.add_argument(
        "--output",
        default="results/neutrino_energy_100cats.png",
        help="Path to save the histogram image",
    )
    parser.add_argument(
        "--dump",
        default="results/neutrino_energy_100cats.npy",
        help="Optional path to store the raw energies as a NumPy .npy file",
    )
    parser.add_argument(
        "--min-energy",
        type=float,
        default=0.0,
        help="Discard events with neutrino energy below this threshold"
    )
    parser.add_argument(
        "--include-discarded",
        action="store_true",
        help="Also read from discarded/ trees in addition to clusters/",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    root_base = Path(args.root_base)
    cats = discover_categories(root_base, args.n_cats)
    seen_keys: Set[Tuple[str, str, int]] = set()
    energies: List[float] = []

    for cat_dir in cats:
        try:
            dataset_dir = find_dataset_dir(cat_dir, args.dataset_type)
        except FileNotFoundError as exc:
            print(f"[WARN] {exc}", file=sys.stderr)
            continue

        prefixes = ["clusters"]
        if args.include_discarded:
            prefixes.append("discarded")

        for root_file in iter_root_files(dataset_dir):
            try:
                with uproot.open(root_file) as file_obj:
                    for prefix in prefixes:
                        energies.extend(
                            extract_energies(
                                file_obj,
                                Path(root_file),
                                prefix,
                                args.plane,
                                seen_keys,
                                cat_dir.name,
                                args.min_energy,
                            )
                        )
            except Exception as exc:  # pragma: no cover
                print(f"[WARN] Failed to open {root_file}: {exc}", file=sys.stderr)
                continue

    if not energies:
        raise RuntimeError("No neutrino energies collected. Check inputs and CAT availability.")

    energies_np = np.array(energies, dtype=np.float64)

    dump_path = Path(args.dump)
    dump_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(dump_path, energies_np)

    title = f"True neutrino energy distribution ({len(cats)} CATs, plane {args.plane})"
    build_histogram(energies_np, args.bins, Path(args.output), title)

    print(f"Collected {len(energies_np)} events from {len(cats)} CATs")
    print(f"Saved histogram to {args.output}")
    print(f"Saved raw data to {args.dump}")


if __name__ == "__main__":
    main()