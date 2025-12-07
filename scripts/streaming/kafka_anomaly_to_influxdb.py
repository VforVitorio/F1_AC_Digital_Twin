"""
Kafka Anomaly to InfluxDB Consumer

Consumes anomaly detection results from 'f1-anomalies' topic and writes them to InfluxDB
for visualization in Grafana.

Architecture:
    Kafka (f1-anomalies) → InfluxDB (f1-anomalies bucket) → Grafana

Usage:
    python kafka_anomaly_to_influxdb.py [--kafka-servers SERVERS] [--topic TOPIC]

Author: F1 Digital Twin Team
"""

import sys
import json
import argparse
import time
from pathlib import Path
from datetime import datetime
from confluent_kafka import Consumer, KafkaError
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import logging

# Add src to path (if needed)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AnomalyInfluxDBWriter:
    """
    Kafka consumer that writes anomaly detection results to InfluxDB.
    """

    def __init__(
        self,
        kafka_servers: str,
        kafka_topic: str,
        consumer_group: str,
        influx_url: str,
        influx_token: str,
        influx_org: str,
        influx_bucket: str
    ):
        """
        Initialize the InfluxDB writer.

        Args:
            kafka_servers: Kafka bootstrap servers
            kafka_topic: Kafka topic to consume from
            consumer_group: Consumer group ID
            influx_url: InfluxDB server URL
            influx_token: InfluxDB authentication token
            influx_org: InfluxDB organization
            influx_bucket: InfluxDB bucket for anomalies
        """
        logger.info("="*70)
        logger.info("INITIALIZING ANOMALY INFLUXDB WRITER")
        logger.info("="*70)
        logger.info(f"Kafka servers: {kafka_servers}")
        logger.info(f"Kafka topic: {kafka_topic}")
        logger.info(f"Consumer group: {consumer_group}")
        logger.info(f"InfluxDB URL: {influx_url}")
        logger.info(f"InfluxDB bucket: {influx_bucket}")

        self.kafka_topic = kafka_topic
        self.influx_bucket = influx_bucket
        self.influx_org = influx_org

        # Setup Kafka consumer
        self._setup_kafka(kafka_servers, kafka_topic, consumer_group)

        # Setup InfluxDB client
        self._setup_influxdb(influx_url, influx_token, influx_org)

        # Statistics
        self.stats = {
            'messages_consumed': 0,
            'points_written': 0,
            'anomalies_written': 0,
            'errors': 0,
            'start_time': time.time()
        }

        logger.info("✅ Anomaly InfluxDB Writer initialized successfully\n")

    def _setup_kafka(self, kafka_servers: str, topic: str, consumer_group: str):
        """Setup Kafka consumer."""
        consumer_config = {
            'bootstrap.servers': kafka_servers,
            'group.id': consumer_group,
            'auto.offset.reset': 'latest',
            'enable.auto.commit': True,
            'auto.commit.interval.ms': 1000,
            'client.id': 'anomaly-influxdb-writer'
        }

        self.consumer = Consumer(consumer_config)
        self.consumer.subscribe([topic])
        logger.info(f"✅ Subscribed to Kafka topic: {topic}")

    def _setup_influxdb(self, url: str, token: str, org: str):
        """Setup InfluxDB client."""
        self.influx_client = InfluxDBClient(url=url, token=token, org=org)
        self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
        logger.info(f"✅ Connected to InfluxDB")

    def process_anomaly_message(self, anomaly: dict):
        """
        Convert anomaly message to InfluxDB points and write.

        Args:
            anomaly: Anomaly message dictionary from Kafka
        """
        try:
            # Parse timestamp
            timestamp = datetime.fromisoformat(anomaly['timestamp'].replace('Z', '+00:00'))

            # Create main anomaly detection point
            point = Point("anomaly_detection") \
                .time(timestamp) \
                .tag("anomaly_type", anomaly.get('anomaly_type', 'unknown')) \
                .tag("severity", anomaly.get('severity', 'unknown')) \
                .tag("is_anomaly", str(anomaly.get('is_anomaly', False))) \
                .tag("lap", str(anomaly.get('lap', 0))) \
                .field("global_score", float(anomaly.get('global_score', 0.0))) \
                .field("anomaly_probability", float(anomaly.get('anomaly_probability', 0.0))) \
                .field("speed_kmh", float(anomaly.get('speed_kmh', 0.0))) \
                .field("distance", float(anomaly.get('distance', 0.0)))

            # Add expert scores
            if 'expert_scores' in anomaly:
                for expert, score in anomaly['expert_scores'].items():
                    point.field(f"{expert}_score", float(score))

            # Add expert weights
            if 'expert_weights' in anomaly:
                for expert, weight in anomaly['expert_weights'].items():
                    point.field(f"{expert}_weight", float(weight))

            # Write to InfluxDB
            self.write_api.write(bucket=self.influx_bucket, org=self.influx_org, record=point)
            self.stats['points_written'] += 1

            # If anomaly detected, write additional details point
            if anomaly.get('is_anomaly', False):
                self._write_anomaly_details(anomaly, timestamp)
                self.stats['anomalies_written'] += 1

        except Exception as e:
            logger.error(f"Error processing anomaly message: {e}")
            self.stats['errors'] += 1
            raise

    def _write_anomaly_details(self, anomaly: dict, timestamp: datetime):
        """
        Write detailed anomaly information as separate points.

        Args:
            anomaly: Anomaly message dictionary
            timestamp: Timestamp for the point
        """
        if 'details' not in anomaly or not anomaly['details']:
            return

        # Create detail point
        detail_point = Point("anomaly_details") \
            .time(timestamp) \
            .tag("anomaly_type", anomaly.get('anomaly_type', 'unknown')) \
            .tag("severity", anomaly.get('severity', 'unknown')) \
            .tag("affected_component", anomaly.get('affected_component', 'unknown')) \
            .tag("lap", str(anomaly.get('lap', 0)))

        # Add all detail fields
        for key, value in anomaly['details'].items():
            if isinstance(value, (int, float)):
                detail_point.field(key, float(value))
            else:
                detail_point.field(key, str(value))

        # Write to InfluxDB
        self.write_api.write(bucket=self.influx_bucket, org=self.influx_org, record=detail_point)

    def run(self):
        """
        Main processing loop.
        """
        logger.info("="*70)
        logger.info("STARTING ANOMALY → INFLUXDB STREAM")
        logger.info("="*70)
        logger.info("Press Ctrl+C to stop\n")

        try:
            while True:
                # Poll for messages
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Consumer error: {msg.error()}")
                        continue

                # Parse anomaly message
                try:
                    anomaly = json.loads(msg.value().decode('utf-8'))
                    self.stats['messages_consumed'] += 1

                    # Write to InfluxDB
                    self.process_anomaly_message(anomaly)

                    # Log anomalies
                    if anomaly.get('is_anomaly', False):
                        logger.info(
                            f"📝 Wrote anomaly to InfluxDB: {anomaly['anomaly_type']} "
                            f"(severity: {anomaly['severity']}, "
                            f"lap: {anomaly.get('lap', 0)}, "
                            f"prob: {anomaly.get('anomaly_probability', 0):.3f})"
                        )

                    # Periodic stats
                    if self.stats['messages_consumed'] % 100 == 0:
                        self._print_stats()

                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    self.stats['errors'] += 1
                    continue

        except KeyboardInterrupt:
            logger.info("\n\n🛑 Shutting down gracefully...")
            self._print_final_stats()

        finally:
            # Cleanup
            self.consumer.close()
            self.influx_client.close()
            logger.info("✅ Shutdown complete")

    def _print_stats(self):
        """Print current statistics."""
        elapsed = time.time() - self.stats['start_time']
        rate = self.stats['messages_consumed'] / elapsed if elapsed > 0 else 0
        anomaly_rate = (
            self.stats['anomalies_written'] / self.stats['messages_consumed'] * 100
            if self.stats['messages_consumed'] > 0 else 0
        )

        logger.info(
            f"📊 Stats: {self.stats['messages_consumed']} msgs, "
            f"{self.stats['points_written']} points written, "
            f"{self.stats['anomalies_written']} anomalies ({anomaly_rate:.1f}%), "
            f"{rate:.1f} msg/s, "
            f"{self.stats['errors']} errors"
        )

    def _print_final_stats(self):
        """Print final statistics."""
        elapsed = time.time() - self.stats['start_time']

        logger.info("\n" + "="*70)
        logger.info("FINAL STATISTICS")
        logger.info("="*70)
        logger.info(f"Runtime: {elapsed:.1f} seconds")
        logger.info(f"Messages consumed: {self.stats['messages_consumed']}")
        logger.info(f"Points written: {self.stats['points_written']}")
        logger.info(f"Anomalies written: {self.stats['anomalies_written']}")
        logger.info(f"Errors: {self.stats['errors']}")

        if elapsed > 0:
            throughput = self.stats['messages_consumed'] / elapsed
            logger.info(f"Average throughput: {throughput:.1f} messages/second")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Write anomaly detection results from Kafka to InfluxDB'
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
        default='f1-anomalies',
        help='Kafka topic with anomalies'
    )
    parser.add_argument(
        '--consumer-group',
        type=str,
        default='anomaly-influxdb-writer',
        help='Consumer group ID'
    )
    parser.add_argument(
        '--influx-url',
        type=str,
        default='http://localhost:8086',
        help='InfluxDB URL'
    )
    parser.add_argument(
        '--influx-token',
        type=str,
        default='f1-telemetry-token-super-secret',
        help='InfluxDB authentication token'
    )
    parser.add_argument(
        '--influx-org',
        type=str,
        default='f1-org',
        help='InfluxDB organization'
    )
    parser.add_argument(
        '--influx-bucket',
        type=str,
        default='f1-anomalies',
        help='InfluxDB bucket for anomalies'
    )

    args = parser.parse_args()

    try:
        # Initialize and run writer
        writer = AnomalyInfluxDBWriter(
            kafka_servers=args.kafka_servers,
            kafka_topic=args.topic,
            consumer_group=args.consumer_group,
            influx_url=args.influx_url,
            influx_token=args.influx_token,
            influx_org=args.influx_org,
            influx_bucket=args.influx_bucket
        )

        writer.run()

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
