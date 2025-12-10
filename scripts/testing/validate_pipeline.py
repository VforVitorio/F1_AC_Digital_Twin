"""
End-to-End Pipeline Validation Script

This script validates the complete anomaly detection pipeline:
1. Test feature extraction with sample data
2. Test MoE model loading and inference
3. Test Kafka connectivity
4. Test InfluxDB connectivity
5. Run mini end-to-end test with sample data

Usage:
    python validate_pipeline.py [--full]

Author: F1 Digital Twin Team
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import logging

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PipelineValidator:
    """Validates all components of the anomaly detection pipeline."""

    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'tests': {},
            'overall_status': 'PENDING'
        }

    def run_all_tests(self, full_test: bool = False) -> dict:
        """
        Run all validation tests.

        Args:
            full_test: If True, runs Kafka/InfluxDB connectivity tests

        Returns:
            Test results dict
        """
        logger.info("="*70)
        logger.info("PIPELINE VALIDATION")
        logger.info("="*70)

        # Test 1: Model files exist
        self._test_model_files()

        # Test 2: Feature processor
        self._test_feature_processor()

        # Test 3: MoE inference
        self._test_moe_inference()

        # Test 4: Sample data processing
        self._test_sample_processing()

        if full_test:
            # Test 5: Kafka connectivity
            self._test_kafka()

            # Test 6: InfluxDB connectivity
            self._test_influxdb()

        # Overall status
        all_passed = all(
            t.get('status') == 'PASSED'
            for t in self.results['tests'].values()
        )
        self.results['overall_status'] = 'PASSED' if all_passed else 'FAILED'

        self._print_summary()
        return self.results

    def _test_model_files(self):
        """Test that all required model files exist."""
        test_name = 'model_files'
        logger.info(f"\n[TEST] {test_name}")
        logger.info("-"*50)

        models_dir = ROOT / 'models' / 'anomaly-detection'
        scalers_dir = ROOT / 'data' / 'processed' / 'MoE-anomaly' / 'scalers'

        required_files = [
            models_dir / 'moe_config.json',
            models_dir / 'gating_network.pkl',
            models_dir / 'gmm_expert1_tire.pkl',
            models_dir / 'gmm_expert2_dynamics.pkl',
            models_dir / 'gmm_expert3_control.pkl',
            models_dir / 'gmm_expert4_power.pkl',
            models_dir / 'gmm_expert1_tire_metadata.json',
            models_dir / 'gmm_expert2_dynamics_metadata.json',
            models_dir / 'gmm_expert3_control_metadata.json',
            models_dir / 'gmm_expert4_power_metadata.json',
        ]

        scaler_files = [
            scalers_dir / 'scaler_expert1_tire.pkl',
            scalers_dir / 'scaler_expert2_dynamics.pkl',
            scalers_dir / 'scaler_expert3_control.pkl',
            scalers_dir / 'scaler_expert4_power.pkl',
        ]

        missing_files = []

        for f in required_files + scaler_files:
            if f.exists():
                logger.info(f"  ✅ {f.name}")
            else:
                logger.error(f"  ❌ {f.name} - NOT FOUND")
                missing_files.append(str(f))

        self.results['tests'][test_name] = {
            'status': 'PASSED' if not missing_files else 'FAILED',
            'missing_files': missing_files,
            'total_files': len(required_files) + len(scaler_files),
            'found_files': len(required_files) + len(scaler_files) - len(missing_files)
        }

    def _test_feature_processor(self):
        """Test feature processor initialization."""
        test_name = 'feature_processor'
        logger.info(f"\n[TEST] {test_name}")
        logger.info("-"*50)

        try:
            from src.feature_processor import RealTimeFeatureExtractor

            scalers_dir = ROOT / 'data' / 'processed' / 'MoE-anomaly' / 'scalers'
            extractor = RealTimeFeatureExtractor(str(scalers_dir))

            logger.info(f"  ✅ Feature processor initialized")
            logger.info(f"  ✅ Loaded {len(extractor.scalers)} scalers")

            self.results['tests'][test_name] = {
                'status': 'PASSED',
                'n_scalers': len(extractor.scalers)
            }

        except Exception as e:
            logger.error(f"  ❌ Failed: {e}")
            self.results['tests'][test_name] = {
                'status': 'FAILED',
                'error': str(e)
            }

    def _test_moe_inference(self):
        """Test MoE model loading and inference."""
        test_name = 'moe_inference'
        logger.info(f"\n[TEST] {test_name}")
        logger.info("-"*50)

        try:
            from src.moe_inference import MoEInference

            models_dir = ROOT / 'models' / 'anomaly-detection'
            moe = MoEInference(str(models_dir))

            logger.info(f"  ✅ MoE model loaded")
            logger.info(f"  ✅ {len(moe.expert_names)} experts loaded")
            logger.info(
                f"  ✅ Gating strategy: {moe.config.get('gating_strategy', 'unknown')}")

            # Test with dummy normalized features (same shape as expected by experts)
            # Each expert expects normalized features array
            import numpy as np
            dummy_features = {
                'expert1_tire': np.zeros(20),      # 20 tire features
                'expert2_dynamics': np.zeros(15),  # 15 dynamics features
                'expert3_control': np.zeros(12),   # 12 control features
                'expert4_power': np.zeros(10)      # 10 power features
            }

            result = moe.predict(dummy_features)
            logger.info(f"  ✅ Inference test passed")
            logger.info(f"     Global score: {result['global_score']:.2f}")
            logger.info(f"     Is anomaly: {result['is_anomaly']}")

            self.results['tests'][test_name] = {
                'status': 'PASSED',
                'n_experts': len(moe.expert_names),
                'gating_strategy': moe.config.get('gating_strategy', 'unknown'),
                'test_result': result
            }

        except Exception as e:
            logger.error(f"  ❌ Failed: {e}")
            import traceback
            traceback.print_exc()
            self.results['tests'][test_name] = {
                'status': 'FAILED',
                'error': str(e)
            }

    def _test_sample_processing(self):
        """Test processing sample telemetry data."""
        test_name = 'sample_processing'
        logger.info(f"\n[TEST] {test_name}")
        logger.info("-"*50)

        try:
            # Load sample data
            data_path = ROOT / 'data' / 'processed' / 'merged_telemetry_cleaned.csv'
            if not data_path.exists():
                raise FileNotFoundError(f"Sample data not found: {data_path}")

            df = pd.read_csv(data_path, nrows=10)
            logger.info(f"  ✅ Loaded {len(df)} sample rows")

            # Process through pipeline
            from src.feature_processor import RealTimeFeatureExtractor
            from src.moe_inference import MoEInference

            scalers_dir = ROOT / 'data' / 'processed' / 'MoE-anomaly' / 'scalers'
            models_dir = ROOT / 'models' / 'anomaly-detection'

            extractor = RealTimeFeatureExtractor(str(scalers_dir))
            moe = MoEInference(str(models_dir))

            # Process first row
            row = df.iloc[0].to_dict()

            # Use process() which extracts and normalizes features
            normalized_features = extractor.process(row)

            # Run inference
            result = moe.predict(normalized_features)

            logger.info(f"  ✅ Sample row processed successfully")
            logger.info(f"     Global score: {result['global_score']:.2f}")
            logger.info(f"     Is anomaly: {result['is_anomaly']}")

            self.results['tests'][test_name] = {
                'status': 'PASSED',
                'sample_result': {
                    'is_anomaly': result['is_anomaly'],
                    'global_score': result['global_score'],
                    'anomaly_type': result.get('anomaly_type', 'none')
                }
            }

        except Exception as e:
            logger.error(f"  ❌ Failed: {e}")
            import traceback
            traceback.print_exc()
            self.results['tests'][test_name] = {
                'status': 'FAILED',
                'error': str(e)
            }

    def _test_kafka(self):
        """Test Kafka connectivity."""
        test_name = 'kafka_connectivity'
        logger.info(f"\n[TEST] {test_name}")
        logger.info("-"*50)

        try:
            from confluent_kafka import Producer, Consumer
            from config import KAFKA_SERVERS, KAFKA_TOPIC

            # Test producer
            producer = Producer({'bootstrap.servers': KAFKA_SERVERS})
            producer.poll(0)
            logger.info(f"  ✅ Kafka producer connected to {KAFKA_SERVERS}")

            # Test consumer (list topics)
            consumer = Consumer({
                'bootstrap.servers': KAFKA_SERVERS,
                'group.id': 'test-validator'
            })
            metadata = consumer.list_topics(timeout=5)
            topics = list(metadata.topics.keys())
            consumer.close()

            logger.info(f"  ✅ Found {len(topics)} topics")
            if KAFKA_TOPIC in topics:
                logger.info(f"  ✅ Topic '{KAFKA_TOPIC}' exists")
            else:
                logger.warning(
                    f"  ⚠️ Topic '{KAFKA_TOPIC}' not found (will be created on first message)")

            self.results['tests'][test_name] = {
                'status': 'PASSED',
                'kafka_servers': KAFKA_SERVERS,
                'topics': topics
            }

        except Exception as e:
            logger.error(f"  ❌ Failed: {e}")
            self.results['tests'][test_name] = {
                'status': 'FAILED',
                'error': str(e)
            }

    def _test_influxdb(self):
        """Test InfluxDB connectivity."""
        test_name = 'influxdb_connectivity'
        logger.info(f"\n[TEST] {test_name}")
        logger.info("-"*50)

        try:
            from influxdb_client import InfluxDBClient
            from config import INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET

            client = InfluxDBClient(
                url=INFLUX_URL,
                token=INFLUX_TOKEN,
                org=INFLUX_ORG
            )

            # Test health
            health = client.health()
            logger.info(f"  ✅ InfluxDB status: {health.status}")

            # List buckets
            buckets_api = client.buckets_api()
            buckets = buckets_api.find_buckets()
            bucket_names = [b.name for b in buckets.buckets]

            logger.info(f"  ✅ Found {len(bucket_names)} buckets")
            if INFLUX_BUCKET in bucket_names:
                logger.info(f"  ✅ Bucket '{INFLUX_BUCKET}' exists")
            else:
                logger.warning(f"  ⚠️ Bucket '{INFLUX_BUCKET}' not found")

            # Check anomaly bucket
            anomaly_bucket = 'f1-anomalies'
            if anomaly_bucket in bucket_names:
                logger.info(f"  ✅ Bucket '{anomaly_bucket}' exists")
            else:
                logger.warning(
                    f"  ⚠️ Bucket '{anomaly_bucket}' not found - needs to be created")

            client.close()

            self.results['tests'][test_name] = {
                'status': 'PASSED',
                'influx_url': INFLUX_URL,
                'buckets': bucket_names,
                'health': health.status
            }

        except Exception as e:
            logger.error(f"  ❌ Failed: {e}")
            self.results['tests'][test_name] = {
                'status': 'FAILED',
                'error': str(e)
            }

    def _print_summary(self):
        """Print test summary."""
        logger.info("\n" + "="*70)
        logger.info("TEST SUMMARY")
        logger.info("="*70)

        for name, result in self.results['tests'].items():
            status = result.get('status', 'UNKNOWN')
            icon = '✅' if status == 'PASSED' else '❌'
            logger.info(f"  {icon} {name}: {status}")

        logger.info("-"*70)
        overall = self.results['overall_status']
        icon = '✅' if overall == 'PASSED' else '❌'
        logger.info(f"  {icon} OVERALL: {overall}")
        logger.info("="*70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Validate anomaly detection pipeline'
    )
    parser.add_argument(
        '--full', '-f',
        action='store_true',
        help='Run full tests including Kafka/InfluxDB connectivity'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Output path for test results JSON'
    )

    args = parser.parse_args()

    validator = PipelineValidator()
    results = validator.run_all_tests(full_test=args.full)

    # Save results
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = ROOT / 'data' / 'testing' / 'validation_results.json'

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    logger.info(f"\n📁 Results saved to: {output_path}")

    # Exit code
    sys.exit(0 if results['overall_status'] == 'PASSED' else 1)


if __name__ == '__main__':
    main()
