#!/usr/bin/env python3
"""Inspect GMM Expert 1 model"""

import pickle
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
models_dir = ROOT / 'models' / 'anomaly-detection'

# Load GMM Expert 1
gmm_path = models_dir / 'gmm_expert1_tire.pkl'
with open(gmm_path, 'rb') as f:
    gmm = pickle.load(f)

print("="*70)
print("GMM EXPERT 1 (TIRE) INSPECTION")
print("="*70)

print(f"\nModel properties:")
print(f"  Components: {gmm.n_components}")
print(f"  Converged: {gmm.converged_}")
print(f"  Covariance type: {gmm.covariance_type}")
print(f"  Means shape: {gmm.means_.shape}")
print(f"  Covariances shape: {gmm.covariances_.shape}")

print(f"\nComponent 0 statistics:")
print(f"  Mean (first 4 features): {gmm.means_[0][:4]}")

# Check covariance matrix
cov = gmm.covariances_[0]
print(f"  Covariance shape: {cov.shape}")

# Compute determinant
det = np.linalg.det(cov)
print(f"  Covariance determinant: {det:.6e}")

if det > 0:
    log_det = np.log(det)
    print(f"  Log determinant: {log_det:.6f}")
else:
    print(f"  [WARNING] Determinant is non-positive!")

# Compute condition number
cond = np.linalg.cond(cov)
print(f"  Condition number: {cond:.6e}")

if cond > 1e10:
    print(f"  [WARNING] Matrix is ill-conditioned!")

# Check eigenvalues
eigenvalues = np.linalg.eigvalsh(cov)
print(f"  Eigenvalues (min/max): {eigenvalues.min():.6e} / {eigenvalues.max():.6e}")

if eigenvalues.min() < 1e-10:
    print(f"  [WARNING] Near-singular covariance matrix!")

# Test score_samples with a simple test point
print(f"\nTesting score_samples:")
test_point = np.zeros((1, 20))  # Zero vector
try:
    score = gmm.score_samples(test_point)
    print(f"  Score for zero vector: {score[0]:.6f}")
except Exception as e:
    print(f"  [ERROR] score_samples failed: {e}")

# Test with mean of component 0
test_point2 = gmm.means_[0].reshape(1, -1)
try:
    score2 = gmm.score_samples(test_point2)
    print(f"  Score for component 0 mean: {score2[0]:.6f}")
except Exception as e:
    print(f"  [ERROR] score_samples failed: {e}")

print("\n" + "="*70)
