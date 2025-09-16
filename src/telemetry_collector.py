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

# ------------------------------
# Assetto Corsa Structures (corrected)
# ------------------------------


class SPageFilePhysics(ctypes.Structure):
    # use default alignment
    _fields_ = [
        ("packetId", ctypes.c_int),
        ("gas", ctypes.c_float),
        ("brake", ctypes.c_float),
        ("fuel", ctypes.c_float),
        ("gear", ctypes.c_int),
        ("rpms", ctypes.c_int),
        ("steerAngle", ctypes.c_float),
        ("speedKmh", ctypes.c_float),
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
    1. Connect to AC's physics and graphics shared memory
    2. Set up signal handlers for Ctrl+C graceful shutdown
    3. Enter main collection loop reading data every READ_INTERVAL seconds
    4. Process and normalize data on exit via save_and_exit()

    Data Collection:
    - Physics data: speed, RPM, throttle, brake, steering, gear
    - Graphics data: lap times, position, distance, car coordinates
    - Lap detection: automatic detection and notification of completed laps

    Error Handling:
    - Graceful connection failure if AC is not running
    - Signal handling for clean shutdown and data preservation
    - Robust data decoding with fallbacks for corrupted memory
    """
    try:
        physics = open_shared_memory_try(
            "acpmf_physics", ctypes.sizeof(SPageFilePhysics))
        graphics = open_shared_memory_try(
            "acpmf_graphics", ctypes.sizeof(SPageFileGraphics))
    except Exception as e:
        print("❌ Could not connect to Assetto Corsa. Is the game running?")
        print("   Error details:", repr(e))
        return

    print("✅ Connected to Assetto Corsa")
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
            print(f"\n✅ Data saved to {filename}")
            print(f"📊 Postprocessing applied: Distance normalized per lap")
            print(f"🔢 Laps detected and processed: {len(lap_start_distances)}")

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
    print("🚀 Starting telemetry collection... Press Ctrl+C to stop and save data\n")
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

        # Build comprehensive telemetry record for this timestamp
        records.append({
            "Timestamp": int(time.time()),
            "Speed_kmh": round(data.speedKmh, 2),
            "RPM": data.rpms,
            "Throttle": round(data.gas, 2),
            "Brake": round(data.brake, 2),
            "Steering": round(data.steerAngle, 3),
            "Gear": gear,
            "CompletedLaps": data_g.completedLaps,
            "iCurrentTime_ms": data_g.iCurrentTime,
            "CurrentLapTime_str": current_lap_time,
            "iLastTime_ms": data_g.iLastTime,
            "iBestTime_ms": data_g.iBestTime,
            "DistanceTraveled_m": round(data_g.distanceTraveled, 3),
            "LapNumberTotal": data_g.numberOfLaps,
            "CurrentSectorIndex": data_g.currentSectorIndex,
            "LastSectorTime_ms": data_g.lastSectorTime,
            "IsInPit": bool(data_g.isInPit),
            "IsInPitLane": bool(data_g.isInPitLane),
            "TyreCompound": tyre_compound_str,
            "CarX": coords[0],
            "CarY": coords[1],
            "CarZ": coords[2],
            "Flag": data_g.flag,
            "SurfaceGrip": round(data_g.surfaceGrip, 3),
        })

        # Display real-time telemetry summary (compact format)
        print(
            f"Speed: {data.speedKmh:.1f} km/h | RPM: {data.rpms} | "
            f"Throttle: {data.gas:.3f} | Brake: {data.brake:.3f} | "
            f"Steering: {data.steerAngle:.3f} | Gear: {gear} | "
            f"Lap: {data_g.completedLaps} | Current: {current_lap_time}"
        )

        # Wait before next reading cycle
        time.sleep(READ_INTERVAL)


if __name__ == "__main__":
    main()
