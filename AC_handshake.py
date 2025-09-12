import mmap
import ctypes
import time
import os
import csv
import signal
import sys

# ------------------------------
# Config
# ------------------------------
DIAGNOSTIC = True   # True prints sizes/offsets to verify memory layout
TELEMETRY_DIR = "TELEMETRY"

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
    candidates = [name, "Local\\" + name, "Global\\" + name]
    last_exc = None
    for cand in candidates:
        try:
            return mmap.mmap(-1, size, cand)
        except Exception as e:
            last_exc = e
    raise last_exc


def decode_c_char_array(arr):
    # arr can be bytes-like or ctypes c_char_Array
    try:
        b = bytes(arr)
        return b.split(b'\x00', 1)[0].decode('utf-8', errors='ignore')
    except Exception:
        try:
            return str(arr).split('\x00', 1)[0]
        except Exception:
            return ""


def decode_c_wchar_array(arr):
    # arr can be c_wchar_Array or already str; robustly try to get the string without nulls
    try:
        # if it's iterable of c_wchar, ''.join will work
        s = "".join(arr)
    except Exception:
        try:
            s = str(arr)
        except Exception:
            s = ""
    return s.split('\x00', 1)[0]


def ms_to_timestr(ms):
    """Convert milliseconds to M:SS.mmm; if ms <= 0 returns empty string"""
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

    def save_csv(*args):
        if records:
            filename = os.path.join(
                TELEMETRY_DIR, f"telemetria_{int(time.time())}.csv")
            with open(filename, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=records[0].keys())
                writer.writeheader()
                writer.writerows(records)
            print(f"\n✅ Data saved to {filename}")
        sys.exit(0)

    signal.signal(signal.SIGINT, save_csv)

    # Main loop
    while True:
        # Read physics
        physics.seek(0)
        buf = physics.read(ctypes.sizeof(SPageFilePhysics))
        data = SPageFilePhysics.from_buffer_copy(buf)

        # Read graphics
        graphics.seek(0)
        buf_g = graphics.read(ctypes.sizeof(SPageFileGraphics))
        data_g = SPageFileGraphics.from_buffer_copy(buf_g)

        # Correct gear (if data.gear > 0, Assetto uses 1..n; you wanted 0..n-1)
        gear = data.gear - 1 if data.gear > 0 else data.gear

        # Decode wide/UTF-16 and normal strings
        current_time_str = decode_c_wchar_array(data_g.currentTime)
        last_time_str = decode_c_wchar_array(data_g.lastTime)
        best_time_str = decode_c_wchar_array(data_g.bestTime)
        split_str = decode_c_wchar_array(data_g.split)
        tyre_compound_str = decode_c_wchar_array(data_g.tyreCompound)

        # Current lap time (iCurrentTime is in ms; if 0 -> empty string)
        current_lap_time = ms_to_timestr(data_g.iCurrentTime)

        # Save record
        records.append({
            "Speed (km/h)": round(data.speedKmh, 2),
            "RPM": data.rpms,
            "Throttle": round(data.gas, 2),
            "Brake": round(data.brake, 2),
            "Steering": round(data.steerAngle, 2),
            "Gear": gear,
            "Completed Laps": data_g.completedLaps,
            "CurrentTime_str": current_time_str,
            "LastTime_str": last_time_str,
            "BestTime_str": best_time_str,
            "Split_str": split_str,
            "TyreCompound": tyre_compound_str,
            "Current Lap Time": current_lap_time,
            "iCurrentTime_ms": data_g.iCurrentTime,
        })

        # Print telemetry line
        print(
            f"Speed: {data.speedKmh:.1f} km/h | RPM: {data.rpms} | "
            f"Throttle: {data.gas:.2f} | Brake: {data.brake:.2f} | "
            f"Steering: {data.steerAngle:.2f} | Gear: {gear} | "
            f"Lap: {data_g.completedLaps} | Current Lap Time: {current_lap_time}"
        )

        time.sleep(0.1)


if __name__ == "__main__":
    main()
