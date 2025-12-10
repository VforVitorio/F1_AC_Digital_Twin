#!/usr/bin/env python3
"""
GMM Expert Training Script
Trains a Gaussian Mixture Model for one expert
"""

from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.mixture import GaussianMixture
import pickle
import json
import sys
import argparse

# Set random seed
SEED = 42
np.random.seed(SEED)

# Configuration
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / 'data' / 'processed' / 'MoE-anomaly'
SPLITS_DIR = DATA_DIR / 'splits'
SCALERS_DIR = DATA_DIR / 'scalers'
MODELS_DIR = ROOT / 'models' / 'anomaly-detection'
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Metadata columns to exclude from features
META_COLS = ['Timestamp', 'CompletedLaps', 'DistanceTraveled_m', 'Distance', 'CurrentSectorIndex', 'IsInPit']


def load_expert_data(expert_name, splits_dir):
    """Load train/val/test data for an expert."""
    splits = {}
    for split_name in ['train', 'val', 'test']:
        filepath = splits_dir / f"{expert_name}_{split_name}.csv"
        if not filepath.exists():
            raise FileNotFoundError(f"Data file not found: {filepath}")
        splits[split_name] = pd.read_csv(filepath)
        print(f"  Loaded {split_name}: {len(splits[split_name]):,} samples")

    return splits


def train_gmm_with_tuning(X_train, X_val, n_components_range=(2, 6)):
    """Train GMM models with different number of components."""
    results = []

    for n_components in range(n_components_range[0], n_components_range[1]):
        print(f"\n  Training GMM with {n_components} components...")

        # Train model
        gmm = GaussianMixture(
            n_components=n_components,
            covariance_type='full',
            random_state=SEED,
            max_iter=200,
            n_init=10
        )

        gmm.fit(X_train)

        # Compute metrics
        train_bic = gmm.bic(X_train)
        train_aic = gmm.aic(X_train)
        val_bic = gmm.bic(X_val)
        val_aic = gmm.aic(X_val)

        # Log likelihood
        train_ll = gmm.score(X_train)
        val_ll = gmm.score(X_val)

        results.append({
            'n_components': n_components,
            'model': gmm,
            'train_bic': train_bic,
            'train_aic': train_aic,
            'val_bic': val_bic,
            'val_aic': val_aic,
            'train_ll': train_ll,
            'val_ll': val_ll,
            'converged': gmm.converged_
        })

        print(f"    Val BIC: {val_bic:.2f}, Val AIC: {val_aic:.2f}, Converged: {gmm.converged_}")

    return results


def compute_anomaly_scores(gmm, X):
    """Compute anomaly scores as negative log-likelihood."""
    log_likelihood = gmm.score_samples(X)
    anomaly_scores = -log_likelihood
    return anomaly_scores


def train_expert(expert_name, n_components_range=(2, 6), threshold_percentile=95):
    """Train GMM for a single expert."""

    print("=" * 70)
    print(f"TRAINING GMM FOR {expert_name.upper()}")
    print("=" * 70)
    print(f"Expert: {expert_name}")
    print(f"Data directory: {SPLITS_DIR}")
    print(f"Models directory: {MODELS_DIR}")

    # Load data
    print("\n[1/6] Loading data...")
    data_splits = load_expert_data(expert_name, SPLITS_DIR)

    # Get feature columns
    FEATURE_COLS = [col for col in data_splits['train'].columns if col not in META_COLS]
    n_features = len(FEATURE_COLS)

    print(f"\n  Features: {n_features}")
    print(f"  Feature list: {FEATURE_COLS[:5]}...")  # Show first 5

    # Extract feature data
    X_train = data_splits['train'][FEATURE_COLS].values
    X_val = data_splits['val'][FEATURE_COLS].values
    X_test = data_splits['test'][FEATURE_COLS].values

    # Train GMM models
    print(f"\n[2/6] Training GMM models (components: {n_components_range[0]}-{n_components_range[1]-1})...")
    gmm_results = train_gmm_with_tuning(X_train, X_val, n_components_range)

    # Select best model
    print("\n[3/6] Selecting best model...")
    best_result = min(gmm_results, key=lambda x: x['val_bic'])
    best_gmm = best_result['model']
    best_n_components = best_result['n_components']

    print(f"\n  Best model:")
    print(f"    Components: {best_n_components}")
    print(f"    Val BIC: {best_result['val_bic']:.2f}")
    print(f"    Val AIC: {best_result['val_aic']:.2f}")
    print(f"    Converged: {best_result['converged']}")

    # Compute anomaly scores
    print("\n[4/6] Computing anomaly scores...")
    scores = {}
    for split_name, split_data in data_splits.items():
        X = split_data[FEATURE_COLS].values
        scores[split_name] = compute_anomaly_scores(best_gmm, X)
        print(f"  {split_name}: Mean={scores[split_name].mean():.3f}, Std={scores[split_name].std():.3f}")

    # Set threshold
    print(f"\n[5/6] Setting anomaly threshold ({threshold_percentile}th percentile)...")
    threshold = np.percentile(scores['train'], threshold_percentile)
    print(f"  Threshold: {threshold:.3f}")

    # Calculate anomaly rates
    print(f"\n  Anomaly rates:")
    for split_name, split_scores in scores.items():
        anomaly_rate = (split_scores > threshold).sum() / len(split_scores) * 100
        print(f"    {split_name}: {anomaly_rate:.2f}%")

    # Save model
    print("\n[6/6] Saving model and metadata...")

    # Save GMM model
    model_path = MODELS_DIR / f'gmm_{expert_name}.pkl'
    with open(model_path, 'wb') as f:
        pickle.dump(best_gmm, f)
    print(f"  [OK] Model saved: {model_path.name}")

    # Save metadata
    metadata = {
        'expert_name': expert_name,
        'n_components': int(best_n_components),
        'n_features': int(n_features),
        'features': FEATURE_COLS,
        'covariance_type': 'full',
        'threshold': float(threshold),
        'threshold_percentile': int(threshold_percentile),
        'metrics': {
            'train_bic': float(best_result['train_bic']),
            'val_bic': float(best_result['val_bic']),
            'train_aic': float(best_result['train_aic']),
            'val_aic': float(best_result['val_aic']),
        },
        'converged': bool(best_result['converged']),
        'train_samples': int(len(X_train)),
        'val_samples': int(len(X_val)),
        'test_samples': int(len(X_test)),
        'anomaly_rates': {
            split_name: float((split_scores > threshold).sum() / len(split_scores) * 100)
            for split_name, split_scores in scores.items()
        }
    }

    metadata_path = MODELS_DIR / f'gmm_{expert_name}_metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"  [OK] Metadata saved: {metadata_path.name}")

    # Final summary
    print("\n" + "=" * 70)
    print("TRAINING COMPLETE!")
    print("=" * 70)
    print(f"\n[OK] Expert: {expert_name}")
    print(f"[OK] Components: {best_n_components}")
    print(f"[OK] Features: {n_features}")
    print(f"[OK] Threshold: {threshold:.3f} ({threshold_percentile}th percentile)")
    print(f"[OK] Files saved:")
    print(f"     - {model_path}")
    print(f"     - {metadata_path}")

    return best_gmm, metadata


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(description='Train GMM expert for MoE anomaly detection')
    parser.add_argument(
        '--expert',
        type=str,
        required=True,
        choices=['expert1_tire', 'expert2_dynamics', 'expert3_control', 'expert4_power'],
        help='Expert to train'
    )
    parser.add_argument(
        '--min-components',
        type=int,
        default=2,
        help='Minimum number of GMM components to try (default: 2)'
    )
    parser.add_argument(
        '--max-components',
        type=int,
        default=6,
        help='Maximum number of GMM components to try (default: 6)'
    )
    parser.add_argument(
        '--threshold-percentile',
        type=int,
        default=95,
        help='Percentile for anomaly threshold (default: 95)'
    )

    args = parser.parse_args()

    # Train the expert
    try:
        train_expert(
            args.expert,
            n_components_range=(args.min_components, args.max_components),
            threshold_percentile=args.threshold_percentile
        )
    except Exception as e:
        print(f"\n[ERROR] Training failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
