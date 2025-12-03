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

            # Build telemetry message
            telemetry_data = {
                # Core telemetry
                'distance': float(data_g.distanceTraveled),
                'timestamp': int(time.time()),
                'speed_kmh': float(data.speedKmh),
                'rpm': int(data.rpms),
                'throttle': float(data.gas),
                'brake': float(data.brake),
                'steering': float(data.steerAngle),
                'gear': int(gear),

                # Lap and timing
                'completed_laps': int(data_g.completedLaps),
                'current_time_ms': int(data_g.iCurrentTime),
                'current_lap_time': str(current_lap_time),
                'last_time_ms': int(data_g.iLastTime),
                'best_time_ms': int(data_g.iBestTime),
                'lap_number_total': int(data_g.numberOfLaps),
                'current_sector_index': int(data_g.currentSectorIndex),
                'last_sector_time_ms': int(data_g.lastSectorTime),

                # Position and environment
                'car_x': float(coords[0]),
                'car_y': float(coords[1]),
                'car_z': float(coords[2]),
                'is_in_pit': bool(data_g.isInPit),
                'is_in_pit_lane': bool(data_g.isInPitLane),
                'tyre_compound': str(tyre_compound_str),
                'flag': int(data_g.flag),
                'surface_grip': float(data_g.surfaceGrip),

                # Kafka timestamp
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
