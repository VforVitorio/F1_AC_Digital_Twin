"""
Real-time Feature Processor for MoE Anomaly Detection

This module handles feature extraction and normalization for the 4-expert MoE system:
- Expert 1: Tire Dynamics (20 features)
- Expert 2: Vehicle Dynamics (16 features)
- Expert 3: Driver Control (6 features)
- Expert 4: Power Systems (4 features)
Total: 46 features

Note: Variables with zero variance have been removed:
      - Expert 3: TC_InAction, ABS_InAction, BrakeBias, BrakeTemp_*
      - Expert 4: Fuel, EngineTemp_Oil, CurrentMaxRpm, EngineBrake, ERS_PowerLevel, ERS_RecoveryLevel

Author: F1 Digital Twin Team
"""

import pickle
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RealTimeFeatureExtractor:
    """
    Extracts and normalizes features from raw telemetry for MoE inference.

    Features are extracted per expert and normalized using pre-fitted StandardScalers
    from the training phase.
    """

    # Expert feature definitions (must match training)
    EXPERT_FEATURES = {
        'expert1_tire': [
            'TireTemp_FL_Avg', 'TireTemp_FR_Avg', 'TireTemp_RL_Avg', 'TireTemp_RR_Avg',
            'TireWear_FL', 'TireWear_FR', 'TireWear_RL', 'TireWear_RR',
            'TirePressure_FL', 'TirePressure_FR', 'TirePressure_RL', 'TirePressure_RR',
            'SlipRatio_FL', 'SlipRatio_FR', 'SlipRatio_RL', 'SlipRatio_RR',
            'SlipAngle_FL', 'SlipAngle_FR', 'SlipAngle_RL', 'SlipAngle_RR'
        ],
        'expert2_dynamics': [
            'AccG_Lateral', 'AccG_Vertical', 'AccG_Longitudinal',
            'LocalVelocity_X', 'LocalVelocity_Y', 'LocalVelocity_Z',
            'AngularVel_X', 'AngularVel_Y', 'AngularVel_Z',
            'Heading', 'Pitch', 'Roll',
            'TireLoad_FL', 'TireLoad_FR', 'TireLoad_RL', 'TireLoad_RR'  # 16 features
        ],
        'expert3_control': [
            'Speed_kmh', 'RPM', 'Throttle', 'Brake', 'Steering', 'Gear'  # 6 features
            # Note: TC_InAction, ABS_InAction, BrakeBias, and BrakeTemp_* removed (zero variance)
        ],
        'expert4_power': [
            'TurboBoost',
            'KERS_Charge', 'KERS_CurrentKJ',
            'DRS_Enabled'  # 4 features
            # Note: Fuel, EngineTemp_Oil, CurrentMaxRpm, EngineBrake, ERS_* removed (zero variance)
        ]
    }

    # Mapping from producer field names (snake_case) to expected names (CamelCase)
    FIELD_NAME_MAPPING = {
        # Tire temperatures
        'tire_temp_fl_avg': 'TireTemp_FL_Avg',
        'tire_temp_fr_avg': 'TireTemp_FR_Avg',
        'tire_temp_rl_avg': 'TireTemp_RL_Avg',
        'tire_temp_rr_avg': 'TireTemp_RR_Avg',
        # Tire wear
        'tire_wear_fl': 'TireWear_FL',
        'tire_wear_fr': 'TireWear_FR',
        'tire_wear_rl': 'TireWear_RL',
        'tire_wear_rr': 'TireWear_RR',
        # Tire pressure
        'tire_pressure_fl': 'TirePressure_FL',
        'tire_pressure_fr': 'TirePressure_FR',
        'tire_pressure_rl': 'TirePressure_RL',
        'tire_pressure_rr': 'TirePressure_RR',
        # Slip ratio (wheel_slip in producer)
        'wheel_slip_fl': 'SlipRatio_FL',
        'wheel_slip_fr': 'SlipRatio_FR',
        'wheel_slip_rl': 'SlipRatio_RL',
        'wheel_slip_rr': 'SlipRatio_RR',
        # Slip angle (not available directly, use wheel_slip as proxy)
        'slip_angle_fl': 'SlipAngle_FL',
        'slip_angle_fr': 'SlipAngle_FR',
        'slip_angle_rl': 'SlipAngle_RL',
        'slip_angle_rr': 'SlipAngle_RR',
        # G-forces
        'accg_lateral': 'AccG_Lateral',
        'accg_vertical': 'AccG_Vertical',
        'accg_longitudinal': 'AccG_Longitudinal',
        # Local velocity
        'local_velocity_x': 'LocalVelocity_X',
        'local_velocity_y': 'LocalVelocity_Y',
        'local_velocity_z': 'LocalVelocity_Z',
        # Angular velocity
        'angular_vel_x': 'AngularVel_X',
        'angular_vel_y': 'AngularVel_Y',
        'angular_vel_z': 'AngularVel_Z',
        # Orientation
        'heading': 'Heading',
        'pitch': 'Pitch',
        'roll': 'Roll',
        # Tire load (map from wheel_load or tire_load)
        'wheel_load_fl': 'TireLoad_FL',
        'wheel_load_fr': 'TireLoad_FR',
        'wheel_load_rl': 'TireLoad_RL',
        'wheel_load_rr': 'TireLoad_RR',
        'tire_load_fl': 'TireLoad_FL',
        'tire_load_fr': 'TireLoad_FR',
        'tire_load_rl': 'TireLoad_RL',
        'tire_load_rr': 'TireLoad_RR',
        'TireLoad_FL': 'TireLoad_FL',  # Identity mappings for CamelCase
        'TireLoad_FR': 'TireLoad_FR',
        'TireLoad_RL': 'TireLoad_RL',
        'TireLoad_RR': 'TireLoad_RR',
        # Control
        'speed_kmh': 'Speed_kmh',
        'rpm': 'RPM',
        'throttle': 'Throttle',
        'brake': 'Brake',
        'steering': 'Steering',
        'gear': 'Gear',
        # Note: Assist systems and brake temps removed due to zero variance in telemetry
        # 'tc_in_action': 'TC_InAction',
        # 'abs_in_action': 'ABS_InAction',
        # 'brake_bias': 'BrakeBias',
        # 'brake_temp_fl': 'BrakeTemp_FL',
        # 'brake_temp_fr': 'BrakeTemp_FR',
        # 'brake_temp_rl': 'BrakeTemp_RL',
        # 'brake_temp_rr': 'BrakeTemp_RR',
        # Power (only variables with variance)
        'turbo_boost': 'TurboBoost',
        'kers_charge': 'KERS_Charge',
        'kers_current_kj': 'KERS_CurrentKJ',
        'drs_enabled': 'DRS_Enabled',
        # Note: Fuel, engine temps, RPM, brake, and ERS levels removed (zero variance)
        # 'fuel': 'Fuel',
        # 'engine_temp_oil': 'EngineTemp_Oil',
        # 'current_max_rpm': 'CurrentMaxRpm',
        # 'engine_brake': 'EngineBrake',
        # 'ers_power_level': 'ERS_PowerLevel',
        # 'ers_recovery_level': 'ERS_RecoveryLevel',
        # Metadata
        'completed_laps': 'CompletedLaps',
        'distance': 'Distance',
        # Additional lowercase mappings for fields that might come in different formats
        'speed_kmh': 'Speed_kmh',
        'speedkmh': 'Speed_kmh',
    }

    # Features that have defaults/proxies and don't need to be in the input
    SYNTHETIC_FEATURES = {
        'EngineTemp_Oil',  # AC Shared Memory doesn't provide this, using default
    }

    def __init__(self, scalers_dir: str):
        """
        Initialize the feature extractor.

        Args:
            scalers_dir: Path to directory containing scaler pickle files
        """
        self.scalers_dir = Path(scalers_dir)
        self.scalers = {}
        self._load_scalers()

        # Statistics for monitoring
        self.stats = {
            'total_processed': 0,
            'missing_values_count': 0,
            'errors': 0
        }

    def _load_scalers(self):
        """Load pre-fitted StandardScalers for each expert."""
        for expert_name in self.EXPERT_FEATURES.keys():
            scaler_path = self.scalers_dir / f'scaler_{expert_name}.pkl'

            if not scaler_path.exists():
                raise FileNotFoundError(
                    f"Scaler not found: {scaler_path}\n"
                    f"Please ensure scalers are generated during data preparation."
                )

            with open(scaler_path, 'rb') as f:
                self.scalers[expert_name] = pickle.load(f)

            logger.info(f"Loaded scaler for {expert_name}: {scaler_path.name}")

    def _normalize_field_names(self, telemetry: Dict[str, float]) -> Dict[str, float]:
        """
        Normalize field names from producer format to expected format.

        Args:
            telemetry: Raw telemetry with snake_case field names

        Returns:
            Telemetry with normalized field names (CamelCase)
        """
        normalized = {}

        for key, value in telemetry.items():
            # Check if this key needs mapping
            if key in self.FIELD_NAME_MAPPING:
                normalized[self.FIELD_NAME_MAPPING[key]] = value
            else:
                # Keep original key (might already be in correct format)
                normalized[key] = value

        # Handle missing fields with sensible defaults or proxies
        # SlipAngle - use wheel_slip as proxy if not available
        if 'SlipAngle_FL' not in normalized and 'SlipRatio_FL' in normalized:
            normalized['SlipAngle_FL'] = normalized.get(
                'SlipRatio_FL', 0.0) * 0.1
            normalized['SlipAngle_FR'] = normalized.get(
                'SlipRatio_FR', 0.0) * 0.1
            normalized['SlipAngle_RL'] = normalized.get(
                'SlipRatio_RL', 0.0) * 0.1
            normalized['SlipAngle_RR'] = normalized.get(
                'SlipRatio_RR', 0.0) * 0.1

        # TireLoad - use wheel_load if available
        if 'TireLoad_FL' not in normalized:
            # Try to get from WheelLoad fields (from telemetry_collector)
            normalized['TireLoad_FL'] = telemetry.get('WheelLoad_FL', telemetry.get('wheel_load_fl', 2500.0))
            normalized['TireLoad_FR'] = telemetry.get('WheelLoad_FR', telemetry.get('wheel_load_fr', 2500.0))
            normalized['TireLoad_RL'] = telemetry.get('WheelLoad_RL', telemetry.get('wheel_load_rl', 2300.0))
            normalized['TireLoad_RR'] = telemetry.get('WheelLoad_RR', telemetry.get('wheel_load_rr', 2300.0))

        # Engine-related fields with defaults
        if 'EngineTemp_Oil' not in normalized:
            normalized['EngineTemp_Oil'] = 90.0  # Normal oil temp
        if 'CurrentMaxRpm' not in normalized:
            normalized['CurrentMaxRpm'] = telemetry.get('rpm', 10000)
        if 'EngineBrake' not in normalized:
            normalized['EngineBrake'] = 0.0

        return normalized

    def extract_features(
        self,
        telemetry: Dict[str, float],
        expert_name: Optional[str] = None
    ) -> Dict[str, np.ndarray]:
        """
        Extract features from raw telemetry for one or all experts.

        Args:
            telemetry: Dictionary of raw telemetry data (156 variables)
            expert_name: Specific expert to extract for, or None for all experts

        Returns:
            Dictionary mapping expert names to feature arrays (unnormalized)

        Example:
            >>> telemetry = {'Speed_kmh': 280.5, 'RPM': 11500, ...}
            >>> features = extractor.extract_features(telemetry)
            >>> features['expert1_tire']  # array of 20 tire features
        """
        # Normalize field names first
        telemetry = self._normalize_field_names(telemetry)

        if expert_name:
            experts_to_process = [expert_name]
        else:
            experts_to_process = list(self.EXPERT_FEATURES.keys())

        extracted = {}

        for expert in experts_to_process:
            feature_names = self.EXPERT_FEATURES[expert]
            features = []

            for feature_name in feature_names:
                value = telemetry.get(feature_name, np.nan)
                features.append(value)

            extracted[expert] = np.array(features, dtype=np.float64)

        return extracted

    def normalize_features(
        self,
        features: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """
        Normalize features using pre-fitted scalers.

        Args:
            features: Dictionary mapping expert names to feature arrays

        Returns:
            Dictionary mapping expert names to normalized feature arrays
        """
        normalized = {}

        for expert_name, feature_array in features.items():
            # Check for missing values
            if np.any(np.isnan(feature_array)):
                self.stats['missing_values_count'] += 1
                logger.warning(
                    f"Missing values detected in {expert_name}: "
                    f"{np.sum(np.isnan(feature_array))} NaN values"
                )
                # Replace NaN with 0 (mean in normalized space)
                feature_array = np.nan_to_num(feature_array, nan=0.0)

            # Reshape for sklearn: (1, n_features)
            feature_array_2d = feature_array.reshape(1, -1)

            # Get scaler for this expert
            scaler = self.scalers[expert_name]

            # DEBUG: Log raw values before normalization
            if expert_name == 'expert1_tire':
                logger.debug(f"[DEBUG] {expert_name} RAW values (first 4): {feature_array[:4]}")
                logger.debug(f"[DEBUG] Scaler mean (first 4): {scaler.mean_[:4]}")
                logger.debug(f"[DEBUG] Scaler scale (first 4): {scaler.scale_[:4]}")

            # Normalize using scaler
            normalized_array = scaler.transform(feature_array_2d)

            # DEBUG: Log normalized values
            if expert_name == 'expert1_tire':
                logger.debug(f"[DEBUG] {expert_name} NORMALIZED (first 4): {normalized_array.flatten()[:4]}")

            # Return as 1D array
            normalized[expert_name] = normalized_array.flatten()

        return normalized

    def process(
        self,
        telemetry: Dict[str, float],
        expert_name: Optional[str] = None
    ) -> Dict[str, np.ndarray]:
        """
        Complete pipeline: extract + normalize features.

        Args:
            telemetry: Raw telemetry dictionary
            expert_name: Specific expert or None for all

        Returns:
            Normalized features ready for MoE inference

        Example:
            >>> telemetry = get_telemetry_from_kafka()
            >>> normalized_features = extractor.process(telemetry)
            >>> # Ready for MoE model
        """
        try:
            # Extract raw features
            raw_features = self.extract_features(telemetry, expert_name)

            # Normalize
            normalized_features = self.normalize_features(raw_features)

            self.stats['total_processed'] += 1

            return normalized_features

        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Error processing telemetry: {e}")
            raise

    def process_batch(
        self,
        telemetry_batch: List[Dict[str, float]],
        expert_name: Optional[str] = None
    ) -> Tuple[Dict[str, np.ndarray], List[int]]:
        """
        Process a batch of telemetry samples.

        Args:
            telemetry_batch: List of telemetry dictionaries
            expert_name: Specific expert or None for all

        Returns:
            Tuple of:
                - Dictionary mapping expert names to 2D arrays (n_samples, n_features)
                - List of indices that failed processing
        """
        results_by_expert = {expert: []
                             for expert in self.EXPERT_FEATURES.keys()}
        failed_indices = []

        for idx, telemetry in enumerate(telemetry_batch):
            try:
                normalized = self.process(telemetry, expert_name)

                for expert, features in normalized.items():
                    results_by_expert[expert].append(features)

            except Exception as e:
                logger.warning(f"Failed to process sample {idx}: {e}")
                failed_indices.append(idx)

        # Convert lists to 2D arrays
        batch_features = {}
        for expert, feature_list in results_by_expert.items():
            if feature_list:
                batch_features[expert] = np.vstack(feature_list)

        return batch_features, failed_indices

    def get_feature_names(self, expert_name: str) -> List[str]:
        """Get the list of feature names for a specific expert."""
        return self.EXPERT_FEATURES.get(expert_name, [])

    def get_stats(self) -> Dict[str, int]:
        """Get processing statistics."""
        return self.stats.copy()

    def reset_stats(self):
        """Reset statistics counters."""
        self.stats = {
            'total_processed': 0,
            'missing_values_count': 0,
            'errors': 0
        }


def validate_telemetry(telemetry: Dict[str, float]) -> Tuple[bool, List[str]]:
    """
    Validate that telemetry contains all required features.

    Args:
        telemetry: Raw telemetry dictionary

    Returns:
        Tuple of (is_valid, list_of_missing_features)
    """
    # Create reverse mapping (expected -> producer)
    reverse_mapping = {
        v: k for k, v in RealTimeFeatureExtractor.FIELD_NAME_MAPPING.items()}

    all_required_features = set()
    for features in RealTimeFeatureExtractor.EXPERT_FEATURES.values():
        all_required_features.update(features)

    # Remove synthetic features that will be generated from proxies/defaults
    synthetic_features = getattr(
        RealTimeFeatureExtractor, 'SYNTHETIC_FEATURES', set())
    required_from_input = all_required_features - synthetic_features

    missing_features = []
    for feature in required_from_input:
        # Check if feature exists directly OR via mapped name
        producer_name = reverse_mapping.get(feature, None)
        if feature not in telemetry and (producer_name is None or producer_name not in telemetry):
            missing_features.append(feature)

    is_valid = len(missing_features) == 0
    return is_valid, missing_features


# Example usage
if __name__ == "__main__":
    import sys

    # Path to scalers
    ROOT = Path(__file__).resolve().parents[1]
    SCALERS_DIR = ROOT / 'data' / 'processed' / 'MoE-anomaly' / 'scalers'

    try:
        # Initialize extractor
        extractor = RealTimeFeatureExtractor(SCALERS_DIR)

        # Mock telemetry sample
        mock_telemetry = {
            'Speed_kmh': 280.5,
            'RPM': 11500,
            'Throttle': 0.95,
            'Brake': 0.0,
            'Steering': 0.15,
            'Gear': 7,
            'TireTemp_FL_Avg': 95.3,
            'TireTemp_FR_Avg': 96.1,
            'TireTemp_RL_Avg': 94.8,
            'TireTemp_RR_Avg': 95.5,
            'TireWear_FL': 0.12,
            'TireWear_FR': 0.13,
            'TireWear_RL': 0.11,
            'TireWear_RR': 0.12,
            'TirePressure_FL': 28.5,
            'TirePressure_FR': 28.3,
            'TirePressure_RL': 29.1,
            'TirePressure_RR': 29.0,
            'SlipRatio_FL': 0.02,
            'SlipRatio_FR': 0.03,
            'SlipRatio_RL': 0.01,
            'SlipRatio_RR': 0.02,
            'SlipAngle_FL': 0.05,
            'SlipAngle_FR': 0.06,
            'SlipAngle_RL': 0.03,
            'SlipAngle_RR': 0.04,
            'AccG_Lateral': 1.5,
            'AccG_Vertical': -0.2,
            'AccG_Longitudinal': 0.8,
            'LocalVelocity_X': 77.9,
            'LocalVelocity_Y': 0.5,
            'LocalVelocity_Z': -0.1,
            'AngularVel_X': 0.02,
            'AngularVel_Y': 0.15,
            'AngularVel_Z': 0.03,
            'Heading': 1.57,
            'Pitch': 0.05,
            'Roll': -0.02,
            'TireLoad_FL': 2500,
            'TireLoad_FR': 2450,
            'TireLoad_RL': 2200,
            'TC_InAction': 0,
            'ABS_InAction': 0,
            'BrakeBias': 0.52,
            'BrakeTemp_FL': 450,
            'BrakeTemp_FR': 455,
            'BrakeTemp_RL': 420,
            'Fuel': 45.2,
            'TurboBoost': 1.8,
            'EngineTemp_Oil': 105,
            'CurrentMaxRpm': 12000,
            'EngineBrake': 0,
            'KERS_Charge': 0.85,
            'KERS_CurrentKJ': 340,
            'ERS_PowerLevel': 5,
            'ERS_RecoveryLevel': 3,
            'DRS_Enabled': 0
        }

        # Validate
        is_valid, missing = validate_telemetry(mock_telemetry)
        if not is_valid:
            print(f"Missing features: {missing}")
            sys.exit(1)

        # Process single sample
        print("\n" + "="*60)
        print("PROCESSING SINGLE TELEMETRY SAMPLE")
        print("="*60)

        normalized = extractor.process(mock_telemetry)

        for expert_name, features in normalized.items():
            print(f"\n{expert_name}:")
            print(f"  Shape: {features.shape}")
            print(f"  Mean: {features.mean():.3f}")
            print(f"  Std: {features.std():.3f}")
            print(f"  Min: {features.min():.3f}, Max: {features.max():.3f}")

        # Statistics
        print("\n" + "="*60)
        print("STATISTICS")
        print("="*60)
        stats = extractor.get_stats()
        for key, value in stats.items():
            print(f"{key}: {value}")

        print("\n✅ Feature processor test successful!")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)
