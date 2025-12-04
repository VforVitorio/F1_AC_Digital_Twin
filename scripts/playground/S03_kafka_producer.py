"""
F1 AC Digital Twin - Kafka Telemetry Producer (Real-Time)
Streams LIVE telemetry data from Assetto Corsa to Kafka topic

ARCHITECTURE:
- AC SHARED MEMORY: Real-time telemetry from Assetto Corsa
- PRODUCER: This script reads live data and sends to Kafka broker
- BROKER: Kafka server on localhost:9092
- TOPIC: 'f1-telemetry' channel for real-time data
- CONSUMER: Scripts reading messages for dashboards
"""

import json
import time
import ctypes
import signal
import sys
from pathlib import Path
from confluent_kafka import Producer

# Add project root to path to import config
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import configuration from centralized config
from config import (
    KAFKA_SERVERS,
    KAFKA_TOPIC,
    READ_INTERVAL
)

# Import modular components
from src.ac_schemas import SPageFilePhysics, SPageFileGraphics
from src.ac_utils import open_shared_memory_try, decode_c_wchar_array, ms_to_timestr
from src.kafka_handlers import setup_kafka_topic, configure_producer, delivery_callback


def stream_live_telemetry(producer):
    """
    Main streaming loop: reads AC telemetry and streams to Kafka
    """
    print("🚀 Starting LIVE telemetry streaming...")
    print("📡 Reading from Assetto Corsa shared memory...")
    print("🎮 Start driving in Assetto Corsa to see data...\n")

    # Connect to AC shared memory
    try:
        physics = open_shared_memory_try(
            "acpmf_physics", ctypes.sizeof(SPageFilePhysics))
        graphics = open_shared_memory_try(
            "acpmf_graphics", ctypes.sizeof(SPageFileGraphics))
    except Exception as e:
        print("❌ Could not connect to Assetto Corsa shared memory")
        print("   Make sure Assetto Corsa is running!")
        print(f"   Error: {repr(e)}")
        return

    print("✅ Connected to Assetto Corsa!\n")

    message_count = 0
    prev_completed_laps = None

    def cleanup(*args):
        """Cleanup on exit"""
        print(f"\n\n🛑 Stopping producer...")
        print(f"📊 Total messages sent: {message_count}")
        producer.flush()
        sys.exit(0)

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, cleanup)
    try:
        signal.signal(signal.SIGTERM, cleanup)
    except Exception:
        pass

    # Main streaming loop
    while True:
        try:
            # Read physics data
            physics.seek(0)
            buf = physics.read(ctypes.sizeof(SPageFilePhysics))
            data = SPageFilePhysics.from_buffer_copy(buf)

            # Read graphics/session data
            graphics.seek(0)
            buf_g = graphics.read(ctypes.sizeof(SPageFileGraphics))
            data_g = SPageFileGraphics.from_buffer_copy(buf_g)

            # Normalize gear (AC uses 1-based)
            gear = data.gear - 1 if data.gear > 0 else data.gear

            # Decode strings
            current_lap_time = ms_to_timestr(data_g.iCurrentTime)
            tyre_compound_str = decode_c_wchar_array(data_g.tyreCompound)

            # Extract coordinates
            coords = tuple(data_g.carCoordinates)

            # Build telemetry message with ALL variables
            telemetry_data = {
                # === INPUTS BÁSICOS ===
                'speed_kmh': float(data.speedKmh),
                'rpm': int(data.rpms),
                'throttle': float(data.gas),
                'brake': float(data.brake),
                'clutch': float(data.clutch),
                'steering': float(data.steerAngle),
                'gear': int(gear),

                # === VECTORES DE VELOCIDAD ===
                'velocity_x': float(data.velocity[0]),
                'velocity_y': float(data.velocity[1]),
                'velocity_z': float(data.velocity[2]),
                'local_velocity_x': float(data.localVelocity[0]),
                'local_velocity_y': float(data.localVelocity[1]),
                'local_velocity_z': float(data.localVelocity[2]),

                # === G-FORCES ===
                'accg_lateral': float(data.accG[0]),
                'accg_vertical': float(data.accG[1]),
                'accg_longitudinal': float(data.accG[2]),

                # === ORIENTACIÓN DEL COCHE ===
                'heading': float(data.heading),
                'pitch': float(data.pitch),
                'roll': float(data.roll),
                'cg_height': float(data.cgHeight),

                # === VELOCIDAD ANGULAR ===
                'angular_vel_x': float(data.localAngularVel[0]),
                'angular_vel_y': float(data.localAngularVel[1]),
                'angular_vel_z': float(data.localAngularVel[2]),

                # === NEUMÁTICOS - TEMPERATURAS (4 ruedas) ===
                'tire_temp_fl_inner': float(data.tyreTempI[0]),
                'tire_temp_fl_middle': float(data.tyreTempM[0]),
                'tire_temp_fl_outer': float(data.tyreTempO[0]),
                'tire_temp_fl_avg': float(data.tyreTemp[0]),
                'tire_temp_fl_core': float(data.tyreCoreTemperature[0]),

                'tire_temp_fr_inner': float(data.tyreTempI[1]),
                'tire_temp_fr_middle': float(data.tyreTempM[1]),
                'tire_temp_fr_outer': float(data.tyreTempO[1]),
                'tire_temp_fr_avg': float(data.tyreTemp[1]),
                'tire_temp_fr_core': float(data.tyreCoreTemperature[1]),

                'tire_temp_rl_inner': float(data.tyreTempI[2]),
                'tire_temp_rl_middle': float(data.tyreTempM[2]),
                'tire_temp_rl_outer': float(data.tyreTempO[2]),
                'tire_temp_rl_avg': float(data.tyreTemp[2]),
                'tire_temp_rl_core': float(data.tyreCoreTemperature[2]),

                'tire_temp_rr_inner': float(data.tyreTempI[3]),
                'tire_temp_rr_middle': float(data.tyreTempM[3]),
                'tire_temp_rr_outer': float(data.tyreTempO[3]),
                'tire_temp_rr_avg': float(data.tyreTemp[3]),
                'tire_temp_rr_core': float(data.tyreCoreTemperature[3]),

                # === NEUMÁTICOS - DESGASTE Y PRESIÓN ===
                'tire_wear_fl': float(data.tyreWear[0]),
                'tire_wear_fr': float(data.tyreWear[1]),
                'tire_wear_rl': float(data.tyreWear[2]),
                'tire_wear_rr': float(data.tyreWear[3]),

                'tire_pressure_fl': float(data.wheelsPressure[0]),
                'tire_pressure_fr': float(data.wheelsPressure[1]),
                'tire_pressure_rl': float(data.wheelsPressure[2]),
                'tire_pressure_rr': float(data.wheelsPressure[3]),

                # === NEUMÁTICOS - DINÁMICA ===
                'wheel_slip_fl': float(data.wheelSlip[0]),
                'wheel_slip_fr': float(data.wheelSlip[1]),
                'wheel_slip_rl': float(data.wheelSlip[2]),
                'wheel_slip_rr': float(data.wheelSlip[3]),

                # === FRENOS ===
                'brake_temp_fl': float(data.brakeTemp[0]),
                'brake_temp_fr': float(data.brakeTemp[1]),
                'brake_temp_rl': float(data.brakeTemp[2]),
                'brake_temp_rr': float(data.brakeTemp[3]),

                # === COMBUSTIBLE Y MOTOR ===
                'fuel': float(data.fuel),
                'turbo_boost': float(data.turboBoost),

                # === ERS/KERS ===
                'ers_recovery_level': int(data.ersRecoveryLevel),
                'ers_power_level': int(data.ersPowerLevel),
                'ers_heat_charging': int(data.ersHeatCharging),
                'ers_is_charging': bool(data.ersIsCharging),
                'kers_charge': float(data.kersCharge),
                'kers_input': float(data.kersInput),
                'kers_current_kj': float(data.kersCurrentKJ),

                # === DRS ===
                'drs': float(data.drs),
                'drs_available': bool(data.drsAvailable),
                'drs_enabled': bool(data.drsEnabled),

                # === AYUDAS DE CONDUCCIÓN ===
                'tc': float(data.tc),
                'tc_in_action': bool(data.tcinAction),
                'abs': float(data.abs),
                'abs_in_action': bool(data.absInAction),

                # === SETUP DEL COCHE ===
                'ride_height_front': float(data.rideHeight[0]),
                'ride_height_rear': float(data.rideHeight[1]),
                'brake_bias': float(data.brakeBias),

                # === AMBIENTE ===
                'air_temp': float(data.airTemp),
                'road_temp': float(data.roadTemp),
                'air_density': float(data.airDensity),

                # === POSICIÓN Y TIEMPOS ===
                'distance': float(data_g.distanceTraveled),
                'completed_laps': int(data_g.completedLaps),
                'current_time_ms': int(data_g.iCurrentTime),
                'current_lap_time': str(current_lap_time),
                'last_time_ms': int(data_g.iLastTime),
                'best_time_ms': int(data_g.iBestTime),
                'lap_number_total': int(data_g.numberOfLaps),
                'current_sector_index': int(data_g.currentSectorIndex),
                'last_sector_time_ms': int(data_g.lastSectorTime),
                'normalized_position': float(data_g.normalizedCarPosition),

                # === POSICIÓN 3D ===
                'car_x': float(coords[0]),
                'car_y': float(coords[1]),
                'car_z': float(coords[2]),

                # === ESTADO EN PISTA ===
                'is_in_pit': bool(data_g.isInPit),
                'is_in_pit_lane': bool(data_g.isInPitLane),
                'tyre_compound': str(tyre_compound_str),
                'flag': int(data_g.flag),
                'surface_grip': float(data_g.surfaceGrip),

                # === METADATA ===
                'timestamp': int(time.time()),
                'kafka_timestamp': int(time.time() * 1000)
            }

            # Send to Kafka
            producer.produce(
                KAFKA_TOPIC,
                value=json.dumps(telemetry_data).encode('utf-8'),
                callback=delivery_callback
            )

            message_count += 1

            # Lap completion detection
            if prev_completed_laps is None:
                prev_completed_laps = data_g.completedLaps
            elif data_g.completedLaps > prev_completed_laps:
                last_lap_time = ms_to_timestr(data_g.iLastTime)
                print(f"\n🏁 LAP COMPLETED! Time: {last_lap_time}\n")
                prev_completed_laps = data_g.completedLaps

            # Display progress every 10 messages
            if message_count % 10 == 0:
                print(f"📡 {message_count:05d} - Speed: {telemetry_data['speed_kmh']:6.1f}km/h | "
                      f"RPM: {telemetry_data['rpm']:5d} | Gear: {telemetry_data['gear']} | "
                      f"Lap: {telemetry_data['completed_laps']} ({current_lap_time})")

            # Poll for delivery reports
            producer.poll(0)

            # Wait before next read
            time.sleep(READ_INTERVAL)

        except Exception as e:
            print(f"⚠️  Error reading telemetry: {e}")
            time.sleep(1)


def main():
    """Main execution function"""
    print("=" * 60)
    print("F1 AC DIGITAL TWIN - REAL-TIME KAFKA PRODUCER")
    print("Streaming LIVE telemetry from Assetto Corsa")
    print("=" * 60)
    print()

    try:
        # Setup Kafka infrastructure
        setup_kafka_topic(KAFKA_SERVERS, KAFKA_TOPIC)
        producer = configure_producer(KAFKA_SERVERS, 'f1-telemetry-realtime-producer')

        print("\n" + "-" * 60 + "\n")

        # Start live streaming
        stream_live_telemetry(producer)

    except KeyboardInterrupt:
        print("\n🛑 Producer stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nMake sure:")
        print("- Assetto Corsa is running")
        print("- Kafka is running (docker-compose up)")
        print("- Required packages are installed")


if __name__ == "__main__":
    main()
