"""
Métricas de rendimiento y análisis competitivo
"""
import numpy as np
import pandas as pd
from src.utils import identify_corners, calculate_time_delta


def calculate_apex_speed(speed_kmh, in_corner):
    """
    Calcula velocidad mínima en curva (apex speed)

    Args:
        speed_kmh: Velocidad
        in_corner: Máscara booleana de curvas

    Returns:
        Velocidad mínima en cada curva
    """
    corner_groups = (in_corner != in_corner.shift()).cumsum()

    apex_speeds = speed_kmh[in_corner].groupby(corner_groups[in_corner]).min()

    return apex_speeds


def calculate_corner_entry_exit_speed(speed_kmh, in_corner):
    """
    Calcula velocidades de entrada y salida de curva

    Args:
        speed_kmh: Velocidad
        in_corner: Máscara de curvas

    Returns:
        DataFrame con entry_speed y exit_speed por curva
    """
    corner_groups = (in_corner != in_corner.shift()).cumsum()

    entry_speeds = speed_kmh[in_corner].groupby(corner_groups[in_corner]).first()
    exit_speeds = speed_kmh[in_corner].groupby(corner_groups[in_corner]).last()

    return pd.DataFrame({
        'entry_speed': entry_speeds,
        'exit_speed': exit_speeds,
        'speed_loss': entry_speeds - exit_speeds.values
    })


def calculate_acceleration_efficiency(throttle, speed_kmh, a_long):
    """
    Eficiencia de aceleración: ganancia de velocidad por throttle aplicado

    Efficiency = Δv / throttle_input

    Args:
        throttle: Input de acelerador (0-1)
        speed_kmh: Velocidad
        a_long: Aceleración longitudinal

    Returns:
        Eficiencia de aceleración
    """
    # Solo durante aceleración
    accelerating = (throttle > 0.5) & (a_long > 0)

    if isinstance(throttle, pd.Series):
        efficiency = pd.Series(0.0, index=throttle.index)
        efficiency[accelerating] = a_long[accelerating] / (throttle[accelerating] + 0.01)
    else:
        efficiency = a_long / (throttle + 0.01) if throttle > 0.5 else 0

    return efficiency


def calculate_braking_efficiency(brake, speed_kmh, a_long, distance):
    """
    Eficiencia de frenado: distancia de frenado y deceleración

    Args:
        brake: Input de freno (0-1)
        speed_kmh: Velocidad
        a_long: Aceleración longitudinal
        distance: Distancia recorrida

    Returns:
        DataFrame con métricas de frenado
    """
    from src.utils import kmh_to_ms

    # Detectar eventos de frenado
    braking = brake > 0.8

    # Agrupar eventos de frenado
    brake_groups = (braking != braking.shift()).cumsum()

    metrics = []

    for group_id in brake_groups[braking].unique():
        mask = (brake_groups == group_id) & braking

        if mask.sum() < 3:
            continue

        # Velocidades inicial y final
        v_initial = speed_kmh[mask].iloc[0]
        v_final = speed_kmh[mask].iloc[-1]

        # Distancia de frenado
        brake_distance = distance[mask].iloc[-1] - distance[mask].iloc[0]

        # Deceleración promedio
        avg_decel = a_long[mask].mean()

        # Distancia teórica (cinemática): d = v²/(2a)
        if avg_decel < -0.1:
            v_i_ms = kmh_to_ms(v_initial)
            v_f_ms = kmh_to_ms(v_final)
            theoretical_distance = (v_i_ms**2 - v_f_ms**2) / (2 * abs(avg_decel))

            efficiency = theoretical_distance / (brake_distance + 0.1)
        else:
            efficiency = 0

        metrics.append({
            'event': group_id,
            'initial_speed': v_initial,
            'final_speed': v_final,
            'brake_distance': brake_distance,
            'avg_decel_g': avg_decel / 9.81,
            'efficiency': efficiency
        })

    return pd.DataFrame(metrics)


def calculate_sector_performance(df):
    """
    Analiza rendimiento por sector

    Args:
        df: DataFrame con telemetría (CurrentSectorIndex, LastSectorTime_ms)

    Returns:
        DataFrame con tiempos y velocidades por sector
    """
    if 'CurrentSectorIndex' not in df.columns:
        return pd.DataFrame()

    sector_stats = df.groupby('CurrentSectorIndex').agg({
        'Speed_kmh': ['mean', 'max', 'min'],
        'Throttle': 'mean',
        'Brake': 'mean',
        'LastSectorTime_ms': lambda x: x.iloc[-1] if len(x) > 0 else 0
    }).reset_index()

    sector_stats.columns = ['Sector', 'speed_mean', 'speed_max', 'speed_min',
                            'throttle_avg', 'brake_avg', 'sector_time_ms']

    sector_stats['sector_time_s'] = sector_stats['sector_time_ms'] / 1000

    return sector_stats


def calculate_time_loss_gain(current_lap_df, reference_lap_df, distance_col='Distance'):
    """
    Calcula tiempo perdido/ganado respecto a vuelta de referencia

    Args:
        current_lap_df: DataFrame de vuelta actual
        reference_lap_df: DataFrame de vuelta de referencia
        distance_col: Nombre de columna de distancia

    Returns:
        Serie con delta de tiempo por punto
    """
    # Interpolar vueltas a misma distancia
    from scipy.interpolate import interp1d

    if 'iCurrentTime_ms' not in current_lap_df.columns:
        return pd.Series()

    current_time = current_lap_df['iCurrentTime_ms'].values / 1000  # a segundos
    current_dist = current_lap_df[distance_col].values

    reference_time = reference_lap_df['iCurrentTime_ms'].values / 1000
    reference_dist = reference_lap_df[distance_col].values

    # Interpolar tiempos de referencia a distancias actuales
    if len(reference_dist) > 1 and len(current_dist) > 1:
        interp_func = interp1d(reference_dist, reference_time,
                               kind='linear', fill_value='extrapolate')

        reference_time_interp = interp_func(current_dist)

        # Delta tiempo
        time_delta = current_time - reference_time_interp

        return pd.Series(time_delta, index=current_lap_df.index)
    else:
        return pd.Series(0, index=current_lap_df.index)


def calculate_consistency_score(lap_times):
    """
    Calcula consistencia del piloto basado en variabilidad de tiempos

    Score = 1 / (std_dev / mean) × 100

    Args:
        lap_times: Serie o lista de tiempos de vuelta

    Returns:
        Score de consistencia (mayor = más consistente)
    """
    if len(lap_times) < 2:
        return 100

    mean_time = np.mean(lap_times)
    std_time = np.std(lap_times)

    if std_time == 0:
        return 100

    consistency = (1 - std_time / mean_time) * 100

    return max(0, consistency)


def identify_improvement_areas(df):
    """
    Identifica áreas de mejora basadas en métricas

    Args:
        df: DataFrame con todas las métricas calculadas

    Returns:
        Dict con recomendaciones
    """
    recommendations = {}

    # Analizar frenado
    if 'brake_force' in df.columns:
        avg_brake_force = df[df['Brake'] > 0.5]['brake_force'].mean()
        if avg_brake_force < 30000:  # N
            recommendations['braking'] = "Frenado suave - aumentar presión de freno"

    # Analizar aceleración
    if 'throttle_rate' in df.columns:
        avg_throttle_rate = df[df['Throttle'] > 0]['throttle_rate'].mean()
        if avg_throttle_rate < 0.5:
            recommendations['throttle'] = "Aplicación lenta de throttle - ser más agresivo"

    # Analizar understeer/oversteer
    if 'understeer_gradient' in df.columns:
        avg_gradient = df['understeer_gradient'].mean()
        if avg_gradient > 2:
            recommendations['balance'] = "Understeer detectado - ajustar setup (menos front wing o más rear)"
        elif avg_gradient < -2:
            recommendations['balance'] = "Oversteer detectado - ajustar setup (más front wing o menos rear)"

    # Analizar suavidad
    if 'steering_rate' in df.columns:
        steering_variance = df['steering_rate'].std()
        if steering_variance > 0.5:
            recommendations['smoothness'] = "Inputs de dirección bruscos - suavizar manejo"

    # Analizar neumáticos
    if 'in_optimal_window' in df.columns:
        time_in_window = df['in_optimal_window'].mean()
        if time_in_window < 0.6:
            recommendations['tires'] = f"Solo {time_in_window*100:.1f}% en ventana óptima de neumáticos"

    return recommendations


def generate_performance_report(df):
    """
    Genera reporte completo de rendimiento

    Args:
        df: DataFrame con toda la telemetría procesada

    Returns:
        Dict con métricas clave
    """
    report = {}

    # Velocidades
    report['avg_speed'] = df['Speed_kmh'].mean()
    report['max_speed'] = df['Speed_kmh'].max()

    # G-forces
    if 'g_combined' in df.columns:
        report['max_g_combined'] = df['g_combined'].max()
        report['avg_g_combined'] = df['g_combined'].mean()

    # Frenado
    if 'brake_force' in df.columns:
        report['max_brake_force'] = df['brake_force'].max()

    # Curvas
    corners = identify_corners(df['Speed_kmh'])
    if corners.sum() > 0:
        report['num_corners'] = (corners != corners.shift()).sum() // 2
        report['avg_corner_speed'] = df[corners]['Speed_kmh'].mean()

    # Neumáticos
    if 'tire_wear' in df.columns:
        report['total_tire_wear'] = df['tire_wear'].iloc[-1]

    # Distancia
    report['total_distance'] = df['DistanceTraveled_m'].iloc[-1]

    return report
