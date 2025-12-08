"""
Kafka MoE Anomaly Detection Consumer

This script consumes telemetry from 'f1-telemetry' topic, runs MoE anomaly detection,
and publishes results to 'f1-anomalies' topic.

Architecture:
    Kafka (f1-telemetry) → Feature Extraction → MoE Inference → Kafka (f1-anomalies)

Usage:
    python kafka_moe_consumer.py [--kafka-servers SERVERS] [--input-topic TOPIC] [--output-topic TOPIC]

Author: F1 Digital Twin Team
"""

from kafka_handlers import setup_anomaly_topic, delivery_callback
from moe_inference import MoEInference
from feature_processor import RealTimeFeatureExtractor, validate_telemetry
import sys
import json
import argparse
import time
from pathlib import Path
from datetime import datetime
from confluent_kafka import Consumer, Producer, KafkaError
import logging

# Add src to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MoEAnomalyDetector:
    """
    Real-time anomaly detector using MoE models.
    Consumes telemetry from Kafka, runs MoE, publishes anomalies.
    """

    def __init__(
        self,
        kafka_servers: str,
        input_topic: str,
        output_topic: str,
        consumer_group: str,
        scalers_dir: str,
        models_dir: str
    ):
        """
        Initialize the MoE anomaly detector.

        Args:
            kafka_servers: Kafka bootstrap servers
            input_topic: Input topic with telemetry (f1-telemetry)
            output_topic: Output topic for anomalies (f1-anomalies)
            consumer_group: Consumer group ID
            scalers_dir: Path to scalers directory
            models_dir: Path to models directory
        """
        self.kafka_servers = kafka_servers
        self.input_topic = input_topic
        self.output_topic = output_topic
        self.consumer_group = consumer_group

        logger.info("="*70)
        logger.info("INITIALIZING MoE ANOMALY DETECTOR")
        logger.info("="*70)
        logger.info(f"Kafka servers: {kafka_servers}")
        logger.info(f"Input topic: {input_topic}")
        logger.info(f"Output topic: {output_topic}")
        logger.info(f"Consumer group: {consumer_group}")

        # Initialize components
        self.feature_extractor = RealTimeFeatureExtractor(scalers_dir)
        self.moe = MoEInference(models_dir)

        # Setup Kafka
        self._setup_kafka()

        # Statistics
        self.stats = {
            'messages_consumed': 0,
            'messages_produced': 0,
            'anomalies_detected': 0,
            'errors': 0,
            'start_time': time.time()
        }

        logger.info("✅ MoE Anomaly Detector initialized successfully\n")

    def _setup_kafka(self):
        """Setup Kafka consumer and producer."""
        # Create anomaly topic if not exists
        setup_anomaly_topic(self.kafka_servers, self.output_topic)

        # Configure consumer
        consumer_config = {
            'bootstrap.servers': self.kafka_servers,
            'group.id': self.consumer_group,
            'auto.offset.reset': 'latest',
            'enable.auto.commit': True,
            'auto.commit.interval.ms': 1000,
            'client.id': 'moe-anomaly-detector'
        }

        self.consumer = Consumer(consumer_config)
        self.consumer.subscribe([self.input_topic])
        logger.info(f"✅ Subscribed to topic: {self.input_topic}")

        # Configure producer
        producer_config = {
            'bootstrap.servers': self.kafka_servers,
            'client.id': 'moe-anomaly-producer',
            'compression.type': 'lz4',
            'linger.ms': 10,  # Small batching for low latency
            'batch.size': 16384
        }

        self.producer = Producer(producer_config)
        logger.info(f"✅ Producer configured for topic: {self.output_topic}")

    def process_telemetry(self, telemetry: dict) -> dict:
        """
        Process telemetry through MoE pipeline.

        Args:
            telemetry: Raw telemetry dictionary

        Returns:
            Anomaly detection result dictionary
        """
        try:
            # 1. Validate telemetry
            is_valid, missing = validate_telemetry(telemetry)

            if not is_valid:
                logger.warning(
                    f"Invalid telemetry: missing {len(missing)} features")
                # Fill missing with None or 0
                for feature in missing:
                    telemetry[feature] = 0.0

            # 2. Extract and normalize features
            normalized_features = self.feature_extractor.process(telemetry)

            # 3. MoE inference
            prediction = self.moe.predict(normalized_features)

            # 4. Build anomaly message
            anomaly_message = self._build_anomaly_message(
                telemetry, prediction)

            return anomaly_message

        except Exception as e:
            logger.error(f"Error processing telemetry: {e}")
            self.stats['errors'] += 1
            raise

    def _build_anomaly_message(self, telemetry: dict, prediction: dict) -> dict:
        """
        Build anomaly message from telemetry and prediction.

        Args:
            telemetry: Raw telemetry
            prediction: MoE prediction result

        Returns:
            Anomaly message dictionary
        """
        # Extract context from telemetry (check both producer and normalized field names)
        lap = telemetry.get(
            'completed_laps', telemetry.get('CompletedLaps', 0))
        distance = telemetry.get('distance', telemetry.get('Distance', 0.0))
        speed = telemetry.get('speed_kmh', telemetry.get('Speed_kmh', 0.0))

        # Build message
        message = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'lap': int(lap),
            'distance': float(distance),
            'speed_kmh': float(speed),
            'is_anomaly': prediction['is_anomaly'],
            'anomaly_type': prediction['anomaly_type'],
            'expert_scores': prediction['expert_scores'],
            'expert_weights': prediction['expert_weights'],
            'global_score': prediction['global_score'],
            'anomaly_probability': prediction['anomaly_probability'],
            'severity': prediction['severity'],
            'affected_component': prediction['affected_component']
        }

        # Add detailed information if anomaly detected
        if prediction['is_anomaly']:
            message['details'] = self._extract_anomaly_details(
                telemetry, prediction)

        return message

    def _extract_anomaly_details(self, telemetry: dict, prediction: dict) -> dict:
        """
        Extract relevant telemetry details based on anomaly type.

        Args:
            telemetry: Raw telemetry
            prediction: MoE prediction

        Returns:
            Dictionary with relevant details
        """
        anomaly_type = prediction['anomaly_type']
        details = {}

        if 'tire' in anomaly_type:
            # Tire-related details
            details.update({
                'TireTemp_FL': telemetry.get('TireTemp_FL_Avg', 0),
                'TireTemp_FR': telemetry.get('TireTemp_FR_Avg', 0),
                'TireTemp_RL': telemetry.get('TireTemp_RL_Avg', 0),
                'TireTemp_RR': telemetry.get('TireTemp_RR_Avg', 0),
                'TireWear_FL': telemetry.get('TireWear_FL', 0),
                'TireWear_FR': telemetry.get('TireWear_FR', 0),
                'TirePressure_FL': telemetry.get('TirePressure_FL', 0),
                'TirePressure_FR': telemetry.get('TirePressure_FR', 0),
            })

        elif 'dynamics' in anomaly_type:
            # Vehicle dynamics details
            details.update({
                'AccG_Lateral': telemetry.get('AccG_Lateral', 0),
                'AccG_Longitudinal': telemetry.get('AccG_Longitudinal', 0),
                'AccG_Vertical': telemetry.get('AccG_Vertical', 0),
                'AngularVel_Y': telemetry.get('AngularVel_Y', 0),
            })

        elif 'control' in anomaly_type:
            # Driver control details
            details.update({
                'Throttle': telemetry.get('Throttle', 0),
                'Brake': telemetry.get('Brake', 0),
                'Steering': telemetry.get('Steering', 0),
                'Gear': telemetry.get('Gear', 0),
                'RPM': telemetry.get('RPM', 0),
            })

        elif 'power' in anomaly_type:
            # Power system details
            details.update({
                'Fuel': telemetry.get('Fuel', 0),
                'EngineTemp_Oil': telemetry.get('EngineTemp_Oil', 0),
                'TurboBoost': telemetry.get('TurboBoost', 0),
                'KERS_Charge': telemetry.get('KERS_Charge', 0),
                'ERS_PowerLevel': telemetry.get('ERS_PowerLevel', 0),
            })

        return details

    def publish_anomaly(self, anomaly_message: dict):
        """
        Publish anomaly message to Kafka.

        Args:
            anomaly_message: Anomaly message dictionary
        """
        try:
            # Serialize to JSON
            message_json = json.dumps(anomaly_message)

            # Publish to Kafka
            self.producer.produce(
                self.output_topic,
                value=message_json.encode('utf-8'),
                callback=delivery_callback
            )

            # Poll for delivery reports
            self.producer.poll(0)

            self.stats['messages_produced'] += 1

            if anomaly_message['is_anomaly']:
                self.stats['anomalies_detected'] += 1

        except Exception as e:
            logger.error(f"Error publishing anomaly: {e}")
            self.stats['errors'] += 1

    def run(self):
        """
        Main processing loop.
        """
        logger.info("="*70)
        logger.info("STARTING MoE ANOMALY DETECTION STREAM")
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

                # Parse telemetry
                try:
                    telemetry = json.loads(msg.value().decode('utf-8'))
                    self.stats['messages_consumed'] += 1

                    # Process through MoE
                    anomaly_message = self.process_telemetry(telemetry)

                    # Publish result
                    self.publish_anomaly(anomaly_message)

                    # Log anomalies
                    if anomaly_message['is_anomaly']:
                        logger.warning(
                            f"🚨 ANOMALY DETECTED: {anomaly_message['anomaly_type']} "
                            f"(severity: {anomaly_message['severity']}, "
                            f"lap: {anomaly_message['lap']}, "
                            f"prob: {anomaly_message['anomaly_probability']:.3f})"
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
            self.producer.flush()
            self.consumer.close()
            logger.info("✅ Shutdown complete")

    def _print_stats(self):
        """Print current statistics."""
        elapsed = time.time() - self.stats['start_time']
        rate = self.stats['messages_consumed'] / elapsed if elapsed > 0 else 0
        anomaly_rate = (
            self.stats['anomalies_detected'] /
            self.stats['messages_consumed'] * 100
            if self.stats['messages_consumed'] > 0 else 0
        )

        logger.info(
            f"📊 Stats: {self.stats['messages_consumed']} msgs, "
            f"{self.stats['anomalies_detected']} anomalies ({anomaly_rate:.1f}%), "
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
        logger.info(f"Messages produced: {self.stats['messages_produced']}")
        logger.info(f"Anomalies detected: {self.stats['anomalies_detected']}")
        logger.info(f"Errors: {self.stats['errors']}")

        if self.stats['messages_consumed'] > 0:
            anomaly_rate = self.stats['anomalies_detected'] / \
                self.stats['messages_consumed'] * 100
            logger.info(f"Anomaly rate: {anomaly_rate:.2f}%")

        if elapsed > 0:
            throughput = self.stats['messages_consumed'] / elapsed
            logger.info(
                f"Average throughput: {throughput:.1f} messages/second")

        # MoE stats
        moe_stats = self.moe.get_stats()
        logger.info(f"\nMoE Statistics:")
        for key, value in moe_stats.items():
            logger.info(f"  {key}: {value}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='MoE Anomaly Detection Kafka Consumer')
    parser.add_argument(
        '--kafka-servers',
        type=str,
        default='localhost:9092',
        help='Kafka bootstrap servers'
    )
    parser.add_argument(
        '--input-topic',
        type=str,
        default='f1-telemetry',
        help='Input topic with telemetry'
    )
    parser.add_argument(
        '--output-topic',
        type=str,
        default='f1-anomalies',
        help='Output topic for anomalies'
    )
    parser.add_argument(
        '--consumer-group',
        type=str,
        default='moe-anomaly-detector',
        help='Consumer group ID'
    )

    args = parser.parse_args()

    # Paths
    scalers_dir = ROOT / 'data' / 'processed' / 'MoE-anomaly' / 'scalers'
    models_dir = ROOT / 'models' / 'anomaly-detection'

    try:
        # Initialize and run detector
        detector = MoEAnomalyDetector(
            kafka_servers=args.kafka_servers,
            input_topic=args.input_topic,
            output_topic=args.output_topic,
            consumer_group=args.consumer_group,
            scalers_dir=str(scalers_dir),
            models_dir=str(models_dir)
        )

        detector.run()

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
