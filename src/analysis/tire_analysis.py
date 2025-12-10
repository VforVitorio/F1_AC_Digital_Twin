"""
Análisis de neumáticos y degradación

Referencias:
- Slip angle & cornering stiffness: https://racingcardynamics.com/racing-tires-lateral-force/
- Cornering force: Fy = Cα × α
"""
import numpy as np
import pandas as pd
from src.utils import F1_PARAMS, GRAVITY, kmh_to_ms


def calculate_slip_ratio(speed_kmh, rpm, gear, wheel_radius=None):
    """
    Calcula slip ratio (deslizamiento longitudinal)

    Slip ratio σ = (ω×r - v) / v

    Donde:
    - ω: Velocidad angular de la rueda
    - r: Radio de la rueda
    - v: Velocidad del vehículo

    Args:
        speed_kmh: Velocidad del vehículo
        rpm: RPM del motor
        gear: Marcha actual
        wheel_radius: Radio de rueda en m

    Returns:
        Slip ratio (0 = sin deslizamiento, >0 = spinning, <0 = lock)
    """
    if wheel_radius is None:
        wheel_radius = F1_PARAMS['wheel_radius']

    # Velocidad real
    v = kmh_to_ms(speed_kmh)

    # Ratios de transmisión aproximados F1 (8 marchas)
    gear_ratios = {
        1: 12.0, 2: 9.5, 3: 7.8, 4: 6.5,
        5: 5.5, 6: 4.8, 7: 4.2, 8: 3.8
    }

    # Velocidad teórica de la rueda desde RPM
    final_drive = 2.5  # Diferencial típico

    if isinstance(gear, pd.Series):
        wheel_rpm = pd.Series(0.0, index=gear.index)
        for g in gear_ratios.keys():
            mask = gear == g
            wheel_rpm[mask] = rpm[mask] / (gear_ratios[g] * final_drive)
    else:
        if gear in gear_ratios:
            wheel_rpm = rpm / (gear_ratios[gear] * final_drive)
        else:
            wheel_rpm = 0

    # Velocidad angular (rad/s)
    omega = (wheel_rpm * 2 * np.pi) / 60

    # Velocidad teórica
    v_wheel = omega * wheel_radius

    # Slip ratio
    slip = (v_wheel - v) / (v + 0.1)  # Evitar división por cero

    return slip.clip(-1, 1)  # Limitar a rango físico


def estimate_tire_temperature(brake, throttle, speed_kmh, a_lat, distance_traveled):
    """
    Estima temperatura relativa del neumático

    Temperatura aumenta con:
    - Energía de frenado
    - Aceleración (slip)
    - Fuerzas laterales
    - Se disipa con distancia

    Args:
        brake: Input de freno (0-1)
        throttle: Input de throttle (0-1)
        speed_kmh: Velocidad
        a_lat: Aceleración lateral
        distance_traveled: Distancia recorrida

    Returns:
        Temperatura normalizada (0-1, mayor = más caliente)
    """
    # Energía de frenado (proporcional a velocidad × brake)
    brake_energy = brake * speed_kmh / 300  # Normalizado

    # Energía de aceleración (spinning genera calor)
    accel_energy = throttle * (1 - speed_kmh / 350)  # Más en bajas velocidades

    # Energía lateral (fuerzas en curvas)
    lateral_energy = np.abs(a_lat) / (6 * GRAVITY)  # Normalizado a 6G

    # Temperatura acumulada
    temp_gain = brake_energy + accel_energy * 0.5 + lateral_energy * 0.3

    # Disipación con distancia (cooling)
    decay_rate = 0.001  # Factor de enfriamiento por metro

    if isinstance(distance_traveled, pd.Series):
        temp = pd.Series(0.0, index=distance_traveled.index)
        for i in range(1, len(temp)):
            dist_delta = distance_traveled.iloc[i] - distance_traveled.iloc[i-1]
            temp.iloc[i] = temp.iloc[i-1] * (1 - decay_rate * dist_delta) + temp_gain.iloc[i]
    else:
        temp = temp_gain

    return temp.clip(0, 1)


def calculate_tire_wear(distance_traveled, brake, a_lat, surface_grip):
    """
    Estima desgaste de neumático

    Desgaste aumenta con:
    - Distancia
    - Frenado intenso
    - Fuerzas laterales altas
    - Bajo grip de superficie (sliding)

    Args:
        distance_traveled: Distancia en metros
        brake: Input de freno
        a_lat: Aceleración lateral
        surface_grip: Grip de superficie (0-1)

    Returns:
        Desgaste acumulado normalizado
    """
    # Tasa de desgaste base por metro
    base_wear_rate = 0.00001

    # Factores que aceleran desgaste
    brake_factor = 1 + brake * 2  # Frenar duplica desgaste
    lateral_factor = 1 + (np.abs(a_lat) / (6 * GRAVITY)) * 1.5
    grip_factor = 2 - surface_grip  # Menos grip = más desgaste

    wear_rate = base_wear_rate * brake_factor * lateral_factor * grip_factor

    # Desgaste acumulado
    if isinstance(distance_traveled, pd.Series):
        dist_increments = distance_traveled.diff().fillna(0)
        wear_increments = wear_rate * dist_increments
        wear = wear_increments.cumsum()
    else:
        wear = distance_traveled * wear_rate

    return wear


def estimate_optimal_tire_window(tire_temp, tire_wear):
    """
    Determina si el neumático está en ventana óptima

    Ventana óptima F1:
    - Temperatura: 0.6 - 0.85 (normalizado)
    - Desgaste: < 0.7 (70%)

    Args:
        tire_temp: Temperatura normalizada
        tire_wear: Desgaste normalizado

    Returns:
        Booleano indicando si está en ventana óptima
    """
    temp_optimal = (tire_temp >= 0.6) & (tire_temp <= 0.85)
    wear_ok = tire_wear < 0.7

    return temp_optimal & wear_ok


def calculate_grip_loss(surface_grip, tire_wear, tire_temp):
    """
    Calcula pérdida de grip total

    Grip = surface_grip × (1 - wear_penalty) × temp_factor

    Args:
        surface_grip: Grip base de superficie
        tire_wear: Desgaste (0-1)
        tire_temp: Temperatura (0-1)

    Returns:
        Grip efectivo (0-1)
    """
    # Penalty por desgaste
    wear_penalty = tire_wear * 0.3  # 30% pérdida máxima

    # Factor de temperatura (parabólico, óptimo en 0.7)
    temp_factor = 1 - 2 * (tire_temp - 0.7)**2
    temp_factor = temp_factor.clip(0.5, 1.0)

    # Grip efectivo
    effective_grip = surface_grip * (1 - wear_penalty) * temp_factor

    return effective_grip.clip(0, 1)


def analyze_tire_degradation_per_lap(df):
    """
    Analiza degradación de neumático por vuelta

    Args:
        df: DataFrame con telemetría

    Returns:
        DataFrame agregado por vuelta con métricas de neumático
    """
    if 'CompletedLaps' not in df.columns:
        return pd.DataFrame()

    laps = df.groupby('CompletedLaps').agg({
        'tire_wear': ['min', 'max', 'mean'],
        'tire_temp': 'mean',
        'effective_grip': 'mean',
        'Speed_kmh': 'mean',
        'Distance': 'max'
    }).reset_index()

    laps.columns = ['Lap', 'wear_min', 'wear_max', 'wear_mean',
                    'temp_mean', 'grip_mean', 'speed_mean', 'distance']

    return laps


def analyze_tires(df):
    """
    Análisis completo de neumáticos

    Args:
        df: DataFrame con telemetría (Speed_kmh, RPM, Gear, Brake, Throttle, etc.)

    Returns:
        DataFrame con métricas de neumáticos
    """
    result = df.copy()

    # Slip ratio
    result['slip_ratio'] = calculate_slip_ratio(
        result['Speed_kmh'],
        result['RPM'],
        result['Gear']
    )

    # Temperatura estimada
    result['tire_temp'] = estimate_tire_temperature(
        result['Brake'],
        result['Throttle'],
        result['Speed_kmh'],
        result.get('a_lat', 0),  # Si ya fue calculado
        result['DistanceTraveled_m']
    )

    # Desgaste
    result['tire_wear'] = calculate_tire_wear(
        result['DistanceTraveled_m'],
        result['Brake'],
        result.get('a_lat', 0),
        result['SurfaceGrip']
    )

    # Ventana óptima
    result['in_optimal_window'] = estimate_optimal_tire_window(
        result['tire_temp'],
        result['tire_wear']
    )

    # Grip efectivo
    result['effective_grip'] = calculate_grip_loss(
        result['SurfaceGrip'],
        result['tire_wear'],
        result['tire_temp']
    )

    return result
