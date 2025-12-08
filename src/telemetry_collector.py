#!/usr/bin/env python3
"""
Assetto Corsa Telemetry Collector

This script connects to Assetto Corsa's shared memory interface to collect
real-time telemetry data during racing sessions. The data is saved to CSV
files with intelligent postprocessing.

Key Features:
- Real-time data collection from AC's physics and graphics shared memory
- Automatic lap detection and completion notifications
- Distance normalization: each lap starts at 0m for proper analysis
- Preserves both original AC data and normalized data
- Graceful shutdown with Ctrl+C saves all collected data
- Optional Kafka streaming for real-time processing

Distance Postprocessing:
The script addresses AC's cumulative distance measurement by creating
lap-relative distances. Instead of distances like 16,984m → 23,547m for
a lap, the output shows 0m → 6,563m, making lap-by-lap analysis possible.
"""
import mmap
import ctypes
import time
import os
import csv
import signal
import sys
import json
import argparse
from datetime import datetime
# ------------------------------
# Config
# ------------------------------
DIAGNOSTIC = True   # True prints sizes/offsets to verify memory layout
# Build dynamic path to data directory
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
TELEMETRY_DIR = os.path.join(project_root, 'data', 'raw')
READ_INTERVAL = 0.1  # seconds between reads

# Kafka configuration (set by command line args)
KAFKA_ENABLED = False
KAFKA_SERVERS = 'localhost:9092'
KAFKA_TOPIC = 'f1-telemetry'
kafka_producer = None

# ------------------------------
# Assetto Corsa Structures (corrected)
# ------------------------------


class SPageFilePhysics(ctypes.Structure):
    """
    Complete Assetto Corsa Physics Shared Memory Structure
    Contains all real-time physics telemetry data from the simulation
    """
    _fields_ = [
        ("packetId", ctypes.c_int),
        ("gas", ctypes.c_float),
        ("brake", ctypes.c_float),
        ("fuel", ctypes.c_float),
        ("gear", ctypes.c_int),
        ("rpms", ctypes.c_int),
        ("steerAngle", ctypes.c_float),
        ("speedKmh", ctypes.c_float),
        ("velocity", ctypes.c_float * 3),           # Velocity vector [x, y, z] in m/s
        ("accG", ctypes.c_float * 3),               # G-forces [x, y, z]
        ("wheelSlip", ctypes.c_float * 4),          # Wheel slip for each tire [FL, FR, RL, RR]
        ("wheelLoad", ctypes.c_float * 4),          # Load on each tire in Newtons
        ("wheelsPressure", ctypes.c_float * 4),     # Tire pressure in PSI
        ("wheelAngularSpeed", ctypes.c_float * 4),  # Angular speed of each wheel in rad/s
        ("tyreWear", ctypes.c_float * 4),           # Tire wear level (0-100%)
        ("tyreDirtyLevel", ctypes.c_float * 4),     # Dirt accumulated on tires
        ("tyreCoreTemperature", ctypes.c_float * 4),# Core temperature of each tire in °C
        ("camberRAD", ctypes.c_float * 4),          # Camber angle in radians
        ("suspensionTravel", ctypes.c_float * 4),   # Suspension travel in meters
        ("drs", ctypes.c_float),                    # DRS status (0 = off, 1 = on)
        ("tc", ctypes.c_float),                     # Traction control level
        ("heading", ctypes.c_float),                # Car heading angle
        ("pitch", ctypes.c_float),                  # Car pitch angle
        ("roll", ctypes.c_float),                   # Car roll angle
        ("cgHeight", ctypes.c_float),               # Center of gravity height
        ("carDamage", ctypes.c_float * 5),          # Damage levels [front, rear, left, right, center]
        ("numberOfTyresOut", ctypes.c_int),         # Number of tires off track
        ("pitLimiterOn", ctypes.c_int),             # Pit limiter status
        ("abs", ctypes.c_float),                    # ABS activation level
        ("kersCharge", ctypes.c_float),             # KERS/ERS charge level
        ("kersInput", ctypes.c_float),              # KERS/ERS input
        ("autoShifterOn", ctypes.c_int),            # Auto shifter enabled
        ("rideHeight", ctypes.c_float * 2),         # Ride height [front, rear] in mm
        ("turboBoost", ctypes.c_float),             # Turbo boost pressure
        ("ballast", ctypes.c_float),                # Ballast weight in kg
        ("airDensity", ctypes.c_float),             # Air density
        ("airTemp", ctypes.c_float),                # Air temperature in °C
        ("roadTemp", ctypes.c_float),               # Road temperature in °C
        ("localAngularVel", ctypes.c_float * 3),    # Local angular velocity [x, y, z]
        ("finalFF", ctypes.c_float),                # Final force feedback value
        ("performanceMeter", ctypes.c_float),       # Performance meter value
        ("engineBrake", ctypes.c_int),              # Engine brake setting
        ("ersRecoveryLevel", ctypes.c_int),         # ERS recovery level
        ("ersPowerLevel", ctypes.c_int),            # ERS power level
        ("ersHeatCharging", ctypes.c_int),          # ERS heat charging
        ("ersIsCharging", ctypes.c_int),            # ERS charging status
        ("kersCurrentKJ", ctypes.c_float),          # Current KERS energy in kJ
        ("drsAvailable", ctypes.c_int),             # DRS available flag
        ("drsEnabled", ctypes.c_int),               # DRS enabled flag
        ("brakeTemp", ctypes.c_float * 4),          # Brake temperature for each wheel in °C
        ("clutch", ctypes.c_float),                 # Clutch position
        ("tyreTempI", ctypes.c_float * 4),          # Tire inner temperature
        ("tyreTempM", ctypes.c_float * 4),          # Tire middle temperature
        ("tyreTempO", ctypes.c_float * 4),          # Tire outer temperature
        ("isAIControlled", ctypes.c_int),           # AI controlled flag
        ("tyreContactPoint", ctypes.c_float * 4 * 3),  # Contact point for each tire [x,y,z] * 4
        ("tyreContactNormal", ctypes.c_float * 4 * 3), # Contact normal for each tire [x,y,z] * 4
        ("tyreContactHeading", ctypes.c_float * 4 * 3),# Contact heading for each tire [x,y,z] * 4
        ("brakeBias", ctypes.c_float),              # Brake bias (front/rear distribution)
        ("localVelocity", ctypes.c_float * 3),      # Local velocity vector [x, y, z]
        ("P2PActivations", ctypes.c_int),           # Push-to-pass activations remaining
        ("P2PStatus", ctypes.c_int),                # Push-to-pass status
        ("currentMaxRpm", ctypes.c_int),            # Current max RPM for current gear
        ("mz", ctypes.c_float * 4),                 # Self-aligning torque for each tire
        ("fx", ctypes.c_float * 4),                 # Longitudinal force for each tire
        ("fy", ctypes.c_float * 4),                 # Lateral force for each tire
        ("slipRatio", ctypes.c_float * 4),          # Slip ratio for each tire
        ("slipAngle", ctypes.c_float * 4),          # Slip angle for each tire
        ("tcinAction", ctypes.c_int),               # TC in action flag
        ("absInAction", ctypes.c_int),              # ABS in action flag
        ("suspensionDamage", ctypes.c_float * 4),   # Suspension damage for each corner
        ("tyreTemp", ctypes.c_float * 4),           # Average tire temperature (combined I/M/O)
    ]


class SPageFileGraphics(ctypes.Structure):
    # NOTE: use c_wchar for wchar_t (UTF-16) and add extra fields to avoid misalignment
    _fields_ = [
        ("packetId", ctypes.c_int),
        ("status", ctypes.c_int),
        ("session", ctypes.c_int),
        ("currentTime", ctypes.c_wchar * 15),   # wchar_t[15]
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
        ("tyreCompound", ctypes.c_wchar * 33),  # wchar_t[33]
        # additional fields that appear in many SM versions (important)
        ("replayTimeMultiplier", ctypes.c_float),
        ("normalizedCarPosition", ctypes.c_float),
        ("carCoordinates", ctypes.c_float * 3),
        ("penaltyTime", ctypes.c_float),
        ("flag", ctypes.c_int),
        ("idealLineOn", ctypes.c_int),
        ("isInPitLane", ctypes.c_int),
        ("surfaceGrip", ctypes.c_float),
    ]

# ------------------------------
# Helpers for shared memory and decoding
# ------------------------------


def open_shared_memory_try(name, size):
    """
    Attempt to open Assetto Corsa's shared memory with fallback strategies.

    AC's shared memory can be located in different namespaces depending on
    system configuration and AC version. This function tries multiple
    common locations to establish a connection.

    Args:
        name (str): Base name of the shared memory object (e.g., "acpmf_physics")
        size (int): Expected size in bytes of the shared memory region

    Returns:
        mmap.mmap: Memory-mapped file object for reading AC data

    Raises:
        Exception: If all connection attempts fail

    Strategy:
        1. Try direct name (Windows default)
        2. Try Local\\ namespace (Windows session-specific)
        3. Try Global\\ namespace (Windows system-wide)
    """
    candidates = [name, "Local\\" + name, "Global\\" + name]
    last_exc = None
    for cand in candidates:
        try:
            return mmap.mmap(-1, size, cand)
        except Exception as e:
            last_exc = e
    raise last_exc


def decode_c_wchar_array(arr):
    """
    Safely decode C wide character arrays from AC's shared memory.

    AC uses UTF-16 wide characters (wchar_t) for string data like lap times
    and tire compounds. This function handles the conversion to Python strings
    while dealing with potential encoding issues and null terminators.

    Args:
        arr: C wide character array from shared memory structure

    Returns:
        str: Decoded string with null terminators removed

    Handles:
        - UTF-16 to Python string conversion
        - Null terminator removal
        - Fallback strategies for malformed data
    """
    # arr can be c_wchar_Array or already str; robustly try to get the string without nulls
    try:
        s = "".join(arr)
    except Exception:
        try:
            s = str(arr)
        except Exception:
            s = ""
    return s.split('\x00', 1)[0]


def ms_to_timestr(ms):
    """
    Convert milliseconds to formatted lap time string (M:SS.mmm).

    AC provides lap times as integer milliseconds. This function converts
    them to a human-readable format commonly used in motorsports.

    Args:
        ms (int): Time in milliseconds

    Returns:
        str: Formatted time string or empty string if invalid

    Examples:
        ms_to_timestr(65432) → "1:05.432"
        ms_to_timestr(123456) → "2:03.456"
        ms_to_timestr(0) → ""
        ms_to_timestr(-1) → ""
    """
    try:
        if not isinstance(ms, int) or ms <= 0:
            return ""
        minutes = ms // 60000
        seconds = (ms % 60000) // 1000
        millis = ms % 1000
        return f"{minutes}:{seconds:02d}.{millis:03d}"
    except Exception:
        return ""


def setup_kafka_producer(servers):
    """
    Setup Kafka producer for streaming telemetry.

    Args:
        servers (str): Kafka bootstrap servers

    Returns:
        Producer: Configured Kafka producer or None if failed
    """
    try:
        from confluent_kafka import Producer

        config = {
            'bootstrap.servers': servers,
            'client.id': 'ac-telemetry-collector'
        }

        producer = Producer(config)
        print(f"[OK] Connected to Kafka: {servers}")
        print(f"[OK] Publishing to topic: {KAFKA_TOPIC}")
        return producer
    except ImportError:
        print("[ERROR] confluent-kafka not installed. Run: pip install confluent-kafka")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to connect to Kafka: {e}")
        return None


def kafka_delivery_callback(err, msg):
    """Callback for Kafka message delivery reports."""
    if err:
        print(f"[ERROR] Kafka delivery failed: {err}")


def send_to_kafka(record):
    """
    Send telemetry record to Kafka.

    Args:
        record (dict): Telemetry data dictionary
    """
    global kafka_producer

    if not kafka_producer:
        return

    try:
        # Convert to JSON
        message = json.dumps(record)

        # Send to Kafka
        kafka_producer.produce(
            KAFKA_TOPIC,
            value=message.encode('utf-8'),
            callback=kafka_delivery_callback
        )

        # Poll for delivery reports (non-blocking)
        kafka_producer.poll(0)

    except Exception as e:
        print(f"[ERROR] Failed to send to Kafka: {e}")

# ------------------------------
# Main
# ------------------------------


def main():
    """
    Main telemetry collection loop with real-time data processing.

    This function establishes connections to AC's shared memory, sets up
    signal handlers for graceful shutdown, and runs the main data collection
    loop. The collected data is processed in real-time and saved on exit.

    Process Flow:
    1. Parse command line arguments
    2. Setup Kafka producer (if enabled)
    3. Connect to AC's physics and graphics shared memory
    4. Set up signal handlers for Ctrl+C graceful shutdown
    5. Enter main collection loop reading data every READ_INTERVAL seconds
    6. Stream to Kafka (if enabled) and/or save to CSV on exit

    Data Collection:
    - Physics data: speed, RPM, throttle, brake, steering, gear
    - Graphics data: lap times, position, distance, car coordinates
    - Lap detection: automatic detection and notification of completed laps

    Error Handling:
    - Graceful connection failure if AC is not running
    - Signal handling for clean shutdown and data preservation
    - Robust data decoding with fallbacks for corrupted memory
    """
    global KAFKA_ENABLED, KAFKA_SERVERS, KAFKA_TOPIC, kafka_producer

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Assetto Corsa Telemetry Collector')
    parser.add_argument('--kafka', action='store_true', help='Enable Kafka streaming')
    parser.add_argument('--kafka-servers', type=str, default='localhost:9092',
                        help='Kafka bootstrap servers (default: localhost:9092)')
    parser.add_argument('--kafka-topic', type=str, default='f1-telemetry',
                        help='Kafka topic name (default: f1-telemetry)')
    args = parser.parse_args()

    KAFKA_ENABLED = args.kafka
    KAFKA_SERVERS = args.kafka_servers
    KAFKA_TOPIC = args.kafka_topic

    # Setup Kafka if enabled
    if KAFKA_ENABLED:
        kafka_producer = setup_kafka_producer(KAFKA_SERVERS)
        if not kafka_producer:
            print("[WARNING] Kafka setup failed, continuing without streaming")
            KAFKA_ENABLED = False

    # Connect to Assetto Corsa
    try:
        physics = open_shared_memory_try(
            "acpmf_physics", ctypes.sizeof(SPageFilePhysics))
        graphics = open_shared_memory_try(
            "acpmf_graphics", ctypes.sizeof(SPageFileGraphics))
    except Exception as e:
        print("[ERROR] Could not connect to Assetto Corsa. Is the game running?")
        print("   Error details:", repr(e))
        return

    print("[OK] Connected to Assetto Corsa")
    print(f"sizeof SPageFilePhysics = {ctypes.sizeof(SPageFilePhysics)} bytes")
    print(
        f"sizeof SPageFileGraphics = {ctypes.sizeof(SPageFileGraphics)} bytes")

    if DIAGNOSTIC:
        print("\n--- SPageFileGraphics Offsets ---")
        try:
            for name, _ in SPageFileGraphics._fields_:
                off = getattr(SPageFileGraphics, name).offset
                print(f"{name}: offset = {off}")
        except Exception as e:
            print("Could not get offsets automatically:", e)
        print("--- End offsets ---\n")

    os.makedirs(TELEMETRY_DIR, exist_ok=True)
    records = []

    # State tracking for lap detection and completion messages
    prev_completed_laps = None

    def save_and_exit(*args):
        """
        Save telemetry data to CSV with postprocessing to normalize lap distances.

        This function performs the following operations:
        1. Collects all raw telemetry data from the session
        2. Postprocesses the data to create lap-relative distance measurements
        3. Saves both original and normalized distance data to CSV

        Distance Normalization Algorithm:
        - Problem: AC's DistanceTraveled_m is cumulative across the entire session
        - Solution: Calculate relative distance from the start of each lap
        - Method: For each lap, subtract the distance where that lap began

        Example:
        Original data:    Lap 0: 16,984m → 18,000m, Lap 1: 23,556m → 24,500m
        Normalized data:  Lap 0: 0m → 1,016m,      Lap 1: 0m → 944m

        This makes each lap start at distance 0, enabling proper lap-by-lap analysis.
        """
        if records:
            # === POSTPROCESSING: LAP-RELATIVE DISTANCE CALCULATION ===
            processed_records = []
            lap_start_distances = {}  # Dictionary: {lap_number: starting_distance_in_meters}

            # Phase 1: Identify where each lap begins and calculate relative distances
            for record in records:
                lap_num = record["CompletedLaps"]
                original_distance = record["DistanceTraveled_m"]

                # Store the starting distance for this lap (first time we see this lap number)
                if lap_num not in lap_start_distances:
                    lap_start_distances[lap_num] = original_distance

                # Calculate distance relative to the start of the current lap
                # Formula: relative_distance = current_distance - distance_at_lap_start
                relative_distance = original_distance - \
                    lap_start_distances[lap_num]

                # Create new record with both original and normalized distance data
                new_record = record.copy()
                new_record["Distance"] = round(
                    relative_distance, 3)  # New normalized column
                # Preserve original AC data
                new_record["DistanceTraveled_m_Original"] = original_distance

                processed_records.append(new_record)

            # Phase 2: Save processed data to CSV file
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = os.path.join(
                TELEMETRY_DIR, f"telemetry_{timestamp}.csv"
            )
            with open(filename, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=list(processed_records[0].keys()))
                writer.writeheader()
                writer.writerows(processed_records)

            # Report successful save with processing statistics
            print(f"\n[OK] Data saved to {filename}")
            print(f"[INFO] Postprocessing applied: Distance normalized per lap")
            print(f"[INFO] Laps detected and processed: {len(lap_start_distances)}")

            # Show lap distance ranges for verification
            for lap_num, start_dist in lap_start_distances.items():
                lap_records = [
                    r for r in processed_records if r["CompletedLaps"] == lap_num]
                if lap_records:
                    max_relative = max(r["Distance"] for r in lap_records)
                    print(
                        f"   Lap {lap_num}: 0m → {max_relative:.0f}m (started at {start_dist:.0f}m absolute)")
        sys.exit(0)

    # Setup signal handlers for graceful shutdown (Ctrl+C, system termination)
    signal.signal(signal.SIGINT, save_and_exit)
    try:
        signal.signal(signal.SIGTERM, save_and_exit)
    except Exception:
        pass  # SIGTERM not available on all platforms

    # === MAIN TELEMETRY COLLECTION LOOP ===
    print("[START] Starting telemetry collection... Press Ctrl+C to stop and save data\n")
    while True:
        # Read current physics data from shared memory
        physics.seek(0)
        buf = physics.read(ctypes.sizeof(SPageFilePhysics))
        data = SPageFilePhysics.from_buffer_copy(buf)

        # Read current graphics/session data from shared memory
        graphics.seek(0)
        buf_g = graphics.read(ctypes.sizeof(SPageFileGraphics))
        data_g = SPageFileGraphics.from_buffer_copy(buf_g)

        # Normalize gear numbering (AC uses 1-based, we prefer 0-based for neutral)
        gear = data.gear - 1 if data.gear > 0 else data.gear

        # Decode AC's wide character strings to Python strings
        current_time_str = decode_c_wchar_array(data_g.currentTime)
        last_time_str = decode_c_wchar_array(data_g.lastTime)
        best_time_str = decode_c_wchar_array(data_g.bestTime)
        split_str = decode_c_wchar_array(data_g.split)
        tyre_compound_str = decode_c_wchar_array(data_g.tyreCompound)

        # Convert current lap time from milliseconds to readable format
        current_lap_time = ms_to_timestr(data_g.iCurrentTime)

        # Lap completion detection and notification
        if prev_completed_laps is None:
            prev_completed_laps = data_g.completedLaps
        else:
            if data_g.completedLaps > prev_completed_laps:
                last_lap_ms = data_g.iLastTime
                print(
                    f"🏁 Lap completed! Time: {ms_to_timestr(last_lap_ms)} (Lap {prev_completed_laps + 1})")
            prev_completed_laps = data_g.completedLaps

        # Extract car coordinates for positional analysis
        coords = tuple(data_g.carCoordinates)

        # Build comprehensive telemetry record for this timestamp with ALL available variables
        record = {
            # === TIMESTAMP ===
            "Timestamp": int(time.time()),

            # === BASIC DRIVING INPUTS ===
            "Speed_kmh": round(data.speedKmh, 2),
            "RPM": data.rpms,
            "Throttle": round(data.gas, 2),
            "Brake": round(data.brake, 2),
            "Clutch": round(data.clutch, 3),
            "Steering": round(data.steerAngle, 3),
            "Gear": gear,

            # === VELOCITY VECTORS (m/s) ===
            "Velocity_X": round(data.velocity[0], 3),
            "Velocity_Y": round(data.velocity[1], 3),
            "Velocity_Z": round(data.velocity[2], 3),
            "LocalVelocity_X": round(data.localVelocity[0], 3),
            "LocalVelocity_Y": round(data.localVelocity[1], 3),
            "LocalVelocity_Z": round(data.localVelocity[2], 3),

            # === G-FORCES ===
            "AccG_Lateral": round(data.accG[0], 3),      # Side-to-side
            "AccG_Vertical": round(data.accG[1], 3),     # Up-down
            "AccG_Longitudinal": round(data.accG[2], 3), # Forward-backward

            # === CAR ORIENTATION ===
            "Heading": round(data.heading, 3),
            "Pitch": round(data.pitch, 3),
            "Roll": round(data.roll, 3),
            "CG_Height": round(data.cgHeight, 3),

            # === ANGULAR VELOCITY ===
            "AngularVel_X": round(data.localAngularVel[0], 3),
            "AngularVel_Y": round(data.localAngularVel[1], 3),
            "AngularVel_Z": round(data.localAngularVel[2], 3),

            # === TIRE DATA - FRONT LEFT (FL) ===
            "TireTemp_FL_Inner": round(data.tyreTempI[0], 1),
            "TireTemp_FL_Middle": round(data.tyreTempM[0], 1),
            "TireTemp_FL_Outer": round(data.tyreTempO[0], 1),
            "TireTemp_FL_Avg": round(data.tyreTemp[0], 1),
            "TireTemp_FL_Core": round(data.tyreCoreTemperature[0], 1),
            "TireWear_FL": round(data.tyreWear[0], 2),
            "TireDirty_FL": round(data.tyreDirtyLevel[0], 3),
            "TirePressure_FL": round(data.wheelsPressure[0], 2),
            "TireLoad_FL": round(data.wheelLoad[0], 1),
            "WheelSlip_FL": round(data.wheelSlip[0], 3),
            "WheelAngularSpeed_FL": round(data.wheelAngularSpeed[0], 3),
            "SlipRatio_FL": round(data.slipRatio[0], 3),
            "SlipAngle_FL": round(data.slipAngle[0], 3),
            "Camber_FL": round(data.camberRAD[0], 4),
            "SuspensionTravel_FL": round(data.suspensionTravel[0], 4),
            "SuspensionDamage_FL": round(data.suspensionDamage[0], 2),
            "BrakeTemp_FL": round(data.brakeTemp[0], 1),
            "Mz_FL": round(data.mz[0], 2),  # Self-aligning torque
            "Fx_FL": round(data.fx[0], 2),  # Longitudinal force
            "Fy_FL": round(data.fy[0], 2),  # Lateral force

            # === TIRE DATA - FRONT RIGHT (FR) ===
            "TireTemp_FR_Inner": round(data.tyreTempI[1], 1),
            "TireTemp_FR_Middle": round(data.tyreTempM[1], 1),
            "TireTemp_FR_Outer": round(data.tyreTempO[1], 1),
            "TireTemp_FR_Avg": round(data.tyreTemp[1], 1),
            "TireTemp_FR_Core": round(data.tyreCoreTemperature[1], 1),
            "TireWear_FR": round(data.tyreWear[1], 2),
            "TireDirty_FR": round(data.tyreDirtyLevel[1], 3),
            "TirePressure_FR": round(data.wheelsPressure[1], 2),
            "TireLoad_FR": round(data.wheelLoad[1], 1),
            "WheelSlip_FR": round(data.wheelSlip[1], 3),
            "WheelAngularSpeed_FR": round(data.wheelAngularSpeed[1], 3),
            "SlipRatio_FR": round(data.slipRatio[1], 3),
            "SlipAngle_FR": round(data.slipAngle[1], 3),
            "Camber_FR": round(data.camberRAD[1], 4),
            "SuspensionTravel_FR": round(data.suspensionTravel[1], 4),
            "SuspensionDamage_FR": round(data.suspensionDamage[1], 2),
            "BrakeTemp_FR": round(data.brakeTemp[1], 1),
            "Mz_FR": round(data.mz[1], 2),
            "Fx_FR": round(data.fx[1], 2),
            "Fy_FR": round(data.fy[1], 2),

            # === TIRE DATA - REAR LEFT (RL) ===
            "TireTemp_RL_Inner": round(data.tyreTempI[2], 1),
            "TireTemp_RL_Middle": round(data.tyreTempM[2], 1),
            "TireTemp_RL_Outer": round(data.tyreTempO[2], 1),
            "TireTemp_RL_Avg": round(data.tyreTemp[2], 1),
            "TireTemp_RL_Core": round(data.tyreCoreTemperature[2], 1),
            "TireWear_RL": round(data.tyreWear[2], 2),
            "TireDirty_RL": round(data.tyreDirtyLevel[2], 3),
            "TirePressure_RL": round(data.wheelsPressure[2], 2),
            "TireLoad_RL": round(data.wheelLoad[2], 1),
            "WheelSlip_RL": round(data.wheelSlip[2], 3),
            "WheelAngularSpeed_RL": round(data.wheelAngularSpeed[2], 3),
            "SlipRatio_RL": round(data.slipRatio[2], 3),
            "SlipAngle_RL": round(data.slipAngle[2], 3),
            "Camber_RL": round(data.camberRAD[2], 4),
            "SuspensionTravel_RL": round(data.suspensionTravel[2], 4),
            "SuspensionDamage_RL": round(data.suspensionDamage[2], 2),
            "BrakeTemp_RL": round(data.brakeTemp[2], 1),
            "Mz_RL": round(data.mz[2], 2),
            "Fx_RL": round(data.fx[2], 2),
            "Fy_RL": round(data.fy[2], 2),

            # === TIRE DATA - REAR RIGHT (RR) ===
            "TireTemp_RR_Inner": round(data.tyreTempI[3], 1),
            "TireTemp_RR_Middle": round(data.tyreTempM[3], 1),
            "TireTemp_RR_Outer": round(data.tyreTempO[3], 1),
            "TireTemp_RR_Avg": round(data.tyreTemp[3], 1),
            "TireTemp_RR_Core": round(data.tyreCoreTemperature[3], 1),
            "TireWear_RR": round(data.tyreWear[3], 2),
            "TireDirty_RR": round(data.tyreDirtyLevel[3], 3),
            "TirePressure_RR": round(data.wheelsPressure[3], 2),
            "TireLoad_RR": round(data.wheelLoad[3], 1),
            "WheelSlip_RR": round(data.wheelSlip[3], 3),
            "WheelAngularSpeed_RR": round(data.wheelAngularSpeed[3], 3),
            "SlipRatio_RR": round(data.slipRatio[3], 3),
            "SlipAngle_RR": round(data.slipAngle[3], 3),
            "Camber_RR": round(data.camberRAD[3], 4),
            "SuspensionTravel_RR": round(data.suspensionTravel[3], 4),
            "SuspensionDamage_RR": round(data.suspensionDamage[3], 2),
            "BrakeTemp_RR": round(data.brakeTemp[3], 1),
            "Mz_RR": round(data.mz[3], 2),
            "Fx_RR": round(data.fx[3], 2),
            "Fy_RR": round(data.fy[3], 2),

            # === FUEL & ENGINE ===
            "Fuel": round(data.fuel, 3),
            "TurboBoost": round(data.turboBoost, 3),
            "EngineTemp_Oil": 90.0,  # AC shared memory doesn't provide oil temp, using default
            "EngineTemp_Water": round(data.airTemp, 1),  # Water temp approximation
            "EngineBrake": data.engineBrake,
            "CurrentMaxRpm": data.currentMaxRpm,

            # === ERS/KERS SYSTEM (F1 specific) ===
            "ERS_RecoveryLevel": data.ersRecoveryLevel,
            "ERS_PowerLevel": data.ersPowerLevel,
            "ERS_HeatCharging": data.ersHeatCharging,
            "ERS_IsCharging": bool(data.ersIsCharging),
            "KERS_Charge": round(data.kersCharge, 3),
            "KERS_Input": round(data.kersInput, 3),
            "KERS_CurrentKJ": round(data.kersCurrentKJ, 2),

            # === DRS (Drag Reduction System) ===
            "DRS": round(data.drs, 3),
            "DRS_Available": bool(data.drsAvailable),
            "DRS_Enabled": bool(data.drsEnabled),

            # === DRIVER AIDS ===
            "TC_Level": round(data.tc, 3),
            "TC_InAction": bool(data.tcinAction),
            "ABS_Level": round(data.abs, 3),
            "ABS_InAction": bool(data.absInAction),
            "AutoShifter": bool(data.autoShifterOn),
            "PitLimiter": bool(data.pitLimiterOn),

            # === VEHICLE SETUP ===
            "RideHeight_Front": round(data.rideHeight[0], 3),
            "RideHeight_Rear": round(data.rideHeight[1], 3),
            "BrakeBias": round(data.brakeBias, 3),
            "Ballast": round(data.ballast, 1),

            # === CAR DAMAGE ===
            "Damage_Front": round(data.carDamage[0], 2),
            "Damage_Rear": round(data.carDamage[1], 2),
            "Damage_Left": round(data.carDamage[2], 2),
            "Damage_Right": round(data.carDamage[3], 2),
            "Damage_Center": round(data.carDamage[4], 2),

            # === ENVIRONMENT ===
            "AirTemp": round(data.airTemp, 1),
            "RoadTemp": round(data.roadTemp, 1),
            "AirDensity": round(data.airDensity, 4),

            # === TRACK POSITION & LAP TIMING ===
            "CompletedLaps": data_g.completedLaps,
            "iCurrentTime_ms": data_g.iCurrentTime,
            "CurrentLapTime_str": current_lap_time,
            "iLastTime_ms": data_g.iLastTime,
            "iBestTime_ms": data_g.iBestTime,
            "DistanceTraveled_m": round(data_g.distanceTraveled, 3),
            "LapNumberTotal": data_g.numberOfLaps,
            "CurrentSectorIndex": data_g.currentSectorIndex,
            "LastSectorTime_ms": data_g.lastSectorTime,
            "NormalizedPosition": round(data_g.normalizedCarPosition, 4),

            # === PIT & TRACK STATUS ===
            "IsInPit": bool(data_g.isInPit),
            "IsInPitLane": bool(data_g.isInPitLane),
            "TyreCompound": tyre_compound_str,
            "Flag": data_g.flag,
            "SurfaceGrip": round(data_g.surfaceGrip, 3),
            "NumberOfTyresOut": data.numberOfTyresOut,

            # === CAR POSITION (3D Coordinates) ===
            "CarX": round(coords[0], 3),
            "CarY": round(coords[1], 3),
            "CarZ": round(coords[2], 3),

            # === ADVANCED TELEMETRY ===
            "FinalFF": round(data.finalFF, 3),  # Force feedback
            "PerformanceMeter": round(data.performanceMeter, 3),
            "IsAIControlled": bool(data.isAIControlled),
            "P2P_Activations": data.P2PActivations,  # Push-to-Pass
            "P2P_Status": data.P2PStatus,
        }

        records.append(record)

        # Send to Kafka if enabled
        if KAFKA_ENABLED:
            send_to_kafka(record)

        # Display real-time telemetry summary with enhanced data
        kafka_status = " | Kafka: ✓" if KAFKA_ENABLED else ""
        print(
            f"Speed: {data.speedKmh:.1f} km/h | RPM: {data.rpms} | Gear: {gear} | "
            f"Throttle: {data.gas:.2f} | Brake: {data.brake:.2f} | "
            f"G-Force: {data.accG[0]:.2f}lat {data.accG[2]:.2f}lon | "
            f"Tire: FL {data.tyreTemp[0]:.0f}°C FR {data.tyreTemp[1]:.0f}°C | "
            f"Lap: {data_g.completedLaps} ({current_lap_time}){kafka_status}"
        )

        # Wait before next reading cycle
        time.sleep(READ_INTERVAL)


if __name__ == "__main__":
    main()
