"""Check which experts have zero-variance features"""
import pickle
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCALERS_DIR = ROOT / 'data' / 'processed' / 'MoE-anomaly' / 'scalers'

experts = ['expert1_tire', 'expert2_dynamics', 'expert3_control', 'expert4_power']

print("=" * 60)
print("ANÁLISIS DE VARIANZA POR EXPERTO")
print("=" * 60)

for expert in experts:
    scaler_path = SCALERS_DIR / f'scaler_{expert}.pkl'

    with open(scaler_path, 'rb') as f:
        scaler = pickle.load(f)

    feature_names = list(scaler.feature_names_in_)
    means = scaler.mean_
    stds = scaler.scale_

    zero_var_features = []
    for i, (feat, mean, std) in enumerate(zip(feature_names, means, stds)):
        if std < 0.001:  # Varianza casi 0
            zero_var_features.append(feat)

    print(f"\n{expert}:")
    print(f"  Total features: {len(feature_names)}")
    print(f"  Features con varianza ~0: {len(zero_var_features)}")

    if zero_var_features:
        print(f"  ❌ Features problemáticas:")
        for feat in zero_var_features:
            print(f"     - {feat}")
    else:
        print(f"  ✅ Todas las features tienen varianza")

print("\n" + "=" * 60)
print("RECOMENDACIÓN")
print("=" * 60)

# Verificar CSV para saber qué features tienen datos
csv_path = ROOT / 'data' / 'raw' / 'telemetry_2025-12-08_18-05-21.csv'
df = pd.read_csv(csv_path, nrows=1000)

print("\nFeatures con datos no-cero en el CSV:")
all_features = []
for expert in experts:
    scaler_path = SCALERS_DIR / f'scaler_{expert}.pkl'
    with open(scaler_path, 'rb') as f:
        scaler = pickle.load(f)
    all_features.extend(scaler.feature_names_in_)

has_data = []
no_data = []

for feat in set(all_features):
    if feat in df.columns:
        nonzero = (df[feat] != 0).sum()
        if nonzero > 0:
            has_data.append(feat)
        else:
            no_data.append(feat)

print(f"\n✅ Con datos ({len(has_data)} features):")
for feat in sorted(has_data)[:10]:  # Primeros 10
    print(f"   - {feat}")
if len(has_data) > 10:
    print(f"   ... y {len(has_data)-10} más")

print(f"\n❌ Sin datos ({len(no_data)} features):")
for feat in sorted(no_data)[:10]:
    print(f"   - {feat}")
if len(no_data) > 10:
    print(f"   ... y {len(no_data)-10} más")

print("\n💡 SOLUCIÓN:")
if 'expert1_tire' in [e for e in experts]:
    print("\n   Puedes DESHABILITAR temporalmente los expertos afectados:")
    print("   1. Modificar moe_config.json para excluir experts problemáticos")
    print("   2. O modificar el código para darles peso 0")
    print("   3. Usar solo expertos con datos reales")
    print("\n   NO necesitas reentrenar si solo quitas expertos completos.")
