"""
Utilidades comunes para análisis de telemetría F1
"""
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter


def calculate_derivative(series, time_series, window=5):
    """
    Calcula la derivada de una serie temporal con suavizado

    Args:
        series: Serie de datos (e.g., velocidad)
        time_series: Serie temporal en segundos
        window: Ventana para suavizado

    Returns:
        Derivada suavizada
    """
    dt = time_series.diff().fillna(0.001)
    derivative = series.diff() / dt

    # Suavizado con Savitzky-Golay
    if len(derivative) > window:
        derivative = pd.Series(
            savgol_filter(derivative.fillna(0), window_length=window, polyorder=2),
            index=derivative.index
        )

    return derivative


def smooth_signal(series, window=5, polyorder=2):
    """
    Suaviza una señal usando filtro Savitzky-Golay

    Args:
        series: Serie a suavizar
        window: Tamaño de ventana (debe ser impar)
        polyorder: Orden del polinomio

    Returns:
        Serie suavizada
    """
    if len(series) < window:
        return series

    if window % 2 == 0:
        window += 1

    # Forward fill luego backward fill para manejar NaN
    filled_series = series.ffill().bfill()

    smoothed = savgol_filter(filled_series,
                             window_length=window,
                             polyorder=polyorder)

    return pd.Series(smoothed, index=series.index)


def kmh_to_ms(speed_kmh):
    """Convierte km/h a m/s"""
    return speed_kmh / 3.6


def ms_to_kmh(speed_ms):
    """Convierte m/s a km/h"""
    return speed_ms * 3.6


def rpm_to_wheel_speed(rpm, gear_ratio, wheel_radius=0.33):
    """
    Calcula velocidad teórica de rueda desde RPM

    Args:
        rpm: Revoluciones por minuto del motor
        gear_ratio: Relación de transmisión (dict por marcha)
        wheel_radius: Radio de rueda en metros (default F1 ~0.33m)

    Returns:
        Velocidad teórica en m/s
    """
    # Velocidad angular de la rueda (rad/s)
    wheel_rpm = rpm / gear_ratio
    wheel_angular_vel = (wheel_rpm * 2 * np.pi) / 60

    return wheel_angular_vel * wheel_radius


def calculate_distance_2d(x, y):
    """
    Calcula distancia euclidiana entre puntos consecutivos

    Args:
        x, y: Coordenadas

    Returns:
        Distancia incremental
    """
    dx = x.diff()
    dy = y.diff()

    return np.sqrt(dx**2 + dy**2)


def calculate_curvature(x, y, smooth_window=7):
    """
    Calcula curvatura de la trayectoria

    Curvature κ = |x'y'' - y'x''| / (x'² + y'²)^(3/2)

    Args:
        x, y: Coordenadas de posición
        smooth_window: Ventana de suavizado

    Returns:
        Curvatura (1/radio)
    """
    # Suavizar coordenadas primero
    x_smooth = smooth_signal(x, window=smooth_window)
    y_smooth = smooth_signal(y, window=smooth_window)

    # Primeras derivadas
    dx = x_smooth.diff()
    dy = y_smooth.diff()

    # Segundas derivadas
    ddx = dx.diff()
    ddy = dy.diff()

    # Curvatura
    numerator = np.abs(dx * ddy - dy * ddx)
    denominator = (dx**2 + dy**2)**(3/2)

    curvature = numerator / denominator
    curvature = curvature.replace([np.inf, -np.inf], np.nan)

    return curvature


def identify_corners(speed, threshold_percentile=30, min_duration=10):
    """
    Identifica curvas basado en reducción de velocidad

    Args:
        speed: Serie de velocidad
        threshold_percentile: Percentil bajo para considerar curva
        min_duration: Duración mínima de curva en samples

    Returns:
        Máscara booleana de curvas
    """
    threshold = speed.quantile(threshold_percentile / 100)
    in_corner = speed < threshold

    # Filtrar curvas muy cortas
    corner_groups = (in_corner != in_corner.shift()).cumsum()
    corner_counts = in_corner.groupby(corner_groups).transform('sum')

    valid_corners = in_corner & (corner_counts >= min_duration)

    return valid_corners


def calculate_time_delta(current_lap_time, reference_lap_time):
    """
    Calcula delta de tiempo punto a punto

    Args:
        current_lap_time: Tiempo acumulado vuelta actual
        reference_lap_time: Tiempo acumulado vuelta referencia

    Returns:
        Delta en segundos (positivo = más lento)
    """
    return current_lap_time - reference_lap_time


# Constantes físicas
GRAVITY = 9.80665  # m/s²
AIR_DENSITY = 1.225  # kg/m³ a nivel del mar

# Parámetros típicos F1
F1_PARAMS = {
    'mass': 798,  # kg (coche + piloto, regulación 2025)
    'wheelbase': 3.6,  # m (aproximado)
    'track_width_front': 1.46,  # m
    'track_width_rear': 1.42,  # m
    'cg_height': 0.30,  # m (centro de gravedad)
    'weight_distribution_front': 0.42,  # 42% delante
    'weight_distribution_rear': 0.58,  # 58% detrás
    'wheel_radius': 0.33,  # m
    'frontal_area': 1.5,  # m²
    'drag_coefficient': 0.85,  # típico
    'downforce_coefficient': 2.5,  # Cl (negativo, genera carga)
}
