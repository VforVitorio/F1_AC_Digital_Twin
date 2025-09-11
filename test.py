import mmap
import ctypes
import time
import os
import csv
import signal
import sys

# ------------------------------
# Estructuras de Assetto Corsa (corregidas)
# ------------------------------


class SPageFilePhysics(ctypes.Structure):
    _pack_ = 1
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
    _pack_ = 1
    _fields_ = [
        ("packetId", ctypes.c_int),
        ("status", ctypes.c_int),
        ("session", ctypes.c_int),
        ("currentTime", ctypes.c_char * 15),   # bytes, no c_wchar
        ("lastTime", ctypes.c_char * 15),
        ("bestTime", ctypes.c_char * 15),
        ("split", ctypes.c_char * 15),
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
        ("tyreCompound", ctypes.c_char * 33),
    ]

# ------------------------------
# Función para abrir shared memory (prueba varios nombres)
# ------------------------------


def open_shared_memory_try(name, size):
    # Intentos: nombre tal cual, Local\name, Global\name
    candidates = [name, "Local\\" + name, "Global\\" + name]
    last_exc = None
    for cand in candidates:
        try:
            # mmap(fileno, length, tagname)
            return mmap.mmap(-1, size, cand)
        except Exception as e:
            last_exc = e
    # lanzar la última excepción para diagnóstico
    raise last_exc

# ------------------------------
# Main loop
# ------------------------------


def main():
    try:
        physics = open_shared_memory_try(
            "acpmf_physics", ctypes.sizeof(SPageFilePhysics))
        graphics = open_shared_memory_try(
            "acpmf_graphics", ctypes.sizeof(SPageFileGraphics))
    except Exception as e:
        print("❌ No se pudo conectar a Assetto Corsa. ¿Está el juego abierto?")
        print("   Detalle del error:", repr(e))
        return

    print("✅ Conectado a Assetto Corsa")

    os.makedirs("TELEMETRIA", exist_ok=True)
    registros = []

    def guardar_csv(*args):
        if registros:
            filename = f"TELEMETRIA/telemetria_{int(time.time())}.csv"
            with open(filename, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=registros[0].keys())
                writer.writeheader()
                writer.writerows(registros)
            print(f"\n✅ Datos guardados en {filename}")
        sys.exit(0)

    # Manejar CTRL+C para guardar CSV al salir
    signal.signal(signal.SIGINT, guardar_csv)

    while True:
        # Leer physics
        physics.seek(0)
        buf = physics.read(ctypes.sizeof(SPageFilePhysics))
        data = SPageFilePhysics.from_buffer_copy(buf)

        # Leer graphics
        graphics.seek(0)
        buf_g = graphics.read(ctypes.sizeof(SPageFileGraphics))
        data_g = SPageFileGraphics.from_buffer_copy(buf_g)

        # Corregir marcha
        gear = data.gear - 1 if data.gear > 0 else data.gear

        # Decodificar strings (bytes -> str), quitando nulls
        def decode_cstr(b):
            return b.split(b'\x00', 1)[0].decode('utf-8', errors='ignore')

        registros.append({
            "Velocidad (km/h)": round(data.speedKmh, 2),
            "RPM": data.rpms,
            "Gas": round(data.gas, 2),
            "Freno": round(data.brake, 2),
            "Volante": round(data.steerAngle, 2),
            "Marcha": gear,
            "Vueltas completadas": data_g.completedLaps,
            "Tiempo actual": decode_cstr(data_g.currentTime),
        })

        print(f"Velocidad: {data.speedKmh:.1f} km/h | RPM: {data.rpms} | "
              f"Gas: {data.gas:.2f} | Freno: {data.brake:.2f} | "
              f"Volante: {data.steerAngle:.2f} | Marcha: {gear} | "
              f"Vuelta: {data_g.completedLaps}")

        time.sleep(0.1)


if __name__ == "__main__":
    main()
