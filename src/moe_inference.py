"""
Mixture of Experts (MoE) Inference Engine for Anomaly Detection

This module provides real-time inference using the 4-expert MoE system:
- Expert 1: Tire Dynamics
- Expert 2: Vehicle Dynamics
- Expert 3: Driver Control
- Expert 4: Power Systems

The gating network (learned LogisticRegression) combines expert predictions.

Author: F1 Digital Twin Team
"""

import pickle
import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MoEInference:
    """
    Mixture of Experts inference engine for real-time anomaly detection.

    Loads pre-trained GMM experts and gating network, performs inference on
    normalized telemetry features.
    """

    def __init__(self, models_dir: str):
        """
        Initialize the MoE inference engine.

        Args:
            models_dir: Path to directory containing model files
        """
        self.models_dir = Path(models_dir)
        self.config = {}
        self.experts = {}
        self.gating_network = None
        self.expert_names = []
        self.thresholds = {}

        self._load_config()
        self._load_models()

        # Statistics
        self.stats = {
            'total_inferences': 0,
            'anomalies_detected': 0,
            'anomalies_by_expert': {name: 0 for name in self.expert_names},
            'errors': 0
        }

        logger.info("MoE Inference Engine initialized successfully")

    def _load_config(self):
        """Load MoE configuration."""
        config_path = self.models_dir / 'moe_config.json'

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.expert_names = self.config['experts']
        self.thresholds = self.config['thresholds']

        logger.info(f"Loaded MoE config: {len(self.expert_names)} experts")

    def _load_models(self):
        """Load all expert GMM models and gating network."""
        # Load expert GMMs
        for expert_name in self.expert_names:
            model_filename = self.config['expert_models'][expert_name]
            model_path = self.models_dir / model_filename

            if not model_path.exists():
                raise FileNotFoundError(
                    f"Expert model not found: {model_path}")

            with open(model_path, 'rb') as f:
                self.experts[expert_name] = pickle.load(f)

            logger.info(f"Loaded {expert_name}: {model_path.name}")

        # Load gating network
        gating_path = self.models_dir / self.config['gating_model']

        if not gating_path.exists():
            raise FileNotFoundError(f"Gating network not found: {gating_path}")

        with open(gating_path, 'rb') as f:
            self.gating_network = pickle.load(f)

        logger.info(f"Loaded gating network: {gating_path.name}")

    def compute_expert_scores(
        self,
        normalized_features: Dict[str, np.ndarray]
    ) -> Dict[str, float]:
        """
        Compute anomaly scores for each expert.

        Anomaly score = -log_likelihood from GMM.
        Higher score = more anomalous.

        Args:
            normalized_features: Dictionary mapping expert names to normalized feature arrays

        Returns:
            Dictionary mapping expert names to anomaly scores
        """
        scores = {}

        for expert_name, features in normalized_features.items():
            # Get GMM model
            gmm = self.experts[expert_name]

            # Ensure 2D shape: (1, n_features)
            if features.ndim == 1:
                features = features.reshape(1, -1)

            # Compute log-likelihood
            log_likelihood = gmm.score_samples(features)[0]

            # Anomaly score = negative log-likelihood
            anomaly_score = -log_likelihood

            scores[expert_name] = float(anomaly_score)

        return scores

    def compute_gating_features(self, expert_scores: Dict[str, float]) -> np.ndarray:
        """
        Create feature vector for gating network.

        Features:
        - Raw scores from each expert (4 features)
        - Relative scores: score - mean_score (4 features)

        Args:
            expert_scores: Dictionary of expert anomaly scores

        Returns:
            Feature array of shape (1, 8) for gating network
        """
        # Extract scores in correct order
        scores = np.array([expert_scores[name] for name in self.expert_names])

        # Compute relative scores
        mean_score = scores.mean()
        relative_scores = scores - mean_score

        # Concatenate: [raw_scores, relative_scores]
        gating_features = np.concatenate([scores, relative_scores])

        return gating_features.reshape(1, -1)

    def compute_expert_weights(self, expert_scores: Dict[str, float]) -> Dict[str, float]:
        """
        Compute expert weights using softmax of anomaly scores.

        This provides interpretable weights showing which expert is "attending"
        to the current situation.

        Args:
            expert_scores: Dictionary of expert anomaly scores

        Returns:
            Dictionary mapping expert names to weights (sum to 1.0)
        """
        scores = np.array([expert_scores[name] for name in self.expert_names])

        # Softmax with temperature
        temperature = 10.0
        # Negative because higher score = more anomalous
        exp_scores = np.exp(-scores / temperature)
        softmax_weights = exp_scores / exp_scores.sum()

        weights = {
            name: float(weight)
            for name, weight in zip(self.expert_names, softmax_weights)
        }

        return weights

    def classify_anomaly_type(
        self,
        expert_scores: Dict[str, float],
        expert_weights: Dict[str, float]
    ) -> Tuple[str, str, Optional[str]]:
        """
        Classify the type and severity of anomaly.

        Args:
            expert_scores: Anomaly scores by expert
            expert_weights: Expert weights (attention)

        Returns:
            Tuple of (anomaly_type, severity, affected_component)

        Anomaly types:
            - tire_overheat
            - tire_wear
            - tire_pressure
            - vehicle_dynamics
            - driver_control
            - power_system
            - multiple
        """
        # Find which experts detected anomalies
        anomalous_experts = []
        for expert_name, score in expert_scores.items():
            threshold = self.thresholds[expert_name]

            # Anomaly = score > threshold (above 95th percentile)
            # This is consistent with how thresholds were computed during training:
            # threshold = np.percentile(scores, 95) -> anomaly if score > threshold
            is_anomaly = score > threshold

            if is_anomaly:
                anomalous_experts.append(expert_name)
                self.stats['anomalies_by_expert'][expert_name] += 1

        # Determine anomaly type
        if len(anomalous_experts) == 0:
            return 'none', 'normal', None

        elif len(anomalous_experts) > 1:
            anomaly_type = 'multiple'
        else:
            # Single expert anomaly
            expert = anomalous_experts[0]
            if expert == 'expert1_tire':
                anomaly_type = 'tire_anomaly'
            elif expert == 'expert2_dynamics':
                anomaly_type = 'vehicle_dynamics'
            elif expert == 'expert3_control':
                anomaly_type = 'driver_control'
            else:  # expert4_power
                anomaly_type = 'power_system'

        # Determine severity based on score deviation from threshold
        max_deviation = 0
        for expert in anomalous_experts:
            score = expert_scores[expert]
            threshold = self.thresholds[expert]
            deviation = abs(score - threshold) / abs(threshold)
            max_deviation = max(max_deviation, deviation)

        if max_deviation > 0.5:
            severity = 'high'
        elif max_deviation > 0.2:
            severity = 'medium'
        else:
            severity = 'low'

        # Affected component (simplified)
        dominant_expert = max(expert_weights, key=expert_weights.get)
        affected_component = dominant_expert.replace(
            'expert', '').replace('_', ' ')

        return anomaly_type, severity, affected_component

    def predict(
        self,
        normalized_features: Dict[str, np.ndarray]
    ) -> Dict:
        """
        Complete MoE inference pipeline.

        Args:
            normalized_features: Dictionary mapping expert names to normalized features

        Returns:
            Dictionary containing:
                - is_anomaly (bool): Whether anomaly detected
                - anomaly_type (str): Type of anomaly
                - severity (str): Severity level (low/medium/high)
                - expert_scores (dict): Scores by expert
                - expert_weights (dict): Attention weights by expert
                - global_score (float): Combined anomaly score
                - anomaly_probability (float): Probability from gating network
                - affected_component (str): Component with anomaly

        Example:
            >>> features = feature_extractor.process(telemetry)
            >>> result = moe.predict(features)
            >>> if result['is_anomaly']:
            >>>     print(f"Anomaly: {result['anomaly_type']} ({result['severity']})")
        """
        try:
            # 1. Compute expert scores
            expert_scores = self.compute_expert_scores(normalized_features)

            # 2. Compute expert weights (interpretability)
            expert_weights = self.compute_expert_weights(expert_scores)

            # 3. Compute global score (weighted average)
            global_score = sum(
                expert_scores[name] * expert_weights[name]
                for name in self.expert_names
            )

            # 4. Use gating network for anomaly detection
            gating_features = self.compute_gating_features(expert_scores)
            anomaly_prediction = self.gating_network.predict(gating_features)[
                0]
            anomaly_probability = self.gating_network.predict_proba(gating_features)[
                0][1]

            is_anomaly = bool(anomaly_prediction)

            # 5. Classify anomaly type and severity
            anomaly_type, severity, affected_component = self.classify_anomaly_type(
                expert_scores, expert_weights
            )

            # Update statistics
            self.stats['total_inferences'] += 1
            if is_anomaly:
                self.stats['anomalies_detected'] += 1

            # 6. Build result dictionary
            result = {
                'is_anomaly': is_anomaly,
                'anomaly_type': anomaly_type,
                'severity': severity,
                'expert_scores': expert_scores,
                'expert_weights': expert_weights,
                'global_score': float(global_score),
                'anomaly_probability': float(anomaly_probability),
                'affected_component': affected_component
            }

            return result

        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Error during inference: {e}")
            raise

    def predict_batch(
        self,
        normalized_features_batch: List[Dict[str, np.ndarray]]
    ) -> List[Dict]:
        """
        Perform batch inference.

        Args:
            normalized_features_batch: List of normalized feature dictionaries

        Returns:
            List of prediction results
        """
        results = []

        for features in normalized_features_batch:
            try:
                result = self.predict(features)
                results.append(result)
            except Exception as e:
                logger.warning(f"Batch inference error: {e}")
                results.append(None)

        return results

    def get_stats(self) -> Dict:
        """Get inference statistics."""
        stats = self.stats.copy()

        if stats['total_inferences'] > 0:
            stats['anomaly_rate'] = stats['anomalies_detected'] / \
                stats['total_inferences']
        else:
            stats['anomaly_rate'] = 0.0

        return stats

    def reset_stats(self):
        """Reset statistics."""
        self.stats = {
            'total_inferences': 0,
            'anomalies_detected': 0,
            'anomalies_by_expert': {name: 0 for name in self.expert_names},
            'errors': 0
        }


# Example usage
if __name__ == "__main__":
    import sys
    from feature_processor import RealTimeFeatureExtractor

    # Paths
    ROOT = Path(__file__).resolve().parents[1]
    MODELS_DIR = ROOT / 'models' / 'anomaly-detection'
    SCALERS_DIR = ROOT / 'data' / 'processed' / 'MoE-anomaly' / 'scalers'

    try:
        # Initialize components
        print("="*60)
        print("INITIALIZING MoE INFERENCE ENGINE")
        print("="*60)

        feature_extractor = RealTimeFeatureExtractor(SCALERS_DIR)
        moe = MoEInference(MODELS_DIR)

        # Mock telemetry
        mock_telemetry = {
            'Speed_kmh': 280.5, 'RPM': 11500, 'Throttle': 0.95, 'Brake': 0.0,
            'Steering': 0.15, 'Gear': 7,
            'TireTemp_FL_Avg': 95.3, 'TireTemp_FR_Avg': 96.1,
            'TireTemp_RL_Avg': 94.8, 'TireTemp_RR_Avg': 95.5,
            'TireWear_FL': 0.12, 'TireWear_FR': 0.13,
            'TireWear_RL': 0.11, 'TireWear_RR': 0.12,
            'TirePressure_FL': 28.5, 'TirePressure_FR': 28.3,
            'TirePressure_RL': 29.1, 'TirePressure_RR': 29.0,
            'SlipRatio_FL': 0.02, 'SlipRatio_FR': 0.03,
            'SlipRatio_RL': 0.01, 'SlipRatio_RR': 0.02,
            'SlipAngle_FL': 0.05, 'SlipAngle_FR': 0.06,
            'SlipAngle_RL': 0.03, 'SlipAngle_RR': 0.04,
            'AccG_Lateral': 1.5, 'AccG_Vertical': -0.2, 'AccG_Longitudinal': 0.8,
            'LocalVelocity_X': 77.9, 'LocalVelocity_Y': 0.5, 'LocalVelocity_Z': -0.1,
            'AngularVel_X': 0.02, 'AngularVel_Y': 0.15, 'AngularVel_Z': 0.03,
            'Heading': 1.57, 'Pitch': 0.05, 'Roll': -0.02,
            'TireLoad_FL': 2500, 'TireLoad_FR': 2450, 'TireLoad_RL': 2200,
            'TC_InAction': 0, 'ABS_InAction': 0, 'BrakeBias': 0.52,
            'BrakeTemp_FL': 450, 'BrakeTemp_FR': 455, 'BrakeTemp_RL': 420,
            'Fuel': 45.2, 'TurboBoost': 1.8, 'EngineTemp_Oil': 105,
            'CurrentMaxRpm': 12000, 'EngineBrake': 0,
            'KERS_Charge': 0.85, 'KERS_CurrentKJ': 340,
            'ERS_PowerLevel': 5, 'ERS_RecoveryLevel': 3, 'DRS_Enabled': 0
        }

        # Process features
        print("\nExtracting and normalizing features...")
        normalized_features = feature_extractor.process(mock_telemetry)

        # Perform inference
        print("\nPerforming MoE inference...")
        result = moe.predict(normalized_features)

        # Display results
        print("\n" + "="*60)
        print("INFERENCE RESULT")
        print("="*60)
        print(f"Anomaly Detected: {result['is_anomaly']}")
        print(f"Anomaly Type: {result['anomaly_type']}")
        print(f"Severity: {result['severity']}")
        print(f"Anomaly Probability: {result['anomaly_probability']:.3f}")
        print(f"Global Score: {result['global_score']:.3f}")
        print(f"Affected Component: {result['affected_component']}")

        print("\nExpert Scores:")
        for expert_name, score in result['expert_scores'].items():
            threshold = moe.thresholds[expert_name]
            print(
                f"  {expert_name:<20} Score: {score:>8.3f}  Threshold: {threshold:>8.3f}")

        print("\nExpert Weights (Attention):")
        for expert_name, weight in result['expert_weights'].items():
            bar = '█' * int(weight * 50)
            print(f"  {expert_name:<20} {weight:.3f} {bar}")

        # Statistics
        print("\n" + "="*60)
        print("STATISTICS")
        print("="*60)
        stats = moe.get_stats()
        for key, value in stats.items():
            print(f"{key}: {value}")

        print("\n✅ MoE inference test successful!")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
