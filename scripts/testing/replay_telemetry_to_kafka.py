"""
Replay Historical Telemetry to Kafka

This script reads telemetry from a CSV file and publishes it to Kafka
simulating real-time data from Assetto Corsa. Useful for end-to-end testing
of the complete pipeline without running the game.

Architecture:
    CSV (historical) → This Script → Kafka (f1-telemetry) → MoE Consumer → InfluxDB → Grafana

Usage:
    python replay_telemetry_to_kafka.py [--input CSV_PATH] [--rate RATE_HZ] [--limit N_SAMPLES]

Examples:
    # Replay at 10 Hz (real-time speed)
    python replay_telemetry_to_kafka.py --input data/raw/telemetry_2025-09-13.csv --rate 10
    
    # Replay at 100 Hz (10x faster) for quick testing
    python replay_telemetry_to_kafka.py --input data/raw/telemetry_2025-09-13.csv --rate 100
    
    # Replay first 1000 samples only
    python replay_telemetry_to_kafka.py --input data/raw/telemetry_2025-09-13.csv --limit 1000

Author: F1 Digital Twin Team
"""

import sys
import json
import argparse
import time
from pathlib import Path
from datetime import datetime
import pandas as pd
from confluent_kafka import Producer
import logging

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def delivery_callback(err, msg):
    """Callback for message delivery confirmation."""
    if err is not None:
        logger.error(f"Message delivery failed: {err}")


class TelemetryReplayer:
    """
    Replays historical telemetry data to Kafka.
    """

    def __init__(
        self,
        kafka_servers: str,
        kafka_topic: str,
        rate_hz: float = 10.0
    ):
        """
        Initialize the replayer.

        Args:
            kafka_servers: Kafka bootstrap servers
            kafka_topic: Topic to publish to
            rate_hz: Publishing rate in Hz
        """
        logger.info("="*70)
        logger.info("INITIALIZING TELEMETRY REPLAYER")
        logger.info("="*70)
        logger.info(f"Kafka servers: {kafka_servers}")
        logger.info(f"Kafka topic: {kafka_topic}")
        logger.info(f"Replay rate: {rate_hz} Hz")

        self.kafka_topic = kafka_topic
        self.rate_hz = rate_hz
        self.interval = 1.0 / rate_hz

        # Setup Kafka producer
        self.producer = Producer({
            'bootstrap.servers': kafka_servers,
            'client.id': 'telemetry-replayer',
            'acks': 'all'
        })

        logger.info("✅ Kafka producer initialized")

    def load_telemetry(self, csv_path: str, limit: int = None) -> pd.DataFrame:
        """
        Load telemetry from CSV file.

        Args:
            csv_path: Path to telemetry CSV
            limit: Maximum number of samples

        Returns:
            DataFrame with telemetry
        """
        logger.info(f"Loading telemetry from: {csv_path}")

        if limit:
            df = pd.read_csv(csv_path, nrows=limit)
        else:
            df = pd.read_csv(csv_path)

        logger.info(f"✅ Loaded {len(df)} samples, {len(df.columns)} columns")
        return df

    def replay(self, telemetry_df: pd.DataFrame) -> dict:
        """
        Replay telemetry to Kafka.

        Args:
            telemetry_df: DataFrame with telemetry

        Returns:
            Statistics dict
        """
        logger.info("="*70)
        logger.info("STARTING TELEMETRY REPLAY")
        logger.info("="*70)
        logger.info(f"Total samples: {len(telemetry_df)}")
        logger.info(
            f"Estimated duration: {len(telemetry_df) / self.rate_hz:.1f} seconds")
        logger.info("-"*70)

        stats = {
            'total_samples': len(telemetry_df),
            'sent_samples': 0,
            'failed_samples': 0,
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'duration_seconds': 0
        }

        start_time = time.time()
        update_interval = max(1, len(telemetry_df) // 20)

        try:
            for idx, row in telemetry_df.iterrows():
                # Convert row to dict (telemetry message)
                telemetry_msg = self._row_to_message(row, idx)

                # Publish to Kafka
                try:
                    self.producer.produce(
                        self.kafka_topic,
                        key=str(idx).encode('utf-8'),
                        value=json.dumps(telemetry_msg).encode('utf-8'),
                        callback=delivery_callback
                    )
                    self.producer.poll(0)
                    stats['sent_samples'] += 1
                except Exception as e:
                    logger.error(f"Failed to send message {idx}: {e}")
                    stats['failed_samples'] += 1

                # Progress update
                if idx > 0 and idx % update_interval == 0:
                    progress = (idx / len(telemetry_df)) * 100
                    elapsed = time.time() - start_time
                    rate = idx / elapsed if elapsed > 0 else 0
                    logger.info(
                        f"Progress: {progress:.1f}% | Sent: {idx} | Rate: {rate:.1f} msg/s")

                # Rate limiting
                time.sleep(self.interval)

        except KeyboardInterrupt:
            logger.info("\n⚠️ Replay interrupted by user")

        finally:
            # Flush remaining messages
            logger.info("Flushing remaining messages...")
            self.producer.flush(timeout=10)

        end_time = time.time()
        stats['end_time'] = datetime.now().isoformat()
        stats['duration_seconds'] = end_time - start_time

        # Print summary
        logger.info("="*70)
        logger.info("REPLAY COMPLETE")
        logger.info("="*70)
        logger.info(f"✅ Sent: {stats['sent_samples']} messages")
        logger.info(f"❌ Failed: {stats['failed_samples']} messages")
        logger.info(f"⏱️  Duration: {stats['duration_seconds']:.1f} seconds")
        logger.info(
            f"📊 Actual rate: {stats['sent_samples'] / stats['duration_seconds']:.1f} msg/s")

        return stats

    def _row_to_message(self, row: pd.Series, idx: int) -> dict:
        """
        Convert DataFrame row to telemetry message.

        Args:
            row: DataFrame row
            idx: Row index

        Returns:
            Telemetry message dict
        """
        # Convert row to dict, handling NaN values
        msg = {}
        for col, val in row.items():
            if pd.isna(val):
                msg[col] = 0.0
            elif isinstance(val, (int, float)):
                msg[col] = float(val)
            else:
                msg[col] = str(val)

        # Add metadata
        msg['_replay'] = True
        msg['_replay_idx'] = idx
        msg['_replay_timestamp'] = datetime.now().isoformat()

        return msg


def main():
    """Main entry point."""
    from config import KAFKA_SERVERS, KAFKA_TOPIC

    parser = argparse.ArgumentParser(
        description='Replay historical telemetry to Kafka'
    )
    parser.add_argument(
        '--input', '-i',
        type=str,
        default=str(ROOT / 'data' / 'processed' /
                    'merged_telemetry_cleaned.csv'),
        help='Path to telemetry CSV file'
    )
    parser.add_argument(
        '--rate', '-r',
        type=float,
        default=10.0,
        help='Replay rate in Hz (default: 10 Hz = real-time)'
    )
    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=None,
        help='Limit number of samples to replay'
    )
    parser.add_argument(
        '--kafka-servers', '-k',
        type=str,
        default=KAFKA_SERVERS,
        help='Kafka bootstrap servers'
    )
    parser.add_argument(
        '--topic', '-t',
        type=str,
        default=KAFKA_TOPIC,
        help='Kafka topic to publish to'
    )

    args = parser.parse_args()

    # Validate input file
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)

    # Create replayer
    replayer = TelemetryReplayer(
        kafka_servers=args.kafka_servers,
        kafka_topic=args.topic,
        rate_hz=args.rate
    )

    # Load telemetry
    telemetry_df = replayer.load_telemetry(str(input_path), limit=args.limit)

    # Replay
    stats = replayer.replay(telemetry_df)

    # Save stats
    stats_path = ROOT / 'data' / 'testing' / 'replay_stats.json'
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    logger.info(f"📁 Stats saved to: {stats_path}")


if __name__ == '__main__':
    main()
