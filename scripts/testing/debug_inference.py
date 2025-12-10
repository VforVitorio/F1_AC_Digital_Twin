#!/usr/bin/env python3
"""Debug MoE inference step by step"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import pickle
import logging

# Set DEBUG logging
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from src.feature_processor import RealTimeFeatureExtractor

# Paths
scalers_dir = ROOT / 'data' / 'processed' / 'MoE-anomaly' / 'scalers'
models_dir = ROOT / 'models' / 'anomaly-detection'
input_csv = ROOT / 'data' / 'raw' / 'telemetry_2025-12-08_18-05-21_FIXED.csv'

print("="*70)
print("DEBUG MoE INFERENCE")
print("="*70)

# Load test sample
print("\n[1] Loading test sample...")
df = pd.read_csv(input_csv, nrows=1)
telemetry = df.iloc[0].to_dict()
print(f"[OK] Loaded sample with {len(telemetry)} fields")
print(f"  TireTemp_FL_Avg: {telemetry.get('TireTemp_FL_Avg', 'N/A')}")
print(f"  TireTemp_FR_Avg: {telemetry.get('TireTemp_FR_Avg', 'N/A')}")
print(f"  TireTemp_RL_Avg: {telemetry.get('TireTemp_RL_Avg', 'N/A')}")
print(f"  TireTemp_RR_Avg: {telemetry.get('TireTemp_RR_Avg', 'N/A')}")

# Initialize feature extractor
print("\n[2] Initializing feature extractor...")
feature_extractor = RealTimeFeatureExtractor(str(scalers_dir))
print("[OK] Feature extractor initialized")

# Process telemetry
print("\n[3] Processing telemetry...")
try:
    normalized_features = feature_extractor.process(telemetry)
    print("[OK] Features extracted and normalized")

    for expert_name, features in normalized_features.items():
        print(f"\n  {expert_name}:")
        print(f"    Shape: {features.shape}")
        print(f"    First 4 values: {features[:4]}")
        print(f"    Min: {features.min():.6f}, Max: {features.max():.6f}")
        print(f"    Mean: {features.mean():.6f}, Std: {features.std():.6f}")

        # Check for NaN or Inf
        if np.isnan(features).any():
            print(f"    [WARNING] Contains NaN values!")
        if np.isinf(features).any():
            print(f"    [WARNING] Contains Inf values!")

except Exception as e:
    print(f"[ERROR] Feature processing failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Load GMM Expert 1
print("\n[4] Loading GMM Expert 1...")
gmm_path = models_dir / 'gmm_expert1_tire.pkl'
with open(gmm_path, 'rb') as f:
    gmm = pickle.load(f)
print(f"[OK] GMM loaded ({gmm.n_components} components)")

# Test GMM scoring
print("\n[5] Testing GMM scoring...")
expert1_features = normalized_features['expert1_tire']
print(f"  Features shape: {expert1_features.shape}")
print(f"  Features dtype: {expert1_features.dtype}")

# Reshape to 2D if needed
if expert1_features.ndim == 1:
    expert1_features_2d = expert1_features.reshape(1, -1)
else:
    expert1_features_2d = expert1_features

print(f"  Reshaped to: {expert1_features_2d.shape}")

try:
    log_likelihood = gmm.score_samples(expert1_features_2d)[0]
    anomaly_score = -log_likelihood

    print(f"\n  Log-likelihood: {log_likelihood:.6f}")
    print(f"  Anomaly score (negative log-likelihood): {anomaly_score:.6f}")

    # Compare with threshold
    with open(models_dir / 'gmm_expert1_tire_metadata.json', 'r') as f:
        import json
        metadata = json.load(f)
        threshold = metadata['threshold']

    print(f"  Threshold: {threshold:.6f}")
    print(f"  Is anomaly: {anomaly_score > threshold}")

except Exception as e:
    print(f"[ERROR] GMM scoring failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
