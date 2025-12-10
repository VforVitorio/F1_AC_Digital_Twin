"""
Continuous Dummy Telemetry Generator

Sends realistic dummy telemetry data to Kafka continuously for testing.
Data flows through: Kafka -> MoE Detector -> InfluxDB -> Grafana

This script generates realistic telemetry that won't trigger anomalies,
allowing you to test the full pipeline and visualize in Grafana.
"""

import sys
import csv
import json
import time
import random
import argparse
from pathlib import Path
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add src to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))


def delivery_callback(err, msg):
    """Callback for message delivery reports."""
    if err:
        logger.error(f'Message delivery failed: {err}')


def convert_row_to_json(row: dict) -> dict:
    """Convert CSV row to proper JSON types."""
    converted = {}

    for key, value in row.items():
        # Skip empty values
        if value == '':
            continue

        # Try to convert to appropriate type
        try:
            # Try boolean
            if value == 'True':
                converted[key] = True
            elif value == 'False':
                converted[key] = False
            # Try int
            elif '.' not in value:
                converted[key] = int(value)
            # Try float
            else:
                converted[key] = float(value)
        except (ValueError, AttributeError):
            # Keep as string
            converted[key] = value

    return converted


def add_variation(telemetry: dict, variation_pct: float = 1.0) -> dict:
    """
    Add small random variations to telemetry data to make it more realistic.

    Args:
        telemetry: Original telemetry dictionary
        variation_pct: Percentage of variation to add (default 1%)

    Returns:
        Modified telemetry with variations
    """
    varied = telemetry.copy()

    # Fields that should vary slightly
    numeric_fields = [
        'Speed_kmh', 'RPM', 'Throttle', 'Brake',
        'AccG_Lateral', 'AccG_Longitudinal',
        'TireTemp_FL_Avg', 'TireTemp_FR_Avg', 'TireTemp_RL_Avg', 'TireTemp_RR_Avg',
        'TireTemp_FL_Inner', 'TireTemp_FL_Middle', 'TireTemp_FL_Outer',
        'TireTemp_FR_Inner', 'TireTemp_FR_Middle', 'TireTemp_FR_Outer',
        'TireTemp_RL_Inner', 'TireTemp_RL_Middle', 'TireTemp_RL_Outer',
        'TireTemp_RR_Inner', 'TireTemp_RR_Middle', 'TireTemp_RR_Outer',
        'TireLoad_FL', 'TireLoad_FR', 'TireLoad_RL', 'TireLoad_RR',
        'Steering', 'Fuel'
    ]

    for field in numeric_fields:
        if field in varied and isinstance(varied[field], (int, float)):
            original_value = varied[field]

            # Skip if value is 0 (means it wasn't in baseline)
            if original_value == 0.0 and 'Temp' in field and 'Avg' in field:
                # For tire average temps, calculate from inner/middle/outer if available
                if 'FL' in field:
                    inner = varied.get('TireTemp_FL_Inner', 0)
                    middle = varied.get('TireTemp_FL_Middle', 0)
                    outer = varied.get('TireTemp_FL_Outer', 0)
                    if inner > 0 and middle > 0 and outer > 0:
                        original_value = (inner + middle + outer) / 3.0
                        varied[field] = original_value
                elif 'FR' in field:
                    inner = varied.get('TireTemp_FR_Inner', 0)
                    middle = varied.get('TireTemp_FR_Middle', 0)
                    outer = varied.get('TireTemp_FR_Outer', 0)
                    if inner > 0 and middle > 0 and outer > 0:
                        original_value = (inner + middle + outer) / 3.0
                        varied[field] = original_value
                elif 'RL' in field:
                    inner = varied.get('TireTemp_RL_Inner', 0)
                    middle = varied.get('TireTemp_RL_Middle', 0)
                    outer = varied.get('TireTemp_RL_Outer', 0)
                    if inner > 0 and middle > 0 and outer > 0:
                        original_value = (inner + middle + outer) / 3.0
                        varied[field] = original_value
                elif 'RR' in field:
                    inner = varied.get('TireTemp_RR_Inner', 0)
                    middle = varied.get('TireTemp_RR_Middle', 0)
                    outer = varied.get('TireTemp_RR_Outer', 0)
                    if inner > 0 and middle > 0 and outer > 0:
                        original_value = (inner + middle + outer) / 3.0
                        varied[field] = original_value

            if original_value == 0:
                continue

            # Add random variation (smaller for more stability)
            variation = original_value * (variation_pct / 100.0)
            varied[field] = original_value + random.uniform(-variation, variation)

            # Keep values in reasonable ranges (less restrictive)
            if field in ['Throttle', 'Brake']:
                varied[field] = max(0.0, min(1.0, varied[field]))
            elif field == 'Speed_kmh':
                varied[field] = max(0.0, varied[field])
            elif field == 'RPM':
                varied[field] = max(1000, min(13500, int(varied[field])))
            # Note: Removed temp limits to allow natural variation

    # Update timestamp to current time
    varied['Timestamp'] = int(time.time())

    return varied


def ensure_kafka_topic(kafka_servers: str, topic: str):
    """Ensure Kafka topic exists."""
    try:
        admin = AdminClient({'bootstrap.servers': kafka_servers})

        # Check if topic exists
        metadata = admin.list_topics(timeout=5)
        if topic in metadata.topics:
            logger.info(f"Kafka topic '{topic}' already exists")
            return True

        # Create topic
        new_topic = NewTopic(
            topic=topic,
            num_partitions=1,
            replication_factor=1
        )

        fs = admin.create_topics([new_topic])
        for topic_name, future in fs.items():
            try:
                future.result()
                logger.info(f"Created Kafka topic '{topic_name}'")
                return True
            except Exception as e:
                logger.error(f"Failed to create topic '{topic_name}': {e}")
                return False
    except Exception as e:
        logger.error(f"Kafka topic setup failed: {e}")
        return False


def load_baseline_data(csv_path: Path, limit: int = 100) -> list:
    """Load baseline telemetry data from CSV."""
    data = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= limit:
                    break
                telemetry = convert_row_to_json(row)
                data.append(telemetry)

        logger.info(f"Loaded {len(data)} baseline telemetry records")
        return data
    except Exception as e:
        logger.error(f"Failed to load baseline data: {e}")
        return []


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Send continuous dummy telemetry to Kafka')
    parser.add_argument(
        '--csv',
        type=str,
        default=str(ROOT / 'data' / 'raw' / 'telemetry_2025-12-08_18-05-21.csv'),
        help='Path to baseline telemetry CSV file'
    )
    parser.add_argument(
        '--kafka-servers',
        type=str,
        default='localhost:9092',
        help='Kafka bootstrap servers'
    )
    parser.add_argument(
        '--topic',
        type=str,
        default='f1-telemetry',
        help='Kafka topic to publish to'
    )
    parser.add_argument(
        '--rate',
        type=float,
        default=0.1,
        help='Delay between messages in seconds (default: 0.1 = 10Hz)'
    )
    parser.add_argument(
        '--variation',
        type=float,
        default=1.0,
        help='Percentage variation to add to data (default: 1%%)'
    )
    parser.add_argument(
        '--baseline-samples',
        type=int,
        default=100,
        help='Number of baseline samples to load from CSV'
    )

    args = parser.parse_args()

    # Validate CSV file
    csv_path = Path(args.csv)
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        sys.exit(1)

    # Ensure Kafka topic exists
    logger.info("Ensuring Kafka topic exists...")
    if not ensure_kafka_topic(args.kafka_servers, args.topic):
        logger.error("Failed to setup Kafka topic")
        sys.exit(1)

    # Load baseline data
    baseline_data = load_baseline_data(csv_path, args.baseline_samples)
    if not baseline_data:
        logger.error("No baseline data loaded")
        sys.exit(1)

    # Configure producer
    producer_config = {
        'bootstrap.servers': args.kafka_servers,
        'client.id': 'continuous-dummy-telemetry'
    }

    producer = Producer(producer_config)

    logger.info("=" * 70)
    logger.info("CONTINUOUS DUMMY TELEMETRY GENERATOR")
    logger.info("=" * 70)
    logger.info(f"CSV file: {csv_path}")
    logger.info(f"Kafka servers: {args.kafka_servers}")
    logger.info(f"Topic: {args.topic}")
    logger.info(f"Rate: {args.rate}s per message ({1/args.rate:.1f} Hz)")
    logger.info(f"Variation: {args.variation}%")
    logger.info(f"Baseline samples: {len(baseline_data)}")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 70)

    # Send continuous data
    try:
        messages_sent = 0
        start_time = time.time()
        baseline_index = 0

        while True:
            # Get baseline telemetry and cycle through
            baseline_telemetry = baseline_data[baseline_index]
            baseline_index = (baseline_index + 1) % len(baseline_data)

            # Add variations to make it realistic
            telemetry = add_variation(baseline_telemetry, args.variation)

            # Serialize to JSON
            message = json.dumps(telemetry)

            # Publish to Kafka
            producer.produce(
                args.topic,
                value=message.encode('utf-8'),
                callback=delivery_callback
            )

            messages_sent += 1

            # Log progress
            if messages_sent % 100 == 0:
                elapsed = time.time() - start_time
                rate = messages_sent / elapsed if elapsed > 0 else 0
                logger.info(
                    f"Sent {messages_sent} messages ({rate:.1f} msg/s) | "
                    f"Speed: {telemetry.get('Speed_kmh', 0):.1f} km/h | "
                    f"RPM: {telemetry.get('RPM', 0)} | "
                    f"Tire FL: {telemetry.get('TireTemp_FL_Avg', 0):.1f}°C"
                )

            # Poll for delivery reports
            producer.poll(0)

            # Rate limiting
            time.sleep(args.rate)

    except KeyboardInterrupt:
        logger.info("\n\nStopping...")
        producer.flush()

        # Final stats
        elapsed = time.time() - start_time
        rate = messages_sent / elapsed if elapsed > 0 else 0

        logger.info("=" * 70)
        logger.info("STOPPED")
        logger.info("=" * 70)
        logger.info(f"Total messages sent: {messages_sent}")
        logger.info(f"Total time: {elapsed:.2f}s")
        logger.info(f"Average rate: {rate:.1f} msg/s")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        producer.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()
