"""
F1 AC Digital Twin - Configuration Module

This module loads environment variables from .env file and provides
centralized configuration for all components of the system.

Usage:
    from config import KAFKA_SERVERS, INFLUX_TOKEN, etc.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Kafka Configuration
KAFKA_SERVERS = os.getenv('KAFKA_SERVERS', 'localhost:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'f1-telemetry')
KAFKA_CONSUMER_GROUP = os.getenv(
    'KAFKA_CONSUMER_GROUP', 'f1-influxdb-consumer-handson2')

# InfluxDB Configuration
INFLUX_URL = os.getenv('INFLUX_URL', 'http://localhost:8086')
INFLUX_TOKEN = os.getenv('INFLUX_TOKEN', '')
INFLUX_ORG = os.getenv('INFLUX_ORG', 'myorg')
INFLUX_BUCKET = os.getenv('INFLUX_BUCKET', 'f1-telemetry')

# Telemetry Settings
READ_INTERVAL = float(os.getenv('READ_INTERVAL', '0.1'))

# =============================================================================
# MoE Anomaly Detection Configuration
# =============================================================================

# Model paths
MOE_MODEL_PATH = os.getenv(
    'MOE_MODEL_PATH',
    str(Path(__file__).parent / 'models' / 'anomaly-detection')
)
MOE_SCALERS_PATH = os.getenv(
    'MOE_SCALERS_PATH',
    str(Path(__file__).parent / 'data' / 'processed' / 'MoE-anomaly' / 'scalers')
)

# Kafka topics for anomaly detection
KAFKA_ANOMALY_TOPIC = os.getenv('KAFKA_ANOMALY_TOPIC', 'f1-anomalies')
KAFKA_MOE_CONSUMER_GROUP = os.getenv(
    'KAFKA_MOE_CONSUMER_GROUP', 'moe-anomaly-detector')

# InfluxDB bucket for anomalies
INFLUX_ANOMALY_BUCKET = os.getenv('INFLUX_ANOMALY_BUCKET', 'f1-anomalies')

# Anomaly detection thresholds (can be overridden, loaded from moe_config.json by default)
ANOMALY_THRESHOLDS = {
    'expert1_tire': float(os.getenv('THRESHOLD_TIRE', '-94.07')),
    'expert2_dynamics': float(os.getenv('THRESHOLD_DYNAMICS', '20.86')),
    'expert3_control': float(os.getenv('THRESHOLD_CONTROL', '-32.55')),
    'expert4_power': float(os.getenv('THRESHOLD_POWER', '-28.00')),
}

# =============================================================================

# Validation
if not INFLUX_TOKEN:
    raise ValueError(
        "INFLUX_TOKEN is not set. Please configure it in the .env file."
    )

# Print loaded configuration (for debugging)


def print_config():
    """Print current configuration (hiding sensitive data)"""
    print("=" * 60)
    print("F1 AC Digital Twin - Configuration")
    print("=" * 60)
    print(f"Kafka Servers: {KAFKA_SERVERS}")
    print(f"Kafka Topic: {KAFKA_TOPIC}")
    print(f"Kafka Consumer Group: {KAFKA_CONSUMER_GROUP}")
    print(f"InfluxDB URL: {INFLUX_URL}")
    print(f"InfluxDB Org: {INFLUX_ORG}")
    print(f"InfluxDB Bucket: {INFLUX_BUCKET}")
    print(
        f"InfluxDB Token: {'*' * 20}...{INFLUX_TOKEN[-10:] if INFLUX_TOKEN else 'NOT SET'}")
    print(f"Read Interval: {READ_INTERVAL}s")
    print("-" * 60)
    print("MoE Anomaly Detection:")
    print(f"  Model Path: {MOE_MODEL_PATH}")
    print(f"  Scalers Path: {MOE_SCALERS_PATH}")
    print(f"  Anomaly Topic: {KAFKA_ANOMALY_TOPIC}")
    print(f"  Anomaly Bucket: {INFLUX_ANOMALY_BUCKET}")
    print("=" * 60)


if __name__ == "__main__":
    # Test configuration loading
    print_config()
