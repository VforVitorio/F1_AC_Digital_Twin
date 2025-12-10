# MoE Anomaly Detection - Real-Time Integration Guide

## Overview

This guide explains how to deploy and use the Mixture of Experts (MoE) anomaly detection system with Assetto Corsa telemetry in real-time.

## Architecture

```
Assetto Corsa (Shared Memory)
    ↓
Kafka Producer → Topic: 'f1-telemetry' (156 vars, 10 Hz)
    ↓
    ├──→ InfluxDB Consumer → Grafana Telemetry Dashboard
    │
    └──→ MoE Anomaly Consumer
            ↓
         1. Extract features (57 vars across 4 experts)
         2. Normalize with StandardScaler
         3. Run GMM experts + Gating Network
         4. Detect anomalies (score > threshold)
            ↓
         Kafka Producer → Topic: 'f1-anomalies'
            ↓
         Anomaly InfluxDB Consumer
            ↓
         InfluxDB (bucket: f1-anomalies)
            ↓
         Grafana Anomaly Dashboard
```

## Components

### 1. Feature Processor (`src/feature_processor.py`)

Extracts and normalizes 57 features from raw telemetry:

| Expert   | Features | Focus                                              |
| -------- | -------- | -------------------------------------------------- |
| Expert 1 | 20       | Tire dynamics (temp, wear, pressure, slip)         |
| Expert 2 | 15       | Vehicle dynamics (G-forces, velocity, orientation) |
| Expert 3 | 12       | Driver control (throttle, brake, steering)         |
| Expert 4 | 10       | Power systems (fuel, turbo, ERS, DRS)              |

### 2. MoE Inference Engine (`src/moe_inference.py`)

- Loads 4 GMM experts + LogisticRegression gating network
- Computes anomaly scores per expert
- Classifies anomaly type and severity
- Returns structured prediction with expert weights

### 3. Kafka MoE Consumer (`scripts/streaming/kafka_moe_consumer.py`)

- Consumes from `f1-telemetry` topic
- Processes each message through MoE pipeline
- Publishes anomalies to `f1-anomalies` topic

### 4. Anomaly InfluxDB Writer (`scripts/streaming/kafka_anomaly_to_influxdb.py`)

- Consumes from `f1-anomalies` topic
- Writes to InfluxDB bucket `f1-anomalies`

## Quick Start

### 1. Start Infrastructure

```bash
docker-compose up -d kafka zookeeper influxdb grafana
```

### 2. Create Anomaly Topic

```python
from src.kafka_handlers import setup_anomaly_topic
setup_anomaly_topic('localhost:9092')
```

### 3. Start MoE Consumer

```bash
# Option A: Direct Python
python scripts/streaming/kafka_moe_consumer.py

# Option B: Docker
docker-compose up moe-anomaly-detector
```

### 4. Start Anomaly Writer

```bash
# Option A: Direct Python
python scripts/streaming/kafka_anomaly_to_influxdb.py

# Option B: Docker
docker-compose up anomaly-to-influx
```

### 5. Start Telemetry Collection

```bash
python src/telemetry_collector.py
```

### 6. View Dashboard

Open Grafana at http://localhost:3000 and navigate to "Anomaly Dashboard".

## Configuration

Environment variables (`.env` file):

```env
# MoE Anomaly Detection
MOE_MODEL_PATH=models/anomaly-detection
MOE_SCALERS_PATH=data/processed/MoE-anomaly/scalers
KAFKA_ANOMALY_TOPIC=f1-anomalies
KAFKA_MOE_CONSUMER_GROUP=moe-anomaly-detector
INFLUX_ANOMALY_BUCKET=f1-anomalies

# Override thresholds (optional)
THRESHOLD_TIRE=-94.07
THRESHOLD_DYNAMICS=20.86
THRESHOLD_CONTROL=-32.55
THRESHOLD_POWER=-28.00
```

## Anomaly Message Format

```json
{
  "timestamp": "2025-12-08T12:00:00.123Z",
  "lap": 5,
  "distance": 1234.56,
  "is_anomaly": true,
  "anomaly_type": "tire_anomaly",
  "severity": "medium",
  "expert_scores": {
    "expert1_tire": -92.5,
    "expert2_dynamics": 15.2,
    "expert3_control": -28.1,
    "expert4_power": -25.3
  },
  "expert_weights": {
    "expert1_tire": 0.65,
    "expert2_dynamics": 0.15,
    "expert3_control": 0.1,
    "expert4_power": 0.1
  },
  "global_score": -45.2,
  "anomaly_probability": 0.78,
  "affected_component": "1_tire"
}
```

## Anomaly Types

| Type               | Expert     | Description                                |
| ------------------ | ---------- | ------------------------------------------ |
| `tire_anomaly`     | Expert 1   | Tire temperature, wear, or grip issues     |
| `vehicle_dynamics` | Expert 2   | Unusual G-forces or vehicle behavior       |
| `driver_control`   | Expert 3   | Erratic inputs or assist system activation |
| `power_system`     | Expert 4   | Engine, ERS, or fuel anomalies             |
| `multiple`         | 2+ experts | Multiple systems affected                  |
| `none`             | -          | Normal operation                           |

## Severity Levels

- **low**: Score slightly above threshold (<20% deviation)
- **medium**: Moderate deviation (20-50%)
- **high**: Significant deviation (>50%)

## Testing

### Offline Testing (no Kafka required)

```bash
python scripts/testing/test_moe_pipeline.py \
    --input data/raw/telemetry_2025-12-03_19-08-39.csv \
    --limit 1000 \
    --visualize
```

### Replay Historical Data

```bash
python scripts/testing/replay_telemetry_to_kafka.py \
    --input data/raw/telemetry_2025-12-03_19-08-39.csv \
    --rate 10
```

## Troubleshooting

### High False Positive Rate

1. Check that scalers match training data
2. Verify feature names match exactly
3. Ensure data is from racing laps (not pit lane)

### No Anomalies Detected

1. Verify thresholds in `moe_config.json`
2. Check GMM models are loaded correctly
3. Confirm Kafka topics are receiving messages

### Missing Features

The system requires these 57 features. If any are missing:

- Check Assetto Corsa shared memory mapping
- Verify telemetry collector configuration

## Model Retraining

If you need to retrain the models:

1. Collect new telemetry data
2. Run notebooks in order:
   - `N00_MoE_data_preparation.ipynb`
   - `N01_MoE_expert1_tire.ipynb`
   - `N02_MoE_expert2_dynamics.ipynb`
   - `N03_MoE_expert3_control.ipynb`
   - `N04_MoE_expert4_power.ipynb`
   - `N05_MoE_gating_network.ipynb`
3. Update thresholds in `moe_config.json`
4. Restart MoE consumer

## Files Reference

| File                                             | Purpose                            |
| ------------------------------------------------ | ---------------------------------- |
| `src/moe_inference.py`                           | MoE model wrapper                  |
| `src/feature_processor.py`                       | Feature extraction & normalization |
| `scripts/streaming/kafka_moe_consumer.py`        | Real-time anomaly detection        |
| `scripts/streaming/kafka_anomaly_to_influxdb.py` | Anomaly persistence                |
| `models/anomaly-detection/moe_config.json`       | Model configuration                |
| `models/anomaly-detection/gmm_expert*.pkl`       | GMM expert models                  |
| `models/anomaly-detection/gating_network.pkl`    | Gating network                     |
| `data/processed/MoE-anomaly/scalers/`            | StandardScaler files               |
