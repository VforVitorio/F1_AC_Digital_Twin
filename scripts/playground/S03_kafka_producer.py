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
import mmap
import ctypes
import signal
import sys
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

# Configuration
KAFKA_TOPIC = 'f1-telemetry'
KAFKA_SERVERS = 'localhost:9092'
READ_INTERVAL = 0.1  # 10Hz sampling rate


# Assetto Corsa Shared Memory Structures
class SPageFilePhysics(ctypes.Structure):
    """Complete AC Physics Shared Memory Structure"""
    _fields_ = [
        ("packetId", ctypes.c_int),
        ("gas", ctypes.c_float),
        ("brake", ctypes.c_float),
        ("fuel", ctypes.c_float),
        ("gear", ctypes.c_int),
        ("rpms", ctypes.c_int),
        ("steerAngle", ctypes.c_float),
        ("speedKmh", ctypes.c_float),
        ("velocity", ctypes.c_float * 3),
        ("accG", ctypes.c_float * 3),
        ("wheelSlip", ctypes.c_float * 4),
        ("wheelLoad", ctypes.c_float * 4),
        ("wheelsPressure", ctypes.c_float * 4),
        ("wheelAngularSpeed", ctypes.c_float * 4),
        ("tyreWear", ctypes.c_float * 4),
        ("tyreDirtyLevel", ctypes.c_float * 4),
        ("tyreCoreTemperature", ctypes.c_float * 4),
        ("camberRAD", ctypes.c_float * 4),
        ("suspensionTravel", ctypes.c_float * 4),
        ("drs", ctypes.c_float),
        ("tc", ctypes.c_float),
        ("heading", ctypes.c_float),
        ("pitch", ctypes.c_float),
        ("roll", ctypes.c_float),
        ("cgHeight", ctypes.c_float),
        ("carDamage", ctypes.c_float * 5),
        ("numberOfTyresOut", ctypes.c_int),
        ("pitLimiterOn", ctypes.c_int),
        ("abs", ctypes.c_float),
        ("kersCharge", ctypes.c_float),
        ("kersInput", ctypes.c_float),
        ("autoShifterOn", ctypes.c_int),
        ("rideHeight", ctypes.c_float * 2),
        ("turboBoost", ctypes.c_float),
        ("ballast", ctypes.c_float),
        ("airDensity", ctypes.c_float),
        ("airTemp", ctypes.c_float),
        ("roadTemp", ctypes.c_float),
        ("localAngularVel", ctypes.c_float * 3),
        ("finalFF", ctypes.c_float),
        ("performanceMeter", ctypes.c_float),
        ("engineBrake", ctypes.c_int),
        ("ersRecoveryLevel", ctypes.c_int),
        ("ersPowerLevel", ctypes.c_int),
        ("ersHeatCharging", ctypes.c_int),
        ("ersIsCharging", ctypes.c_int),
        ("kersCurrentKJ", ctypes.c_float),
        ("drsAvailable", ctypes.c_int),
        ("drsEnabled", ctypes.c_int),
        ("brakeTemp", ctypes.c_float * 4),
        ("clutch", ctypes.c_float),
        ("tyreTempI", ctypes.c_float * 4),
        ("tyreTempM", ctypes.c_float * 4),
        ("tyreTempO", ctypes.c_float * 4),
        ("isAIControlled", ctypes.c_int),
        ("tyreContactPoint", ctypes.c_float * 4 * 3),
        ("tyreContactNormal", ctypes.c_float * 4 * 3),
        ("tyreContactHeading", ctypes.c_float * 4 * 3),
        ("brakeBias", ctypes.c_float),
        ("localVelocity", ctypes.c_float * 3),
        ("P2PActivations", ctypes.c_int),
        ("P2PStatus", ctypes.c_int),
        ("currentMaxRpm", ctypes.c_int),
        ("mz", ctypes.c_float * 4),
        ("fx", ctypes.c_float * 4),
        ("fy", ctypes.c_float * 4),
        ("slipRatio", ctypes.c_float * 4),
        ("slipAngle", ctypes.c_float * 4),
        ("tcinAction", ctypes.c_int),
        ("absInAction", ctypes.c_int),
        ("suspensionDamage", ctypes.c_float * 4),
        ("tyreTemp", ctypes.c_float * 4),
    ]


class SPageFileGraphics(ctypes.Structure):
    """AC Graphics/Session Shared Memory Structure"""
    _fields_ = [
        ("packetId", ctypes.c_int),
        ("status", ctypes.c_int),
        ("session", ctypes.c_int),
        ("currentTime", ctypes.c_wchar * 15),
        ("lastTime", ctypes.c_wchar * 15),
        ("bestTime", ctypes.c_wchar * 15),
        ("split", ctypes.c_wchar * 15),
        ("completedLaps", ctypes.c_int),
        ("position", ctypes.c_int),
        ("iCurrentTime", ctypes.c_int),
        ("iLastTime", ctypes.c_int),
        ("iBestTime", ctypes.c_int),
        ("sessionTimeLeft", ctypes.c_float),
        ("distanceTraveled", ctypes.c_float),
        ("isInPit", ctypes.c_int),
        ("currentSectorIndex", ctypes.c_int),
        ("lastSectorTime", ctypes.c_int),
        ("numberOfLaps", ctypes.c_int),
        ("tyreCompound", ctypes.c_wchar * 33),
        ("replayTimeMultiplier", ctypes.c_float),
        ("normalizedCarPosition", ctypes.c_float),
        ("carCoordinates", ctypes.c_float * 3),
        ("penaltyTime", ctypes.c_float),
        ("flag", ctypes.c_int),
        ("idealLineOn", ctypes.c_int),
        ("isInPitLane", ctypes.c_int),
        ("surfaceGrip", ctypes.c_float),
    ]


def open_shared_memory_try(name, size):
    """Try to open AC shared memory with fallback strategies"""
    candidates = [name, "Local\\" + name, "Global\\" + name]
    last_exc = None
    for cand in candidates:
        try:
            return mmap.mmap(-1, size, cand)
        except Exception as e:
            last_exc = e
    raise last_exc


def decode_c_wchar_array(arr):
    """Safely decode C wide character arrays"""
    try:
        s = "".join(arr)
    except Exception:
        try:
            s = str(arr)
        except Exception:
            s = ""
    return s.split('\x00', 1)[0]


def ms_to_timestr(ms):
    """Convert milliseconds to formatted lap time string"""
    try:
        if not isinstance(ms, int) or ms <= 0:
            return ""
        minutes = ms // 60000
        seconds = (ms % 60000) // 1000
        millis = ms % 1000
        return f"{minutes}:{seconds:02d}.{millis:03d}"
    except Exception:
        return ""


def setup_kafka_topic():
    """Create Kafka topic if it doesn't exist"""
    print("🔧 Setting up Kafka topic...")

    admin_client = AdminClient({'bootstrap.servers': KAFKA_SERVERS})

    try:
        topic = NewTopic(KAFKA_TOPIC, num_partitions=1, replication_factor=1)
        admin_client.create_topics([topic])
        print(f"✅ Topic '{KAFKA_TOPIC}' created successfully")
    except Exception as e:
        print(f"ℹ️  Topic already exists or error: {e}")


def configure_producer():
    """Configure Kafka producer"""
    print("⚙️  Configuring Kafka producer...")

    config = {
        'bootstrap.servers': KAFKA_SERVERS,
        'client.id': 'f1-telemetry-realtime-producer'
    }

    producer = Producer(config)
    print("✅ Producer configured successfully")
    return producer


def delivery_callback(err, msg):
    """Callback for message delivery confirmation"""
    if err is not None:
        print(f"❌ Message delivery failed: {err}")


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
        setup_kafka_topic()
        producer = configure_producer()

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
