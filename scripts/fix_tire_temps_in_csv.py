#!/usr/bin/env python3
"""
Fix Tire Temperature Averages in CSV

Calculates TireTemp_XX_Avg from Inner/Middle/Outer values
"""

import pandas as pd
import sys
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def fix_tire_temps(input_csv: Path, output_csv: Path):
    """Fix tire temperature averages in CSV."""

    logger.info(f"Reading CSV: {input_csv}")
    df = pd.read_csv(input_csv)

    logger.info(f"Original shape: {df.shape}")
    logger.info(f"Sample BEFORE fix:")
    logger.info(f"  TireTemp_FL_Avg: {df['TireTemp_FL_Avg'].iloc[0]}")
    logger.info(f"  TireTemp_FL_Inner: {df['TireTemp_FL_Inner'].iloc[0]}")
    logger.info(f"  TireTemp_FL_Middle: {df['TireTemp_FL_Middle'].iloc[0]}")
    logger.info(f"  TireTemp_FL_Outer: {df['TireTemp_FL_Outer'].iloc[0]}")

    # Calculate tire temperature averages
    for tire in ['FL', 'FR', 'RL', 'RR']:
        inner = f'TireTemp_{tire}_Inner'
        middle = f'TireTemp_{tire}_Middle'
        outer = f'TireTemp_{tire}_Outer'
        avg = f'TireTemp_{tire}_Avg'

        logger.info(f"Calculating {avg} from {inner}, {middle}, {outer}")
        df[avg] = (df[inner] + df[middle] + df[outer]) / 3.0

        # Report stats
        logger.info(f"  {avg}: mean={df[avg].mean():.2f}°C, std={df[avg].std():.2f}°C, "
                   f"min={df[avg].min():.2f}°C, max={df[avg].max():.2f}°C")

    logger.info(f"\nSample AFTER fix:")
    logger.info(f"  TireTemp_FL_Avg: {df['TireTemp_FL_Avg'].iloc[0]:.2f}")
    logger.info(f"  TireTemp_FR_Avg: {df['TireTemp_FR_Avg'].iloc[0]:.2f}")
    logger.info(f"  TireTemp_RL_Avg: {df['TireTemp_RL_Avg'].iloc[0]:.2f}")
    logger.info(f"  TireTemp_RR_Avg: {df['TireTemp_RR_Avg'].iloc[0]:.2f}")

    # Save fixed CSV
    logger.info(f"\nSaving fixed CSV to: {output_csv}")
    df.to_csv(output_csv, index=False)
    logger.info(f"✓ Done! Fixed CSV saved with {len(df)} rows")

    return df


if __name__ == "__main__":
    ROOT = Path(__file__).resolve().parents[1]

    input_csv = ROOT / 'data' / 'raw' / 'telemetry_2025-12-08_18-05-21.csv'
    output_csv = ROOT / 'data' / 'raw' / 'telemetry_2025-12-08_18-05-21_FIXED.csv'

    if not input_csv.exists():
        logger.error(f"Input CSV not found: {input_csv}")
        sys.exit(1)

    logger.info("=" * 70)
    logger.info("FIXING TIRE TEMPERATURE AVERAGES IN CSV")
    logger.info("=" * 70)

    fix_tire_temps(input_csv, output_csv)

    logger.info("=" * 70)
    logger.info("NEXT STEPS:")
    logger.info("=" * 70)
    logger.info("1. Update prepare_moe_data.py to use FIXED CSV")
    logger.info("2. Run: python scripts/training/prepare_moe_data.py")
    logger.info("3. Retrain models")
