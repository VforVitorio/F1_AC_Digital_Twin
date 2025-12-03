"""
InfluxDB Telemetry Pipeline
Pipeline class for consuming Kafka messages and storing in InfluxDB
"""

import json
import logging
from datetime import datetime, timezone
from confluent_kafka import KafkaError
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS


logger = logging.getLogger(__name__)


class F1TelemetryPipeline:
    """
    HANDS-ON 2: Complete F1 telemetry pipeline
    Consumes data from Kafka and stores it in InfluxDB for Grafana visualization
    """

    def __init__(self):
        """
        Task 2.1: Initialize Kafka and InfluxDB connections
        """
        self.consumer = None
        self.influx_client = None
        self.write_api = None
        self.message_count = 0
        self.error_count = 0

        print("=" * 60)
        print("F1 AC DIGITAL TWIN - HANDS-ON 2")
        print("IoT Dashboard Real-Time Visualization")
        print("=" * 60)

    def task_2_1_setup_influxdb(self, influx_url, influx_token, influx_org, influx_bucket):
        """
        Task 2.1: Setup InfluxDB connection and data model

        Configures InfluxDB connection and defines data model
        to store F1 telemetry as time series.

        Args:
            influx_url: InfluxDB URL
            influx_token: InfluxDB authentication token
            influx_org: InfluxDB organization
            influx_bucket: InfluxDB bucket name

        Returns:
            True if setup successful, False otherwise
        """
        print("📊 Task 2.1: Setup InfluxDB connection and data model...")

        try:
            # Create InfluxDB client
            self.influx_client = InfluxDBClient(
                url=influx_url,
                token=influx_token,
                org=influx_org
            )

            # Verify connection and health status
            health = self.influx_client.health()
            print(f"✅ InfluxDB Health: {health.status}")

            # Configure Write API with synchronous mode for debugging
            self.write_api = self.influx_client.write_api(
                write_options=SYNCHRONOUS)

            # Verify bucket exists
            buckets_api = self.influx_client.buckets_api()
            bucket = buckets_api.find_bucket_by_name(influx_bucket)

            if bucket:
                print(f"✅ Bucket '{influx_bucket}' found: {bucket.id}")
                print(
                    "✅ Data Model: f1_telemetry measurement with tags (car, driver, track)")
                print(
                    "✅ Fields: speed_kmh, rpm, throttle, brake, steering, gear, current_time_ms, car_x, car_y, car_z, distance")
            else:
                print(f"❌ Bucket '{influx_bucket}' not found")
                return False

            return True

        except Exception as e:
            print(f"❌ InfluxDB setup error: {e}")
            return False

    def task_2_2_setup_kafka_consumer(self, consumer):
        """
        Task 2.2: Set Kafka Consumer for real-time ingestion

        Args:
            consumer: Configured Kafka Consumer instance

        Returns:
            True if setup successful
        """
        print("🔧 Task 2.2: Set Kafka Consumer for real-time ingestion...")
        self.consumer = consumer
        return True

    def create_telemetry_point(self, telemetry_data):
        """
        Crear punto de datos InfluxDB con estructura optimizada para Grafana

        Modelo de datos actualizado para las variables del DF filtrado:
        Speed_kmh, RPM, Throttle, Brake, Steering, Gear, iCurrentTime_ms, CarX, CarY, CarZ, Distance

        - Measurement: f1_telemetry
        - Tags: car, driver, track (para filtros en Grafana)
        - Fields: todas las métricas del DF filtrado
        - Timestamp: UTC con precisión de nanosegundos

        Args:
            telemetry_data: Dictionary with telemetry data

        Returns:
            InfluxDB Point object or None if error
        """
        try:
            # Tags para categorización y filtros en Grafana
            point = Point("f1_telemetry") \
                .tag("car", "f1_2023") \
                .tag("driver", "hamilton") \
                .tag("track", "monza") \
                .tag("session", "practice") \
                .tag("data_source", "assetto_corsa")

            # Fields con todas las métricas del DF filtrado
            point = point \
                .field("speed_kmh", float(telemetry_data.get('speed_kmh', 0))) \
                .field("rpm", int(telemetry_data.get('rpm', 0))) \
                .field("throttle", float(telemetry_data.get('throttle', 0))) \
                .field("brake", float(telemetry_data.get('brake', 0))) \
                .field("steering", float(telemetry_data.get('steering', 0))) \
                .field("gear", int(telemetry_data.get('gear', 0))) \
                .field("current_time_ms", int(telemetry_data.get('current_time_ms', 0))) \
                .field("car_x", float(telemetry_data.get('car_x', 0))) \
                .field("car_y", float(telemetry_data.get('car_y', 0))) \
                .field("car_z", float(telemetry_data.get('car_z', 0))) \
                .field("distance", float(telemetry_data.get('distance', 0)))

            point = point \
                .field("throttle_percentage", float(telemetry_data.get('throttle', 0)) * 100) \
                .field("brake_percentage", float(telemetry_data.get('brake', 0)) * 100) \
                .field("steering_angle", float(telemetry_data.get('steering', 0))) \
                .field("is_braking", 1 if float(telemetry_data.get('brake', 0)) > 0.1 else 0) \
                .field("is_accelerating", 1 if float(telemetry_data.get('throttle', 0)) > 0.1 else 0) \
                .field("is_turning_left", 1 if float(telemetry_data.get('steering', 0)) < -0.1 else 0) \
                .field("is_turning_right", 1 if float(telemetry_data.get('steering', 0)) > 0.1 else 0)

            # Timestamp preciso
            point = point.time(datetime.now(timezone.utc), WritePrecision.NS)

            return point

        except Exception as e:
            logger.error(f"Error creating telemetry point: {e}")
            return None

    def process_message(self, message, influx_bucket, influx_org):
        """
        Procesar mensaje de Kafka y escribir a InfluxDB

        Args:
            message: Kafka message
            influx_bucket: InfluxDB bucket name
            influx_org: InfluxDB organization

        Returns:
            True if successful, False otherwise
        """
        try:
            telemetry_data = json.loads(message.value().decode('utf-8'))

            point = self.create_telemetry_point(telemetry_data)

            if point:
                self.write_api.write(bucket=influx_bucket,
                                     org=influx_org, record=point)

                self.message_count += 1

                if self.message_count % 10 == 0:
                    print(f"📡 {self.message_count:03d} messages processed - "
                          f"Speed: {telemetry_data.get('speed_kmh', 0):6.1f}km/h | "
                          f"RPM: {telemetry_data.get('rpm', 0):5d} | "
                          f"Gear: {telemetry_data.get('gear', 0)} | "
                          f"Steering: {telemetry_data.get('steering', 0):5.2f} | "
                          f"Distance: {telemetry_data.get('distance', 0):6.1f}m")

                return True

        except json.JSONDecodeError as e:
            self.error_count += 1
            logger.error(f"JSON decode error: {e}")
            return False

        except Exception as e:
            self.error_count += 1
            logger.error(f"Message processing error: {e}")
            return False

    def start_real_time_pipeline(self, kafka_topic, influx_bucket, influx_org):
        """
        Task 2.3: Iniciar pipeline en tiempo real

        Consume mensajes de Kafka y los procesa hacia InfluxDB
        para visualización inmediata en Grafana.

        Args:
            kafka_topic: Kafka topic name
            influx_bucket: InfluxDB bucket name
            influx_org: InfluxDB organization
        """
        print("🚀 Task 2.3: Starting real-time telemetry pipeline...")
        print(
            f"📊 Data flow: Kafka Topic '{kafka_topic}' → InfluxDB '{influx_bucket}' → Grafana")
        print("-" * 60)

        try:
            while True:
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Consumer error: {msg.error()}")
                        break

                success = self.process_message(msg, influx_bucket, influx_org)

                if not success:
                    logger.warning("Failed to process message")

        except KeyboardInterrupt:
            print("\n🛑 Pipeline stopped by user")

        except Exception as e:
            logger.error(f"Pipeline error: {e}")

        finally:
            self.cleanup()

    def cleanup(self):
        """
        Limpiar recursos y mostrar estadísticas
        """
        print("\n🧹 Cleaning up resources...")

        if self.consumer:
            self.consumer.close()
            print("✅ Kafka consumer closed")

        if self.write_api:
            self.write_api.flush()

        if self.influx_client:
            self.influx_client.close()
            print("✅ InfluxDB client closed")

        # Estadísticas finales
        print("\n📈 PIPELINE STATISTICS:")
        print(f"📊 Messages processed: {self.message_count}")
        print(f"❌ Errors encountered: {self.error_count}")

        if self.message_count > 0:
            success_rate = (
                (self.message_count - self.error_count) / self.message_count) * 100
            print(f"✅ Success rate: {success_rate:.1f}%")

        print("🏁 HANDS-ON 2 Consumer completed successfully")
