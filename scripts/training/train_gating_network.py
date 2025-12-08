#!/usr/bin/env python3
"""
MoE Gating Network Training Script
Trains the gating network to combine predictions from all expert models
"""

from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
import pickle
import json
import sys

# Set random seed
SEED = 42
np.random.seed(SEED)

# Configuration
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / 'data' / 'processed' / 'MoE-anomaly'
SPLITS_DIR = DATA_DIR / 'splits'
MODELS_DIR = ROOT / 'models' / 'anomaly-detection'

# Expert names
EXPERT_NAMES = ['expert1_tire', 'expert2_dynamics', 'expert3_control', 'expert4_power']

# Metadata columns
META_COLS = ['Timestamp', 'CompletedLaps', 'DistanceTraveled_m', 'Distance', 'CurrentSectorIndex', 'IsInPit']


def load_expert_data(expert_name, splits_dir):
    """Load train/val/test data for an expert."""
    splits = {}
    for split_name in ['train', 'val', 'test']:
        filepath = splits_dir / f"{expert_name}_{split_name}.csv"
        if not filepath.exists():
            raise FileNotFoundError(f"Data file not found: {filepath}")
        splits[split_name] = pd.read_csv(filepath)
    return splits


def compute_expert_scores(gmm, data, feature_cols):
    """Compute anomaly scores (negative log-likelihood)."""
    X = data[feature_cols].values
    log_likelihood = gmm.score_samples(X)
    return -log_likelihood


def create_gating_features(expert_scores_dict):
    """Create features for learned gating network."""
    scores_array = np.stack(list(expert_scores_dict.values()), axis=1)

    # Basic features: raw scores
    features = scores_array

    # Additional features: relative scores
    score_means = scores_array.mean(axis=1, keepdims=True)
    relative_scores = scores_array - score_means

    # Combine features
    features = np.concatenate([scores_array, relative_scores], axis=1)

    return features


def create_labels(expert_scores_dict, thresholds_dict):
    """Create binary labels: 1 if anomaly detected by any expert."""
    labels = np.zeros(len(list(expert_scores_dict.values())[0]), dtype=bool)

    for expert_name, scores in expert_scores_dict.items():
        threshold = thresholds_dict[expert_name]
        # Anomaly scores are -log_likelihood, so higher = more anomalous
        labels |= (scores > threshold)

    return labels.astype(int)


def uniform_gating(expert_scores):
    """Uniform gating: average all expert scores equally."""
    scores_array = np.stack(list(expert_scores.values()), axis=1)
    return scores_array.mean(axis=1)


def confidence_gating(expert_scores, temperature=10.0):
    """Confidence-based gating: weight experts by softmax of their scores."""
    scores_array = np.stack(list(expert_scores.values()), axis=1)

    # Compute softmax weights
    exp_scores = np.exp(scores_array / temperature)
    weights = exp_scores / exp_scores.sum(axis=1, keepdims=True)

    # Weighted average
    combined = (scores_array * weights).sum(axis=1)

    return combined, weights


def train_gating_network():
    """Train the MoE gating network."""

    print("=" * 70)
    print("TRAINING MOE GATING NETWORK")
    print("=" * 70)
    print(f"Models directory: {MODELS_DIR}")
    print(f"Data directory: {SPLITS_DIR}")

    # Load expert models and metadata
    print("\n[1/6] Loading expert models...")
    experts = {}
    thresholds = {}
    metadata = {}

    for expert_name in EXPERT_NAMES:
        # Load model
        model_path = MODELS_DIR / f'gmm_{expert_name}.pkl'
        if not model_path.exists():
            raise FileNotFoundError(f"Expert model not found: {model_path}")

        with open(model_path, 'rb') as f:
            experts[expert_name] = pickle.load(f)

        # Load metadata
        metadata_path = MODELS_DIR / f'gmm_{expert_name}_metadata.json'
        with open(metadata_path, 'r') as f:
            metadata[expert_name] = json.load(f)
            thresholds[expert_name] = metadata[expert_name]['threshold']

        print(f"  [OK] {expert_name}: {experts[expert_name].n_components} components, "
              f"threshold={thresholds[expert_name]:.3f}")

    # Load data and compute scores
    print("\n[2/6] Loading data and computing expert scores...")
    expert_data = {}

    for expert_name in EXPERT_NAMES:
        print(f"\n  Processing {expert_name}...")

        # Load data splits
        data_splits = load_expert_data(expert_name, SPLITS_DIR)

        # Get feature columns
        feature_cols = [col for col in data_splits['train'].columns if col not in META_COLS]

        # Compute scores
        expert_data[expert_name] = {
            'train_scores': compute_expert_scores(experts[expert_name], data_splits['train'], feature_cols),
            'val_scores': compute_expert_scores(experts[expert_name], data_splits['val'], feature_cols),
            'test_scores': compute_expert_scores(experts[expert_name], data_splits['test'], feature_cols)
        }

        print(f"    Train: {len(expert_data[expert_name]['train_scores']):,} samples")
        print(f"    Val: {len(expert_data[expert_name]['val_scores']):,} samples")
        print(f"    Test: {len(expert_data[expert_name]['test_scores']):,} samples")

    # Compute uniform gating baseline
    print("\n[3/6] Computing uniform gating baseline...")
    uniform_train_scores = uniform_gating({
        name: expert_data[name]['train_scores'] for name in experts.keys()
    })
    uniform_val_scores = uniform_gating({
        name: expert_data[name]['val_scores'] for name in experts.keys()
    })
    uniform_test_scores = uniform_gating({
        name: expert_data[name]['test_scores'] for name in experts.keys()
    })

    uniform_threshold = np.percentile(uniform_train_scores, 95)

    print(f"  Uniform threshold (95th percentile): {uniform_threshold:.3f}")
    print(f"  Train: mean={uniform_train_scores.mean():.3f}, std={uniform_train_scores.std():.3f}")
    print(f"  Val: mean={uniform_val_scores.mean():.3f}, std={uniform_val_scores.std():.3f}")
    print(f"  Test: mean={uniform_test_scores.mean():.3f}, std={uniform_test_scores.std():.3f}")

    # Compute confidence-based gating
    print("\n[4/6] Computing confidence-based gating...")
    conf_train_scores, conf_train_weights = confidence_gating({
        name: expert_data[name]['train_scores'] for name in experts.keys()
    })
    conf_val_scores, _ = confidence_gating({
        name: expert_data[name]['val_scores'] for name in experts.keys()
    })
    conf_test_scores, _ = confidence_gating({
        name: expert_data[name]['test_scores'] for name in experts.keys()
    })

    conf_threshold = np.percentile(conf_train_scores, 95)

    print(f"  Confidence threshold (95th percentile): {conf_threshold:.3f}")
    print(f"  Train: mean={conf_train_scores.mean():.3f}, std={conf_train_scores.std():.3f}")
    print(f"  Val: mean={conf_val_scores.mean():.3f}, std={conf_val_scores.std():.3f}")
    print(f"  Test: mean={conf_test_scores.mean():.3f}, std={conf_test_scores.std():.3f}")

    print(f"\n  Average expert weights (train):")
    for i, name in enumerate(experts.keys()):
        print(f"    {name}: {conf_train_weights[:, i].mean():.3f}")

    # Train learned gating network
    print("\n[5/6] Training learned gating network...")

    # Prepare training data
    X_gating_train = create_gating_features({
        name: expert_data[name]['train_scores'] for name in experts.keys()
    })
    y_gating_train = create_labels({
        name: expert_data[name]['train_scores'] for name in experts.keys()
    }, thresholds)

    X_gating_val = create_gating_features({
        name: expert_data[name]['val_scores'] for name in experts.keys()
    })
    y_gating_val = create_labels({
        name: expert_data[name]['val_scores'] for name in experts.keys()
    }, thresholds)

    X_gating_test = create_gating_features({
        name: expert_data[name]['test_scores'] for name in experts.keys()
    })
    y_gating_test = create_labels({
        name: expert_data[name]['test_scores'] for name in experts.keys()
    }, thresholds)

    print(f"  Gating features shape: {X_gating_train.shape}")
    print(f"  Anomaly rate - Train: {y_gating_train.mean()*100:.2f}%")
    print(f"  Anomaly rate - Val: {y_gating_val.mean()*100:.2f}%")
    print(f"  Anomaly rate - Test: {y_gating_test.mean()*100:.2f}%")

    # Train logistic regression
    gating_model = LogisticRegression(
        random_state=SEED,
        max_iter=1000,
        class_weight='balanced'
    )

    gating_model.fit(X_gating_train, y_gating_train)

    # Evaluate
    train_pred = gating_model.predict(X_gating_train)
    val_pred = gating_model.predict(X_gating_val)
    test_pred = gating_model.predict(X_gating_test)

    train_acc = (train_pred == y_gating_train).mean()
    val_acc = (val_pred == y_gating_val).mean()
    test_acc = (test_pred == y_gating_test).mean()

    print(f"\n  Learned gating performance:")
    print(f"    Train accuracy: {train_acc*100:.2f}%")
    print(f"    Val accuracy: {val_acc*100:.2f}%")
    print(f"    Test accuracy: {test_acc*100:.2f}%")

    # Feature importances
    print(f"\n  Learned feature importances:")
    feature_names = [f"{name}_score" for name in experts.keys()] + \
                    [f"{name}_relative" for name in experts.keys()]
    for feat, coef in zip(feature_names, gating_model.coef_[0]):
        print(f"    {feat}: {coef:.4f}")

    # Save gating network
    print("\n[6/6] Saving gating network and configuration...")

    with open(MODELS_DIR / 'gating_network.pkl', 'wb') as f:
        pickle.dump(gating_model, f)
    print(f"  [OK] Gating model saved: gating_network.pkl")

    # Create MoE configuration
    moe_config = {
        'experts': EXPERT_NAMES,
        'n_experts': len(EXPERT_NAMES),
        'expert_models': {name: f'gmm_{name}.pkl' for name in EXPERT_NAMES},
        'gating_model': 'gating_network.pkl',
        'thresholds': {k: float(v) for k, v in thresholds.items()},
        'gating_strategy': 'learned',
        'uniform_threshold': float(uniform_threshold),
        'confidence_threshold': float(conf_threshold),
        'metrics': {
            'uniform_gating': {
                'train_mean': float(uniform_train_scores.mean()),
                'val_mean': float(uniform_val_scores.mean()),
                'test_mean': float(uniform_test_scores.mean())
            },
            'confidence_gating': {
                'train_mean': float(conf_train_scores.mean()),
                'val_mean': float(conf_val_scores.mean()),
                'test_mean': float(conf_test_scores.mean())
            },
            'learned_gating': {
                'train_accuracy': float(train_acc),
                'val_accuracy': float(val_acc),
                'test_accuracy': float(test_acc)
            }
        }
    }

    with open(MODELS_DIR / 'moe_config.json', 'w') as f:
        json.dump(moe_config, f, indent=2)
    print(f"  [OK] Configuration saved: moe_config.json")

    # Final summary
    print("\n" + "=" * 70)
    print("GATING NETWORK TRAINING COMPLETE!")
    print("=" * 70)
    print(f"\n[OK] Number of experts: {moe_config['n_experts']}")
    print(f"[OK] Gating strategy: {moe_config['gating_strategy']}")
    print(f"[OK] Learned gating accuracy: {test_acc*100:.2f}%")
    print(f"\n[OK] Experts:")
    for expert in moe_config['experts']:
        print(f"     - {expert}")
    print(f"\n[OK] Files saved:")
    print(f"     - {MODELS_DIR / 'gating_network.pkl'}")
    print(f"     - {MODELS_DIR / 'moe_config.json'}")


def main():
    """Main execution."""
    try:
        train_gating_network()
    except Exception as e:
        print(f"\n[ERROR] Training failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
