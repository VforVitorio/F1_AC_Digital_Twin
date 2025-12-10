"""Check scaler dimensions to debug feature mismatch"""
import pickle
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCALERS_DIR = ROOT / 'data' / 'processed' / 'MoE-anomaly' / 'scalers'

experts = ['expert1_tire', 'expert2_dynamics', 'expert3_control', 'expert4_power']

print("=" * 60)
print("SCALER DIMENSIONS CHECK")
print("=" * 60)

for expert in experts:
    scaler_path = SCALERS_DIR / f'scaler_{expert}.pkl'

    with open(scaler_path, 'rb') as f:
        scaler = pickle.load(f)

    n_features = len(scaler.mean_)
    feature_names = list(scaler.feature_names_in_) if hasattr(scaler, 'feature_names_in_') else None

    print(f"\n{expert}:")
    print(f"  N features: {n_features}")

    if feature_names:
        print(f"  Feature names:")
        for i, name in enumerate(feature_names, 1):
            print(f"    {i}. {name}")
    else:
        print(f"  Feature names: NOT AVAILABLE")
