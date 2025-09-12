# Assetto Corsa — Printable Mini-Guide: Shared Memory Telemetry Decoding

A compact, printer-friendly reference that shows exactly **how to decode the most useful Assetto Corsa shared-memory fields** (types, decoding functions, examples) and a recommended set of CSV/dashboard columns for your AC-Gym / distributed training project.

---

## Quick Summary (One Line)

Declare wide strings as `ctypes.c_wchar * N` (UTF-16, 2 bytes per char) and read ints/floats/arrays with the matching `ctypes` types. If string fields are declared incorrectly (e.g. `c_char`), all following offsets will be wrong and you will read garbage.

---

# 1. Core Mapping — Fields You Will Use for Training

Use this mapping between Assetto fields (structure names used in the code) and the training variables you listed.

| Training name  |                            Assetto field (struct) | ctypes type                                                             | Notes                                                                                 |
| -------------- | ------------------------------------------------: | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `vel` (speed)  |                       `SPageFilePhysics.speedKmh` | `ctypes.c_float`                                                        | km/h                                                                                  |
| `rpm`          |                           `SPageFilePhysics.rpms` | `ctypes.c_int`                                                          | integer RPM                                                                           |
| `steer_angle`  |                     `SPageFilePhysics.steerAngle` | `ctypes.c_float`                                                        | degrees (or radians depending on plugin) — inspect HUD vs raw                         |
| `throttle`     |                            `SPageFilePhysics.gas` | `ctypes.c_float`                                                        | 0.0–1.0                                                                               |
| `brake`        |                          `SPageFilePhysics.brake` | `ctypes.c_float`                                                        | 0.0–1.0                                                                               |
| `gear`         |                           `SPageFilePhysics.gear` | `ctypes.c_int`                                                          | game uses 1..N for forward, 0 neutral, -1 reverse — you may want to convert to 0..N-1 |
| `lap_progress` | compute from `distanceTraveled` or `iCurrentTime` | `distanceTraveled`: `c_float` (graphics) / `iCurrentTime`: `c_int` (ms) | See section on lap progress calculation below                                         |

---

# 2. Recommended `ctypes` Declarations (Core Snippet)

```py
# physics page (examples)
class SPageFilePhysics(ctypes.Structure):
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

# graphics page (strings as wide chars)
class SPageFileGraphics(ctypes.Structure):
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
        ("iCurrentTime", ctypes.c_int),  # ms
        ("iLastTime", ctypes.c_int),
        ("iBestTime", ctypes.c_int),
        ("sessionTimeLeft", ctypes.c_float),
        ("distanceTraveled", ctypes.c_float),
        ("isInPit", ctypes.c_int),
        ("currentSectorIndex", ctypes.c_int),
        ("lastSectorTime", ctypes.c_int),
        ("numberOfLaps", ctypes.c_int),
        ("tyreCompound", ctypes.c_wchar * 33),
        # optional extra trailing fields...
    ]
```

---

# 3. Decode Helpers (Copy/Paste)

```py
def decode_c_wchar_array(arr) -> str:
    """Decode ctypes.c_wchar_Array -> Python str without trailing nulls."""
    try:
        s = "".join(arr)          # arr is c_wchar array
    except Exception:
        s = str(arr)
    return s.split("\x00", 1)[0]

def decode_c_char_array(arr) -> str:
    """Decode ctypes.c_char_Array -> Python str (utf-8), trimming null bytes."""
    try:
        b = bytes(arr)
        return b.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
    except Exception:
        return ""

def ms_to_timestr(ms: int) -> str:
    """ms (int) -> 'M:SS.mmm'. Return '' for non-positive values."""
    if not isinstance(ms, int) or ms <= 0:
        return ""
    minutes = ms // 60000
    seconds = (ms % 60000) // 1000
    millis = ms % 1000
    return f"{minutes}:{seconds:02d}.{millis:03d}"
```

Usage example:

```py
current_time_str = decode_c_wchar_array(data_g.currentTime)
current_lap_time_str = ms_to_timestr(data_g.iCurrentTime)
```

---

# 4. How to Parse Every Useful Variable for a Telemetry Dashboard

Below are field-by-field decoding notes and what to store for the dashboard / training.

### Physics Page (Fast-Changing Telemetry)

- **`speedKmh`** (`c_float`) → store numeric km/h (`round(speedKmh,2)`).
- **`rpms`** (`c_int`) → integer RPM.
- **`gas` / throttle** (`c_float`) → 0.0..1.0, store as float.
- **`brake`** (`c_float`) → 0.0..1.0, store as float.
- **`steerAngle`** (`c_float`) → store float; for ML you may normalize to \[-1,1] by max steering range.
- **`gear`** (`c_int`) → convert if desired: `gear_adj = gear - 1 if gear > 0 else gear` to make 0-based.
- **`fuel`** (`c_float`) → fuel remaining.
- **Other physics floats** can include accelerations in some layouts — check if present in your version.

### Graphics Page (Session & Lap Info)

- **`currentTime`** (`c_wchar * 15`) → human string printed on HUD (useful for display only).
- **`iCurrentTime`** (`c_int`) → current lap time in **ms**. Use for ML signals and lap detection.
- **`iLastTime` / `iBestTime`** (`c_int`) → ms values for last / best lap — useful for reward shaping.
- **`lastTime`, `bestTime`** (`c_wchar[]`) → textual display copies (optional).
- **`completedLaps`** (`c_int`) → integer laps finished (use for lap events).
- **`distanceTraveled`** (`c_float`) → cumulative distance along the track (meters). Good for lap progress if you know track lap length.
- **`numberOfLaps`** (`c_int`) → total laps in session when available.
- **`currentSectorIndex`, `lastSectorTime`** → integer sector index and last sector time — useful for sector-based rewards.
- **`isInPit`, `isInPitLane`** (`c_int`) → booleans (0/1): avoid training actions while in pit.
- **`tyreCompound`** (`c_wchar * 33`) → string compound name — useful to tag data.

### Arrays & Coordinates

- **`carCoordinates`** (`c_float * 3`) → `[x, y, z]` position in world coordinates. Store as triple; can be used for advanced progress / off-track detection.
- **`normalizedCarPosition`/`surfaceGrip`** → floats describing position relative to track and grip — useful for state.

### Flags / Booleans

- **`flag`** (`c_int`) → race flag (0 none, 1 yellow, etc.) — check community doc for exact codes. Use to penalize or ignore data during flags.
- **`idealLineOn`** (`c_int`) → whether the ideal line is shown (display-only).

---

# 5. Lap Progress (How to Compute `lap_progress`)

Two robust approaches:

**A — Using `distanceTraveled` (recommended if accurate):**

- If `track_length_m` is known for the track (meters), then:

  ```py
  lap_progress = (distanceTraveled % track_length_m) / track_length_m
  ```

  where `%` handles multiple laps & resets. `distanceTraveled` is usually cumulative meters travelled in session.

**B — Using `iCurrentTime` (when you do not have track length):**

- Estimate expected lap time (e.g., `expected_lap_ms`) or use dynamic window:

  ```py
  lap_progress = min(1.0, data_g.iCurrentTime / expected_lap_ms)
  ```

- This is approximate and sensitive to `expected_lap_ms`.

**C — Lap Detection (Event):**

- Detect a new lap by monitoring `completedLaps`. When `data_g.completedLaps > prev_completedLaps`, you have a lap finish. `iLastTime` gives last lap ms.

---

# 6. CSV / Dashboard Column Recommendations

Minimum columns for training & dashboard:

```
timestamp_utc
speed_kmh
rpm
throttle
brake
steer_angle
gear
completed_laps
iCurrentTime_ms
current_lap_time_str
iLastTime_ms
iBestTime_ms
distance_traveled_m
lap_progress (computed)
is_in_pit
current_sector_index
tyre_compound
car_x,car_y,car_z
flag
```

Add derived columns:

- `speed_normalized` (0..1 by car top speed)
- `steer_normalized` (-1..1)
- `accel_longitudinal`, `accel_lateral` (if available / computed)
- `lap_delta` (`iCurrentTime` - bestLapSoFar)

---

# 7. Lap Event Snippet (Save Last Lap on Finish)

```py
prev_completed = data_g.completedLaps
# inside loop after reading data_g:
if data_g.completedLaps > prev_completed:
    # lap finished
    last_lap_ms = data_g.iLastTime
    print("Lap finished:", ms_to_timestr(last_lap_ms))
prev_completed = data_g.completedLaps
```

`iLastTime` is the most reliable millisecond measure for the lap just finished.

---

# 8. Diagnostics to Validate Structure/Layout

When starting, always print:

```py
print("sizeof SPageFileGraphics:", ctypes.sizeof(SPageFileGraphics))
for name, _ in SPageFileGraphics._fields_:
    print(name, getattr(SPageFileGraphics, name).offset)
```

Check that `completedLaps` and `iCurrentTime` offsets are reasonable (i.e. less than `sizeof` and in expected order). If not, your wide strings are declared incorrectly or your SM version has different trailing fields.

---

# 9. Common Pitfalls & Fixes

- **Strings declared as `c_char`** → corrupted offsets for later ints/floats. Fix by using `c_wchar`.
- **Forcing `_pack_` incorrectly** → misalignment. Prefer default alignment unless you have exact matching packing.
- **Different SM version / mod** → add/remove trailing fields to `SPageFileGraphics` to match offsets.
- **Reading fewer bytes than `ctypes.sizeof(...)`** → `from_buffer_copy` will be wrong. Always `read(ctypes.sizeof(struct))`.

---

# 10. Short Checklist Before Collecting Data for Training

1. Use the `SPageFileGraphics` structure with `c_wchar` for wide strings.
2. Verify `ctypes.sizeof` and offsets.
3. Print a few telemetry lines and ensure `iCurrentTime` evolves each frame and `completedLaps` increments correctly when you cross the line.
4. Log `iCurrentTime_ms`, `iLastTime_ms`, and `completed_laps` into CSV immediately upon lap completion.
5. Tag records with `tyre_compound` and `is_in_pit` to filter out invalid training data.

---

## End — Printable Note

This guide provides everything needed to reliably decode Assetto Corsa telemetry for AI training projects. For implementation examples, see the `test.py` script in this repository which demonstrates practical usage of these concepts.

### Key Resources

- **AssettoCorsaGym**: https://github.com/dasGringuen/assetto_corsa_gym
- **AC Shared Memory Documentation**: https://www.assettocorsa.net/forum/index.php?threads/shared-memory-interface.40892/
- **Project Repository**: Contains working examples and complete implementation

### Integration with AI Training

This telemetry data serves as the foundation for:

- **Behavior Cloning**: Supervised learning from human driving data
- **Reinforcement Learning**: State representation for RL algorithms
- **Distributed Training**: Data collection across multiple AC instances
- **Performance Analysis**: Lap time optimization and driving pattern analysis

---

_This document is part of the F1 AC Digital Twin project focused on autonomous driving AI development in Assetto Corsa._
