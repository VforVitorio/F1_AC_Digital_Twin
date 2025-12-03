"""
F1 AC Digital Twin - HANDS-ON 2
Kafka to InfluxDB Consumer + Real-Time Telemetry Dashboard

COMPLETE ARCHITECTURE:
AC Shared Memory → Producer → Kafka Topic → Consumer → InfluxDB → Grafana Dashboard

HANDS-ON 2 OBJECTIVES:
✓ Configure InfluxDB for time series data storage
✓ Create ingestion pipeline from Kafka to InfluxDB
✓ Configure Grafana for professional visualization
✓ Design real-time F1 telemetry dashboard
✓ Implement basic alerts in Grafana

TASKS:
- Task 2.1: Setup InfluxDB connection and data model
- Task 2.2: Create Kafka Consumer for real-time ingestion
- Task 2.3: Configure Grafana datasource and dashboard

NOTE: This consumer now works with LIVE telemetry data from Assetto Corsa
streamed in real-time through the Kafka producer.
"""

import logging
import sys
from pathlib import Path
from confluent_kafka import Consumer
from influxdb_client import InfluxDBClient

# Add project root to path to import config
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import configuration from centralized config
from config import (
    KAFKA_SERVERS,
    KAFKA_TOPIC,
    KAFKA_CONSUMER_GROUP,
    INFLUX_URL,
    INFLUX_TOKEN,
    INFLUX_ORG,
    INFLUX_BUCKET
)

# Import modular components
from src.kafka_handlers import configure_consumer
from src.influx_pipeline import F1TelemetryPipeline

# Use imported consumer group name
CONSUMER_GROUP = KAFKA_CONSUMER_GROUP


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def verify_prerequisites():
    """
    Verificar que todos los servicios estén corriendo
    """
    print("🔍 Verifying prerequisites...")

    services_ok = True

    # Test Kafka
    try:
        from confluent_kafka import Consumer
        test_consumer = Consumer({
            'bootstrap.servers': KAFKA_SERVERS,
            'group.id': 'test-group'
        })
        metadata = test_consumer.list_topics(timeout=5)
        test_consumer.close()

        if KAFKA_TOPIC in metadata.topics:
            print("✅ Kafka: Topic found and accessible")
        else:
            print(
                f"⚠️  Kafka: Topic '{KAFKA_TOPIC}' not found (run producer first)")

    except Exception as e:
        print(f"❌ Kafka: Connection failed - {e}")
        services_ok = False

    # Test InfluxDB
    try:
        client = InfluxDBClient(
            url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        client.close()
        print("✅ InfluxDB: Connection successful")
    except Exception as e:
        print(f"❌ InfluxDB: Connection failed - {e}")
        services_ok = False

    return services_ok


def main():
    """
    Función principal - HANDS-ON 2 completo
    """
    print("Starting HANDS-ON 2 verification...")

    # Verificar prerequisites
    if not verify_prerequisites():
        print("\n❌ Prerequisites not met. Please ensure:")
        print("1. Docker services are running: docker-compose ps")
        print("2. Producer has created the Kafka topic")
        print("3. InfluxDB is initialized with correct token")
        return

    print("\n" + "=" * 60)

    try:
        # Crear pipeline
        pipeline = F1TelemetryPipeline()

        # Task 2.1: Setup InfluxDB
        if not pipeline.task_2_1_setup_influxdb(
            INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET
        ):
            return

        print("\n" + "-" * 40)

        # Task 2.2: Setup Kafka Consumer
        consumer = configure_consumer(
            KAFKA_SERVERS, CONSUMER_GROUP, KAFKA_TOPIC,
            'f1-telemetry-handson2-consumer'
        )
        if not pipeline.task_2_2_setup_kafka_consumer(consumer):
            return

        print("\n" + "-" * 40)

        # Task 2.3: Start real-time pipeline
        pipeline.start_real_time_pipeline(KAFKA_TOPIC, INFLUX_BUCKET, INFLUX_ORG)

    except Exception as e:
        print(f"❌ HANDS-ON 2 failed: {e}")


if __name__ == "__main__":
    main()
