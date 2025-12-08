"""
Kafka CSV Producer - Send telemetry from CSV to Kafka

Reads telemetry CSV and publishes to Kafka topic 'f1-telemetry'
for real-time processing by MoE anomaly detector.
"""

import sys
import csv
import json
import time
import argparse
from pathlib import Path
from confluent_kafka import Producer
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
    else:
        logger.debug(f'Message delivered to {msg.topic()} [{msg.partition()}]')


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


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Send telemetry from CSV to Kafka')
    parser.add_argument(
        '--csv',
        type=str,
        required=True,
        help='Path to telemetry CSV file'
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
        help='Limit number of messages to send (default: all)'
    )

    args = parser.parse_args()

    # Validate CSV file
    csv_path = Path(args.csv)
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        sys.exit(1)

    # Configure producer
    producer_config = {
        'bootstrap.servers': args.kafka_servers,
        'client.id': 'csv-telemetry-producer'
    }

    producer = Producer(producer_config)

    logger.info("="*70)
    logger.info("KAFKA CSV PRODUCER")
    logger.info("="*70)
    logger.info(f"CSV file: {csv_path}")
    logger.info(f"Kafka servers: {args.kafka_servers}")
    logger.info(f"Topic: {args.topic}")
    logger.info(f"Rate: {args.rate}s per message ({1/args.rate:.1f} Hz)")
    if args.limit:
        logger.info(f"Limit: {args.limit} messages")
    logger.info("="*70)

    # Read and send CSV
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            messages_sent = 0
            start_time = time.time()

            for row in reader:
                # Convert row to proper JSON types
                telemetry = convert_row_to_json(row)

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
                    logger.info(f"Sent {messages_sent} messages ({rate:.1f} msg/s)")

                # Check limit
                if args.limit and messages_sent >= args.limit:
                    logger.info(f"Reached limit of {args.limit} messages")
                    break

                # Poll for delivery reports
                producer.poll(0)

                # Rate limiting
                time.sleep(args.rate)

            # Flush remaining messages
            logger.info("Flushing remaining messages...")
            producer.flush()

            # Final stats
            elapsed = time.time() - start_time
            rate = messages_sent / elapsed if elapsed > 0 else 0

            logger.info("="*70)
            logger.info("COMPLETED")
            logger.info("="*70)
            logger.info(f"Total messages sent: {messages_sent}")
            logger.info(f"Total time: {elapsed:.2f}s")
            logger.info(f"Average rate: {rate:.1f} msg/s")
            logger.info("="*70)

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        producer.flush()
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
