#!/usr/bin/env python3
"""
Train All GMM Experts
Trains all 4 experts sequentially with corrected data
"""

import sys
from pathlib import Path

# Add parent to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts' / 'training'))

from train_gmm_expert import train_expert

def main():
    """Train all experts."""
    print("=" * 80)
    print("TRAINING ALL GMM EXPERTS WITH CORRECTED DATA")
    print("=" * 80)

    experts = [
        'expert1_tire',
        'expert2_dynamics',
        'expert3_control',
        'expert4_power'
    ]

    results = {}

    for i, expert_name in enumerate(experts, 1):
        print(f"\n\n{'='*80}")
        print(f"TRAINING EXPERT {i}/4: {expert_name}")
        print(f"{'='*80}\n")

        try:
            gmm, metadata = train_expert(
                expert_name=expert_name,
                n_components_range=(2, 6),
                threshold_percentile=95
            )

            results[expert_name] = {
                'success': True,
                'n_components': metadata['n_components'],
                'threshold': metadata['threshold'],
                'anomaly_rate_train': metadata['anomaly_rates']['train']
            }

            print(f"\n[OK] {expert_name} trained successfully!")
            print(f"   Components: {metadata['n_components']}")
            print(f"   Threshold: {metadata['threshold']:.3f}")
            print(f"   Train anomaly rate: {metadata['anomaly_rates']['train']:.2f}%")

        except Exception as e:
            print(f"\n[ERROR] Failed to train {expert_name}: {e}")
            results[expert_name] = {'success': False, 'error': str(e)}
            continue

    # Summary
    print("\n\n" + "=" * 80)
    print("TRAINING SUMMARY")
    print("=" * 80)

    for expert_name, result in results.items():
        if result['success']:
            print(f"\n✅ {expert_name}:")
            print(f"   Components: {result['n_components']}")
            print(f"   Threshold: {result['threshold']:.3f}")
            print(f"   Train anomaly rate: {result['anomaly_rate_train']:.2f}%")
        else:
            print(f"\n❌ {expert_name}: FAILED")
            print(f"   Error: {result['error']}")

    # Check if all succeeded
    all_success = all(r['success'] for r in results.values())

    if all_success:
        print("\n" + "=" * 80)
        print("✅ ALL EXPERTS TRAINED SUCCESSFULLY!")
        print("=" * 80)
        print("\nNext steps:")
        print("1. Train gating network: python scripts/training/train_gating_network.py")
        print("2. Restart moe-detector container: docker-compose restart moe-detector")
        print("3. Test pipeline: python scripts/testing/test_moe_pipeline.py --limit 1000")
        return 0
    else:
        print("\n" + "=" * 80)
        print("⚠️ SOME EXPERTS FAILED TO TRAIN")
        print("=" * 80)
        return 1

if __name__ == "__main__":
    sys.exit(main())
