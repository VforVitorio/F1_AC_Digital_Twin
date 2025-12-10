#!/usr/bin/env python3
"""
MoE Data Preparation Script
Prepares telemetry data for training with 46 features (20+16+6+4)
Variables with zero variance have been removed from Experts 3 and 4
"""

from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
import json
import pickle
import sys

# Set random seed for reproducibility
SEED = 42
np.random.seed(SEED)

# Configuration
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / 'data'
RAW_DIR = DATA_DIR / 'raw'
PROCESSED_DIR = DATA_DIR / 'processed' / 'MoE-anomaly'

# Input file - updated to latest telemetry (FIXED CSV with corrected tire temps)
INPUT_FILE = RAW_DIR / 'telemetry_2025-12-08_18-05-21_FIXED.csv'

# Create output directories
SPLITS_DIR = PROCESSED_DIR / 'splits'
SCALERS_DIR = PROCESSED_DIR / 'scalers'
FIGS_DIR = PROCESSED_DIR / 'figs'
METADATA_DIR = PROCESSED_DIR / 'metadata'

for dir_path in [SPLITS_DIR, SCALERS_DIR, FIGS_DIR, METADATA_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Split ratios
SPLIT_RATIOS = (0.70, 0.15, 0.15)  # train, val, test

# Expert 1: Tire Dynamics (20 features)
TIRE_FEATURES = [
    # Temperature (4 wheels)
    'TireTemp_FL_Avg', 'TireTemp_FR_Avg',
    'TireTemp_RL_Avg', 'TireTemp_RR_Avg',

    # Wear (4 wheels)
    'TireWear_FL', 'TireWear_FR',
    'TireWear_RL', 'TireWear_RR',

    # Pressure (4 wheels)
    'TirePressure_FL', 'TirePressure_FR',
    'TirePressure_RL', 'TirePressure_RR',

    # Slip Ratio (4 wheels)
    'SlipRatio_FL', 'SlipRatio_FR',
    'SlipRatio_RL', 'SlipRatio_RR',

    # Slip Angle (4 wheels)
    'SlipAngle_FL', 'SlipAngle_FR',
    'SlipAngle_RL', 'SlipAngle_RR',
]

# Expert 2: Vehicle Dynamics (16 features) - UPDATED
DYNAMICS_FEATURES = [
    # G-forces
    'AccG_Lateral', 'AccG_Vertical', 'AccG_Longitudinal',

    # Local velocities
    'LocalVelocity_X', 'LocalVelocity_Y', 'LocalVelocity_Z',

    # Angular velocities
    'AngularVel_X', 'AngularVel_Y', 'AngularVel_Z',

    # Orientation
    'Heading', 'Pitch', 'Roll',

    # Load distribution (ALL 4 wheels)
    'TireLoad_FL', 'TireLoad_FR', 'TireLoad_RL', 'TireLoad_RR',
]

# Expert 3: Driver Control (6 features) - UPDATED
# Note: TC_InAction, ABS_InAction, BrakeBias, and BrakeTemp variables removed due to zero variance
CONTROL_FEATURES = [
    # Basic controls (only variables with variance in telemetry data)
    'Speed_kmh', 'RPM', 'Throttle', 'Brake', 'Steering', 'Gear',
]

# Expert 4: Power Systems (4 features) - UPDATED
# Note: Fuel, EngineTemp_Oil, CurrentMaxRpm, EngineBrake, ERS_PowerLevel, ERS_RecoveryLevel removed (zero variance)
POWER_FEATURES = [
    'TurboBoost',
    'KERS_Charge', 'KERS_CurrentKJ',
    'DRS_Enabled',
]

# Metadata columns for context
META_COLS = ['Timestamp', 'CompletedLaps', 'DistanceTraveled_m', 'CurrentSectorIndex', 'IsInPit']

# All expert features combined
ALL_EXPERT_FEATURES = TIRE_FEATURES + DYNAMICS_FEATURES + CONTROL_FEATURES + POWER_FEATURES


def load_telemetry_data(file_path):
    """Load raw telemetry CSV file."""
    print(f"\nLoading telemetry data from {file_path.name}...")
    df = pd.read_csv(file_path)

    print(f"[OK] Loaded successfully")
    print(f"   Shape: {df.shape}")
    print(f"   Columns: {len(df.columns)}")
    print(f"   Memory: {df.memory_usage(deep=True).sum() / 1024**2:.1f} MB")

    return df


def check_feature_availability(df, feature_lists):
    """Check if all required features exist in dataframe."""
    available_cols = set(df.columns)
    missing = {}

    for expert_name, features in feature_lists.items():
        missing_feats = [f for f in features if f not in available_cols]
        if missing_feats:
            missing[expert_name] = missing_feats

    return missing


def clean_data(df, feature_cols):
    """Clean data: handle missing values and infinities."""
    df_clean = df.copy()

    # Replace infinities with NaN
    df_clean[feature_cols] = df_clean[feature_cols].replace([np.inf, -np.inf], np.nan)

    # Fill missing values with forward fill, then backward fill
    df_clean[feature_cols] = df_clean[feature_cols].ffill().bfill()

    # If still NaN, fill with column mean
    df_clean[feature_cols] = df_clean[feature_cols].fillna(df_clean[feature_cols].mean())

    return df_clean


def split_by_laps(df, split_ratios=(0.7, 0.15, 0.15), seed=42):
    """Split data by complete laps to avoid data leakage."""
    # Get unique laps
    unique_laps = df['CompletedLaps'].unique()
    n_laps = len(unique_laps)

    # Shuffle laps
    np.random.seed(seed)
    shuffled_laps = np.random.permutation(unique_laps)

    # Calculate split indices
    n_train = int(n_laps * split_ratios[0])
    n_val = int(n_laps * split_ratios[1])

    # Split laps
    train_laps = shuffled_laps[:n_train]
    val_laps = shuffled_laps[n_train:n_train + n_val]
    test_laps = shuffled_laps[n_train + n_val:]

    # Create splits
    splits = {
        'train': df[df['CompletedLaps'].isin(train_laps)].copy(),
        'val': df[df['CompletedLaps'].isin(val_laps)].copy(),
        'test': df[df['CompletedLaps'].isin(test_laps)].copy()
    }

    # Summary
    print("\n" + "=" * 60)
    print("DATA SPLIT SUMMARY")
    print("=" * 60)
    for split_name, split_df in splits.items():
        n_laps_split = split_df['CompletedLaps'].nunique()
        pct = n_laps_split / n_laps * 100
        print(f"\n{split_name.upper()}:")
        print(f"  Laps: {n_laps_split} ({pct:.1f}%)")
        print(f"  Samples: {len(split_df):,}")

    return splits


def prepare_expert_data(splits, feature_cols, expert_name):
    """Extract and normalize features for a specific expert."""
    print(f"\nPreparing data for {expert_name}...")

    # Extract features
    expert_splits = {}
    for split_name, df in splits.items():
        # Check which metadata columns exist
        available_meta = [col for col in META_COLS if col in df.columns]
        expert_splits[split_name] = df[feature_cols + available_meta].copy()

    # Fit scaler on training data
    scaler = StandardScaler()
    scaler.fit(expert_splits['train'][feature_cols])

    # Transform all splits
    for split_name in expert_splits.keys():
        scaled_features = scaler.transform(expert_splits[split_name][feature_cols])

        scaled_df = pd.DataFrame(
            scaled_features,
            columns=feature_cols,
            index=expert_splits[split_name].index
        )

        # Add metadata columns
        for meta_col in available_meta:
            scaled_df[meta_col] = expert_splits[split_name][meta_col].values

        expert_splits[split_name] = scaled_df

    print(f"  [OK] Processed {len(feature_cols)} features")

    return expert_splits, scaler


def main():
    """Main execution function."""
    print("=" * 70)
    print("MoE DATA PREPARATION - 46 FEATURES")
    print("=" * 70)
    print(f"\nInput file: {INPUT_FILE}")
    print(f"Output directory: {PROCESSED_DIR}")
    print(f"Split ratios: {SPLIT_RATIOS}")

    # Validate input file
    if not INPUT_FILE.exists():
        print(f"\n[ERROR] Input file not found: {INPUT_FILE}")
        sys.exit(1)

    # Load data
    df_raw = load_telemetry_data(INPUT_FILE)

    # Feature counts
    print("\n" + "=" * 60)
    print("FEATURE COUNTS")
    print("=" * 60)
    print(f"Expert 1 (Tire): {len(TIRE_FEATURES)} features")
    print(f"Expert 2 (Dynamics): {len(DYNAMICS_FEATURES)} features")
    print(f"Expert 3 (Control): {len(CONTROL_FEATURES)} features")
    print(f"Expert 4 (Power): {len(POWER_FEATURES)} features")
    print(f"Total: {len(ALL_EXPERT_FEATURES)} features")

    # Check feature availability
    feature_lists = {
        'Expert 1 (Tire)': TIRE_FEATURES,
        'Expert 2 (Dynamics)': DYNAMICS_FEATURES,
        'Expert 3 (Control)': CONTROL_FEATURES,
        'Expert 4 (Power)': POWER_FEATURES,
    }

    missing_features = check_feature_availability(df_raw, feature_lists)

    if missing_features:
        print("\n[ERROR] Missing features:")
        for expert, feats in missing_features.items():
            print(f"\n{expert}:")
            for f in feats:
                print(f"  - {f}")
        sys.exit(1)
    else:
        print("\n[OK] All required features are available")

    # Clean data
    print("\nCleaning data...")
    df_clean = clean_data(df_raw, ALL_EXPERT_FEATURES)
    print(f"[OK] Data cleaned. Remaining NaN values: {df_clean[ALL_EXPERT_FEATURES].isna().sum().sum()}")

    # Create splits
    splits = split_by_laps(df_clean, SPLIT_RATIOS, SEED)

    # Prepare data for all experts
    expert_data = {}
    scalers = {}

    expert_data['expert1_tire'], scalers['expert1_tire'] = prepare_expert_data(
        splits, TIRE_FEATURES, 'Expert 1 (Tire Dynamics)'
    )

    expert_data['expert2_dynamics'], scalers['expert2_dynamics'] = prepare_expert_data(
        splits, DYNAMICS_FEATURES, 'Expert 2 (Vehicle Dynamics)'
    )

    expert_data['expert3_control'], scalers['expert3_control'] = prepare_expert_data(
        splits, CONTROL_FEATURES, 'Expert 3 (Driver Control)'
    )

    expert_data['expert4_power'], scalers['expert4_power'] = prepare_expert_data(
        splits, POWER_FEATURES, 'Expert 4 (Power Systems)'
    )

    # Save expert splits
    print("\n" + "=" * 60)
    print("SAVING PROCESSED DATA")
    print("=" * 60)

    for expert_name, expert_splits in expert_data.items():
        print(f"\n{expert_name}:")
        for split_name, df in expert_splits.items():
            filename = f"{expert_name}_{split_name}.csv"
            filepath = SPLITS_DIR / filename
            df.to_csv(filepath, index=False)
            print(f"  [OK] Saved {filename} ({len(df):,} samples)")

    # Save scalers
    print("\nSaving scalers:")

    for expert_name, scaler in scalers.items():
        filename = f"scaler_{expert_name}.pkl"
        filepath = SCALERS_DIR / filename

        with open(filepath, 'wb') as f:
            pickle.dump(scaler, f)

        n_features = scaler.n_features_in_
        print(f"  [OK] Saved {filename} ({n_features} features)")

    # Save metadata
    metadata = {
        'input_file': str(INPUT_FILE.name),
        'total_samples': len(df_clean),
        'split_ratios': SPLIT_RATIOS,
        'seed': SEED,
        'features': {
            'expert1_tire': TIRE_FEATURES,
            'expert2_dynamics': DYNAMICS_FEATURES,
            'expert3_control': CONTROL_FEATURES,
            'expert4_power': POWER_FEATURES
        },
        'feature_counts': {
            'expert1_tire': len(TIRE_FEATURES),
            'expert2_dynamics': len(DYNAMICS_FEATURES),
            'expert3_control': len(CONTROL_FEATURES),
            'expert4_power': len(POWER_FEATURES),
            'total': len(ALL_EXPERT_FEATURES)
        }
    }

    metadata_file = METADATA_DIR / 'preparation_metadata.json'
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"\n[OK] Saved metadata: {metadata_file.name}")

    # Final summary
    print("\n" + "=" * 70)
    print("DATA PREPARATION COMPLETE!")
    print("=" * 70)
    print(f"\n[OK] Total features: {len(ALL_EXPERT_FEATURES)}")
    print(f"   - Expert 1 (Tire): {len(TIRE_FEATURES)} features")
    print(f"   - Expert 2 (Dynamics): {len(DYNAMICS_FEATURES)} features")
    print(f"   - Expert 3 (Control): {len(CONTROL_FEATURES)} features")
    print(f"   - Expert 4 (Power): {len(POWER_FEATURES)} features")
    print(f"\n[OK] Data splits saved to: {SPLITS_DIR}")
    print(f"[OK] Scalers saved to: {SCALERS_DIR}")
    print(f"\nReady for GMM training!")


if __name__ == "__main__":
    main()
