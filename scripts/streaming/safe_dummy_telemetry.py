"""
Safe Dummy Telemetry Generator

Sends EXACT training data to Kafka without modifications.
This guarantees no anomalies will be detected since the model was trained on this data.
"""

import sys
import csv
import json
import time
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

    # DO NOT calculate tire averages - keep them as 0.0 to match training data
    # The model was trained on TireTemp_XX_Avg = 0.0, so we need to send the same
    # to avoid triggering anomalies

    # Update timestamp to current time
    converted['Timestamp'] = int(time.time())

    return converted


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


def load_training_data(csv_path: Path, limit: int = None) -> list:
    """Load training telemetry data from CSV."""
    data = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break
                telemetry = convert_row_to_json(row)
                data.append(telemetry)

        logger.info(f"Loaded {len(data)} training telemetry records")
        return data
    except Exception as e:
        logger.error(f"Failed to load training data: {e}")
        return []


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Send safe training data to Kafka (no anomalies)')
    parser.add_argument(
        '--csv',
        type=str,
        default=str(ROOT / 'data' / 'raw' / 'telemetry_2025-12-08_18-05-21.csv'),
        help='Path to training telemetry CSV file'
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
        '--limit',
        type=int,
        default=None,
        help='Number of samples to load from CSV (default: all)'
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

    # Load training data
    training_data = load_training_data(csv_path, args.limit)
    if not training_data:
        logger.error("No training data loaded")
        sys.exit(1)

    # Configure producer
    producer_config = {
        'bootstrap.servers': args.kafka_servers,
        'client.id': 'safe-dummy-telemetry'
    }

    producer = Producer(producer_config)

    logger.info("=" * 70)
    logger.info("SAFE DUMMY TELEMETRY GENERATOR")
    logger.info("=" * 70)
    logger.info(f"CSV file: {csv_path}")
    logger.info(f"Kafka servers: {args.kafka_servers}")
    logger.info(f"Topic: {args.topic}")
    logger.info(f"Rate: {args.rate}s per message ({1/args.rate:.1f} Hz)")
    logger.info(f"Training samples: {len(training_data)}")
    logger.info("Sending EXACT training data (no variations)")
    logger.info("This should produce ZERO anomalies")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 70)

    # Send continuous data
    try:
        messages_sent = 0
        start_time = time.time()
        data_index = 0

        while True:
            # Get exact training telemetry (cycle through data)
            telemetry = training_data[data_index].copy()
            data_index = (data_index + 1) % len(training_data)

            # Update only the timestamp to current time
            telemetry['Timestamp'] = int(time.time())

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
                    f"✓ Sent {messages_sent} messages ({rate:.1f} msg/s) | "
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
