#!/usr/bin/env python3
"""
Sample Loader Module

Loads cluster images from CC and ES sample folders and selects
a specified number of events from each type.
"""

import numpy as np
from pathlib import Path
import glob


def load_and_select_samples(cc_folder, es_folder, n_cc_events, n_es_events,
                            file_pattern='*_planeX.npz', cc_file_pattern=None,
                            es_file_pattern=None, shuffle=True,
                            random_seed=42, output_dir=None, verbose=False,
                            load_all_planes=False,
                            cc_vol_folder=None, es_vol_folder=None,
                            event_budget_mode='generated', events_per_file=40):
    """
    Load and select samples from CC and ES folders.

    Selection strategy: Go through files in order, count events (not clusters),
    stop when reaching the target number of events.

    Args:
        cc_folder: Path to CC cluster images folder (X subfolder, or base folder if load_all_planes=True)
        es_folder: Path to ES cluster images folder (X subfolder, or base folder if load_all_planes=True)
        n_cc_events: Number of CC events to select
        n_es_events: Number of ES events to select
        file_pattern: Default file pattern to match for both sources
        cc_file_pattern: Optional CC-specific file pattern
        es_file_pattern: Optional ES-specific file pattern
        shuffle: Whether to shuffle clusters after selection
        random_seed: Random seed for reproducibility
        output_dir: Optional directory to save selected data
        verbose: Print detailed progress
        load_all_planes: If True, load X, U, V planes from separate subfolders
        cc_vol_folder: Optional path to pre-computed large-format CT volume images for CC
        es_vol_folder: Optional path to pre-computed large-format CT volume images for ES
        event_budget_mode: How n_cc_events / n_es_events are counted.
            'generated' (default): budget in GENERATED events, identity =
                (file index in sorted order, event number). Files hold
                `events_per_file` generated events numbered 1..events_per_file, so
                n_events_target spans n_events_target // events_per_file complete files
                plus the first (n_events_target % events_per_file) events of the next
                one. Generated events that leave no matched cluster still count.
            'legacy': the pre-2026-09 behaviour, a set of bare event numbers. Because
                event numbers restart at 1 in every file the set saturates at
                `events_per_file`, the target is never reached and ALL files are loaded.
                Kept only to reproduce past results.
        events_per_file: Generated events per input file (40 for the SN burst samples).

    Returns:
        dict with selected images, metadata, and statistics
        If load_all_planes=True, images dict contains 'X', 'U', 'V' keys
        If cc_vol_folder/es_vol_folder provided, result contains 'ct_images' (N, H, W) array
    """

    if verbose:
        print(f"\nLoading samples:")
        print(f"  CC folder: {cc_folder}")
        print(f"  ES folder: {es_folder}")
        print(f"  Target: {n_cc_events} CC events, {n_es_events} ES events")
        if load_all_planes:
            print(f"  Mode: 3-plane (X, U, V)")
        if cc_vol_folder:
            print(f"  CT volume folder (CC): {cc_vol_folder}")
        if es_vol_folder:
            print(f"  CT volume folder (ES): {es_vol_folder}")

    cc_pattern = cc_file_pattern or file_pattern
    es_pattern = es_file_pattern or file_pattern

    # Load CC samples
    cc_data = _load_samples_from_folder(
        cc_folder, n_cc_events, cc_pattern,
        sample_type='CC', verbose=verbose,
        load_all_planes=load_all_planes,
        vol_folder=cc_vol_folder,
        event_budget_mode=event_budget_mode,
        events_per_file=events_per_file,
    )

    # Load ES samples
    es_data = _load_samples_from_folder(
        es_folder, n_es_events, es_pattern,
        sample_type='ES', verbose=verbose,
        load_all_planes=load_all_planes,
        vol_folder=es_vol_folder,
        event_budget_mode=event_budget_mode,
        events_per_file=events_per_file,
    )

    # Combine data
    if load_all_planes:
        all_images = {
            'X': np.concatenate([cc_data['images']['X'], es_data['images']['X']], axis=0),
            'U': np.concatenate([cc_data['images']['U'], es_data['images']['U']], axis=0),
            'V': np.concatenate([cc_data['images']['V'], es_data['images']['V']], axis=0),
        }
    else:
        all_images = np.concatenate([cc_data['images'], es_data['images']], axis=0)
    all_metadata = np.concatenate([cc_data['metadata'], es_data['metadata']], axis=0)

    # Combine CT volume refs if available
    cc_refs = cc_data.get('ct_vol_refs')
    es_refs = es_data.get('ct_vol_refs')
    all_ct_vol_refs = None
    if cc_refs is not None and es_refs is not None:
        all_ct_vol_refs = cc_refs + es_refs
    elif cc_refs is not None or es_refs is not None:
        all_ct_vol_refs = (cc_refs or []) + (es_refs or [])

    # Shuffle if requested
    if shuffle:
        np.random.seed(random_seed)
        n_samples = len(all_metadata)
        indices = np.random.permutation(n_samples)
        if load_all_planes:
            all_images = {k: v[indices] for k, v in all_images.items()}
        else:
            all_images = all_images[indices]
        all_metadata = all_metadata[indices]
        if all_ct_vol_refs is not None:
            all_ct_vol_refs = [all_ct_vol_refs[i] for i in indices]
        if verbose:
            print(f"\n✓ Shuffled {n_samples} clusters")

    # Save if output directory specified
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if load_all_planes:
            np.savez(
                output_path / 'selected_samples.npz',
                images_x=all_images['X'],
                images_u=all_images['U'],
                images_v=all_images['V'],
                metadata=all_metadata
            )
        else:
            np.savez(
                output_path / 'selected_samples.npz',
                images=all_images,
                metadata=all_metadata
            )

        # Save summary
        n_total = len(all_metadata)
        with open(output_path / 'selection_summary.txt', 'w') as f:
            f.write(f"Sample Selection Summary\n")
            f.write(f"{'='*60}\n\n")
            f.write(f"Event budget mode: {event_budget_mode} "
                    f"({events_per_file} generated events/file)\n")
            f.write(f"CC generated-event budget: {cc_data['n_events_budget']} "
                    f"over {cc_data['n_files_budget']} files\n")
            f.write(f"ES generated-event budget: {es_data['n_events_budget']} "
                    f"over {es_data['n_files_budget']} files\n\n")
            f.write(f"CC Events: {cc_data['n_events']} (requested: {n_cc_events})\n")
            f.write(f"CC Clusters: {cc_data['n_clusters']}\n\n")
            f.write(f"ES Events: {es_data['n_events']} (requested: {n_es_events})\n")
            f.write(f"ES Clusters: {es_data['n_clusters']}\n\n")
            f.write(f"Total Clusters: {n_total}\n")
            f.write(f"Shuffled: {shuffle}\n")
            f.write(f"3-Plane Mode: {load_all_planes}\n")
            if shuffle:
                f.write(f"Random Seed: {random_seed}\n")

        if verbose:
            print(f"\n✓ Saved selected samples to {output_path}")

    return {
        'images': all_images,
        'metadata': all_metadata,
        'ct_vol_refs': all_ct_vol_refs,
        'n_cc_events': cc_data['n_events'],
        'n_es_events': es_data['n_events'],
        'n_cc_clusters': cc_data['n_clusters'],
        'n_es_clusters': es_data['n_clusters'],
        'total_clusters': len(all_metadata),
        'cc_files_used': cc_data['files_used'],
        'es_files_used': es_data['files_used'],
        'three_plane_mode': load_all_planes,
        'event_budget_mode': event_budget_mode,
        'events_per_file': int(events_per_file),
        'n_cc_events_budget': cc_data['n_events_budget'],
        'n_es_events_budget': es_data['n_events_budget'],
        'n_cc_files_budget': cc_data['n_files_budget'],
        'n_es_files_budget': es_data['n_files_budget'],
    }


def _load_samples_from_folder(folder, n_events_target, file_pattern,
                              sample_type='CC', verbose=False,
                              load_all_planes=False, vol_folder=None,
                              event_budget_mode='generated', events_per_file=40):
    """
    Load samples from a single folder until reaching target number of events.

    Metadata format (18 columns):
      0: event number
      1: is_marley
      2: is_main_track (1 = main track cluster)
      3: is_es_interaction
      4-6: true_pos (x,y,z)
      7-9: true_particle_mom (px,py,pz)
      10: cluster_energy
      11: true_particle_energy
      12: plane_number
      13: match_id (links clusters across U, V, X planes; -1 = unmatched)
      14: nu_energy
      15-17: nu_mom (px, py, pz)

    Args:
        folder: Path to folder (X subfolder if load_all_planes=False, base folder if True)
        n_events_target: Number of events to load
        file_pattern: Pattern to match files (e.g., '*_planeX.npz')
        sample_type: 'CC' or 'ES' for logging
        verbose: Print progress
        load_all_planes: If True, load X, U, V from subfolders and match by match_id
    """
    folder_path = Path(folder)

    if load_all_planes:
        # folder should be the base folder containing X/, U/, V/ subfolders
        x_folder = folder_path / 'X'
        u_folder = folder_path / 'U'
        v_folder = folder_path / 'V'

        if not all(p.exists() for p in [x_folder, u_folder, v_folder]):
            raise ValueError(f"3-plane mode requires X/, U/, V/ subfolders in {folder}")

        # Use X-plane pattern to find files
        x_pattern = file_pattern
        files = sorted(x_folder.glob(x_pattern))
    else:
        if not folder_path.exists():
            raise ValueError(f"Folder not found: {folder}")
        files = sorted(folder_path.glob(file_pattern))

    if not files:
        raise ValueError(f"No files matching pattern '{file_pattern}' in {folder}")

    if verbose:
        print(f"\n  {sample_type}: Found {len(files)} files")

    images_list_x = []
    images_list_u = []
    images_list_v = []
    metadata_list = []
    vol_images_list = []
    events_seen = set()
    files_used = []

    vol_folder_path = Path(vol_folder) / 'X' if vol_folder else None

    # --- generated-event budget -------------------------------------------------
    # Event numbers restart at 1..events_per_file in EVERY file, so an event is only
    # identified by (file index in sorted order, event number). n_events_target
    # generated events = `n_full_files` complete files plus the first `n_rest` events
    # of the next one. Generated events whose clusters do not survive matching still
    # consume the budget, which is the point: a burst is the first N GENERATED events.
    budget_mode = str(event_budget_mode or 'generated').lower()
    if budget_mode not in ('generated', 'legacy'):
        raise ValueError(f"Unsupported event_budget_mode: {event_budget_mode!r} "
                         "(expected 'generated' or 'legacy')")
    budget_generated = budget_mode == 'generated'
    events_per_file = int(events_per_file)
    if budget_generated and events_per_file < 1:
        raise ValueError(f"events_per_file must be >= 1, got {events_per_file}")
    if budget_generated:
        n_full_files = int(n_events_target) // events_per_file
        n_rest = int(n_events_target) % events_per_file
        last_file_idx = n_full_files if n_rest > 0 else n_full_files - 1
        n_files_budget = last_file_idx + 1
    else:
        n_full_files = n_rest = 0
        last_file_idx = len(files) - 1
        n_files_budget = len(files)

    def _in_generated_budget(f_idx, ev_num):
        if f_idx < n_full_files:
            return True
        return f_idx == n_full_files and 1 <= ev_num <= n_rest

    if budget_generated and verbose:
        print(f"  {sample_type}: generated-event budget {n_events_target} = "
              f"{n_full_files} full files + first {n_rest} events of file {n_full_files + 1} "
              f"({events_per_file} events/file)")

    for file_idx, file_path in enumerate(files):
        if budget_generated:
            if file_idx > last_file_idx:
                break
        elif len(events_seen) >= n_events_target:
            break

        try:
            data_x = np.load(file_path, allow_pickle=True)
            imgs_x = data_x['images']
            meta_x = data_x['metadata']

            if load_all_planes:
                # Build corresponding U and V file paths
                file_name = file_path.name
                u_file = folder_path / 'U' / file_name.replace('planeX', 'planeU')
                v_file = folder_path / 'V' / file_name.replace('planeX', 'planeV')

                if not u_file.exists() or not v_file.exists():
                    if verbose:
                        print(f"\n  Warning: Missing U/V for {file_name}, skipping")
                    continue

                data_u = np.load(u_file, allow_pickle=True)
                data_v = np.load(v_file, allow_pickle=True)
                imgs_u, meta_u = data_u['images'], data_u['metadata']
                imgs_v, meta_v = data_v['images'], data_v['metadata']

                # Filter for main tracks only (column 2 == 1)
                is_main_x = meta_x[:, 2] == 1
                is_main_u = meta_u[:, 2] == 1
                is_main_v = meta_v[:, 2] == 1

                # Get match_ids for main tracks (column 13), excluding -1 (unmatched)
                match_ids_x = {int(m): i for i, m in enumerate(meta_x[:, 13]) if is_main_x[i] and m != -1}
                match_ids_u = {int(m): i for i, m in enumerate(meta_u[:, 13]) if is_main_u[i] and m != -1}
                match_ids_v = {int(m): i for i, m in enumerate(meta_v[:, 13]) if is_main_v[i] and m != -1}

                # Find common match_ids across all 3 planes
                common_ids = set(match_ids_x.keys()) & set(match_ids_u.keys()) & set(match_ids_v.keys())

                # Compute the corresponding CT volume file path (strip "_matched")
                vol_file_ref = None
                if vol_folder_path is not None:
                    vol_file_name = file_path.name.replace('_matched', '')
                    vol_file_ref = str(vol_folder_path / vol_file_name)

                # Process matched clusters
                for match_id in sorted(common_ids):
                    idx_x = match_ids_x[match_id]
                    idx_u = match_ids_u[match_id]
                    idx_v = match_ids_v[match_id]

                    event_num = int(meta_x[idx_x, 0])

                    if budget_generated:
                        if not _in_generated_budget(file_idx, event_num):
                            continue
                        events_seen.add((file_idx, event_num))
                    else:
                        if event_num not in events_seen:
                            if len(events_seen) >= n_events_target:
                                break
                            events_seen.add(event_num)
                        if event_num not in events_seen:
                            continue

                    # Include all matched clusters from selected events
                    images_list_x.append(imgs_x[idx_x])
                    images_list_u.append(imgs_u[idx_u])
                    images_list_v.append(imgs_v[idx_v])
                    metadata_list.append(meta_x[idx_x])  # Use X metadata as reference
                    if vol_file_ref is not None:
                        # Store (file_path, match_id) reference — loaded lazily by CT tagger
                        vol_images_list.append((vol_file_ref, match_id))
            else:
                # Single-plane mode: process all clusters
                for i in range(len(imgs_x)):
                    event_num = int(meta_x[i, 0])

                    if budget_generated:
                        if not _in_generated_budget(file_idx, event_num):
                            continue
                        events_seen.add((file_idx, event_num))
                    else:
                        if event_num not in events_seen:
                            if len(events_seen) >= n_events_target:
                                break
                            events_seen.add(event_num)
                        if event_num not in events_seen:
                            continue

                    images_list_x.append(imgs_x[i])
                    metadata_list.append(meta_x[i])

            files_used.append(str(file_path.name))

            if verbose and (file_idx + 1) % 10 == 0:
                print(f"    Processed {file_idx + 1}/{len(files)} files, "
                      f"{len(events_seen)} events, {len(images_list_x)} clusters", end='\r')

            if budget_generated:
                if file_idx >= last_file_idx:
                    break
            elif len(events_seen) >= n_events_target:
                break

        except Exception as e:
            print(f"\n  Warning: Error loading {file_path.name}: {e}")
            continue

    if budget_generated:
        if len(files) < n_files_budget:
            print(f"\n  WARNING: {sample_type}: only {len(files)} files available, "
                  f"{n_files_budget} needed for {n_events_target} generated events "
                  f"({events_per_file} per file)")
    elif len(events_seen) < n_events_target:
        print(f"\n  WARNING: Only found {len(events_seen)} events "
              f"(requested {n_events_target})")

    if load_all_planes:
        images = {
            'X': np.array(images_list_x, dtype=np.float32),
            'U': np.array(images_list_u, dtype=np.float32),
            'V': np.array(images_list_v, dtype=np.float32),
        }
    else:
        images = np.array(images_list_x, dtype=np.float32)
    metadata = np.array(metadata_list, dtype=np.float32)

    # CT volume refs: list of (vol_file_path_str, match_id) — loaded lazily by the CT tagger
    ct_vol_refs = vol_images_list if (vol_folder_path is not None and vol_images_list) else None
    if verbose and ct_vol_refs is not None:
        print(f"  CT volume refs: {len(ct_vol_refs)} entries (lazy-loaded)")

    if verbose:
        n_clusters = len(images_list_x)
        mode_str = " (matched via match_id)" if load_all_planes else ""
        print(f"\n  {sample_type}: Loaded {len(events_seen)} events, "
              f"{n_clusters} clusters{mode_str} from {len(files_used)} files")

    return {
        'images': images,
        'metadata': metadata,
        'ct_vol_refs': ct_vol_refs,
        'n_events': len(events_seen),
        'n_clusters': len(images_list_x),
        'files_used': files_used,
        'n_events_budget': int(n_events_target) if budget_generated else None,
        'n_files_budget': min(n_files_budget, len(files)),
        'budget_mode': budget_mode,
    }
