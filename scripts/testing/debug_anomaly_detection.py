"""
Debug script to understand why 100% of samples are detected as anomalies.
"""
import sys
import json
from pathlib import Path
import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings('ignore')

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))


def main():
    """Diagnostic analysis of anomaly detection."""
    from src.feature_processor import RealTimeFeatureExtractor
    from src.moe_inference import MoEInference

    scalers_dir = ROOT / 'data' / 'processed' / 'MoE-anomaly' / 'scalers'
    models_dir = ROOT / 'models' / 'anomaly-detection'
    data_file = ROOT / 'data' / 'raw' / 'telemetry_2025-12-03_19-08-39.csv'

    print("=" * 70)
    print("ANOMALY DETECTION DIAGNOSTIC")
    print("=" * 70)

    # Load config
    with open(models_dir / 'moe_config.json') as f:
        config = json.load(f)

    print("\n📊 THRESHOLDS FROM CONFIG:")
    for expert, threshold in config['thresholds'].items():
        print(f"  {expert}: {threshold:.4f}")

    # Initialize
    print("\n🔧 Initializing components...")
    fe = RealTimeFeatureExtractor(scalers_dir)
    moe = MoEInference(models_dir)

    # Load data
    print(f"\n📂 Loading: {data_file.name}")
    df = pd.read_csv(data_file, nrows=100)
    print(f"   {len(df)} samples")

    # Collect scores
    all_scores = {e: [] for e in config['experts']}

    print("\n🔍 Processing...")
    for _, row in df.iterrows():
        features = fe.process(row.to_dict())
        if features is None:
            continue
        scores = moe.compute_expert_scores(features)
        for e in config['experts']:
            all_scores[e].append(scores[e])

    # Analysis
    print("\n" + "=" * 70)
    print("SCORE ANALYSIS")
    print("=" * 70)

    for expert in config['experts']:
        scores = np.array(all_scores[expert])
        threshold = config['thresholds'][expert]

        print(f"\n📈 {expert.upper()}")
        print(f"   Threshold:   {threshold:.4f}")
        print(f"   Score Range: [{scores.min():.4f}, {scores.max():.4f}]")
        print(f"   Score Mean:  {scores.mean():.4f}")

        # All experts use: score > threshold = anomaly (95th percentile)
        pct = (scores > threshold).mean() * 100
        print(f"   Rule: score > threshold = anomaly")
        if threshold < scores.min():
            print(f"   ❌ PROBLEM: threshold < min(scores) → 0% anomalies!")
        elif threshold > scores.max():
            print(f"   ❌ PROBLEM: threshold > max(scores) → 0% anomalies!")

        print(f"   🚨 Anomaly Rate: {pct:.1f}%")


if __name__ == '__main__':
    main()
