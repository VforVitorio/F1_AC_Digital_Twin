"""
Análisis de racing line y optimización de trayectoria
"""
import numpy as np
import pandas as pd
from src.utils import calculate_curvature, smooth_signal, calculate_distance_2d


def analyze_trajectory(x, y, speed_kmh):
    """
    Analiza la trayectoria del vehículo

    Args:
        x, y: Coordenadas de posición
        speed_kmh: Velocidad

    Returns:
        DataFrame con análisis de trayectoria
    """
    # Curvatura
    curvature = calculate_curvature(x, y)

    # Radio de giro (inverso de curvatura)
    turn_radius = 1 / (curvature.replace(0, np.nan))
    turn_radius = turn_radius.clip(-1000, 1000)  # Limitar extremos

    # Distancia incremental
    distance = calculate_distance_2d(x, y)

    # Velocidad tangencial
    from src.utils import kmh_to_ms
    v = kmh_to_ms(speed_kmh)

    return pd.DataFrame({
        'curvature': curvature,
        'turn_radius': turn_radius,
        'distance_increment': distance,
        'speed_ms': v
    })


def calculate_ideal_racing_line(x, y, track_width=10):
    """
    Aproxima línea de carrera ideal basada en geometría

    La línea ideal minimiza curvatura total

    Args:
        x, y: Coordenadas de trayectoria
        track_width: Ancho de pista disponible (m)

    Returns:
        Coordenadas x, y de línea ideal (suavizada)
    """
    # Suavizar trayectoria como aproximación a línea ideal
    x_ideal = smooth_signal(pd.Series(x), window=15)
    y_ideal = smooth_signal(pd.Series(y), window=15)

    return x_ideal, y_ideal


def calculate_deviation_from_ideal(x_actual, y_actual, x_ideal, y_ideal):
    """
    Calcula desviación de la línea ideal

    Args:
        x_actual, y_actual: Trayectoria actual
        x_ideal, y_ideal: Trayectoria ideal

    Returns:
        Desviación en metros
    """
    deviation = np.sqrt((x_actual - x_ideal)**2 + (y_actual - y_ideal)**2)

    return deviation


def find_optimal_braking_points(speed_kmh, brake, distance, x, y):
    """
    Identifica puntos de frenado y evalúa si son óptimos

    Args:
        speed_kmh: Velocidad
        brake: Input de freno
        distance: Distancia recorrida
        x, y: Coordenadas

    Returns:
        DataFrame con puntos de frenado
    """
    # Detectar inicio de frenado
    brake_start = (brake > 0.1) & (brake.shift(1) <= 0.1)

    braking_points = []

    for idx in brake_start[brake_start].index:
        if idx == 0:
            continue

        braking_points.append({
            'index': idx,
            'distance': distance.loc[idx],
            'speed': speed_kmh.loc[idx],
            'x': x.loc[idx],
            'y': y.loc[idx]
        })

    return pd.DataFrame(braking_points)


def calculate_smoothness_index(steering, throttle, brake):
    """
    Calcula índice de suavidad de pilotaje

    Suavidad = baja variabilidad en inputs

    Args:
        steering: Input de dirección
        throttle: Input de throttle
        brake: Input de freno

    Returns:
        Score de suavidad (0-100, mayor = más suave)
    """
    # Calcular variabilidad de inputs
    steering_var = steering.diff().abs().mean()
    throttle_var = throttle.diff().abs().mean()
    brake_var = brake.diff().abs().mean()

    # Normalizar (valores típicos de varianza)
    steering_score = max(0, 100 - steering_var * 1000)
    throttle_score = max(0, 100 - throttle_var * 200)
    brake_score = max(0, 100 - brake_var * 200)

    # Promedio ponderado
    smoothness = (steering_score * 0.4 + throttle_score * 0.3 + brake_score * 0.3)

    return smoothness


def identify_late_apex_corners(x, y, speed, curvature):
    """
    Identifica curvas donde se puede aplicar late apex

    Late apex: mejor para curvas seguidas de rectas largas

    Args:
        x, y: Coordenadas
        speed: Velocidad
        curvature: Curvatura de trayectoria

    Returns:
        Índices de curvas candidatas para late apex
    """
    # Detectar curvas (alta curvatura)
    high_curvature = curvature > curvature.quantile(0.7)

    # Detectar salidas a recta (curvatura baja después de curva)
    next_straight = (curvature.shift(-10) < curvature.quantile(0.3))

    # Candidatos a late apex
    late_apex_corners = high_curvature & next_straight

    return late_apex_corners


def compare_racing_lines(lap1_df, lap2_df, distance_col='Distance'):
    """
    Compara dos racing lines (e.g., dos vueltas)

    Args:
        lap1_df: DataFrame vuelta 1 con x, y, distance
        lap2_df: DataFrame vuelta 2
        distance_col: Columna de distancia para alinear

    Returns:
        DataFrame con comparación
    """
    from scipy.interpolate import interp1d

    # Interpolar lap2 a distancias de lap1
    if len(lap2_df) < 2:
        return pd.DataFrame()

    # Coordenadas lap1
    x1 = lap1_df['CarX'].values
    y1 = lap1_df['CarY'].values
    d1 = lap1_df[distance_col].values

    # Coordenadas lap2
    x2 = lap2_df['CarX'].values
    y2 = lap2_df['CarY'].values
    d2 = lap2_df[distance_col].values

    # Interpolar
    interp_x2 = interp1d(d2, x2, kind='linear', fill_value='extrapolate')
    interp_y2 = interp1d(d2, y2, kind='linear', fill_value='extrapolate')

    x2_aligned = interp_x2(d1)
    y2_aligned = interp_y2(d1)

    # Diferencias
    deviation = np.sqrt((x1 - x2_aligned)**2 + (y1 - y2_aligned)**2)

    return pd.DataFrame({
        'distance': d1,
        'x_lap1': x1,
        'y_lap1': y1,
        'x_lap2': x2_aligned,
        'y_lap2': y2_aligned,
        'deviation': deviation
    })


def calculate_minimum_time_trajectory(speed, curvature, distance):
    """
    Estima trayectoria de tiempo mínimo (simplificado)

    Velocidad máxima en curva limitada por:
    v_max = sqrt(a_lat_max × r)

    Args:
        speed: Velocidad actual
        curvature: Curvatura de trayectoria
        distance: Distancia

    Returns:
        Velocidad teórica óptima
    """
    from src.utils import GRAVITY

    # Aceleración lateral máxima (F1 ~6G)
    a_lat_max = 6 * GRAVITY

    # Radio de giro
    turn_radius = 1 / (curvature.replace(0, 1e-6))
    turn_radius = np.abs(turn_radius).clip(1, 1000)

    # Velocidad máxima en curva (m/s)
    v_max_ms = np.sqrt(a_lat_max * turn_radius)

    # Convertir a km/h
    v_max_kmh = v_max_ms * 3.6

    return v_max_kmh


def analyze_racing_line(df):
    """
    Análisis completo de racing line

    Args:
        df: DataFrame con telemetría (CarX, CarY, Speed_kmh, etc.)

    Returns:
        DataFrame con métricas de racing line
    """
    result = df.copy()

    # Análisis de trayectoria
    traj_analysis = analyze_trajectory(
        result['CarX'],
        result['CarY'],
        result['Speed_kmh']
    )
    result = pd.concat([result, traj_analysis], axis=1)

    # Línea ideal
    x_ideal, y_ideal = calculate_ideal_racing_line(
        result['CarX'],
        result['CarY']
    )
    result['x_ideal'] = x_ideal
    result['y_ideal'] = y_ideal

    # Desviación
    result['line_deviation'] = calculate_deviation_from_ideal(
        result['CarX'],
        result['CarY'],
        result['x_ideal'],
        result['y_ideal']
    )

    # Suavidad
    smoothness = calculate_smoothness_index(
        result['Steering'],
        result['Throttle'],
        result['Brake']
    )
    result['smoothness_score'] = smoothness

    # Velocidad teórica óptima
    result['optimal_speed'] = calculate_minimum_time_trajectory(
        result['Speed_kmh'],
        result['curvature'],
        result['Distance']
    )

    # Delta velocidad vs óptima
    result['speed_deficit'] = result['Speed_kmh'] - result['optimal_speed']

    return result
