#!/usr/bin/env python3
"""Quick test of MoE pipeline without emojis"""

import sys
from pathlib import Path
import pandas as pd

# Add src to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from src.feature_processor import RealTimeFeatureExtractor
from src.moe_inference import MoEInference

def main():
    print("="*70)
    print("MoE PIPELINE QUICK TEST")
    print("="*70)

    # Paths
    scalers_dir = ROOT / 'data' / 'processed' / 'MoE-anomaly' / 'scalers'
    models_dir = ROOT / 'models' / 'anomaly-detection'
    input_csv = ROOT / 'data' / 'raw' / 'telemetry_2025-12-08_18-05-21_FIXED.csv'

    # Initialize pipeline
    print("\n[1/4] Initializing pipeline...")
    feature_extractor = RealTimeFeatureExtractor(str(scalers_dir))
    moe = MoEInference(str(models_dir))
    print("[OK] Pipeline initialized")

    # Load test data
    print("\n[2/4] Loading test data...")
    df = pd.read_csv(input_csv, nrows=1000)
    print(f"[OK] Loaded {len(df)} samples with {len(df.columns)} columns")

    # Process samples
    print("\n[3/4] Processing samples...")
    results = []
    errors = 0

    for idx, row in df.iterrows():
        try:
            telemetry = row.to_dict()
            normalized_features = feature_extractor.process(telemetry)
            prediction = moe.predict(normalized_features)
            results.append(prediction)

            if idx % 100 == 0:
                print(f"  Processed {idx+1}/{len(df)} samples...")

        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  [ERROR] Sample {idx}: {e}")

    print(f"\n[OK] Processed {len(results)}/{len(df)} samples successfully")
    print(f"     Errors: {errors}")

    # Analyze results
    print("\n[4/4] Analyzing results...")
    anomalies = sum(1 for r in results if r['is_anomaly'])
    anomaly_rate = anomalies / len(results) * 100 if results else 0

    print(f"\n{'='*70}")
    print("RESULTS")
    print(f"{'='*70}")
    print(f"Total samples: {len(results)}")
    print(f"Anomalies detected: {anomalies} ({anomaly_rate:.2f}%)")
    print(f"Normal samples: {len(results) - anomalies} ({100-anomaly_rate:.2f}%)")

    # Anomaly breakdown
    if anomalies > 0:
        anomaly_types = {}
        severities = {'low': 0, 'medium': 0, 'high': 0, 'normal': 0}

        for r in results:
            if r['is_anomaly']:
                atype = r['anomaly_type']
                anomaly_types[atype] = anomaly_types.get(atype, 0) + 1
                severity = r['severity']
                severities[severity] = severities.get(severity, 0) + 1

        print(f"\nAnomaly Types:")
        for atype, count in sorted(anomaly_types.items(), key=lambda x: x[1], reverse=True):
            pct = count / anomalies * 100
            print(f"  {atype}: {count} ({pct:.1f}%)")

        print(f"\nSeverity Distribution:")
        for severity in ['low', 'medium', 'high']:
            count = severities[severity]
            pct = count / anomalies * 100 if anomalies else 0
            print(f"  {severity}: {count} ({pct:.1f}%)")

    # Average scores
    avg_scores = {
        'expert1_tire': sum(r['expert_scores']['expert1_tire'] for r in results) / len(results),
        'expert2_dynamics': sum(r['expert_scores']['expert2_dynamics'] for r in results) / len(results),
        'expert3_control': sum(r['expert_scores']['expert3_control'] for r in results) / len(results),
        'expert4_power': sum(r['expert_scores']['expert4_power'] for r in results) / len(results),
        'global': sum(r['global_score'] for r in results) / len(results)
    }

    print(f"\nAverage Anomaly Scores:")
    print(f"  Expert 1 (Tire): {avg_scores['expert1_tire']:.3f}")
    print(f"  Expert 2 (Dynamics): {avg_scores['expert2_dynamics']:.3f}")
    print(f"  Expert 3 (Control): {avg_scores['expert3_control']:.3f}")
    print(f"  Expert 4 (Power): {avg_scores['expert4_power']:.3f}")
    print(f"  Global Score: {avg_scores['global']:.3f}")

    print(f"\n{'='*70}")
    if 5 <= anomaly_rate <= 25:
        print("[OK] Anomaly rate is within healthy range (5-25%)")
    elif anomaly_rate > 50:
        print("[WARNING] Anomaly rate is high (>50%) - may need tuning")
    else:
        print(f"[INFO] Anomaly rate: {anomaly_rate:.2f}%")
    print(f"{'='*70}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
