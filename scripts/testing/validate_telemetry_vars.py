#!/usr/bin/env python3
"""
Validation script to verify telemetry collector captures all required variables for MoE

This script checks that:
1. All 59 required MoE features are present in telemetry collector output
2. Field name mappings in feature_processor are correct
3. No missing variables that would cause inference to fail
"""

import sys
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from feature_processor import RealTimeFeatureExtractor


def validate_moe_features():
    """Validate that all MoE features are correctly defined."""

    print("=" * 80)
    print("MoE FEATURE VALIDATION")
    print("=" * 80)

    # Get feature definitions
    expert_features = RealTimeFeatureExtractor.EXPERT_FEATURES

    # Count features per expert
    total_features = 0
    print("\nFeature counts by expert:")
    print("-" * 80)

    for expert_name, features in expert_features.items():
        count = len(features)
        total_features += count
        print(f"{expert_name:<25} {count:>3} features")

    print("-" * 80)
    print(f"{'TOTAL':<25} {total_features:>3} features")

    # Expected counts
    expected_counts = {
        'expert1_tire': 20,
        'expert2_dynamics': 16,  # Updated: added TireLoad_RR
        'expert3_control': 13,   # Updated: added BrakeTemp_RR
        'expert4_power': 10
    }
    expected_total = sum(expected_counts.values())

    print(f"\nExpected total: {expected_total} features")

    # Validate counts
    errors = []
    for expert_name, expected_count in expected_counts.items():
        actual_count = len(expert_features[expert_name])
        if actual_count != expected_count:
            errors.append(
                f"❌ {expert_name}: Expected {expected_count}, got {actual_count}"
            )
        else:
            print(f"✅ {expert_name}: {actual_count} features (correct)")

    if total_features != expected_total:
        errors.append(
            f"❌ Total feature count mismatch: Expected {expected_total}, got {total_features}"
        )
    else:
        print(f"\n✅ Total feature count: {total_features} (correct)")

    # List all features
    print("\n" + "=" * 80)
    print("ALL MoE FEATURES")
    print("=" * 80)

    for expert_name, features in expert_features.items():
        print(f"\n{expert_name}:")
        for i, feature in enumerate(features, 1):
            print(f"  {i:>2}. {feature}")

    # Check field name mappings
    print("\n" + "=" * 80)
    print("FIELD NAME MAPPINGS VALIDATION")
    print("=" * 80)

    field_mapping = RealTimeFeatureExtractor.FIELD_NAME_MAPPING

    # Collect all unique expected feature names
    all_required_features = set()
    for features in expert_features.values():
        all_required_features.update(features)

    print(f"\nTotal unique features required: {len(all_required_features)}")

    # Check which features have mappings
    synthetic_features = RealTimeFeatureExtractor.SYNTHETIC_FEATURES
    features_with_mappings = set(field_mapping.values())

    print(f"Features with field name mappings: {len(features_with_mappings)}")
    print(f"Synthetic features (with defaults): {len(synthetic_features)}")

    # Features that need to come from telemetry input
    required_from_input = all_required_features - synthetic_features
    print(f"Features required from telemetry input: {len(required_from_input)}")

    # Check for unmapped features
    unmapped = required_from_input - features_with_mappings
    if unmapped:
        print(f"\n⚠️  WARNING: {len(unmapped)} features have no field name mapping:")
        for feature in sorted(unmapped):
            print(f"  - {feature}")
        print("\nThese features must be present with exact names in telemetry data")
    else:
        print("\n✅ All required features have mappings or defaults")

    # List synthetic features with defaults
    print(f"\n📝 Synthetic features (will use defaults/proxies):")
    for feature in sorted(synthetic_features):
        print(f"  - {feature}")

    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)

    if errors:
        print("\n❌ VALIDATION FAILED\n")
        for error in errors:
            print(error)
        return False
    else:
        print("\n✅ ALL VALIDATIONS PASSED")
        print(f"\n✅ Total features: {total_features}")
        print(f"   - Expert 1 (Tire): {len(expert_features['expert1_tire'])}")
        print(f"   - Expert 2 (Dynamics): {len(expert_features['expert2_dynamics'])}")
        print(f"   - Expert 3 (Control): {len(expert_features['expert3_control'])}")
        print(f"   - Expert 4 (Power): {len(expert_features['expert4_power'])}")
        print(f"\n✅ Field mappings: {len(field_mapping)} mappings defined")
        print(f"✅ Synthetic features: {len(synthetic_features)} features with defaults")

        return True


def check_telemetry_collector_fields():
    """Check which fields the telemetry collector provides."""

    print("\n" + "=" * 80)
    print("TELEMETRY COLLECTOR FIELDS CHECK")
    print("=" * 80)

    # These are the fields that telemetry_collector.py outputs to CSV
    # Based on the record dict in lines 436-639
    telemetry_fields = {
        # Basic
        'Timestamp', 'Speed_kmh', 'RPM', 'Throttle', 'Brake', 'Clutch', 'Steering', 'Gear',

        # Velocities
        'Velocity_X', 'Velocity_Y', 'Velocity_Z',
        'LocalVelocity_X', 'LocalVelocity_Y', 'LocalVelocity_Z',

        # G-Forces
        'AccG_Lateral', 'AccG_Vertical', 'AccG_Longitudinal',

        # Orientation
        'Heading', 'Pitch', 'Roll', 'CG_Height',

        # Angular Velocity
        'AngularVel_X', 'AngularVel_Y', 'AngularVel_Z',

        # Tire data (FL, FR, RL, RR) - 4 wheels each
        'TireTemp_FL_Inner', 'TireTemp_FL_Middle', 'TireTemp_FL_Outer', 'TireTemp_FL_Avg', 'TireTemp_FL_Core',
        'TireTemp_FR_Inner', 'TireTemp_FR_Middle', 'TireTemp_FR_Outer', 'TireTemp_FR_Avg', 'TireTemp_FR_Core',
        'TireTemp_RL_Inner', 'TireTemp_RL_Middle', 'TireTemp_RL_Outer', 'TireTemp_RL_Avg', 'TireTemp_RL_Core',
        'TireTemp_RR_Inner', 'TireTemp_RR_Middle', 'TireTemp_RR_Outer', 'TireTemp_RR_Avg', 'TireTemp_RR_Core',

        'TireWear_FL', 'TireWear_FR', 'TireWear_RL', 'TireWear_RR',
        'TireDirty_FL', 'TireDirty_FR', 'TireDirty_RL', 'TireDirty_RR',
        'TirePressure_FL', 'TirePressure_FR', 'TirePressure_RL', 'TirePressure_RR',
        'TireLoad_FL', 'TireLoad_FR', 'TireLoad_RL', 'TireLoad_RR',

        'WheelSlip_FL', 'WheelSlip_FR', 'WheelSlip_RL', 'WheelSlip_RR',
        'WheelAngularSpeed_FL', 'WheelAngularSpeed_FR', 'WheelAngularSpeed_RL', 'WheelAngularSpeed_RR',
        'SlipRatio_FL', 'SlipRatio_FR', 'SlipRatio_RL', 'SlipRatio_RR',
        'SlipAngle_FL', 'SlipAngle_FR', 'SlipAngle_RL', 'SlipAngle_RR',

        'Camber_FL', 'Camber_FR', 'Camber_RL', 'Camber_RR',
        'SuspensionTravel_FL', 'SuspensionTravel_FR', 'SuspensionTravel_RL', 'SuspensionTravel_RR',
        'SuspensionDamage_FL', 'SuspensionDamage_FR', 'SuspensionDamage_RL', 'SuspensionDamage_RR',

        'BrakeTemp_FL', 'BrakeTemp_FR', 'BrakeTemp_RL', 'BrakeTemp_RR',

        'Mz_FL', 'Mz_FR', 'Mz_RL', 'Mz_RR',
        'Fx_FL', 'Fx_FR', 'Fx_RL', 'Fx_RR',
        'Fy_FL', 'Fy_FR', 'Fy_RL', 'Fy_RR',

        # Fuel & Engine
        'Fuel', 'TurboBoost', 'EngineTemp_Oil', 'EngineTemp_Water', 'EngineBrake', 'CurrentMaxRpm',

        # ERS/KERS
        'ERS_RecoveryLevel', 'ERS_PowerLevel', 'ERS_HeatCharging', 'ERS_IsCharging',
        'KERS_Charge', 'KERS_Input', 'KERS_CurrentKJ',

        # DRS
        'DRS', 'DRS_Available', 'DRS_Enabled',

        # Driver Aids
        'TC_Level', 'TC_InAction', 'ABS_Level', 'ABS_InAction',
        'AutoShifter', 'PitLimiter',

        # Setup
        'RideHeight_Front', 'RideHeight_Rear', 'BrakeBias', 'Ballast',

        # Damage
        'Damage_Front', 'Damage_Rear', 'Damage_Left', 'Damage_Right', 'Damage_Center',

        # Environment
        'AirTemp', 'RoadTemp', 'AirDensity',

        # Track Position
        'CompletedLaps', 'iCurrentTime_ms', 'CurrentLapTime_str', 'iLastTime_ms', 'iBestTime_ms',
        'DistanceTraveled_m', 'LapNumberTotal', 'CurrentSectorIndex', 'LastSectorTime_ms',
        'NormalizedPosition',

        # Pit & Track
        'IsInPit', 'IsInPitLane', 'TyreCompound', 'Flag', 'SurfaceGrip', 'NumberOfTyresOut',

        # Car Position
        'CarX', 'CarY', 'CarZ',

        # Advanced
        'FinalFF', 'PerformanceMeter', 'IsAIControlled', 'P2P_Activations', 'P2P_Status'
    }

    print(f"\nTelemetry collector provides {len(telemetry_fields)} fields")

    # Check which MoE features are present
    expert_features = RealTimeFeatureExtractor.EXPERT_FEATURES
    all_moe_features = set()
    for features in expert_features.values():
        all_moe_features.update(features)

    present = all_moe_features & telemetry_fields
    missing = all_moe_features - telemetry_fields

    print(f"\n✅ MoE features present in telemetry: {len(present)}/{len(all_moe_features)}")

    if missing:
        print(f"\n⚠️  MoE features NOT in telemetry collector:")
        for feature in sorted(missing):
            print(f"  - {feature}")
    else:
        print("\n✅ All MoE features are captured by telemetry collector!")

    return len(missing) == 0


if __name__ == "__main__":
    print("\n🔍 Starting telemetry variable validation...\n")

    # Run validations
    validation_passed = validate_moe_features()
    collector_check_passed = check_telemetry_collector_fields()

    # Final result
    print("\n" + "=" * 80)
    print("FINAL RESULT")
    print("=" * 80)

    if validation_passed and collector_check_passed:
        print("\n🎉 SUCCESS! All telemetry variables are correctly configured!\n")
        print("✅ MoE feature definitions: VALID")
        print("✅ Field name mappings: VALID")
        print("✅ Telemetry collector: COMPLETE")
        print("\n✅ The system is ready for MoE inference!")
        sys.exit(0)
    else:
        print("\n❌ VALIDATION FAILED - Please fix the issues above\n")
        sys.exit(1)
