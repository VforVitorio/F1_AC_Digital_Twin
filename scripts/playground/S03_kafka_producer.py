"""
F1 AC Digital Twin - Kafka Telemetry Producer
S03 Digital Twin University Subject Source File
HANDS-ON 1: Tasks 2.1, 2.2, 2.3
Streams telemetry data from CSV to Kafka topic
"""

import pandas as pd
import json
import time
from pathlib import Path
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

# Configuration
# Resolve repository root two levels up from this file (scripts/playground/ -> scripts -> repo root)
ROOT = Path(__file__).resolve().parents[2]
# Build CSV path in a cross-platform way
CSV_FILE = ROOT / 'data' / 'raw' / 'LAPS_OUTPUT' / \
    'lap_2_telemetry_2025-09-13_16-18-26.csv'
KAFKA_TOPIC = 'f1-telemetry'
KAFKA_SERVERS = 'localhost:9092'
DEMO_ROWS = 50  # Only first 50 rows for demo
STREAM_DELAY = 0.1  # 10 messages per second


def load_and_examine_data():
    """Task 2.1: Load CSV and examine telemetry structure"""
    print("📊 Task 2.1: Loading telemetry data...")

    # Load telemetry CSV file
    if not CSV_FILE.exists():
        print(f"❌ CSV no encontrado en: {CSV_FILE}")
        return None, None

    df = pd.read_csv(CSV_FILE)

    # Display structure information
    print("Available columns:")
    print(df.columns.tolist())
    print(f"\nTotal rows: {len(df)}")
    print("\nFirst 5 rows:")
    print(df.head())

    # Select relevant fields for streaming
    selected_fields = ['Speed_kmh', 'RPM',
                       'Throttle', 'Brake', 'Gear', 'CompletedLaps']

    # Verify all fields exist
    missing_fields = [
        field for field in selected_fields if field not in df.columns]
    if missing_fields:
        print(f"⚠️ Missing fields: {missing_fields}")
        return None, None
    else:
        print("✅ All required fields are available")

    # Show sample of selected data
    print(f"\nSelected fields sample:")
    print(df[selected_fields].head())

    return df, selected_fields


def setup_kafka_topic():
    """Task 2.2: Create Kafka topic if doesn't exist"""
    print("🔧 Task 2.2: Setting up Kafka topic...")

    admin_client = AdminClient({'bootstrap.servers': KAFKA_SERVERS})

    try:
        topic = NewTopic(KAFKA_TOPIC, num_partitions=1, replication_factor=1)
        admin_client.create_topics([topic])
        print(f"✅ Topic '{KAFKA_TOPIC}' created successfully")
    except Exception as e:
        print(f"Topic already exists or error: {e}")


def configure_producer():
    """Task 2.2: Configure Kafka producer"""
    print("⚙️ Configuring Kafka producer...")

    config = {
        'bootstrap.servers': KAFKA_SERVERS,
        'client.id': 'f1-telemetry-producer'
    }

    producer = Producer(config)
    print("✅ Producer configured successfully")
    return producer


def stream_telemetry_data(df, selected_fields, producer):
    """Task 2.3: Stream telemetry data to Kafka"""
    print(f"🚀 Task 2.3: Starting telemetry streaming...")

    # Use only first rows for demo
    demo_data = df[selected_fields].head(DEMO_ROWS)

    print(f"Streaming {len(demo_data)} telemetry records...")

    for index, row in demo_data.iterrows():
        # Convert row to dictionary
        telemetry_data = {
            'speed': float(row['Speed_kmh']),
            'rpm': int(row['RPM']),
            'throttle': float(row['Throttle']),
            'brake': float(row['Brake']),
            'gear': int(row['Gear']),
            'lap': int(row['CompletedLaps'])
        }

        # Send to Kafka (confluent-kafka format)
        producer.produce(
            KAFKA_TOPIC,
            value=json.dumps(telemetry_data).encode('utf-8'),
            callback=delivery_callback
        )

        # Show progress
        print(f"📡 {index+1}/{DEMO_ROWS} - Speed: {telemetry_data['speed']:.1f}km/h, "
              f"RPM: {telemetry_data['rpm']}, Gear: {telemetry_data['gear']}, "
              f"Lap: {telemetry_data['lap']}")

        # Poll for delivery reports
        producer.poll(0)

        # Simulate real-time streaming
        time.sleep(STREAM_DELAY)

    # Ensure all messages are delivered
    producer.flush()
    print("✅ Telemetry streaming completed successfully")


def delivery_callback(err, msg):
    """Callback for message delivery confirmation"""
    if err is not None:
        print(f"❌ Message delivery failed: {err}")
    # Uncomment for verbose delivery confirmation:
    # else:
    #     print(f"✅ Message delivered to {msg.topic()} [{msg.partition()}]")


def main():
    """Main execution function"""
    print("=" * 60)
    print("F1 AC DIGITAL TWIN - KAFKA TELEMETRY PRODUCER")
    print("HANDS-ON 1: Tasks 2.1, 2.2, 2.3")
    print("=" * 60)

    try:
        # Task 2.1: Load and examine data
        df, selected_fields = load_and_examine_data()
        if df is None:
            print("❌ Failed to load data. Check CSV file path.")
            return

        print("\n" + "-" * 40)

        # Task 2.2: Setup Kafka
        setup_kafka_topic()
        producer = configure_producer()

        print("\n" + "-" * 40)

        # Task 2.3: Stream data
        stream_telemetry_data(df, selected_fields, producer)

        print("\n" + "=" * 60)
        print("🏁 PRODUCER TASKS COMPLETED SUCCESSFULLY")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure:")
        print("- CSV file 'lap_2_telemetry.csv' exists in current directory")
        print("- Kafka is running (docker-compose up)")
        print("- Required packages installed: pip install confluent-kafka pandas")


if __name__ == "__main__":
    main()
