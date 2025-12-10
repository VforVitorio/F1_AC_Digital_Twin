"""
Synthetic Data Generator - Direct to InfluxDB

Generates realistic synthetic telemetry and "healthy" anomaly data
and writes it directly to InfluxDB for Grafana visualization.

NO Kafka, NO Models, NO Anomalies - Just clean demo data!
"""

import time
import random
import math
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# InfluxDB Configuration
INFLUX_URL = 'http://localhost:8086'
INFLUX_TOKEN = 'f1-telemetry-token-super-secret'
INFLUX_ORG = 'f1-org'
INFLUX_BUCKET_TELEMETRY = 'f1-telemetry'
INFLUX_BUCKET_ANOMALIES = 'f1-anomalies'


class SyntheticF1Data:
    """Generate realistic F1 telemetry data."""

    def __init__(self):
        self.lap = 1
        self.time_in_lap = 0.0
        self.speed = 150.0
        self.rpm = 8000
        self.throttle = 0.5
        self.brake = 0.0
        self.steering = 0.0
        self.gear = 4

        # Tire temperatures (realistic range)
        self.tire_temps = {
            'FL': 80.0,
            'FR': 80.0,
            'RL': 82.0,
            'RR': 82.0
        }

        # Track position (for creating realistic lap progression)
        self.track_position = 0.0  # 0.0 to 1.0

    def update(self, dt=0.1):
        """Update simulation state."""
        self.time_in_lap += dt
        self.track_position += dt / 90.0  # ~90 second lap

        # Complete lap every 90 seconds
        if self.track_position >= 1.0:
            self.track_position = 0.0
            self.lap += 1
            logger.info(f"🏁 Lap {self.lap} completed!")

        # Simulate realistic driving through corners and straights
        # Position 0.0-0.2: Fast straight
        # Position 0.2-0.4: Medium corner
        # Position 0.4-0.6: Slow corner
        # Position 0.6-0.8: Medium straight
        # Position 0.8-1.0: Fast corner

        if 0.0 <= self.track_position < 0.2:
            # Fast straight - high speed, high throttle
            target_speed = 280 + random.uniform(-10, 10)
            target_throttle = 0.95 + random.uniform(-0.05, 0.05)
            target_brake = 0.0
            target_gear = 7
            target_steering = random.uniform(-0.05, 0.05)

        elif 0.2 <= self.track_position < 0.4:
            # Medium corner - moderate speed
            target_speed = 180 + random.uniform(-10, 10)
            target_throttle = 0.6 + random.uniform(-0.1, 0.1)
            target_brake = 0.3 if self.speed > 200 else 0.0
            target_gear = 5
            target_steering = random.uniform(0.3, 0.5)

        elif 0.4 <= self.track_position < 0.6:
            # Slow corner - low speed
            target_speed = 120 + random.uniform(-10, 10)
            target_throttle = 0.4 + random.uniform(-0.1, 0.1)
            target_brake = 0.6 if self.speed > 140 else 0.0
            target_gear = 3
            target_steering = random.uniform(-0.6, -0.4)

        elif 0.6 <= self.track_position < 0.8:
            # Medium straight
            target_speed = 220 + random.uniform(-10, 10)
            target_throttle = 0.85 + random.uniform(-0.05, 0.05)
            target_brake = 0.0
            target_gear = 6
            target_steering = random.uniform(-0.1, 0.1)

        else:
            # Fast corner
            target_speed = 200 + random.uniform(-10, 10)
            target_throttle = 0.75 + random.uniform(-0.1, 0.1)
            target_brake = 0.2 if self.speed > 220 else 0.0
            target_gear = 5
            target_steering = random.uniform(0.4, 0.6)

        # Smooth transitions
        self.speed += (target_speed - self.speed) * 0.1
        self.throttle += (target_throttle - self.throttle) * 0.2
        self.brake += (target_brake - self.brake) * 0.3
        self.gear = target_gear
        self.steering += (target_steering - self.steering) * 0.2

        # RPM based on speed and gear
        self.rpm = int(5000 + (self.speed / 280.0) * 8000 + random.uniform(-200, 200))
        self.rpm = max(3000, min(13000, self.rpm))

        # Tire temperatures increase with speed and braking
        heat_factor = (self.speed / 280.0) * 5 + (self.brake * 10)
        for tire in self.tire_temps:
            # Rear tires run hotter
            base_temp = 82.0 if tire.startswith('R') else 78.0
            self.tire_temps[tire] += (base_temp + heat_factor - self.tire_temps[tire]) * 0.05
            self.tire_temps[tire] += random.uniform(-0.5, 0.5)
            # Keep in realistic range
            self.tire_temps[tire] = max(70.0, min(95.0, self.tire_temps[tire]))

    def get_telemetry(self):
        """Get current telemetry data point."""
        # G-forces based on driving
        g_lateral = self.steering * 2.5 + random.uniform(-0.2, 0.2)
        g_longitudinal = (self.throttle - self.brake) * 1.5 + random.uniform(-0.1, 0.1)

        return {
            'Speed_kmh': round(self.speed, 1),
            'RPM': self.rpm,
            'Gear': self.gear,
            'Throttle': round(self.throttle, 3),
            'Brake': round(self.brake, 3),
            'Steering': round(self.steering, 3),
            'AccG_Lateral': round(g_lateral, 3),
            'AccG_Longitudinal': round(g_longitudinal, 3),
            'AccG_Vertical': round(random.uniform(-0.3, 0.3), 3),
            'TireTemp_FL_Inner': round(self.tire_temps['FL'] - 2, 1),
            'TireTemp_FL_Middle': round(self.tire_temps['FL'], 1),
            'TireTemp_FL_Outer': round(self.tire_temps['FL'] + 2, 1),
            'TireTemp_FL_Avg': round(self.tire_temps['FL'], 1),
            'TireTemp_FR_Inner': round(self.tire_temps['FR'] - 2, 1),
            'TireTemp_FR_Middle': round(self.tire_temps['FR'], 1),
            'TireTemp_FR_Outer': round(self.tire_temps['FR'] + 2, 1),
            'TireTemp_FR_Avg': round(self.tire_temps['FR'], 1),
            'TireTemp_RL_Inner': round(self.tire_temps['RL'] - 2, 1),
            'TireTemp_RL_Middle': round(self.tire_temps['RL'], 1),
            'TireTemp_RL_Outer': round(self.tire_temps['RL'] + 2, 1),
            'TireTemp_RL_Avg': round(self.tire_temps['RL'], 1),
            'TireTemp_RR_Inner': round(self.tire_temps['RR'] - 2, 1),
            'TireTemp_RR_Middle': round(self.tire_temps['RR'], 1),
            'TireTemp_RR_Outer': round(self.tire_temps['RR'] + 2, 1),
            'TireTemp_RR_Avg': round(self.tire_temps['RR'], 1),
            'TireLoad_FL': round(1800 + random.uniform(-200, 200), 1),
            'TireLoad_FR': round(1800 + random.uniform(-200, 200), 1),
            'TireLoad_RL': round(2000 + random.uniform(-200, 200), 1),
            'TireLoad_RR': round(2000 + random.uniform(-200, 200), 1),
            'TirePressure_FL': round(25.5 + random.uniform(-0.2, 0.2), 2),
            'TirePressure_FR': round(25.5 + random.uniform(-0.2, 0.2), 2),
            'TirePressure_RL': round(25.6 + random.uniform(-0.2, 0.2), 2),
            'TirePressure_RR': round(25.6 + random.uniform(-0.2, 0.2), 2),
            'Fuel': round(50.0 - (self.time_in_lap / 90.0) * 2, 2),
            'CompletedLaps': self.lap,
        }

    def get_healthy_anomaly_scores(self):
        """Generate healthy (low) anomaly scores."""
        # All scores should be low (indicating no anomalies)
        return {
            'expert1_tire': round(-95.0 + random.uniform(-2, 2), 2),
            'expert2_dynamics': round(18.0 + random.uniform(-2, 2), 2),
            'expert3_control': round(2.5 + random.uniform(-1, 1), 2),
            'expert4_power': round(0.15 + random.uniform(-0.05, 0.05), 2),
            'global_score': round(-20.0 + random.uniform(-5, 5), 2),
            'anomaly_probability': round(random.uniform(0.01, 0.05), 3),  # 1-5% probability
            'is_anomaly': False,
            'anomaly_type': 'none',
            'severity': 'low'
        }


def write_telemetry_to_influx(telemetry, write_api):
    """Write telemetry to InfluxDB."""
    from datetime import datetime, timezone

    point = Point("telemetry").time(datetime.now(timezone.utc))

    for key, value in telemetry.items():
        if isinstance(value, (int, float)):
            point = point.field(key, float(value))

    write_api.write(bucket=INFLUX_BUCKET_TELEMETRY, org=INFLUX_ORG, record=point)


def write_anomaly_to_influx(anomaly_data, lap, write_api):
    """Write anomaly scores to InfluxDB."""
    from datetime import datetime, timezone

    point = Point("anomaly") \
        .time(datetime.now(timezone.utc)) \
        .tag("anomaly_type", anomaly_data['anomaly_type']) \
        .tag("is_anomaly", str(anomaly_data['is_anomaly'])) \
        .tag("lap", str(lap)) \
        .tag("severity", anomaly_data['severity']) \
        .field("expert1_tire_score", anomaly_data['expert1_tire']) \
        .field("expert2_dynamics_score", anomaly_data['expert2_dynamics']) \
        .field("expert3_control_score", anomaly_data['expert3_control']) \
        .field("expert4_power_score", anomaly_data['expert4_power']) \
        .field("global_score", anomaly_data['global_score']) \
        .field("anomaly_probability", anomaly_data['anomaly_probability'])

    write_api.write(bucket=INFLUX_BUCKET_ANOMALIES, org=INFLUX_ORG, record=point)


def main():
    """Main entry point."""
    logger.info("=" * 70)
    logger.info("SYNTHETIC DATA GENERATOR - DIRECT TO INFLUXDB")
    logger.info("=" * 70)
    logger.info(f"InfluxDB URL: {INFLUX_URL}")
    logger.info(f"Telemetry bucket: {INFLUX_BUCKET_TELEMETRY}")
    logger.info(f"Anomalies bucket: {INFLUX_BUCKET_ANOMALIES}")
    logger.info("Generating clean synthetic data with NO anomalies")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 70)

    # Connect to InfluxDB
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    # Initialize synthetic data generator
    sim = SyntheticF1Data()

    points_written = 0
    start_time = time.time()

    try:
        while True:
            # Update simulation
            sim.update(dt=0.1)

            # Get telemetry and anomaly data
            telemetry = sim.get_telemetry()
            anomaly_scores = sim.get_healthy_anomaly_scores()

            # Write to InfluxDB
            write_telemetry_to_influx(telemetry, write_api)
            write_anomaly_to_influx(anomaly_scores, sim.lap, write_api)

            points_written += 1

            # Log progress
            if points_written % 100 == 0:
                elapsed = time.time() - start_time
                rate = points_written / elapsed if elapsed > 0 else 0
                logger.info(
                    f"✓ Written {points_written} points ({rate:.1f} pts/s) | "
                    f"Lap: {sim.lap} | Speed: {telemetry['Speed_kmh']:.0f} km/h | "
                    f"RPM: {telemetry['RPM']} | Gear: {telemetry['Gear']} | "
                    f"Tire FL: {telemetry['TireTemp_FL_Avg']:.1f}°C | "
                    f"Anomaly prob: {anomaly_scores['anomaly_probability']:.1%}"
                )

            # Sleep to maintain ~10Hz rate
            time.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("\n\nStopping...")
    finally:
        client.close()

        elapsed = time.time() - start_time
        rate = points_written / elapsed if elapsed > 0 else 0

        logger.info("=" * 70)
        logger.info("STOPPED")
        logger.info("=" * 70)
        logger.info(f"Total points written: {points_written}")
        logger.info(f"Total time: {elapsed:.2f}s")
        logger.info(f"Average rate: {rate:.1f} pts/s")
        logger.info(f"Laps completed: {sim.lap}")
        logger.info("=" * 70)


if __name__ == "__main__":
    main()
