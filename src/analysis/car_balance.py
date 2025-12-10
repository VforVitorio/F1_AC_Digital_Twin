"""
Análisis de balance del coche (car balance)

Referencias:
- Weight transfer: https://www.f1technical.net/forum/viewtopic.php?t=9554
- Lateral load transfer: https://suspensionsecrets.co.uk/lateral-and-longitudinal-load-transfer/
"""
import numpy as np
import pandas as pd
from src.utils import F1_PARAMS, GRAVITY


def calculate_longitudinal_weight_transfer(a_long, mass=None, cg_height=None, wheelbase=None):
    """
    Transferencia de peso longitudinal (frenado/aceleración)

    Δw = (α × h × m) / L

    Donde:
    - Δw: Cambio de carga en ruedas delanteras
    - α: Aceleración longitudinal (m/s²)
    - h: Altura del centro de gravedad (m)
    - m: Masa del vehículo (kg)
    - L: Distancia entre ejes (wheelbase) (m)

    Referencias:
    - https://www.formula1-dictionary.net/weight_transfer.html

    Args:
        a_long: Aceleración longitudinal en m/s²
        mass: Masa del vehículo (default F1_PARAMS)
        cg_height: Altura CG (default F1_PARAMS)
        wheelbase: Distancia entre ejes (default F1_PARAMS)

    Returns:
        Transferencia de peso en N (positivo = carga en delanteras)
    """
    if mass is None:
        mass = F1_PARAMS['mass']
    if cg_height is None:
        cg_height = F1_PARAMS['cg_height']
    if wheelbase is None:
        wheelbase = F1_PARAMS['wheelbase']

    # Durante frenado (a_long negativa), peso se transfiere a delante
    # Durante aceleración (a_long positiva), peso se transfiere atrás
    delta_weight = (a_long * cg_height * mass * GRAVITY) / wheelbase

    return delta_weight


def calculate_lateral_weight_transfer(a_lat, mass=None, cg_height=None, track_width=None):
    """
    Transferencia de peso lateral (curvas)

    Δw = (a_y × h × m) / t

    Donde:
    - a_y: Aceleración lateral (m/s²)
    - h: Altura del centro de gravedad (m)
    - m: Masa del vehículo (kg)
    - t: Ancho de vía (track width) (m)

    Referencias:
    - https://cloud.wikis.utexas.edu/wiki/spaces/LHRSOLAR/pages/89298939/Lateral+Load+Transfer+Calculations

    Args:
        a_lat: Aceleración lateral en m/s²
        mass: Masa del vehículo
        cg_height: Altura CG
        track_width: Ancho de vía (promedio front/rear)

    Returns:
        Transferencia de peso lateral en N
    """
    if mass is None:
        mass = F1_PARAMS['mass']
    if cg_height is None:
        cg_height = F1_PARAMS['cg_height']
    if track_width is None:
        # Promedio entre delantero y trasero
        track_width = (F1_PARAMS['track_width_front'] + F1_PARAMS['track_width_rear']) / 2

    delta_weight = (np.abs(a_lat) * cg_height * mass * GRAVITY) / track_width

    return delta_weight


def calculate_dynamic_weight_distribution(a_long, a_lat):
    """
    Distribución dinámica de peso en las 4 ruedas

    Args:
        a_long: Aceleración longitudinal (m/s²)
        a_lat: Aceleración lateral (m/s²)

    Returns:
        DataFrame con peso en cada rueda (FL, FR, RL, RR) en N
    """
    mass = F1_PARAMS['mass']
    weight = mass * GRAVITY

    # Peso estático
    front_static = weight * F1_PARAMS['weight_distribution_front']
    rear_static = weight * F1_PARAMS['weight_distribution_rear']

    # Transferencias
    long_transfer = calculate_longitudinal_weight_transfer(a_long)
    lat_transfer = calculate_lateral_weight_transfer(a_lat)

    # Distribución dinámica
    # Front Left
    FL = (front_static / 2) + long_transfer / 2 - lat_transfer / 2 * np.sign(a_lat)
    # Front Right
    FR = (front_static / 2) + long_transfer / 2 + lat_transfer / 2 * np.sign(a_lat)
    # Rear Left
    RL = (rear_static / 2) - long_transfer / 2 - lat_transfer / 2 * np.sign(a_lat)
    # Rear Right
    RR = (rear_static / 2) - long_transfer / 2 + lat_transfer / 2 * np.sign(a_lat)

    return pd.DataFrame({
        'FL': FL,
        'FR': FR,
        'RL': RL,
        'RR': RR
    })


def calculate_brake_balance(brake, a_long, speed_kmh):
    """
    Estima balance de frenado (distribución front/rear)

    Durante frenado, más peso en delanteras permite más frenado delantero
    Balance óptimo ~60-65% delante en F1

    Args:
        brake: Input de freno (0-1)
        a_long: Aceleración longitudinal (m/s²)
        speed_kmh: Velocidad (para considerar aerodinamics)

    Returns:
        Porcentaje de frenado delantero estimado
    """
    # Durante frenado, a_long es negativa
    braking_moments = brake > 0.1

    if isinstance(a_long, pd.Series):
        brake_balance = pd.Series(0.5, index=a_long.index)
    else:
        brake_balance = 0.5

    # Más velocidad = más downforce = permite más frenado delantero
    # Transferencia de peso también favorece delante
    speed_factor = (speed_kmh / 300).clip(0, 1)  # Normalizado a 300 km/h
    transfer_factor = (np.abs(a_long) / (6 * GRAVITY)).clip(0, 1)  # Normalizado a 6G

    # Balance dinámico (0.5 = 50%, más peso delante durante frenado)
    brake_balance[braking_moments] = 0.50 + 0.15 * speed_factor[braking_moments] + 0.05 * transfer_factor[braking_moments]

    return brake_balance.clip(0.4, 0.7)  # Limitar a rango realista


def calculate_understeer_gradient(steering, speed_kmh, a_lat, smooth_window=11):
    """
    Calcula gradiente de understeer/oversteer

    Understeer gradient = d(steering)/d(a_lat)

    - Positivo: Understeer (necesita más volante para misma aceleración lateral)
    - Negativo: Oversteer (necesita menos volante)
    - Cero: Neutral

    Referencias:
    - Racing Car Dynamics

    Args:
        steering: Ángulo de dirección normalizado
        speed_kmh: Velocidad
        a_lat: Aceleración lateral
        smooth_window: Ventana para suavizado

    Returns:
        Gradiente de understeer (positivo = understeer)
    """
    from src.utils import smooth_signal, calculate_derivative

    # Solo calcular en curvas (a_lat significativa)
    corner_mask = np.abs(a_lat) > 0.5  # m/s²

    if isinstance(steering, pd.Series):
        gradient = pd.Series(0.0, index=steering.index)

        if corner_mask.sum() > smooth_window:
            steering_smooth = smooth_signal(steering, window=smooth_window)
            a_lat_smooth = smooth_signal(a_lat, window=smooth_window)

            # Derivada de steering respecto a a_lat
            d_steering = steering_smooth[corner_mask].diff()
            d_alat = a_lat_smooth[corner_mask].diff()

            # Evitar división por cero
            d_alat = d_alat.replace(0, 1e-6)

            gradient[corner_mask] = (d_steering / d_alat).clip(-10, 10)
    else:
        gradient = 0.0

    return gradient


def calculate_aerodynamic_balance(speed_kmh, Cl=None, Cd=None):
    """
    Estima balance aerodinámico (downforce vs drag)

    Downforce = 0.5 × ρ × A × Cl × v²
    Drag = 0.5 × ρ × A × Cd × v²

    Referencias:
    - https://www.formula1-dictionary.net/downforce.html
    - https://en.wikipedia.org/wiki/Downforce

    Args:
        speed_kmh: Velocidad en km/h
        Cl: Coeficiente de downforce (default F1_PARAMS)
        Cd: Coeficiente de drag (default F1_PARAMS)

    Returns:
        DataFrame con downforce y drag en N
    """
    from src.utils import kmh_to_ms, AIR_DENSITY

    if Cl is None:
        Cl = F1_PARAMS['downforce_coefficient']
    if Cd is None:
        Cd = F1_PARAMS['drag_coefficient']

    speed_ms = kmh_to_ms(speed_kmh)
    A = F1_PARAMS['frontal_area']

    # Fórmulas aerodinámicas
    downforce = 0.5 * AIR_DENSITY * A * Cl * (speed_ms ** 2)
    drag = 0.5 * AIR_DENSITY * A * Cd * (speed_ms ** 2)

    return pd.DataFrame({
        'downforce': downforce,
        'drag': drag,
        'L_D_ratio': Cl / Cd  # Ratio lift/drag
    })


def analyze_car_balance(df):
    """
    Análisis completo de balance del coche

    Args:
        df: DataFrame con telemetría incluyendo a_long, a_lat

    Returns:
        DataFrame con métricas de balance
    """
    result = df.copy()

    # Transferencias de peso
    result['long_weight_transfer'] = calculate_longitudinal_weight_transfer(result['a_long'])
    result['lat_weight_transfer'] = calculate_lateral_weight_transfer(result['a_lat'])

    # Distribución dinámica
    wheel_weights = calculate_dynamic_weight_distribution(result['a_long'], result['a_lat'])
    result = pd.concat([result, wheel_weights], axis=1)

    # Balance de frenado
    result['brake_balance'] = calculate_brake_balance(
        result['Brake'],
        result['a_long'],
        result['Speed_kmh']
    )

    # Understeer gradient
    result['understeer_gradient'] = calculate_understeer_gradient(
        result['Steering'],
        result['Speed_kmh'],
        result['a_lat']
    )

    # Aerodinámica
    aero = calculate_aerodynamic_balance(result['Speed_kmh'])
    result = pd.concat([result, aero], axis=1)

    return result
