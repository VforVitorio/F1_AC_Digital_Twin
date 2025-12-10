"""
Telemetry to InfluxDB Writer

Consumes telemetry from Kafka and writes to InfluxDB for Grafana visualization.
"""

import sys
import json
import time
from pathlib import Path
from confluent_kafka import Consumer, KafkaError
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment or defaults
KAFKA_SERVERS = 'localhost:9092'
KAFKA_TOPIC = 'f1-telemetry'
KAFKA_GROUP = 'telemetry-influxdb-writer'

INFLUX_URL = 'http://localhost:8086'
INFLUX_TOKEN = 'f1-telemetry-token-super-secret'
INFLUX_ORG = 'f1-org'
INFLUX_BUCKET = 'f1-telemetry'


def write_telemetry_to_influx(telemetry: dict, write_api):
    """Write telemetry data point to InfluxDB."""
    try:
        # Create measurement point
        point = Point("telemetry")

        # Add timestamp
        if 'Timestamp' in telemetry:
            point = point.time(telemetry['Timestamp'], write_precision='s')

        # Add core metrics as fields
        core_fields = [
            'Speed_kmh', 'RPM', 'Gear', 'Throttle', 'Brake',
            'AccG_Lateral', 'AccG_Longitudinal', 'AccG_Vertical',
            'TireTemp_FL_Avg', 'TireTemp_FR_Avg', 'TireTemp_RL_Avg', 'TireTemp_RR_Avg',
            'TireTemp_FL_Inner', 'TireTemp_FL_Middle', 'TireTemp_FL_Outer',
            'TireTemp_FR_Inner', 'TireTemp_FR_Middle', 'TireTemp_FR_Outer',
            'TireTemp_RL_Inner', 'TireTemp_RL_Middle', 'TireTemp_RL_Outer',
            'TireTemp_RR_Inner', 'TireTemp_RR_Middle', 'TireTemp_RR_Outer',
            'TireLoad_FL', 'TireLoad_FR', 'TireLoad_RL', 'TireLoad_RR',
            'TirePressure_FL', 'TirePressure_FR', 'TirePressure_RL', 'TirePressure_RR',
            'Steering', 'Fuel', 'CompletedLaps'
        ]

        for field in core_fields:
            if field in telemetry and telemetry[field] is not None:
                point = point.field(field, float(telemetry[field]))

        # Write to InfluxDB
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)

        return True
    except Exception as e:
        logger.error(f"Failed to write telemetry to InfluxDB: {e}")
        return False


def main():
    """Main entry point."""
    logger.info("=" * 70)
    logger.info("TELEMETRY TO INFLUXDB WRITER")
    logger.info("=" * 70)
    logger.info(f"Kafka servers: {KAFKA_SERVERS}")
    logger.info(f"Kafka topic: {KAFKA_TOPIC}")
    logger.info(f"Consumer group: {KAFKA_GROUP}")
    logger.info(f"InfluxDB URL: {INFLUX_URL}")
    logger.info(f"InfluxDB bucket: {INFLUX_BUCKET}")
    logger.info("=" * 70)

    # Configure Kafka consumer
    consumer_config = {
        'bootstrap.servers': KAFKA_SERVERS,
        'group.id': KAFKA_GROUP,
        'auto.offset.reset': 'latest',
        'enable.auto.commit': True
    }

    consumer = Consumer(consumer_config)
    consumer.subscribe([KAFKA_TOPIC])

    # Configure InfluxDB client
    influx_client = InfluxDBClient(
        url=INFLUX_URL,
        token=INFLUX_TOKEN,
        org=INFLUX_ORG
    )
    write_api = influx_client.write_api(write_options=SYNCHRONOUS)

    logger.info("✓ Connected to Kafka and InfluxDB")
    logger.info("Waiting for telemetry messages...")

    messages_processed = 0
    start_time = time.time()

    try:
        while True:
            msg = consumer.poll(timeout=1.0)

            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                else:
                    logger.error(f"Kafka error: {msg.error()}")
                    continue

            try:
                # Parse telemetry message
                telemetry = json.loads(msg.value().decode('utf-8'))

                # Write to InfluxDB
                if write_telemetry_to_influx(telemetry, write_api):
                    messages_processed += 1

                    # Log progress
                    if messages_processed % 100 == 0:
                        elapsed = time.time() - start_time
                        rate = messages_processed / elapsed if elapsed > 0 else 0
                        speed = telemetry.get('Speed_kmh', 0)
                        rpm = telemetry.get('RPM', 0)
                        tire_temp = telemetry.get('TireTemp_FL_Avg', 0)
                        logger.info(
                            f"📊 Processed {messages_processed} messages ({rate:.1f} msg/s) | "
                            f"Speed: {speed:.1f} km/h | RPM: {rpm} | Tire FL: {tire_temp:.1f}°C"
                        )

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse message: {e}")
            except Exception as e:
                logger.error(f"Error processing message: {e}")

    except KeyboardInterrupt:
        logger.info("\n\nShutting down...")
    finally:
        consumer.close()
        influx_client.close()

        elapsed = time.time() - start_time
        rate = messages_processed / elapsed if elapsed > 0 else 0

        logger.info("=" * 70)
        logger.info("STOPPED")
        logger.info("=" * 70)
        logger.info(f"Total messages processed: {messages_processed}")
        logger.info(f"Total time: {elapsed:.2f}s")
        logger.info(f"Average rate: {rate:.1f} msg/s")
        logger.info("=" * 70)


if __name__ == "__main__":
    main()
