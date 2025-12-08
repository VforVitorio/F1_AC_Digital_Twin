#!/usr/bin/env python3
"""
Script para ejecutar análisis completo de telemetría F1

Uso:
    python run_analysis.py data/raw/telemetry_2025-09-24_18-43-55.csv

Genera:
    - Archivo CSV procesado en data/processed/
    - Visualizaciones en data/figures/ (opcional)
"""

import sys
import pandas as pd
from pathlib import Path
import argparse

# Añadir raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Importar módulos de análisis
from src.analysis import vehicle_dynamics as vd
from src.analysis import car_balance as cb
from src.analysis import tire_analysis as ta
from src.analysis import performance_metrics as pm
from src.analysis import racing_line as rl
from src.analysis import energy_power as ep


def load_telemetry(filepath):
    """Carga archivo de telemetría"""
    print(f"Cargando telemetría desde: {filepath}")
    df = pd.read_csv(filepath)
    print(f"  → {len(df)} registros cargados")
    return df


def run_full_analysis(df):
    """Ejecuta análisis completo"""
    print("\n=== EJECUTANDO ANÁLISIS ===")

    # 1. Dinámica vehicular
    print("1. Análisis de dinámica vehicular...")
    df = vd.analyze_vehicle_dynamics(df)
    print(f"   ✓ G-force máxima: {df['g_combined'].max():.2f} G")

    # 2. Balance del coche
    print("2. Análisis de balance...")
    df = cb.analyze_car_balance(df)
    print(f"   ✓ Downforce máx: {df['downforce'].max():.0f} N")

    # 3. Neumáticos
    print("3. Análisis de neumáticos...")
    df = ta.analyze_tires(df)
    print(f"   ✓ Desgaste final: {df['tire_wear'].iloc[-1]:.4f}")

    # 4. Racing line
    print("4. Análisis de racing line...")
    df = rl.analyze_racing_line(df)
    print(f"   ✓ Smoothness: {df['smoothness_score'].iloc[0]:.1f}/100")

    # 5. Energía
    print("5. Análisis energético...")
    df = ep.analyze_energy_power(df)
    print(f"   ✓ E_cinética máx: {df['kinetic_energy'].max()/1e6:.2f} MJ")

    return df


def generate_report(df):
    """Genera reporte de rendimiento"""
    print("\n=== REPORTE DE RENDIMIENTO ===")

    report = pm.generate_performance_report(df)
    for key, value in report.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")

    print("\n=== RECOMENDACIONES ===")
    recommendations = pm.identify_improvement_areas(df)
    if recommendations:
        for category, suggestion in recommendations.items():
            print(f"\n{category.upper()}:")
            print(f"  → {suggestion}")
    else:
        print("Sin recomendaciones críticas")


def save_results(df, output_path):
    """Guarda resultados procesados"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(output_path, index=False)
    print(f"\n✓ Datos guardados en: {output_path}")
    print(f"  Columnas totales: {len(df.columns)}")


def main():
    parser = argparse.ArgumentParser(
        description='Análisis de telemetría F1 con ecuaciones de ingeniería'
    )
    parser.add_argument(
        'input_file',
        type=str,
        help='Ruta al archivo CSV de telemetría'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='data/processed/telemetry_analyzed.csv',
        help='Ruta de salida para datos procesados'
    )
    parser.add_argument(
        '--no-report',
        action='store_true',
        help='No mostrar reporte de rendimiento'
    )

    args = parser.parse_args()

    # Verificar que existe el archivo
    if not Path(args.input_file).exists():
        print(f"Error: Archivo no encontrado: {args.input_file}")
        sys.exit(1)

    # Pipeline de análisis
    df = load_telemetry(args.input_file)
    df = run_full_analysis(df)

    if not args.no_report:
        generate_report(df)

    save_results(df, args.output)

    print("\n✓ Análisis completado exitosamente")


if __name__ == '__main__':
    main()
