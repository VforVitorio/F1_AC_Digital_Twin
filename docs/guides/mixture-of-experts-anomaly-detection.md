# Mixture of Experts + Anomaly Detection System

## Implementation Plan for F1 Telemetry Analysis

**Author**: Claude
**Date**: 2025-12-06
**Status**: Planning Phase

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Expert Specifications](#expert-specifications)
4. [Implementation Plan](#implementation-plan)
5. [Technical Details](#technical-details)
6. [Evaluation Strategy](#evaluation-strategy)
7. [Next Steps](#next-steps)

---

## Overview

### Objective

Design and implement a Mixture of Experts (MoE) system with Gaussian Mixture Models (GMM) for detecting anomalies in F1 telemetry data.

### Motivation

- **156 telemetry variables** available - too many for a single model
- **Different subsystems** (tires, dynamics, control, power) have distinct behaviors
- **Specialized experts** can detect domain-specific anomalies better than general models
- **Interpretability**: Each expert provides insights into specific failure modes

### Key Benefits

1. **Specialized detection**: Each expert focuses on its domain
2. **Scalability**: Add/remove experts without affecting others
3. **Interpretability**: Know which subsystem has anomalies
4. **Efficiency**: Process only relevant features per expert

---

## System Architecture

### High-Level Design

```
                          ┌─────────────────┐
                          │  Raw Telemetry  │
                          │   (156 vars)    │
                          └────────┬────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │      Gating Network         │
                    │  (Context-based routing)    │
                    └──────────────┬──────────────┘
                                   │
            ┌──────────┬───────────┼───────────┬──────────┐
            │          │           │           │          │
      ┌─────▼────┐ ┌──▼────┐ ┌────▼────┐ ┌────▼─────┐   │
      │ Expert 1 │ │Expert 2│ │Expert 3 │ │ Expert 4 │   │
      │  Tire    │ │Dynamics│ │ Control │ │  Power   │   │
      │ Dynamics │ │Vehicle │ │ Driver  │ │ Systems  │   │
      └─────┬────┘ └──┬─────┘ └────┬────┘ └────┬─────┘   │
            │         │            │           │          │
            │    ┌────▼────────────▼───────────▼────┐     │
            │    │      GMM Anomaly Detectors       │     │
            │    │  (3-5 components per expert)     │     │
            │    └────┬─────────────────────────────┘     │
            │         │                                    │
            └─────────▼────────────────────────────────────┘
                      │
              ┌───────▼────────┐
              │  Anomaly Score │
              │  + Expert ID   │
              └────────────────┘
```

### Component Breakdown

#### 1. Gating Network

- **Input**: Speed, Distance, CurrentSectorIndex, IsInPit
- **Output**: Expert weights (which expert(s) to activate)
- **Architecture**: Simple MLP or rule-based
- **Purpose**: Route telemetry to appropriate expert(s)

#### 2. Expert Networks (4 specialized)

- Each expert focuses on a subsystem
- Independent GMM for each expert
- Outputs anomaly score in [0, 1]

#### 3. Aggregation Layer

- Combines expert outputs
- Weighted by gating network
- Final anomaly score + expert attribution

---

## Expert Specifications

### Expert 1: Tire Dynamics Expert

**Responsibility**: Detect tire-related anomalies

**Input Features (20 variables)**:

```python
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

    # Slip (4 wheels)
    'SlipRatio_FL', 'SlipRatio_FR',
    'SlipRatio_RL', 'SlipRatio_RR',

    # Slip angle (4 wheels)
    'SlipAngle_FL', 'SlipAngle_FR',
    'SlipAngle_RL', 'SlipAngle_RR',
]
```

**Anomalies Detected**:

- Overheating (TireTemp > threshold)
- Uneven wear between wheels
- Pressure loss
- Excessive slip (loss of traction)
- Lock-up during braking

**GMM Configuration**:

- **N components**: 4
  - Component 1: Straight line (low slip, even temps)
  - Component 2: Normal cornering (moderate slip)
  - Component 3: Hard braking (high slip, temp rise)
  - Component 4: Tire degradation (high wear, pressure drop)

---

### Expert 2: Vehicle Dynamics Expert

**Responsibility**: Detect vehicle physics anomalies

**Input Features (15 variables)**:

```python
DYNAMICS_FEATURES = [
    # G-forces
    'AccG_Lateral', 'AccG_Vertical', 'AccG_Longitudinal',

    # Local velocities
    'LocalVelocity_X', 'LocalVelocity_Y', 'LocalVelocity_Z',

    # Angular velocities
    'AngularVel_X', 'AngularVel_Y', 'AngularVel_Z',

    # Orientation
    'Heading', 'Pitch', 'Roll',

    # Load distribution
    'TireLoad_FL', 'TireLoad_FR',
    'TireLoad_RL', 'TireLoad_RR',
]
```

**Anomalies Detected**:

- Impossible G-forces (crash/collision)
- Loss of downforce
- Spin/trompo (high AngularVel_Z)
- Airborne (TireLoad all near zero)
- Weight transfer issues

**GMM Configuration**:

- **N components**: 5
  - Component 1: Straight (low lateral G)
  - Component 2: Braking (high longitudinal G)
  - Component 3: Cornering (high lateral G)
  - Component 4: Combined (braking + turning)
  - Component 5: Transition zones

---

### Expert 3: Driver Control Expert

**Responsibility**: Detect driver input anomalies

**Input Features (12 variables)**:

```python
CONTROL_FEATURES = [
    # Basic controls
    'Speed_kmh', 'RPM', 'Throttle', 'Brake', 'Steering', 'Gear',

    # Assist systems
    'TC_InAction', 'ABS_InAction',

    # Brake system
    'BrakeBias',
    'BrakeTemp_FL', 'BrakeTemp_FR', 'BrakeTemp_RL', 'BrakeTemp_RR',
]
```

**Anomalies Detected**:

- Throttle + Brake simultaneous
- Wrong gear for RPM
- Braking in unexpected locations
- Over-steering
- TC/ABS constantly active (poor driving)
- Brake fade (overheating)

**GMM Configuration**:

- **N components**: 3
  - Component 1: Acceleration (high throttle, low brake)
  - Component 2: Coasting (medium throttle, no brake)
  - Component 3: Braking (no throttle, high brake)

---

### Expert 4: Power Systems Expert

**Responsibility**: Detect power unit & ERS anomalies

**Input Features (10 variables)**:

```python
POWER_FEATURES = [
    # Engine
    'Fuel', 'TurboBoost', 'EngineTemp_Oil',
    'CurrentMaxRpm', 'EngineBrake',

    # KERS/ERS
    'KERS_Charge', 'KERS_CurrentKJ',
    'ERS_PowerLevel', 'ERS_RecoveryLevel',

    # DRS
    'DRS_Enabled',
]
```

**Anomalies Detected**:

- Suboptimal ERS usage
- DRS deployed in corner (dangerous)
- Engine overheating
- Abnormal fuel consumption
- KERS depletion at wrong time

**GMM Configuration**:

- **N components**: 3
  - Component 1: Deployment (using KERS/ERS)
  - Component 2: Recovery (harvesting energy)
  - Component 3: Neutral (coasting)

---

## Implementation Plan

### Phase 1: Data Preparation

**Tasks**:

1. Load telemetry CSV with all 156 variables
2. Feature selection per expert
3. Data cleaning & normalization
4. Split by lap_id (train/val/test)

**Deliverables**:

- `data/processed/MoE-anomaly/train_expert{1-4}.csv`
- `data/processed/MoE-anomaly/scaler_expert{1-4}.pkl`

**Code skeleton**:

```python
import pandas as pd
from sklearn.preprocessing import StandardScaler

# Load data
df = pd.read_csv('data/raw/telemetry_2025-12-03_19-08-39.csv')

# Expert 1: Tire features
tire_scaler = StandardScaler()
tire_features = df[TIRE_FEATURES]
tire_features_scaled = tire_scaler.fit_transform(tire_features)

# Repeat for experts 2-4...
```

---

### Phase 2: GMM Training

**Tasks**:

1. Train GMM per expert (4 models)
2. Hyperparameter tuning (n_components, covariance_type)
3. Validation using BIC/AIC scores
4. Save trained models

**Deliverables**:

- `models/anomaly-detection/gmm_expert1_tire.pkl`
- `models/anomaly-detection/gmm_expert2_dynamics.pkl`
- `models/anomaly-detection/gmm_expert3_control.pkl`
- `models/anomaly-detection/gmm_expert4_power.pkl`
- Training report with BIC/AIC curves

**Code skeleton**:

```python
from sklearn.mixture import GaussianMixture
import numpy as np

# Expert 1: Tire GMM
gmm_tire = GaussianMixture(
    n_components=4,
    covariance_type='full',
    random_state=42,
    max_iter=200
)

gmm_tire.fit(tire_features_scaled)

# Compute anomaly scores
log_likelihood = gmm_tire.score_samples(tire_features_scaled)
anomaly_scores = -log_likelihood  # Higher = more anomalous

# Threshold selection (e.g., 95th percentile)
threshold = np.percentile(anomaly_scores, 95)
```

---

### Phase 3: Gating Network

**Tasks**:

1. Design gating strategy (rule-based or learned)
2. Implement context-aware routing
3. Test expert activation patterns

**Deliverables**:

- `models/anomaly-detection/gating_network.pkl`
- Visualization of expert activations

**Option A: Rule-based Gating**:

```python
def gating_network(speed, in_pit, sector_idx):
    """
    Rule-based expert activation

    Returns: dict of expert weights
    """
    weights = {
        'tire': 1.0,      # Always active
        'dynamics': 1.0,  # Always active
        'control': 1.0,   # Always active
        'power': 0.0      # Default off
    }

    # Activate power expert during straights
    if speed > 250:
        weights['power'] = 1.0

    # Reduce tire expert in pit
    if in_pit:
        weights['tire'] = 0.3

    return weights
```

**Option B: Learned Gating (MLP)**:

```python
import torch.nn as nn

class GatingNetwork(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(4, 16)  # Input: speed, distance, sector, in_pit
        self.fc2 = nn.Linear(16, 4)  # Output: 4 expert weights

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        weights = torch.softmax(self.fc2(x), dim=-1)
        return weights
```

---

### Phase 4: Integration & Testing

**Tasks**:

1. Integrate all experts + gating
2. End-to-end anomaly detection pipeline
3. Test on validation laps
4. Visualize detected anomalies

**Deliverables**:

- `src/anomaly_detection/moe_detector.py`
- Test report with example anomalies
- Visualization dashboard

**Integration code**:

```python
class MoEAnomalyDetector:
    def __init__(self, gmm_models, gating_network, scalers):
        self.gmm_tire = gmm_models['tire']
        self.gmm_dynamics = gmm_models['dynamics']
        self.gmm_control = gmm_models['control']
        self.gmm_power = gmm_models['power']
        self.gating = gating_network
        self.scalers = scalers

    def detect_anomalies(self, telemetry_sample):
        """
        Detect anomalies using MoE approach

        Args:
            telemetry_sample: dict with all telemetry variables

        Returns:
            anomaly_score: float in [0, 1]
            expert_scores: dict of individual expert scores
            active_experts: list of experts that triggered
        """
        # Get gating weights
        context = [
            telemetry_sample['Speed_kmh'],
            telemetry_sample['Distance'],
            telemetry_sample['CurrentSectorIndex'],
            telemetry_sample['IsInPit']
        ]
        weights = self.gating.predict(context)

        # Extract features per expert
        tire_feats = extract_features(telemetry_sample, TIRE_FEATURES)
        dynamics_feats = extract_features(telemetry_sample, DYNAMICS_FEATURES)
        control_feats = extract_features(telemetry_sample, CONTROL_FEATURES)
        power_feats = extract_features(telemetry_sample, POWER_FEATURES)

        # Scale features
        tire_feats = self.scalers['tire'].transform([tire_feats])
        dynamics_feats = self.scalers['dynamics'].transform([dynamics_feats])
        control_feats = self.scalers['control'].transform([control_feats])
        power_feats = self.scalers['power'].transform([power_feats])

        # Get anomaly scores from each expert
        scores = {
            'tire': -self.gmm_tire.score_samples(tire_feats)[0],
            'dynamics': -self.gmm_dynamics.score_samples(dynamics_feats)[0],
            'control': -self.gmm_control.score_samples(control_feats)[0],
            'power': -self.gmm_power.score_samples(power_feats)[0]
        }

        # Weighted aggregation
        final_score = sum(weights[exp] * scores[exp] for exp in scores)

        # Identify triggered experts (above threshold)
        thresholds = {'tire': 5.0, 'dynamics': 5.0, 'control': 5.0, 'power': 5.0}
        active = [exp for exp, score in scores.items() if score > thresholds[exp]]

        return final_score, scores, active
```

---

## Technical Details

### GMM Hyperparameters

| Expert   | N Components | Covariance Type | Rationale                                 |
| -------- | ------------ | --------------- | ----------------------------------------- |
| Tire     | 4            | `full`        | Captures correlations between wheel temps |
| Dynamics | 5            | `full`        | Complex multimodal behavior in corners    |
| Control  | 3            | `diag`        | Simpler, independent control actions      |
| Power    | 3            | `diag`        | ERS states are fairly independent         |

### Anomaly Threshold Selection

**Method**: Percentile-based

- Train on normal laps only (no crashes/spins)
- Set threshold at 95th percentile of training scores
- Tune per expert based on false positive rate

**Alternative**: Use validation set to optimize thresholds

---

## Evaluation Strategy

### Metrics

1. **Detection Rate**: % of true anomalies detected
2. **False Positive Rate**: % of normal samples flagged
3. **Precision/Recall**: Standard classification metrics
4. **Expert Attribution Accuracy**: Did the right expert trigger?

### Test Cases

Create synthetic anomalies:

1. **Tire blowout**: Set TireTemp_FL = 150°C, TirePressure_FL = 0
2. **Spin**: Set AngularVel_Z = 5.0 rad/s
3. **Wrong gear**: Set Gear=2 when RPM=11000, Speed=250
4. **DRS in corner**: Set DRS_Enabled=1 when Steering > 0.3

### Validation

- Test on held-out laps (15% test set)
- Manual review of top 100 anomalies
- Visualization of anomaly timeline per lap

---

## Visualization & Monitoring

### Anomaly Dashboard

```
┌────────────────────────────────────────────────────────┐
│ Lap #42 - Anomaly Detection Report                    │
├────────────────────────────────────────────────────────┤
│                                                        │
│ Overall Anomaly Score: 0.73 🔴                        │
│                                                        │
│ Expert Breakdown:                                      │
│   🛞 Tire Dynamics:    0.92 ⚠️  (TRIGGERED)           │
│   📐 Vehicle Dynamics: 0.45 ✅                         │
│   🎮 Driver Control:   0.38 ✅                         │
│   ⚡ Power Systems:    0.15 ✅                         │
│                                                        │
│ Detected Issues:                                       │
│   • Tire overheating FL: 145°C (normal: 90-110°C)     │
│   • Excessive slip FL: 0.85 (threshold: 0.6)          │
│                                                        │
│ Timeline:                                              │
│   ██████████░░░░░░░░░░░░ [Anomaly spike at 45.2s]     │
│                                                        │
└────────────────────────────────────────────────────────┘
```

---

## Next Steps

### Immediate (This Week)

1. ✅ Create implementation plan (this document)
2. ⬜ Set up data pipeline for 156 variables
3. ⬜ Implement feature extraction per expert
4. ⬜ Create notebook: `N00_MoE_data_preparation.ipynb`

### Short-term (Next 2 Weeks)

1. ⬜ Train GMM models for all 4 experts
2. ⬜ Implement rule-based gating network
3. ⬜ Create evaluation test cases
4. ⬜ Build visualization dashboard

### Long-term (Next Month)

1. ⬜ Deploy real-time anomaly detection
2. ⬜ Integrate with Grafana for monitoring
3. ⬜ Collect feedback and refine thresholds
4. ⬜ Add more experts (e.g., Aero, Damage)

---

## File Structure

```
F1_AC_Digital_Twin/
├── data/
│   ├── raw/
│   │   └── telemetry_2025-12-03_19-08-39.csv
│   └── processed/
│       └── MoE-anomaly/
│           ├── train_expert1_tire.csv
│           ├── train_expert2_dynamics.csv
│           ├── train_expert3_control.csv
│           ├── train_expert4_power.csv
│           └── scalers/
│
├── models/
│   └── anomaly-detection/
│       ├── gmm_expert1_tire.pkl
│       ├── gmm_expert2_dynamics.pkl
│       ├── gmm_expert3_control.pkl
│       ├── gmm_expert4_power.pkl
│       └── gating_network.pkl
│
├── notebooks/
│   └── anomaly-detection/
│       ├── N00_MoE_data_preparation.ipynb
│       ├── N01_MoE_gmm_training.ipynb
│       ├── N02_MoE_gating_network.ipynb
│       └── N03_MoE_evaluation.ipynb
│
├── src/
│   └── anomaly_detection/
│       ├── __init__.py
│       ├── moe_detector.py
│       ├── expert_models.py
│       ├── gating.py
│       └── visualizations.py
│
└── docs/
    └── guides/
        └── mixture-of-experts-anomaly-detection.md  # This file
```

---

## References

- [Gaussian Mixture Models - scikit-learn](https://scikit-learn.org/stable/modules/mixture.html)
- [Mixture of Experts Layer - TensorFlow](https://www.tensorflow.org/tutorials/structured_data/moe)
- [Anomaly Detection with GMM](https://towardsdatascience.com/anomaly-detection-with-gaussian-mixture-models-gmm-f9e0c6993e9d)

---

**Document Status**: ✅ Complete
**Ready for Implementation**: Yes
**Estimated Time**: 4 weeks
**Priority**: High
