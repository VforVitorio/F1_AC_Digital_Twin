"""
F1 AC Digital Twin - Kafka Telemetry Producer
HANDS-ON 1: Tasks 2.1, 2.2, 2.3
Streams telemetry data from CSV to Kafka topic

ARCHITECTURE EXPLANATION:
- BROKER: Kafka server running on localhost:9092 (intermediary that stores/distributes messages)
- PRODUCER: This Python script (reads data and sends to broker)  
- TOPIC: 'f1-telemetry' channel that organizes messages
- CONSUMER: Future scripts that will read these messages for analysis
"""

import pandas as pd
import json
import time
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

# Configuration - All constants centralized for easy modification
CSV_FILE = 'lap_2_telemetry.csv'      # Real telemetry data from Assetto Corsa
KAFKA_TOPIC = 'f1-telemetry'          # Specialized channel for F1 data only
KAFKA_SERVERS = 'localhost:9092'      # Address of our Kafka broker
DEMO_ROWS = 50                        # Only first 50 rows for demo
# 10 messages per second (simulates 10Hz real telemetry)
STREAM_DELAY = 0.1


def load_and_examine_data():
    """
    Task 2.1: Load CSV and examine telemetry structure

    This function prepares real F1 telemetry data instead of simulated sensors.
    Uses real metrics captured from Assetto Corsa: speed, RPM, throttle, brake, 
    gear and lap number. This gives us a realistic dataset for streaming.
    """
    print("📊 Task 2.1: Loading telemetry data...")

    # Load telemetry CSV file - Real data from F1 AC Digital Twin project
    df = pd.read_csv(CSV_FILE)

    # Display structure information for verification
    print("Available columns:")
    print(df.columns.tolist())
    print(f"\nTotal rows: {len(df)}")
    print("\nFirst 5 rows:")
    print(df.head())

    # Select relevant fields for streaming - Core F1 metrics only
    selected_fields = ['Speed_kmh', 'RPM',
                       'Throttle', 'Brake', 'Gear', 'CompletedLaps']

    # Verify all required fields exist in CSV
    missing_fields = [
        field for field in selected_fields if field not in df.columns]
    if missing_fields:
        print(f"⚠️ Missing fields: {missing_fields}")
        return None, None
    else:
        print("✅ All required fields are available")

    # Show sample of selected data for validation
    print(f"\nSelected fields sample:")
    print(df[selected_fields].head())

    return df, selected_fields


def setup_kafka_topic():
    """
    Task 2.2: Create Kafka topic if doesn't exist

    The TOPIC acts as a specialized channel (like TV channel for F1 only).
    Multiple producers can send to it, multiple consumers can read from it.
    This decoupled architecture enables scalability and fault tolerance.
    """
    print("🔧 Task 2.2: Setting up Kafka topic...")

    # Create admin client to manage Kafka infrastructure
    admin_client = AdminClient({'bootstrap.servers': KAFKA_SERVERS})

    try:
        # Create topic with 1 partition for simplicity (production would use multiple)
        topic = NewTopic(KAFKA_TOPIC, num_partitions=1, replication_factor=1)
        admin_client.create_topics([topic])
        print(f"✅ Topic '{KAFKA_TOPIC}' created successfully")
    except Exception as e:
        print(f"Topic already exists or error: {e}")


def configure_producer():
    """
    Task 2.2: Configure Kafka producer

    PRODUCER establishes connection with BROKER (localhost:9092).
    bootstrap.servers = broker address (where to send messages)
    client.id = unique identifier for this producer (helps with monitoring)
    """
    print("⚙️ Configuring Kafka producer...")

    # Producer configuration - connects to broker and identifies itself
    config = {
        'bootstrap.servers': KAFKA_SERVERS,  # Broker address
        'client.id': 'f1-telemetry-producer'  # Unique identifier for monitoring
    }

    producer = Producer(config)
    print("✅ Producer configured successfully")
    return producer


def stream_telemetry_data(df, selected_fields, producer):
    """
    Task 2.3: Stream telemetry data to Kafka

    This demonstrates the core Producer → Broker → Topic flow:
    1. Convert CSV row to JSON dictionary (structured telemetry message)
    2. Send to Kafka topic using producer.produce()  
    3. Broker stores message in 'f1-telemetry' topic
    4. Messages wait there until consumers read them

    Each message represents one telemetry snapshot with F1 metrics.
    """
    print(f"🚀 Task 2.3: Starting telemetry streaming...")

    # Use only first rows for demo - simulates real-time data capture
    demo_data = df[selected_fields].head(DEMO_ROWS)

    print(f"Streaming {len(demo_data)} telemetry records...")

    for index, row in demo_data.iterrows():
        # Convert CSV row to structured JSON message
        # This mimics real telemetry: speed, RPM, driver inputs (throttle/brake/gear), lap info
        telemetry_data = {
            'speed': float(row['Speed_kmh']),      # Vehicle speed in km/h
            'rpm': int(row['RPM']),                # Engine RPM
            'throttle': float(row['Throttle']),    # Throttle input (0.0-1.0)
            'brake': float(row['Brake']),          # Brake input (0.0-1.0)
            'gear': int(row['Gear']),              # Current gear
            'lap': int(row['CompletedLaps'])       # Lap number
        }

        # CORE KAFKA OPERATION: Send message to broker
        # - Topic: 'f1-telemetry' (destination channel)
        # - Value: JSON-serialized telemetry data
        # - Callback: Confirms successful delivery
        producer.produce(
            KAFKA_TOPIC,                           # Destination topic
            value=json.dumps(telemetry_data).encode('utf-8'),  # JSON message
            callback=delivery_callback             # Delivery confirmation
        )

        # Show real-time progress - demonstrates streaming nature
        print(f"📡 {index+1}/{DEMO_ROWS} - Speed: {telemetry_data['speed']:.1f}km/h, "
              f"RPM: {telemetry_data['rpm']}, Gear: {telemetry_data['gear']}, "
              f"Lap: {telemetry_data['lap']}")

        # Poll for delivery reports (async confirmation handling)
        producer.poll(0)

        # Simulate real-time streaming frequency (10Hz = 10 messages/second)
        # Real F1 telemetry often runs at 50-100Hz, we use 10Hz for demo clarity
        time.sleep(STREAM_DELAY)

    # Ensure all messages are delivered before finishing
    producer.flush()
    print("✅ Telemetry streaming completed successfully")


def delivery_callback(err, msg):
    """
    Callback for message delivery confirmation

    This confirms each message successfully reached the broker.
    In production, you'd log failures for retry logic.
    """
    if err is not None:
        print(f"❌ Message delivery failed: {err}")
    # Uncomment for verbose delivery confirmation:
    # else:
    #     print(f"✅ Message delivered to {msg.topic()} [{msg.partition()}]")


def main():
    """
    Main execution function - Demonstrates complete Producer workflow

    TERMINAL OUTPUT EXPLANATION:
    - Task 2.1: Loads and verifies CSV telemetry data  
    - Task 2.2: Creates topic and configures producer
    - Task 2.3: Streams 50 messages at 10Hz simulating real telemetry

    Each 📡 line shows a message sent to broker with real F1 metrics:
    Speed progression (89km/h → 245km/h) demonstrates real AC data streaming.
    This establishes the foundation for future AI analysis and training.
    """
    print("=" * 60)
    print("F1 AC DIGITAL TWIN - KAFKA TELEMETRY PRODUCER")
    print("HANDS-ON 1: Tasks 2.1, 2.2, 2.3")
    print("=" * 60)

    try:
        # Task 2.1: Load and examine data
        # Prepares real F1 telemetry from Assetto Corsa for streaming
        df, selected_fields = load_and_examine_data()
        if df is None:
            print("❌ Failed to load data. Check CSV file path.")
            return

        print("\n" + "-" * 40)

        # Task 2.2: Setup Kafka infrastructure
        # Creates topic and producer - establishes Producer→Broker connection
        setup_kafka_topic()
        producer = configure_producer()

        print("\n" + "-" * 40)

        # Task 2.3: Stream data
        # Demonstrates Producer→Broker→Topic flow with real F1 data
        stream_telemetry_data(df, selected_fields, producer)

        print("\n" + "=" * 60)
        print("🏁 PRODUCER TASKS COMPLETED SUCCESSFULLY")
        print("🔍 CHECK CONFLUENT CONTROL CENTER: http://localhost:9021")
        print("📍 Navigate to: Topics → f1-telemetry → Messages")
        print("📊 You should see 50 JSON telemetry messages")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure:")
        print("- CSV file 'lap_2_telemetry.csv' exists in current directory")
        print("- Kafka is running (docker-compose up)")
        print("- Required packages installed: pip install confluent-kafka pandas")


if __name__ == "__main__":
    main()
