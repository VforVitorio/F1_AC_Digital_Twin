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
        Crear punto de datos InfluxDB con TODAS las variables de telemetría

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

            # === INPUTS BÁSICOS ===
            point = point \
                .field("speed_kmh", float(telemetry_data.get('speed_kmh', 0))) \
                .field("rpm", int(telemetry_data.get('rpm', 0))) \
                .field("throttle", float(telemetry_data.get('throttle', 0))) \
                .field("brake", float(telemetry_data.get('brake', 0))) \
                .field("clutch", float(telemetry_data.get('clutch', 0))) \
                .field("steering", float(telemetry_data.get('steering', 0))) \
                .field("gear", int(telemetry_data.get('gear', 0)))

            # === VECTORES DE VELOCIDAD ===
            point = point \
                .field("velocity_x", float(telemetry_data.get('velocity_x', 0))) \
                .field("velocity_y", float(telemetry_data.get('velocity_y', 0))) \
                .field("velocity_z", float(telemetry_data.get('velocity_z', 0))) \
                .field("local_velocity_x", float(telemetry_data.get('local_velocity_x', 0))) \
                .field("local_velocity_y", float(telemetry_data.get('local_velocity_y', 0))) \
                .field("local_velocity_z", float(telemetry_data.get('local_velocity_z', 0)))

            # === G-FORCES ===
            point = point \
                .field("accg_lateral", float(telemetry_data.get('accg_lateral', 0))) \
                .field("accg_vertical", float(telemetry_data.get('accg_vertical', 0))) \
                .field("accg_longitudinal", float(telemetry_data.get('accg_longitudinal', 0)))

            # === ORIENTACIÓN ===
            point = point \
                .field("heading", float(telemetry_data.get('heading', 0))) \
                .field("pitch", float(telemetry_data.get('pitch', 0))) \
                .field("roll", float(telemetry_data.get('roll', 0))) \
                .field("cg_height", float(telemetry_data.get('cg_height', 0)))

            # === VELOCIDAD ANGULAR ===
            point = point \
                .field("angular_vel_x", float(telemetry_data.get('angular_vel_x', 0))) \
                .field("angular_vel_y", float(telemetry_data.get('angular_vel_y', 0))) \
                .field("angular_vel_z", float(telemetry_data.get('angular_vel_z', 0)))

            # === NEUMÁTICOS - TEMPERATURAS ===
            point = point \
                .field("tire_temp_fl_inner", float(telemetry_data.get('tire_temp_fl_inner', 0))) \
                .field("tire_temp_fl_middle", float(telemetry_data.get('tire_temp_fl_middle', 0))) \
                .field("tire_temp_fl_outer", float(telemetry_data.get('tire_temp_fl_outer', 0))) \
                .field("tire_temp_fl_avg", float(telemetry_data.get('tire_temp_fl_avg', 0))) \
                .field("tire_temp_fl_core", float(telemetry_data.get('tire_temp_fl_core', 0))) \
                .field("tire_temp_fr_inner", float(telemetry_data.get('tire_temp_fr_inner', 0))) \
                .field("tire_temp_fr_middle", float(telemetry_data.get('tire_temp_fr_middle', 0))) \
                .field("tire_temp_fr_outer", float(telemetry_data.get('tire_temp_fr_outer', 0))) \
                .field("tire_temp_fr_avg", float(telemetry_data.get('tire_temp_fr_avg', 0))) \
                .field("tire_temp_fr_core", float(telemetry_data.get('tire_temp_fr_core', 0))) \
                .field("tire_temp_rl_inner", float(telemetry_data.get('tire_temp_rl_inner', 0))) \
                .field("tire_temp_rl_middle", float(telemetry_data.get('tire_temp_rl_middle', 0))) \
                .field("tire_temp_rl_outer", float(telemetry_data.get('tire_temp_rl_outer', 0))) \
                .field("tire_temp_rl_avg", float(telemetry_data.get('tire_temp_rl_avg', 0))) \
                .field("tire_temp_rl_core", float(telemetry_data.get('tire_temp_rl_core', 0))) \
                .field("tire_temp_rr_inner", float(telemetry_data.get('tire_temp_rr_inner', 0))) \
                .field("tire_temp_rr_middle", float(telemetry_data.get('tire_temp_rr_middle', 0))) \
                .field("tire_temp_rr_outer", float(telemetry_data.get('tire_temp_rr_outer', 0))) \
                .field("tire_temp_rr_avg", float(telemetry_data.get('tire_temp_rr_avg', 0))) \
                .field("tire_temp_rr_core", float(telemetry_data.get('tire_temp_rr_core', 0)))

            # === NEUMÁTICOS - DESGASTE Y PRESIÓN ===
            point = point \
                .field("tire_wear_fl", float(telemetry_data.get('tire_wear_fl', 0))) \
                .field("tire_wear_fr", float(telemetry_data.get('tire_wear_fr', 0))) \
                .field("tire_wear_rl", float(telemetry_data.get('tire_wear_rl', 0))) \
                .field("tire_wear_rr", float(telemetry_data.get('tire_wear_rr', 0))) \
                .field("tire_pressure_fl", float(telemetry_data.get('tire_pressure_fl', 0))) \
                .field("tire_pressure_fr", float(telemetry_data.get('tire_pressure_fr', 0))) \
                .field("tire_pressure_rl", float(telemetry_data.get('tire_pressure_rl', 0))) \
                .field("tire_pressure_rr", float(telemetry_data.get('tire_pressure_rr', 0)))

            # === NEUMÁTICOS - DINÁMICA ===
            point = point \
                .field("wheel_slip_fl", float(telemetry_data.get('wheel_slip_fl', 0))) \
                .field("wheel_slip_fr", float(telemetry_data.get('wheel_slip_fr', 0))) \
                .field("wheel_slip_rl", float(telemetry_data.get('wheel_slip_rl', 0))) \
                .field("wheel_slip_rr", float(telemetry_data.get('wheel_slip_rr', 0)))

            # === FRENOS ===
            point = point \
                .field("brake_temp_fl", float(telemetry_data.get('brake_temp_fl', 0))) \
                .field("brake_temp_fr", float(telemetry_data.get('brake_temp_fr', 0))) \
                .field("brake_temp_rl", float(telemetry_data.get('brake_temp_rl', 0))) \
                .field("brake_temp_rr", float(telemetry_data.get('brake_temp_rr', 0)))

            # === COMBUSTIBLE Y MOTOR ===
            point = point \
                .field("fuel", float(telemetry_data.get('fuel', 0))) \
                .field("turbo_boost", float(telemetry_data.get('turbo_boost', 0)))

            # === ERS/KERS ===
            point = point \
                .field("ers_recovery_level", int(telemetry_data.get('ers_recovery_level', 0))) \
                .field("ers_power_level", int(telemetry_data.get('ers_power_level', 0))) \
                .field("ers_heat_charging", int(telemetry_data.get('ers_heat_charging', 0))) \
                .field("ers_is_charging", int(telemetry_data.get('ers_is_charging', 0))) \
                .field("kers_charge", float(telemetry_data.get('kers_charge', 0))) \
                .field("kers_input", float(telemetry_data.get('kers_input', 0))) \
                .field("kers_current_kj", float(telemetry_data.get('kers_current_kj', 0)))

            # === DRS ===
            point = point \
                .field("drs", float(telemetry_data.get('drs', 0))) \
                .field("drs_available", int(telemetry_data.get('drs_available', 0))) \
                .field("drs_enabled", int(telemetry_data.get('drs_enabled', 0)))

            # === AYUDAS DE CONDUCCIÓN ===
            point = point \
                .field("tc", float(telemetry_data.get('tc', 0))) \
                .field("tc_in_action", int(telemetry_data.get('tc_in_action', 0))) \
                .field("abs", float(telemetry_data.get('abs', 0))) \
                .field("abs_in_action", int(telemetry_data.get('abs_in_action', 0)))

            # === SETUP DEL COCHE ===
            point = point \
                .field("ride_height_front", float(telemetry_data.get('ride_height_front', 0))) \
                .field("ride_height_rear", float(telemetry_data.get('ride_height_rear', 0))) \
                .field("brake_bias", float(telemetry_data.get('brake_bias', 0)))

            # === AMBIENTE ===
            point = point \
                .field("air_temp", float(telemetry_data.get('air_temp', 0))) \
                .field("road_temp", float(telemetry_data.get('road_temp', 0))) \
                .field("air_density", float(telemetry_data.get('air_density', 0)))

            # === POSICIÓN Y TIEMPOS ===
            point = point \
                .field("distance", float(telemetry_data.get('distance', 0))) \
                .field("completed_laps", int(telemetry_data.get('completed_laps', 0))) \
                .field("current_time_ms", int(telemetry_data.get('current_time_ms', 0))) \
                .field("last_time_ms", int(telemetry_data.get('last_time_ms', 0))) \
                .field("best_time_ms", int(telemetry_data.get('best_time_ms', 0))) \
                .field("current_sector_index", int(telemetry_data.get('current_sector_index', 0))) \
                .field("normalized_position", float(telemetry_data.get('normalized_position', 0)))

            # === POSICIÓN 3D ===
            point = point \
                .field("car_x", float(telemetry_data.get('car_x', 0))) \
                .field("car_y", float(telemetry_data.get('car_y', 0))) \
                .field("car_z", float(telemetry_data.get('car_z', 0)))

            # === CAMPOS DERIVADOS ===
            point = point \
                .field("throttle_percentage", float(telemetry_data.get('throttle', 0)) * 100) \
                .field("brake_percentage", float(telemetry_data.get('brake', 0)) * 100) \
                .field("is_braking", 1 if float(telemetry_data.get('brake', 0)) > 0.1 else 0) \
                .field("is_accelerating", 1 if float(telemetry_data.get('throttle', 0)) > 0.1 else 0)

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
