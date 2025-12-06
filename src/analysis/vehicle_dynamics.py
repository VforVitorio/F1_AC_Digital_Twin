"""
Ecuaciones de dinámica vehicular para telemetría F1

Referencias:
- Lateral/Longitudinal g-forces: https://github.com/theOehrly/Fast-F1/discussions/613
- Slip angle: https://www.formula1-dictionary.net/slip_angle.html
"""
import numpy as np
import pandas as pd
from src.utils import calculate_derivative, smooth_signal, kmh_to_ms, GRAVITY


def calculate_longitudinal_acceleration(speed_kmh, time_ms, smooth_window=5):
    """
    Calcula aceleración longitudinal desde velocidad

    a_long = dv/dt

    Args:
        speed_kmh: Velocidad en km/h
        time_ms: Tiempo en milisegundos
        smooth_window: Ventana de suavizado

    Returns:
        Aceleración longitudinal en m/s²
    """
    speed_ms = kmh_to_ms(speed_kmh)
    time_s = time_ms / 1000.0

    # Derivada de velocidad
    accel = calculate_derivative(speed_ms, time_s, window=smooth_window)

    return accel


def calculate_lateral_acceleration(speed_kmh, steering, wheelbase=3.6, smooth_window=5):
    """
    Calcula aceleración lateral estimada desde velocidad y steering

    Para movimiento circular: a_lat = v²/r
    Radio de giro: r ≈ wheelbase / tan(steering_angle)

    Args:
        speed_kmh: Velocidad en km/h
        steering: Ángulo de dirección (normalizado -1 a 1)
        wheelbase: Distancia entre ejes en metros
        smooth_window: Ventana de suavizado

    Returns:
        Aceleración lateral en m/s²
    """
    speed_ms = kmh_to_ms(speed_kmh)

    # Estimar ángulo de steering (asumiendo rango de ±30° para normalizado)
    max_steering_angle = np.radians(30)
    steering_angle = steering * max_steering_angle

    # Radio de giro
    # Evitar división por cero
    tan_steering = np.tan(steering_angle)
    tan_steering = tan_steering.replace(0, 1e-6)

    turn_radius = wheelbase / np.abs(tan_steering)

    # Aceleración centrípeta
    a_lat = (speed_ms ** 2) / turn_radius

    # Mantener signo de steering
    a_lat = a_lat * np.sign(steering)

    # Limitar valores extremos
    a_lat = a_lat.clip(-60, 60)  # F1 max ~6G lateral

    return smooth_signal(a_lat, window=smooth_window)


def calculate_g_forces(a_long, a_lat):
    """
    Convierte aceleraciones a g-forces

    1 g = 9.80665 m/s²

    Args:
        a_long: Aceleración longitudinal en m/s²
        a_lat: Aceleración lateral en m/s²

    Returns:
        Tupla (g_long, g_lat, g_combined)
    """
    g_long = a_long / GRAVITY
    g_lat = a_lat / GRAVITY

    # G combinada (vector resultante)
    g_combined = np.sqrt(g_long**2 + g_lat**2)

    return g_long, g_lat, g_combined


def calculate_braking_force(brake, speed_kmh, mass=798):
    """
    Estima fuerza de frenado

    F_brake ∝ brake_input × speed (mayor efecto a alta velocidad)

    Args:
        brake: Input de freno (0-1)
        speed_kmh: Velocidad en km/h
        mass: Masa del vehículo en kg

    Returns:
        Fuerza de frenado estimada en N
    """
    speed_ms = kmh_to_ms(speed_kmh)

    # Fuerza proporcional a input y velocidad (modelo simplificado)
    # Max frenado F1 ~6G de deceleración
    max_braking_force = mass * GRAVITY * 6  # ~47000 N

    # Fuerza estimada
    brake_force = brake * max_braking_force * (speed_ms / 100)  # Normalizado a 100 m/s

    return brake_force.clip(0, max_braking_force)


def calculate_slip_angle(steering, speed_kmh, a_lat, wheelbase=3.6, cg_position=0.42):
    """
    Estima slip angle (ángulo de deriva)

    Slip angle α ≈ arctan(a_lat / a_long) para simplificación
    Más preciso: depende de cornering stiffness del neumático

    Referencias:
    - https://www.formula1-dictionary.net/slip_angle.html
    - Fy = Cα × α (cornering stiffness)

    Args:
        steering: Ángulo de dirección normalizado
        speed_kmh: Velocidad en km/h
        a_lat: Aceleración lateral en m/s²
        wheelbase: Distancia entre ejes
        cg_position: Posición CG (0.42 = 42% adelante)

    Returns:
        Slip angle estimado en grados
    """
    speed_ms = kmh_to_ms(speed_kmh)

    # Evitar división por cero
    speed_ms = speed_ms.replace(0, 0.1)

    # Slip angle simplificado: α ≈ a_lat / v² × wheelbase
    slip_angle = np.arctan2(a_lat, speed_ms**2 / wheelbase)

    # Convertir a grados
    slip_angle_deg = np.degrees(slip_angle)

    # Limitar a rango realista (-15° a +15°)
    slip_angle_deg = slip_angle_deg.clip(-15, 15)

    return slip_angle_deg


def calculate_steering_rate(steering, time_ms):
    """
    Calcula tasa de cambio del volante (steering rate)

    d(steering)/dt - indicador de suavidad del piloto

    Args:
        steering: Ángulo de dirección
        time_ms: Tiempo en ms

    Returns:
        Steering rate en unidades/segundo
    """
    time_s = time_ms / 1000.0
    steering_rate = calculate_derivative(steering, time_s, window=3)

    return steering_rate


def calculate_throttle_rate(throttle, time_ms):
    """
    Calcula tasa de aplicación de throttle

    Args:
        throttle: Posición del acelerador (0-1)
        time_ms: Tiempo en ms

    Returns:
        Throttle rate en unidades/segundo
    """
    time_s = time_ms / 1000.0
    throttle_rate = calculate_derivative(throttle, time_s, window=3)

    return throttle_rate


def analyze_vehicle_dynamics(df):
    """
    Análisis completo de dinámica vehicular

    Args:
        df: DataFrame con telemetría (Speed_kmh, Steering, Throttle, Brake, iCurrentTime_ms)

    Returns:
        DataFrame con columnas adicionales de análisis dinámico
    """
    result = df.copy()

    # Aceleraciones
    result['a_long'] = calculate_longitudinal_acceleration(
        result['Speed_kmh'],
        result['iCurrentTime_ms']
    )

    result['a_lat'] = calculate_lateral_acceleration(
        result['Speed_kmh'],
        result['Steering']
    )

    # G-forces
    g_long, g_lat, g_combined = calculate_g_forces(
        result['a_long'],
        result['a_lat']
    )
    result['g_long'] = g_long
    result['g_lat'] = g_lat
    result['g_combined'] = g_combined

    # Fuerza de frenado
    result['brake_force'] = calculate_braking_force(
        result['Brake'],
        result['Speed_kmh']
    )

    # Slip angle
    result['slip_angle'] = calculate_slip_angle(
        result['Steering'],
        result['Speed_kmh'],
        result['a_lat']
    )

    # Rates
    result['steering_rate'] = calculate_steering_rate(
        result['Steering'],
        result['iCurrentTime_ms']
    )

    result['throttle_rate'] = calculate_throttle_rate(
        result['Throttle'],
        result['iCurrentTime_ms']
    )

    return result
