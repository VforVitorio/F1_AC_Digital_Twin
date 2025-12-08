"""
Análisis energético y de potencia

Referencias:
- Downforce power consumption: P = F_drag × v
- Kinetic energy: E_k = 0.5 × m × v²
"""
import numpy as np
import pandas as pd
from src.utils import F1_PARAMS, kmh_to_ms, GRAVITY, AIR_DENSITY


def calculate_kinetic_energy(speed_kmh, mass=None):
    """
    Calcula energía cinética

    E_k = 0.5 × m × v²

    Args:
        speed_kmh: Velocidad en km/h
        mass: Masa del vehículo (kg)

    Returns:
        Energía cinética en Joules
    """
    if mass is None:
        mass = F1_PARAMS['mass']

    v = kmh_to_ms(speed_kmh)

    E_k = 0.5 * mass * (v ** 2)

    return E_k


def calculate_braking_energy(speed_initial, speed_final, mass=None):
    """
    Calcula energía disipada en frenado

    E_brake = ΔE_k = 0.5 × m × (v_i² - v_f²)

    Args:
        speed_initial: Velocidad inicial (km/h)
        speed_final: Velocidad final (km/h)
        mass: Masa del vehículo

    Returns:
        Energía disipada en Joules
    """
    if mass is None:
        mass = F1_PARAMS['mass']

    v_i = kmh_to_ms(speed_initial)
    v_f = kmh_to_ms(speed_final)

    E_brake = 0.5 * mass * (v_i**2 - v_f**2)

    return E_brake


def estimate_engine_power(a_long, speed_kmh, drag_force, mass=None):
    """
    Estima potencia del motor

    P = F × v
    F = m × a + F_drag + F_rolling

    Args:
        a_long: Aceleración longitudinal (m/s²)
        speed_kmh: Velocidad (km/h)
        drag_force: Fuerza de drag aerodinámica (N)
        mass: Masa del vehículo

    Returns:
        Potencia estimada en kW
    """
    if mass is None:
        mass = F1_PARAMS['mass']

    v = kmh_to_ms(speed_kmh)

    # Fuerza de aceleración
    F_accel = mass * a_long

    # Fuerza de rodadura (aproximada, ~1% del peso)
    F_rolling = mass * GRAVITY * 0.01

    # Fuerza total requerida
    F_total = F_accel + drag_force + F_rolling

    # Potencia (P = F × v)
    P_watts = F_total * v

    # Convertir a kW
    P_kw = P_watts / 1000

    # Limitar a rango realista F1 (~1000 HP = 750 kW)
    P_kw = P_kw.clip(0, 800)

    return P_kw


def calculate_drag_power_loss(speed_kmh, Cd=None, A=None):
    """
    Calcula potencia absorbida por drag

    P_drag = F_drag × v = 0.5 × ρ × A × Cd × v³

    Nota: Potencia aumenta con el CUBO de la velocidad

    Args:
        speed_kmh: Velocidad
        Cd: Coeficiente de drag
        A: Área frontal

    Returns:
        Potencia perdida por drag en kW
    """
    if Cd is None:
        Cd = F1_PARAMS['drag_coefficient']
    if A is None:
        A = F1_PARAMS['frontal_area']

    v = kmh_to_ms(speed_kmh)

    # Fuerza de drag
    F_drag = 0.5 * AIR_DENSITY * A * Cd * (v ** 2)

    # Potencia
    P_drag_watts = F_drag * v

    P_drag_kw = P_drag_watts / 1000

    return P_drag_kw


def calculate_downforce_energy_cost(speed_kmh, downforce):
    """
    Costo energético del downforce

    Mayor downforce = mayor drag = más potencia necesaria

    Args:
        speed_kmh: Velocidad
        downforce: Fuerza de downforce (N)

    Returns:
        Potencia adicional requerida en kW
    """
    v = kmh_to_ms(speed_kmh)

    # Downforce incrementa drag (aproximadamente Cd_induced ∝ Cl²)
    # Simplificado: drag inducido por downforce
    induced_drag = downforce * 0.15  # Factor aproximado

    P_induced_kw = (induced_drag * v) / 1000

    return P_induced_kw


def calculate_energy_per_lap(df):
    """
    Calcula energía consumida por vuelta

    Args:
        df: DataFrame con telemetría de una vuelta completa

    Returns:
        Energía total en MJ (megajoules)
    """
    if 'engine_power' not in df.columns:
        return 0

    # Potencia en kW
    power_kw = df['engine_power']

    # Tiempo incremental (segundos)
    time_s = df['iCurrentTime_ms'].diff().fillna(0) / 1000

    # Energía = Potencia × Tiempo
    energy_increments = power_kw * time_s  # kJ

    # Energía total
    total_energy_kj = energy_increments.sum()
    total_energy_mj = total_energy_kj / 1000

    return total_energy_mj


def identify_high_energy_zones(df, threshold_percentile=80):
    """
    Identifica zonas de alto consumo energético

    Args:
        df: DataFrame con engine_power
        threshold_percentile: Percentil para considerar "alto"

    Returns:
        Máscara booleana de zonas de alto consumo
    """
    if 'engine_power' not in df.columns:
        return pd.Series(False, index=df.index)

    threshold = df['engine_power'].quantile(threshold_percentile / 100)

    high_energy = df['engine_power'] > threshold

    return high_energy


def calculate_fuel_consumption_estimate(energy_mj, fuel_energy_density=43.5):
    """
    Estima consumo de combustible

    Args:
        energy_mj: Energía consumida en MJ
        fuel_energy_density: Energía por kg de combustible (MJ/kg)
                            Gasolina ~43.5 MJ/kg

    Returns:
        Combustible consumido en kg
    """
    # Eficiencia térmica motor F1 ~50%
    thermal_efficiency = 0.50

    # Combustible necesario
    fuel_kg = energy_mj / (fuel_energy_density * thermal_efficiency)

    return fuel_kg


def calculate_ers_recovery_potential(brake_force, speed_kmh, distance):
    """
    Estima potencial de recuperación ERS (Energy Recovery System)

    Args:
        brake_force: Fuerza de frenado (N)
        speed_kmh: Velocidad
        distance: Distancia incremental

    Returns:
        Energía recuperable en kJ
    """
    from src.utils import kmh_to_ms

    v = kmh_to_ms(speed_kmh)

    # Energía de frenado
    braking = brake_force > 0

    # Potencia de frenado
    P_brake_watts = brake_force * v

    # Tiempo (asumiendo distancia / velocidad)
    time_s = distance / (v + 0.1)

    # Energía recuperable (solo durante frenado, eficiencia ~70%)
    ers_efficiency = 0.70
    energy_recovered = P_brake_watts * time_s * ers_efficiency / 1000  # kJ

    energy_recovered[~braking] = 0

    return energy_recovered


def calculate_speed_for_max_efficiency(downforce, drag, mass=None):
    """
    Calcula velocidad óptima para eficiencia energética

    Trade-off: más velocidad = más tiempo en recta pero más consumo

    Args:
        downforce: Fuerza de downforce (N)
        drag: Fuerza de drag (N)
        mass: Masa del vehículo

    Returns:
        Velocidad óptima estimada (km/h)
    """
    if mass is None:
        mass = F1_PARAMS['mass']

    # Simplificado: velocidad donde potencia/velocidad es mínima
    # En F1, esto es altamente dependiente de setup

    # Aproximación: balance entre downforce y drag
    L_D_ratio = downforce / (drag + 1)

    # Más L/D permite mayor velocidad eficiente
    v_optimal_ms = 60 + L_D_ratio * 10  # Fórmula empírica

    v_optimal_kmh = v_optimal_ms * 3.6

    return v_optimal_kmh.clip(200, 350)


def analyze_energy_power(df):
    """
    Análisis completo de energía y potencia

    Args:
        df: DataFrame con telemetría completa

    Returns:
        DataFrame con métricas energéticas
    """
    result = df.copy()

    # Energía cinética
    result['kinetic_energy'] = calculate_kinetic_energy(result['Speed_kmh'])

    # Potencia de drag
    result['drag_power_loss'] = calculate_drag_power_loss(result['Speed_kmh'])

    # Potencia del motor
    if 'a_long' in result.columns and 'drag' in result.columns:
        result['engine_power'] = estimate_engine_power(
            result['a_long'],
            result['Speed_kmh'],
            result['drag']
        )

    # Costo de downforce
    if 'downforce' in result.columns:
        result['downforce_cost'] = calculate_downforce_energy_cost(
            result['Speed_kmh'],
            result['downforce']
        )

    # Recuperación ERS
    if 'brake_force' in result.columns:
        dist_increment = result['Distance'].diff().fillna(0)
        result['ers_recovery'] = calculate_ers_recovery_potential(
            result['brake_force'],
            result['Speed_kmh'],
            dist_increment
        )

    return result
