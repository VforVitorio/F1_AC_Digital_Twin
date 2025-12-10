"""
Offline Testing Script for MoE Anomaly Detection Pipeline

This script tests the complete pipeline:
1. Load historical telemetry from CSV
2. Extract and normalize features
3. Run MoE inference
4. Save results and generate visualizations

Usage:
    python test_moe_pipeline.py [--input CSV_PATH] [--limit N_SAMPLES] [--visualize]

Author: F1 Digital Twin Team
"""

import sys
import argparse
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import json
import warnings

# Suppress sklearn warnings
warnings.filterwarnings('ignore', category=UserWarning, module='sklearn')

# Add src to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))


class MoEPipelineTester:
    """
    Offline tester for the MoE anomaly detection pipeline.
    """

    def __init__(self, scalers_dir: str, models_dir: str):
        """
        Initialize the pipeline tester.

        Args:
            scalers_dir: Path to scalers directory
            models_dir: Path to models directory
        """
        from src.feature_processor import RealTimeFeatureExtractor, validate_telemetry
        from src.moe_inference import MoEInference

        print("="*70)
        print("INITIALIZING MoE PIPELINE TESTER")
        print("="*70)

        self.feature_extractor = RealTimeFeatureExtractor(scalers_dir)
        self.moe = MoEInference(models_dir)
        self.validate_telemetry = validate_telemetry

        print("[OK] Pipeline initialized successfully\n")

    def load_telemetry(self, csv_path: str, limit: int = None) -> pd.DataFrame:
        """
        Load telemetry data from CSV.

        Args:
            csv_path: Path to telemetry CSV file
            limit: Maximum number of samples to load (None for all)

        Returns:
            DataFrame with telemetry data
        """
        print(f"Loading telemetry from: {csv_path}")

        if limit:
            df = pd.read_csv(csv_path, nrows=limit)
        else:
            df = pd.read_csv(csv_path)

        print(f"✅ Loaded {len(df)} samples, {len(df.columns)} variables\n")
        return df

    def process_telemetry(
        self,
        telemetry_df: pd.DataFrame,
        verbose: bool = True
    ) -> pd.DataFrame:
        """
        Process telemetry through the complete pipeline.

        Args:
            telemetry_df: DataFrame with raw telemetry
            verbose: Print progress

        Returns:
            DataFrame with results (original data + anomaly predictions)
        """
        print("="*70)
        print("PROCESSING TELEMETRY THROUGH MoE PIPELINE")
        print("="*70)

        results = []
        n_samples = len(telemetry_df)
        update_interval = max(1, n_samples // 20)  # Update every 5%

        for idx, row in telemetry_df.iterrows():
            # Convert row to dictionary
            telemetry = row.to_dict()

            try:
                # 1. Validate telemetry
                is_valid, missing = self.validate_telemetry(telemetry)

                if not is_valid:
                    print(
                        f"⚠️  Sample {idx}: Missing features: {missing[:5]}...")
                    continue

                # 2. Extract and normalize features
                normalized_features = self.feature_extractor.process(telemetry)

                # 3. MoE inference
                prediction = self.moe.predict(normalized_features)

                # 4. Store result
                result = {
                    'sample_idx': idx,
                    'is_anomaly': prediction['is_anomaly'],
                    'anomaly_type': prediction['anomaly_type'],
                    'severity': prediction['severity'],
                    'anomaly_probability': prediction['anomaly_probability'],
                    'global_score': prediction['global_score'],
                    'expert2_score': prediction['expert_scores']['expert2_dynamics'],
                    'expert3_score': prediction['expert_scores']['expert3_control'],
                    'expert4_score': prediction['expert_scores']['expert4_power'],
                    'expert2_weight': prediction['expert_weights']['expert2_dynamics'],
                    'expert3_weight': prediction['expert_weights']['expert3_control'],
                    'expert4_weight': prediction['expert_weights']['expert4_power'],
                    'affected_component': prediction['affected_component']
                }

                results.append(result)

                # Progress update
                if verbose and (idx % update_interval == 0 or idx == n_samples - 1):
                    progress = (idx + 1) / n_samples * 100
                    anomaly_count = sum(r['is_anomaly'] for r in results)
                    anomaly_rate = anomaly_count / \
                        len(results) * 100 if results else 0
                    print(f"Progress: {progress:>5.1f}% | "
                          f"Samples: {len(results):>6} | "
                          f"Anomalies: {anomaly_count:>5} ({anomaly_rate:.1f}%)")

            except Exception as e:
                print(f"❌ Error processing sample {idx}: {e}")
                continue

        # Convert to DataFrame
        results_df = pd.DataFrame(results)

        print(f"\n✅ Processing complete: {len(results_df)} samples processed")
        print(f"   Anomalies detected: {results_df['is_anomaly'].sum()} "
              f"({results_df['is_anomaly'].mean()*100:.2f}%)\n")

        return results_df

    def save_results(self, results_df: pd.DataFrame, output_path: str):
        """
        Save results to CSV.

        Args:
            results_df: DataFrame with results
            output_path: Path to output CSV file
        """
        results_df.to_csv(output_path, index=False)
        print(f"✅ Results saved to: {output_path}\n")

    def generate_visualizations(self, results_df: pd.DataFrame, output_dir: str):
        """
        Generate visualization plots.

        Args:
            results_df: DataFrame with results
            output_dir: Directory to save plots
        """
        print("="*70)
        print("GENERATING VISUALIZATIONS")
        print("="*70)

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Set style
        sns.set_style("whitegrid")

        # 1. Anomaly timeline
        fig, ax = plt.subplots(figsize=(16, 4))
        ax.scatter(results_df['sample_idx'], results_df['global_score'],
                   c=results_df['is_anomaly'], cmap='RdYlGn_r',
                   alpha=0.6, s=10, edgecolors='none')
        ax.set_xlabel('Sample Index', fontsize=12)
        ax.set_ylabel('Global Anomaly Score', fontsize=12)
        ax.set_title('Anomaly Score Timeline', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / 'anomaly_timeline.png',
                    dpi=150, bbox_inches='tight')
        plt.close()
        print("✅ Generated: anomaly_timeline.png")

        # 2. Expert scores distribution
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        if not isinstance(axes, np.ndarray):
            axes = [axes]

        # Mapping from expert index to threshold key
        expert_type_map = {
            'expert2': 'dynamics',
            'expert3': 'control',
            'expert4': 'power'
        }

        for idx, expert in enumerate(['expert2', 'expert3', 'expert4']):
            ax = axes[idx]
            score_col = f'{expert}_score'

            # Plot distribution
            results_df[score_col].hist(
                bins=50, alpha=0.7, ax=ax, edgecolor='black')

            # Add threshold line
            expert_type = expert_type_map[expert]
            threshold = self.moe.thresholds[f'{expert}_{expert_type}']

            ax.axvline(threshold, color='r', linestyle='--', linewidth=2,
                       label=f'Threshold: {threshold:.2f}')

            ax.set_xlabel('Anomaly Score', fontsize=11)
            ax.set_ylabel('Frequency', fontsize=11)
            ax.set_title(f'{expert.replace("expert", "Expert ")} Score Distribution',
                         fontsize=12, fontweight='bold')
            ax.legend()
            ax.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()
        plt.savefig(output_dir / 'expert_scores.png',
                    dpi=150, bbox_inches='tight')
        plt.close()
        print("✅ Generated: expert_scores.png")

        # 3. Expert weights (attention)
        fig, ax = plt.subplots(figsize=(12, 6))

        weight_cols = ['expert2_weight', 'expert3_weight', 'expert4_weight']
        avg_weights = results_df[weight_cols].mean()

        colors = ['#ff7f0e', '#2ca02c', '#d62728']
        bars = ax.bar(range(3), avg_weights, color=colors,
                      edgecolor='black', linewidth=1.5)

        ax.set_xticks(range(3))
        ax.set_xticklabels(
            ['Dynamics', 'Control', 'Power'], fontsize=12)
        ax.set_ylabel('Average Weight', fontsize=12)
        ax.set_title('Average Expert Weights (Attention)',
                     fontsize=14, fontweight='bold')
        ax.set_ylim(0, max(avg_weights) * 1.2)
        ax.grid(True, alpha=0.3, axis='y')

        # Add value labels on bars
        for bar, weight in zip(bars, avg_weights):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                    f'{weight:.3f}', ha='center', va='bottom', fontsize=11)

        plt.tight_layout()
        plt.savefig(output_dir / 'expert_weights.png',
                    dpi=150, bbox_inches='tight')
        plt.close()
        print("✅ Generated: expert_weights.png")

        # 4. Anomaly type distribution
        if results_df['is_anomaly'].sum() > 0:
            anomalies = results_df[results_df['is_anomaly']]

            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

            # Anomaly type
            anomaly_counts = anomalies['anomaly_type'].value_counts()
            ax1.bar(range(len(anomaly_counts)), anomaly_counts.values, color='#d62728',
                    edgecolor='black', linewidth=1.5)
            ax1.set_xticks(range(len(anomaly_counts)))
            ax1.set_xticklabels(anomaly_counts.index,
                                rotation=45, ha='right', fontsize=10)
            ax1.set_ylabel('Count', fontsize=12)
            ax1.set_title('Anomaly Types', fontsize=13, fontweight='bold')
            ax1.grid(True, alpha=0.3, axis='y')

            # Severity
            severity_counts = anomalies['severity'].value_counts()
            severity_order = ['low', 'medium', 'high']
            severity_counts = severity_counts.reindex(
                severity_order, fill_value=0)

            colors_severity = ['#2ca02c', '#ff7f0e', '#d62728']
            ax2.bar(range(len(severity_counts)), severity_counts.values,
                    color=colors_severity, edgecolor='black', linewidth=1.5)
            ax2.set_xticks(range(len(severity_counts)))
            ax2.set_xticklabels(severity_order, fontsize=11)
            ax2.set_ylabel('Count', fontsize=12)
            ax2.set_title('Anomaly Severity', fontsize=13, fontweight='bold')
            ax2.grid(True, alpha=0.3, axis='y')

            plt.tight_layout()
            plt.savefig(output_dir / 'anomaly_analysis.png',
                        dpi=150, bbox_inches='tight')
            plt.close()
            print("✅ Generated: anomaly_analysis.png")

        print(f"\n✅ All visualizations saved to: {output_dir}\n")

    def generate_report(self, results_df: pd.DataFrame) -> dict:
        """
        Generate summary report.

        Args:
            results_df: DataFrame with results

        Returns:
            Dictionary with summary statistics
        """
        report = {
            'total_samples': len(results_df),
            'anomalies_detected': int(results_df['is_anomaly'].sum()),
            'anomaly_rate': float(results_df['is_anomaly'].mean()),
            'anomaly_types': results_df[results_df['is_anomaly']]['anomaly_type'].value_counts().to_dict(),
            'severity_distribution': results_df[results_df['is_anomaly']]['severity'].value_counts().to_dict(),
            'average_global_score': float(results_df['global_score'].mean()),
            'average_expert_weights': {
                'expert2_dynamics': float(results_df['expert2_weight'].mean()),
                'expert3_control': float(results_df['expert3_weight'].mean()),
                'expert4_power': float(results_df['expert4_weight'].mean())
            },
            'feature_extractor_stats': self.feature_extractor.get_stats(),
            'moe_stats': self.moe.get_stats()
        }

        return report


def main():
    """Main testing function."""
    parser = argparse.ArgumentParser(
        description='Test MoE anomaly detection pipeline')
    parser.add_argument('--input', type=str, help='Path to input CSV file')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of samples')
    parser.add_argument('--visualize', action='store_true',
                        help='Generate visualizations')
    parser.add_argument('--output-dir', type=str,
                        default=None, help='Output directory')

    args = parser.parse_args()

    # Paths
    if args.input:
        input_csv = Path(args.input)
    else:
        # Use latest telemetry file
        data_dir = ROOT / 'data' / 'raw'
        csv_files = list(data_dir.glob('telemetry_*.csv'))
        if not csv_files:
            print("❌ No telemetry files found in data/raw/")
            sys.exit(1)
        input_csv = max(csv_files, key=lambda p: p.stat().st_mtime)

    scalers_dir = ROOT / 'data' / 'processed' / 'MoE-anomaly' / 'scalers'
    models_dir = ROOT / 'models' / 'anomaly-detection'

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = ROOT / 'data' / 'testing'
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Initialize tester
        tester = MoEPipelineTester(scalers_dir, models_dir)

        # Load telemetry
        telemetry_df = tester.load_telemetry(input_csv, limit=args.limit)

        # Process
        results_df = tester.process_telemetry(telemetry_df, verbose=True)

        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_csv = output_dir / f'anomaly_results_{timestamp}.csv'
        tester.save_results(results_df, output_csv)

        # Generate report
        report = tester.generate_report(results_df)

        print("="*70)
        print("SUMMARY REPORT")
        print("="*70)
        print(f"Total Samples: {report['total_samples']}")
        print(
            f"Anomalies Detected: {report['anomalies_detected']} ({report['anomaly_rate']*100:.2f}%)")
        print(f"\nAnomaly Types:")
        for atype, count in report['anomaly_types'].items():
            print(f"  {atype}: {count}")
        print(f"\nSeverity Distribution:")
        for severity, count in report['severity_distribution'].items():
            print(f"  {severity}: {count}")
        print(f"\nAverage Expert Weights:")
        for expert, weight in report['average_expert_weights'].items():
            print(f"  {expert}: {weight:.3f}")

        # Save report
        report_path = output_dir / f'report_{timestamp}.json'
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n✅ Report saved to: {report_path}")

        # Generate visualizations
        if args.visualize:
            viz_dir = output_dir / f'visualizations_{timestamp}'
            tester.generate_visualizations(results_df, viz_dir)

        print("\n" + "="*70)
        print("✅ PIPELINE TEST COMPLETE")
        print("="*70)

    except Exception as e:
        print(f"\n❌ Pipeline test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
