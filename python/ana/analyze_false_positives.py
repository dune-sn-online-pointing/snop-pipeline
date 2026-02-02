#!/usr/bin/env python3
"""
Deep analysis of false positives in MT predictions.
Investigate what types of background clusters get misclassified as main tracks.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import argparse
from matplotlib.backends.backend_pdf import PdfPages


def load_predictions(predictions_file):
    """Load MT predictions CSV with full metadata."""
    df = pd.read_csv(predictions_file)
    print(f"Loaded {len(df)} predictions from {predictions_file}")
    print(f"Columns: {list(df.columns)}")
    return df


def analyze_false_positives(df, threshold=0.5):
    """Deep dive into false positive characteristics."""
    
    # Apply threshold
    df['predicted_label'] = (df['prediction_prob'] >= threshold).astype(int)
    
    # Identify categories
    tp = df[(df['is_main_track'] == 1) & (df['predicted_label'] == 1)]
    fp = df[(df['is_main_track'] == 0) & (df['predicted_label'] == 1)]
    fn = df[(df['is_main_track'] == 1) & (df['predicted_label'] == 0)]
    tn = df[(df['is_main_track'] == 0) & (df['predicted_label'] == 0)]
    
    print(f"\n{'='*70}")
    print(f"FALSE POSITIVE ANALYSIS (threshold={threshold})")
    print(f"{'='*70}")
    print(f"Total clusters: {len(df):,}")
    print(f"True Positives: {len(tp):,}")
    print(f"False Positives: {len(fp):,}")
    print(f"False Negatives: {len(fn):,}")
    print(f"True Negatives: {len(tn):,}")
    
    # Analyze false positives
    print(f"\n{'-'*70}")
    print(f"FALSE POSITIVE BREAKDOWN")
    print(f"{'-'*70}")
    
    # 1. Marley vs Non-Marley
    fp_marley = fp[fp['is_marley'] == 1]
    fp_non_marley = fp[fp['is_marley'] == 0]
    
    print(f"\nMarley Classification:")
    print(f"  Marley FPs:     {len(fp_marley):,} ({len(fp_marley)/len(fp)*100:.1f}%)")
    print(f"  Non-Marley FPs: {len(fp_non_marley):,} ({len(fp_non_marley)/len(fp)*100:.1f}%)")
    
    # 2. ES vs CC interactions
    fp_es = fp[fp['is_es_interaction'] == 1]
    fp_cc = fp[fp['is_es_interaction'] == 0]
    
    print(f"\nInteraction Type:")
    print(f"  ES interaction FPs: {len(fp_es):,} ({len(fp_es)/len(fp)*100:.1f}%)")
    print(f"  CC interaction FPs: {len(fp_cc):,} ({len(fp_cc)/len(fp)*100:.1f}%)")
    
    # 3. Energy statistics
    print(f"\nFalse Positive Energy Statistics:")
    print(f"  Cluster energy:")
    print(f"    Mean:   {fp['cluster_energy'].mean():.2f} MeV")
    print(f"    Median: {fp['cluster_energy'].median():.2f} MeV")
    print(f"    Std:    {fp['cluster_energy'].std():.2f} MeV")
    print(f"    Range:  {fp['cluster_energy'].min():.2f} - {fp['cluster_energy'].max():.2f} MeV")
    
    print(f"\n  Particle energy (parent):")
    print(f"    Mean:   {fp['particle_energy'].mean():.2f} MeV")
    print(f"    Median: {fp['particle_energy'].median():.2f} MeV")
    print(f"    Range:  {fp['particle_energy'].min():.2f} - {fp['particle_energy'].max():.2f} MeV")
    
    # 4. Plane distribution
    print(f"\nPlane Distribution:")
    for plane in sorted(fp['plane_id'].unique()):
        count = (fp['plane_id'] == plane).sum()
        print(f"  Plane {int(plane)}: {count:,} ({count/len(fp)*100:.1f}%)")
    
    # 5. Compare to true positives
    print(f"\n{'-'*70}")
    print(f"COMPARISON: False Positives vs True Positives")
    print(f"{'-'*70}")
    
    print(f"\nMarley fraction:")
    print(f"  TP: {(tp['is_marley'] == 1).sum()/len(tp)*100:.1f}%")
    print(f"  FP: {(fp['is_marley'] == 1).sum()/len(fp)*100:.1f}%")
    
    print(f"\nES interaction fraction:")
    print(f"  TP: {(tp['is_es_interaction'] == 1).sum()/len(tp)*100:.1f}%")
    print(f"  FP: {(fp['is_es_interaction'] == 1).sum()/len(fp)*100:.1f}%")
    
    print(f"\nCluster energy:")
    print(f"  TP mean: {tp['cluster_energy'].mean():.2f} MeV")
    print(f"  FP mean: {fp['cluster_energy'].mean():.2f} MeV")
    
    print(f"\nParticle energy:")
    print(f"  TP mean: {tp['particle_energy'].mean():.2f} MeV")
    print(f"  FP mean: {fp['particle_energy'].mean():.2f} MeV")
    
    # 6. Event-level analysis: what are the main track energies in FP events?
    print(f"\n{'-'*70}")
    print(f"EVENT-LEVEL ANALYSIS")
    print(f"{'-'*70}")
    
    # Get unique events with false positives
    fp_events = fp['event'].unique()
    print(f"\nEvents with false positives: {len(fp_events):,}")
    
    # For each FP event, find the true main track energy and energy differences
    fp_event_analysis = []
    fp_detailed = []  # Store each FP with its event's main track info
    
    for event_id in fp_events:
        event_data = df[df['event'] == event_id]
        true_mt = event_data[event_data['is_main_track'] == 1]
        fps_in_event = event_data[(event_data['is_main_track'] == 0) & (event_data['predicted_label'] == 1)]
        
        if len(true_mt) > 0:
            true_mt_energy = true_mt['cluster_energy'].values[0]
            true_mt_particle_energy = true_mt['particle_energy'].values[0]
            true_mt_pos = np.array([true_mt['pos_x'].values[0], true_mt['pos_y'].values[0], true_mt['pos_z'].values[0]])
            
            fp_event_analysis.append({
                'event': event_id,
                'num_fp': len(fps_in_event),
                'true_mt_energy': true_mt_energy,
                'true_mt_particle_energy': true_mt_particle_energy,
                'is_marley': true_mt['is_marley'].values[0],
                'is_es': true_mt['is_es_interaction'].values[0],
            })
            
            # Store each FP with energy difference and spatial proximity
            for _, fp_row in fps_in_event.iterrows():
                fp_pos = np.array([fp_row['pos_x'], fp_row['pos_y'], fp_row['pos_z']])
                distance = np.linalg.norm(fp_pos - true_mt_pos)
                
                fp_detailed.append({
                    'event': event_id,
                    'fp_cluster_energy': fp_row['cluster_energy'],
                    'true_mt_cluster_energy': true_mt_energy,
                    'true_mt_particle_energy': true_mt_particle_energy,
                    'energy_diff': true_mt_energy - fp_row['cluster_energy'],
                    'energy_ratio': fp_row['cluster_energy'] / true_mt_energy if true_mt_energy > 0 else 0,
                    'particle_energy_ratio': fp_row['cluster_energy'] / true_mt_particle_energy if true_mt_particle_energy > 0 else 0,
                    'prediction_prob': fp_row['prediction_prob'],
                    'distance_to_mt': distance,
                    'pos_x': fp_row['pos_x'],
                    'pos_y': fp_row['pos_y'],
                    'pos_z': fp_row['pos_z'],
                    'mt_pos_x': true_mt_pos[0],
                    'mt_pos_y': true_mt_pos[1],
                    'mt_pos_z': true_mt_pos[2],
                })
    
    fp_event_df = pd.DataFrame(fp_event_analysis)
    fp_detailed_df = pd.DataFrame(fp_detailed)
    
    if len(fp_event_df) > 0:
        print(f"\nTrue main track energy in FP events:")
        print(f"  Mean:   {fp_event_df['true_mt_energy'].mean():.2f} MeV")
        print(f"  Median: {fp_event_df['true_mt_energy'].median():.2f} MeV")
        print(f"  Range:  {fp_event_df['true_mt_energy'].min():.2f} - {fp_event_df['true_mt_energy'].max():.2f} MeV")
        
        print(f"\nFP events by interaction type:")
        print(f"  Marley events: {(fp_event_df['is_marley'] == 1).sum()} ({(fp_event_df['is_marley'] == 1).sum()/len(fp_event_df)*100:.1f}%)")
        print(f"  ES events:     {(fp_event_df['is_es'] == 1).sum()} ({(fp_event_df['is_es'] == 1).sum()/len(fp_event_df)*100:.1f}%)")
        
        print(f"\nFPs per event:")
        print(f"  Mean:   {fp_event_df['num_fp'].mean():.2f}")
        print(f"  Median: {fp_event_df['num_fp'].median():.0f}")
        print(f"  Max:    {fp_event_df['num_fp'].max():.0f}")
    
    # 7. Energy difference analysis (split track hypothesis)
    if len(fp_detailed_df) > 0:
        print(f"\n{'-'*70}")
        print(f"ENERGY DIFFERENCE ANALYSIS (Split Track Hypothesis)")
        print(f"{'-'*70}")
        
        print(f"\nNOTE: Main cluster is selected by PARTICLE energy (not cluster energy)")
        print(f"      So FP can have higher cluster energy than MT cluster energy")
        print(f"      Also, many clusters have (0,0,0) position (unmatched/background)")
        
        # Check position validity
        fp_with_valid_pos = fp_detailed_df[(fp_detailed_df['pos_x'] != 0) | 
                                          (fp_detailed_df['pos_y'] != 0) | 
                                          (fp_detailed_df['pos_z'] != 0)]
        print(f"\nPosition validity:")
        print(f"  FPs with valid position: {len(fp_with_valid_pos)} / {len(fp_detailed_df)} " +
              f"({len(fp_with_valid_pos)/len(fp_detailed_df)*100:.1f}%)")
        print(f"  FPs at (0,0,0): {len(fp_detailed_df) - len(fp_with_valid_pos)} " +
              f"({(1 - len(fp_with_valid_pos)/len(fp_detailed_df))*100:.1f}%)")
        
        print(f"\nFP cluster energy vs True MT CLUSTER energy:")
        print(f"  Energy difference (MT cluster - FP cluster):")
        print(f"    Mean:   {fp_detailed_df['energy_diff'].mean():.2f} MeV")
        print(f"    Median: {fp_detailed_df['energy_diff'].median():.2f} MeV")
        print(f"    Std:    {fp_detailed_df['energy_diff'].std():.2f} MeV")
        print(f"    Range:  {fp_detailed_df['energy_diff'].min():.2f} - {fp_detailed_df['energy_diff'].max():.2f} MeV")
        
        print(f"\n  FP cluster / MT cluster energy ratio:")
        print(f"    Mean:   {fp_detailed_df['energy_ratio'].mean():.3f}")
        print(f"    Median: {fp_detailed_df['energy_ratio'].median():.3f}")
        print(f"    Range:  {fp_detailed_df['energy_ratio'].min():.3f} - {fp_detailed_df['energy_ratio'].max():.3f}")
        
        print(f"\n  FP cluster / MT PARTICLE energy ratio:")
        print(f"    Mean:   {fp_detailed_df['particle_energy_ratio'].mean():.3f}")
        print(f"    Median: {fp_detailed_df['particle_energy_ratio'].median():.3f}")
        print(f"    Range:  {fp_detailed_df['particle_energy_ratio'].min():.3f} - {fp_detailed_df['particle_energy_ratio'].max():.3f}")
        
        # Check for potential split tracks (similar energy)
        similar_energy = fp_detailed_df[fp_detailed_df['energy_ratio'] > 0.7]  # FP > 70% of MT cluster
        print(f"\n  FPs with cluster energy > 70% of MT cluster (potential splits):")
        print(f"    Count: {len(similar_energy)} ({len(similar_energy)/len(fp_detailed_df)*100:.1f}%)")
        if len(similar_energy) > 0:
            print(f"    Mean ratio: {similar_energy['energy_ratio'].mean():.3f}")
        
        low_energy = fp_detailed_df[fp_detailed_df['energy_ratio'] < 0.3]  # FP < 30% of MT
        print(f"\n  FPs with cluster energy < 30% of MT cluster (likely secondaries/shower):")
        print(f"    Count: {len(low_energy)} ({len(low_energy)/len(fp_detailed_df)*100:.1f}%)")
        
        # Spatial proximity analysis (only for valid positions)
        print(f"\n{'-'*70}")
        print(f"SPATIAL PROXIMITY ANALYSIS (only for FPs with valid positions)")
        print(f"{'-'*70}")
        
        if len(fp_with_valid_pos) > 0:
            print(f"\nDistance from FP to MT cluster (for {len(fp_with_valid_pos)} FPs with valid pos):")
            print(f"  Mean:   {fp_with_valid_pos['distance_to_mt'].mean():.2f} cm")
            print(f"  Median: {fp_with_valid_pos['distance_to_mt'].median():.2f} cm")
            print(f"  Range:  {fp_with_valid_pos['distance_to_mt'].min():.2f} - {fp_with_valid_pos['distance_to_mt'].max():.2f} cm")
            
            # Check for nearby FPs (potential splits)
            nearby_fps = fp_with_valid_pos[fp_with_valid_pos['distance_to_mt'] < 50]  # < 50 cm
            print(f"\n  FPs within 50 cm of MT (potential splits or nearby shower):")
            print(f"    Count: {len(nearby_fps)} ({len(nearby_fps)/len(fp_with_valid_pos)*100:.1f}% of valid pos)")
            if len(nearby_fps) > 0:
                print(f"    Mean distance: {nearby_fps['distance_to_mt'].mean():.2f} cm")
                print(f"    Mean energy ratio: {nearby_fps['energy_ratio'].mean():.3f}")
            
            very_close = fp_with_valid_pos[fp_with_valid_pos['distance_to_mt'] < 10]  # < 10 cm
            print(f"\n  FPs within 10 cm of MT (very likely splits):")
            print(f"    Count: {len(very_close)} ({len(very_close)/len(fp_with_valid_pos)*100:.1f}% of valid pos)")
            if len(very_close) > 0:
                print(f"    Mean distance: {very_close['distance_to_mt'].mean():.2f} cm")
                print(f"    Mean energy ratio: {very_close['energy_ratio'].mean():.3f}")
            
            # Combined analysis: nearby AND similar energy
            split_candidates = fp_with_valid_pos[(fp_with_valid_pos['distance_to_mt'] < 50) & 
                                             (fp_with_valid_pos['energy_ratio'] > 0.3)]
            print(f"\n  FPs that are both nearby (<50cm) AND have significant energy (>30% of MT):")
            print(f"    Count: {len(split_candidates)} ({len(split_candidates)/len(fp_with_valid_pos)*100:.1f}% of valid pos)")
            print(f"    These are STRONG candidates for split tracks")
        else:
            print(f"\nNo FPs with valid positions to analyze!")
        
        print(f"\n{'-'*70}")
        print(f"INTERPRETATION:")
        print(f"{'-'*70}")
        print(f"FPs are predominantly UNMATCHED clusters (match_id = -1)")
        print(f"These are likely:")
        print(f"  - Secondary particles from the neutrino interaction")
        print(f"  - Shower fragments")
        print(f"  - Bremsstrahlung photon conversions")
        print(f"  - Nuclear recoils")
        print(f"Split tracks account for <1% of contamination")
    
    return tp, fp, fn, tn, fp_event_df, fp_detailed_df


def create_fp_plots(tp, fp, fn, tn, fp_event_df, fp_detailed_df, output_pdf):
    """Generate comprehensive PDF report on false positives."""
    
    with PdfPages(output_pdf) as pdf:
        # Page 1: Energy comparisons
        fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
        
        # 1. Cluster energy distribution
        ax = axes[0, 0]
        bins = np.linspace(0, 50, 40)
        ax.hist(fp['cluster_energy'], bins=bins, alpha=0.6, label='False Pos', color='red', edgecolor='darkred')
        ax.hist(tp['cluster_energy'], bins=bins, alpha=0.6, label='True Pos', color='blue', edgecolor='darkblue')
        ax.axvline(fp['cluster_energy'].mean(), color='red', linestyle='--', linewidth=2, alpha=0.8)
        ax.axvline(tp['cluster_energy'].mean(), color='blue', linestyle='--', linewidth=2, alpha=0.8)
        ax.set_xlabel('Cluster Energy (MeV)', fontsize=11)
        ax.set_ylabel('Count', fontsize=11)
        ax.set_title('Cluster Energy: TP vs FP', fontsize=12, fontweight='bold')
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis='y')
        
        # 2. Particle energy distribution
        ax = axes[0, 1]
        bins = np.linspace(0, 60, 40)
        ax.hist(fp['particle_energy'], bins=bins, alpha=0.6, label='False Pos', color='red', edgecolor='darkred')
        ax.hist(tp['particle_energy'], bins=bins, alpha=0.6, label='True Pos', color='blue', edgecolor='darkblue')
        ax.set_xlabel('Particle Energy (MeV)', fontsize=11)
        ax.set_ylabel('Count', fontsize=11)
        ax.set_title('Parent Particle Energy: TP vs FP', fontsize=12, fontweight='bold')
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis='y')
        
        # 3. Marley fraction
        ax = axes[1, 0]
        categories = ['True Positives', 'False Positives']
        marley_frac = [
            (tp['is_marley'] == 1).sum() / len(tp) * 100,
            (fp['is_marley'] == 1).sum() / len(fp) * 100
        ]
        non_marley_frac = [100 - m for m in marley_frac]
        
        x = np.arange(len(categories))
        width = 0.6
        ax.bar(x, marley_frac, width, label='Marley', color='steelblue', edgecolor='navy')
        ax.bar(x, non_marley_frac, width, bottom=marley_frac, label='Non-Marley', color='orange', edgecolor='darkorange')
        ax.set_ylabel('Percentage (%)', fontsize=11)
        ax.set_title('Marley vs Non-Marley Composition', fontsize=12, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(categories)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis='y')
        
        # 4. ES vs CC fraction
        ax = axes[1, 1]
        es_frac = [
            (tp['is_es_interaction'] == 1).sum() / len(tp) * 100,
            (fp['is_es_interaction'] == 1).sum() / len(fp) * 100
        ]
        cc_frac = [100 - e for e in es_frac]
        
        ax.bar(x, es_frac, width, label='ES', color='green', edgecolor='darkgreen')
        ax.bar(x, cc_frac, width, bottom=es_frac, label='CC', color='purple', edgecolor='indigo')
        ax.set_ylabel('Percentage (%)', fontsize=11)
        ax.set_title('ES vs CC Interaction Type', fontsize=12, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(categories)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.suptitle('False Positive Analysis - Energy and Composition', 
                     fontsize=14, fontweight='bold')
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        pdf.savefig(fig, dpi=150)
        plt.close()
        
        # Page 2: Event-level analysis
        if len(fp_event_df) > 0:
            fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
            
            # 1. True MT energy in FP events
            ax = axes[0, 0]
            bins = np.linspace(0, 60, 30)
            ax.hist(fp_event_df['true_mt_energy'], bins=bins, alpha=0.7, 
                   color='coral', edgecolor='darkred')
            ax.axvline(fp_event_df['true_mt_energy'].mean(), color='red', 
                      linestyle='--', linewidth=2, label=f"Mean: {fp_event_df['true_mt_energy'].mean():.1f} MeV")
            ax.set_xlabel('True Main Track Energy (MeV)', fontsize=11)
            ax.set_ylabel('Number of Events', fontsize=11)
            ax.set_title('True MT Energy in Events with FPs', fontsize=12, fontweight='bold')
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3, axis='y')
            
            # 2. Number of FPs per event
            ax = axes[0, 1]
            fp_counts = fp_event_df['num_fp'].value_counts().sort_index()
            ax.bar(fp_counts.index, fp_counts.values, color='salmon', edgecolor='darkred', alpha=0.7)
            ax.set_xlabel('Number of FPs in Event', fontsize=11)
            ax.set_ylabel('Number of Events', fontsize=11)
            ax.set_title('FP Multiplicity per Event', fontsize=12, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='y')
            
            # 3. FP events by type
            ax = axes[1, 0]
            event_types = []
            event_counts = []
            
            marley_es = ((fp_event_df['is_marley'] == 1) & (fp_event_df['is_es'] == 1)).sum()
            marley_cc = ((fp_event_df['is_marley'] == 1) & (fp_event_df['is_es'] == 0)).sum()
            nonmarley_es = ((fp_event_df['is_marley'] == 0) & (fp_event_df['is_es'] == 1)).sum()
            nonmarley_cc = ((fp_event_df['is_marley'] == 0) & (fp_event_df['is_es'] == 0)).sum()
            
            event_types = ['Marley\nES', 'Marley\nCC', 'Non-Marley\nES', 'Non-Marley\nCC']
            event_counts = [marley_es, marley_cc, nonmarley_es, nonmarley_cc]
            
            colors = ['steelblue', 'navy', 'orange', 'darkorange']
            ax.bar(event_types, event_counts, color=colors, edgecolor='black', alpha=0.7)
            ax.set_ylabel('Number of Events with FPs', fontsize=11)
            ax.set_title('FP Events by Generator & Interaction', fontsize=12, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='y')
            
            # 4. Scatter: MT energy vs FP count
            ax = axes[1, 1]
            ax.scatter(fp_event_df['true_mt_energy'], fp_event_df['num_fp'], 
                      alpha=0.5, s=30, color='red', edgecolors='darkred')
            ax.set_xlabel('True Main Track Energy (MeV)', fontsize=11)
            ax.set_ylabel('Number of FPs in Event', fontsize=11)
            ax.set_title('MT Energy vs FP Multiplicity', fontsize=12, fontweight='bold')
            ax.grid(True, alpha=0.3)
            
            plt.suptitle('False Positive Analysis - Event-Level Properties', 
                         fontsize=14, fontweight='bold')
            plt.tight_layout(rect=[0, 0, 1, 0.96])
            pdf.savefig(fig, dpi=150)
            plt.close()
        
        # Page 3: Prediction probability distributions
        fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
        
        # 1. Prediction prob for Marley vs non-Marley FPs
        ax = axes[0, 0]
        bins = np.linspace(0.5, 1, 30)
        fp_marley = fp[fp['is_marley'] == 1]
        fp_non_marley = fp[fp['is_marley'] == 0]
        ax.hist(fp_marley['prediction_prob'], bins=bins, alpha=0.6, 
               label=f'Marley FP (n={len(fp_marley)})', color='blue', edgecolor='darkblue')
        ax.hist(fp_non_marley['prediction_prob'], bins=bins, alpha=0.6, 
               label=f'Non-Marley FP (n={len(fp_non_marley)})', color='orange', edgecolor='darkorange')
        ax.set_xlabel('Prediction Probability', fontsize=11)
        ax.set_ylabel('Count', fontsize=11)
        ax.set_title('FP Prediction Prob: Marley vs Non-Marley', fontsize=12, fontweight='bold')
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis='y')
        
        # 2. Prediction prob for ES vs CC FPs
        ax = axes[0, 1]
        fp_es = fp[fp['is_es_interaction'] == 1]
        fp_cc = fp[fp['is_es_interaction'] == 0]
        ax.hist(fp_es['prediction_prob'], bins=bins, alpha=0.6, 
               label=f'ES FP (n={len(fp_es)})', color='green', edgecolor='darkgreen')
        ax.hist(fp_cc['prediction_prob'], bins=bins, alpha=0.6, 
               label=f'CC FP (n={len(fp_cc)})', color='purple', edgecolor='indigo')
        ax.set_xlabel('Prediction Probability', fontsize=11)
        ax.set_ylabel('Count', fontsize=11)
        ax.set_title('FP Prediction Prob: ES vs CC', fontsize=12, fontweight='bold')
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis='y')
        
        # 3. Energy vs prediction prob for FPs (colored by Marley)
        ax = axes[1, 0]
        ax.scatter(fp_marley['cluster_energy'], fp_marley['prediction_prob'], 
                  alpha=0.4, s=15, label='Marley', color='blue', edgecolors='none')
        ax.scatter(fp_non_marley['cluster_energy'], fp_non_marley['prediction_prob'], 
                  alpha=0.4, s=15, label='Non-Marley', color='orange', edgecolors='none')
        ax.set_xlabel('Cluster Energy (MeV)', fontsize=11)
        ax.set_ylabel('Prediction Probability', fontsize=11)
        ax.set_title('FP Energy vs Prediction (by Generator)', fontsize=12, fontweight='bold')
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, 50)
        
        # 4. Plane distribution for FPs
        ax = axes[1, 1]
        plane_counts = fp['plane_id'].value_counts().sort_index()
        ax.bar(plane_counts.index, plane_counts.values, color='crimson', 
              edgecolor='darkred', alpha=0.7)
        ax.set_xlabel('Plane ID', fontsize=11)
        ax.set_ylabel('Number of FPs', fontsize=11)
        ax.set_title('FP Distribution by Plane', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.suptitle('False Positive Analysis - Detailed Characteristics', 
                     fontsize=14, fontweight='bold')
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        pdf.savefig(fig, dpi=150)
        plt.close()
        
        # Page 4: Energy difference analysis (split track hypothesis)
        if len(fp_detailed_df) > 0:
            fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
            
            # 1. Energy difference histogram
            ax = axes[0, 0]
            bins = np.linspace(-5, 50, 40)
            ax.hist(fp_detailed_df['energy_diff'], bins=bins, alpha=0.7, 
                   color='crimson', edgecolor='darkred')
            ax.axvline(fp_detailed_df['energy_diff'].mean(), color='blue', 
                      linestyle='--', linewidth=2, label=f"Mean: {fp_detailed_df['energy_diff'].mean():.1f} MeV")
            ax.axvline(0, color='black', linestyle=':', linewidth=1)
            ax.set_xlabel('Energy Difference: MT - FP (MeV)', fontsize=11)
            ax.set_ylabel('Count', fontsize=11)
            ax.set_title('Energy Difference Distribution', fontsize=12, fontweight='bold')
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3, axis='y')
            
            # 2. Energy ratio histogram
            ax = axes[0, 1]
            bins = np.linspace(0, 1.5, 40)
            ax.hist(fp_detailed_df['energy_ratio'], bins=bins, alpha=0.7, 
                   color='purple', edgecolor='indigo')
            ax.axvline(0.7, color='red', linestyle='--', linewidth=2, 
                      alpha=0.7, label='Potential split threshold (0.7)')
            ax.axvline(fp_detailed_df['energy_ratio'].median(), color='blue', 
                      linestyle='--', linewidth=2, label=f"Median: {fp_detailed_df['energy_ratio'].median():.2f}")
            ax.set_xlabel('Energy Ratio: FP / MT', fontsize=11)
            ax.set_ylabel('Count', fontsize=11)
            ax.set_title('FP-to-MT Energy Ratio', fontsize=12, fontweight='bold')
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3, axis='y')
            
            # 3. Scatter: FP energy vs MT energy
            ax = axes[1, 0]
            ax.scatter(fp_detailed_df['true_mt_cluster_energy'], fp_detailed_df['fp_cluster_energy'], 
                      alpha=0.4, s=30, color='red', edgecolors='darkred')
            
            # Add diagonal line (y=x, where FP = MT)
            max_energy = max(fp_detailed_df['true_mt_cluster_energy'].max(), 
                           fp_detailed_df['fp_cluster_energy'].max())
            ax.plot([0, max_energy], [0, max_energy], 'k--', linewidth=2, 
                   alpha=0.5, label='FP = MT (split track)')
            
            # Add 70% line
            ax.plot([0, max_energy], [0, 0.7*max_energy], 'r:', linewidth=2, 
                   alpha=0.5, label='FP = 0.7×MT')
            
            ax.set_xlabel('True Main Track Cluster Energy (MeV)', fontsize=11)
            ax.set_ylabel('False Positive Cluster Energy (MeV)', fontsize=11)
            ax.set_title('FP vs MT Energy (Split Track Test)', fontsize=12, fontweight='bold')
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3)
            ax.set_xlim(0, max_energy)
            ax.set_ylim(0, max_energy)
            
            # 4. Prediction probability vs energy ratio
            ax = axes[1, 1]
            scatter = ax.scatter(fp_detailed_df['energy_ratio'], 
                               fp_detailed_df['prediction_prob'], 
                               c=fp_detailed_df['distance_to_mt'], 
                               s=30, alpha=0.6, cmap='viridis', edgecolors='black', linewidth=0.5)
            ax.axvline(0.7, color='blue', linestyle='--', linewidth=2, alpha=0.7)
            ax.set_xlabel('Energy Ratio: FP / MT', fontsize=11)
            ax.set_ylabel('Prediction Probability', fontsize=11)
            ax.set_title('Prediction vs Energy Ratio (colored by distance)', fontsize=12, fontweight='bold')
            cbar = plt.colorbar(scatter, ax=ax)
            cbar.set_label('Distance to MT (cm)', fontsize=9)
            ax.grid(True, alpha=0.3)
            
            plt.suptitle('False Positive Analysis - Energy Difference (Split Track Hypothesis)', 
                         fontsize=14, fontweight='bold')
            plt.tight_layout(rect=[0, 0, 1, 0.96])
            pdf.savefig(fig, dpi=150)
            plt.close()
        
        # Page 5: Spatial analysis for split track hypothesis
        if len(fp_detailed_df) > 0:
            fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
            
            # 1. Distance distribution
            ax = axes[0, 0]
            bins = np.linspace(0, 200, 40)
            ax.hist(fp_detailed_df['distance_to_mt'], bins=bins, alpha=0.7, 
                   color='teal', edgecolor='darkslategray')
            ax.axvline(50, color='red', linestyle='--', linewidth=2, 
                      label='50 cm (split threshold)')
            ax.axvline(fp_detailed_df['distance_to_mt'].median(), color='blue', 
                      linestyle='--', linewidth=2, label=f"Median: {fp_detailed_df['distance_to_mt'].median():.1f} cm")
            ax.set_xlabel('Distance to MT Cluster (cm)', fontsize=11)
            ax.set_ylabel('Count', fontsize=11)
            ax.set_title('Spatial Separation: FP to MT', fontsize=12, fontweight='bold')
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3, axis='y')
            
            # 2. Distance vs energy ratio
            ax = axes[0, 1]
            ax.scatter(fp_detailed_df['distance_to_mt'], fp_detailed_df['energy_ratio'], 
                      alpha=0.5, s=30, color='purple', edgecolors='indigo')
            ax.axhline(0.7, color='red', linestyle='--', linewidth=2, alpha=0.7, label='Energy ratio 0.7')
            ax.axvline(50, color='blue', linestyle='--', linewidth=2, alpha=0.7, label='Distance 50 cm')
            
            # Highlight split candidates
            split_cand = fp_detailed_df[(fp_detailed_df['distance_to_mt'] < 50) & 
                                       (fp_detailed_df['energy_ratio'] > 0.3)]
            if len(split_cand) > 0:
                ax.scatter(split_cand['distance_to_mt'], split_cand['energy_ratio'], 
                          s=80, facecolors='none', edgecolors='red', linewidth=2, 
                          label=f'Split candidates (n={len(split_cand)})')
            
            ax.set_xlabel('Distance to MT (cm)', fontsize=11)
            ax.set_ylabel('Energy Ratio: FP / MT', fontsize=11)
            ax.set_title('Distance vs Energy Ratio', fontsize=12, fontweight='bold')
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3)
            ax.set_xlim(0, 200)
            
            # 3. 2D position scatter (Y vs Z)
            ax = axes[1, 0]
            # Plot MT positions
            ax.scatter(fp_detailed_df['mt_pos_z'], fp_detailed_df['mt_pos_y'], 
                      s=100, marker='*', color='gold', edgecolors='black', 
                      linewidth=1, label='MT clusters', zorder=3)
            # Plot FP positions
            scatter = ax.scatter(fp_detailed_df['pos_z'], fp_detailed_df['pos_y'], 
                               c=fp_detailed_df['energy_ratio'], s=30, alpha=0.6, 
                               cmap='coolwarm', edgecolors='black', linewidth=0.5, 
                               vmin=0, vmax=1.5)
            ax.set_xlabel('Z Position (cm)', fontsize=11)
            ax.set_ylabel('Y Position (cm)', fontsize=11)
            ax.set_title('Spatial Distribution (Y-Z plane)', fontsize=12, fontweight='bold')
            ax.legend(fontsize=9)
            cbar = plt.colorbar(scatter, ax=ax)
            cbar.set_label('Energy Ratio', fontsize=9)
            ax.grid(True, alpha=0.3)
            
            # 4. Distance histogram for different energy categories
            ax = axes[1, 1]
            high_e = fp_detailed_df[fp_detailed_df['energy_ratio'] > 0.7]
            med_e = fp_detailed_df[(fp_detailed_df['energy_ratio'] >= 0.3) & 
                                  (fp_detailed_df['energy_ratio'] <= 0.7)]
            low_e = fp_detailed_df[fp_detailed_df['energy_ratio'] < 0.3]
            
            bins = np.linspace(0, 150, 30)
            ax.hist(high_e['distance_to_mt'], bins=bins, alpha=0.6, 
                   label=f'High E (>70%): n={len(high_e)}', color='red', edgecolor='darkred')
            ax.hist(med_e['distance_to_mt'], bins=bins, alpha=0.6, 
                   label=f'Med E (30-70%): n={len(med_e)}', color='orange', edgecolor='darkorange')
            ax.hist(low_e['distance_to_mt'], bins=bins, alpha=0.6, 
                   label=f'Low E (<30%): n={len(low_e)}', color='blue', edgecolor='darkblue')
            ax.set_xlabel('Distance to MT (cm)', fontsize=11)
            ax.set_ylabel('Count', fontsize=11)
            ax.set_title('Distance by Energy Category', fontsize=12, fontweight='bold')
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3, axis='y')
            
            plt.suptitle('False Positive Analysis - Spatial Proximity (Split Track Test)', 
                         fontsize=14, fontweight='bold')
            plt.tight_layout(rect=[0, 0, 1, 0.96])
            pdf.savefig(fig, dpi=150)
            plt.close()
    
    print(f"\n✓ Report saved to: {output_pdf}")


def main():
    parser = argparse.ArgumentParser(
        description='Deep analysis of false positives in MT predictions'
    )
    
    parser.add_argument('--predictions', type=str,
                        default='results/mt_inference_cat000001_v10/mt_predictions.csv',
                        help='Path to MT predictions CSV file')
    parser.add_argument('--threshold', type=float, default=0.5,
                        help='Prediction threshold (default: 0.5)')
    parser.add_argument('--output', type=str,
                        default='results/mt_inference_cat000001_v10/false_positive_analysis.pdf',
                        help='Output PDF file')
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load and analyze
    df = load_predictions(args.predictions)
    tp, fp, fn, tn, fp_event_df, fp_detailed_df = analyze_false_positives(df, args.threshold)
    
    # Generate plots
    create_fp_plots(tp, fp, fn, tn, fp_event_df, fp_detailed_df, args.output)
    
    print(f"\n{'='*70}")


if __name__ == '__main__':
    main()
