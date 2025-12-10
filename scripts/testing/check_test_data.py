"""Check if we're testing with train data or test data"""
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Load test results
results_df = pd.read_csv(ROOT / 'data' / 'testing' / 'anomaly_results_20251210_104153.csv')
print("Test results loaded:", len(results_df), "samples")
print()

# Load original CSV
csv_path = ROOT / 'data' / 'raw' / 'telemetry_2025-12-08_18-05-21.csv'
df_full = pd.read_csv(csv_path)
df_test_samples = df_full.iloc[results_df['sample_idx'].values]

print("=" * 60)
print("DATA SPLIT ANALYSIS")
print("=" * 60)

print(f"\nCSV completo:")
print(f"  Total samples: {len(df_full):,}")
print(f"  Total laps: {df_full['CompletedLaps'].nunique()}")
print(f"  Lap range: {df_full['CompletedLaps'].min()} - {df_full['CompletedLaps'].max()}")

print(f"\nMuestras testeadas (primeras 1000):")
print(f"  Sample indices: {results_df['sample_idx'].min()} - {results_df['sample_idx'].max()}")
print(f"  Laps únicos: {sorted(df_test_samples['CompletedLaps'].unique())}")
print(f"  Total laps: {df_test_samples['CompletedLaps'].nunique()}")

# Load test split to compare
test_split_path = ROOT / 'data' / 'processed' / 'MoE-anomaly' / 'splits' / 'expert1_tire_test.csv'
if test_split_path.exists():
    df_test_split = pd.read_csv(test_split_path)
    print(f"\nTest split oficial (de entrenamiento):")
    print(f"  Total samples: {len(df_test_split):,}")

    # Try to identify which laps are in test split by looking at timestamps
    print(f"\n⚠️  Las primeras 1000 filas del CSV NO son necesariamente del test split!")
    print(f"    Test split: 10,084 samples (15% de 80 laps ≈ 12 laps)")
    print(f"    Testeando: {df_test_samples['CompletedLaps'].nunique()} laps")
    print(f"\n💡 Para testear correctamente, deberías usar el test split guardado:")
    print(f"    data/processed/MoE-anomaly/splits/expert*_test.csv")
