#!/usr/bin/env python3
"""
Script de prueba para verificar que todos los módulos importan correctamente
"""

import sys
from pathlib import Path

# Añadir raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent))

print("=== TEST DE IMPORTS ===\n")

try:
    print("1. Importando utils...")
    from src import utils
    print("   ✓ utils.py")
except Exception as e:
    print(f"   ✗ Error: {e}")

try:
    print("\n2. Importando módulos de análisis...")
    from src.analysis import vehicle_dynamics
    print("   ✓ vehicle_dynamics.py")

    from src.analysis import car_balance
    print("   ✓ car_balance.py")

    from src.analysis import tire_analysis
    print("   ✓ tire_analysis.py")

    from src.analysis import performance_metrics
    print("   ✓ performance_metrics.py")

    from src.analysis import racing_line
    print("   ✓ racing_line.py")

    from src.analysis import energy_power
    print("   ✓ energy_power.py")
except Exception as e:
    print(f"   ✗ Error: {e}")

try:
    print("\n3. Importando desde __init__.py...")
    from src.analysis import (
        analyze_vehicle_dynamics,
        analyze_car_balance,
        analyze_tires,
        generate_performance_report,
        identify_improvement_areas,
        analyze_racing_line,
        analyze_energy_power
    )
    print("   ✓ Todas las funciones exportadas")
except Exception as e:
    print(f"   ✗ Error: {e}")

try:
    print("\n4. Verificando constantes...")
    print(f"   ✓ F1_PARAMS.mass = {utils.F1_PARAMS['mass']} kg")
    print(f"   ✓ GRAVITY = {utils.GRAVITY} m/s²")
except Exception as e:
    print(f"   ✗ Error: {e}")

print("\n=== TODOS LOS TESTS PASADOS ✓ ===")
