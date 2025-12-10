"""Check what values the scaler was trained on"""
import pickle
import numpy as np
from pathlib import Path

scaler_path = Path('data/processed/MoE-anomaly/scalers/scaler_expert1_tire.pkl')

with open(scaler_path, 'rb') as f:
    scaler = pickle.load(f)

print("=" * 70)
print("EXPERT 1 (TIRE) SCALER ANALYSIS")
print("=" * 70)
print("\nFeatures (in order):")
print("0-3: TireTemp_FL/FR/RL/RR_Avg")
print("4-7: TireWear_FL/FR/RL/RR")
print("8-11: TirePressure_FL/FR/RL/RR")
print("12-15: SlipRatio_FL/FR/RL/RR")
print("16-19: SlipAngle_FL/FR/RL/RR")

print("\n" + "=" * 70)
print("TIRE TEMPERATURE AVERAGES (Features 0-3)")
print("=" * 70)
print(f"Mean values: {scaler.mean_[:4]}")
print(f"Std deviation: {scaler.scale_[:4]}")
print(f"Expected range (mean ± 2*std):")
for i in range(4):
    lower = scaler.mean_[i] - 2 * scaler.scale_[i]
    upper = scaler.mean_[i] + 2 * scaler.scale_[i]
    tire = ['FL', 'FR', 'RL', 'RR'][i]
    print(f"  {tire}: {lower:.2f}°C to {upper:.2f}°C")

print("\n" + "=" * 70)
print("TIRE WEAR (Features 4-7)")
print("=" * 70)
print(f"Mean values: {scaler.mean_[4:8]}")
print(f"Std deviation: {scaler.scale_[4:8]}")

print("\n" + "=" * 70)
print("TIRE PRESSURE (Features 8-11)")
print("=" * 70)
print(f"Mean values: {scaler.mean_[8:12]}")
print(f"Std deviation: {scaler.scale_[8:12]}")

print("\n" + "=" * 70)
print("🔴 PROBLEMA IDENTIFICADO")
print("=" * 70)
if np.all(scaler.mean_[:4] < 1.0):
    print("❌ TireTemp_XX_Avg mean ≈ 0 → El modelo fue entrenado con temperaturas en 0°C!")
    print("   Cuando enviamos temperaturas reales (75-80°C), el modelo las ve como anomalías.")
    print("\n✅ SOLUCIÓN:")
    print("   1. Reentrenar el modelo con TireTemp_XX_Avg calculados correctamente")
    print("   2. O enviar TireTemp_XX_Avg = 0 (temporalmente) para testing")
else:
    print("✅ TireTemp_XX_Avg parece correcto")
    print(f"   Mean: {scaler.mean_[:4]}")
