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

# Configuration - Updated to use lap_1_data.csv
CSV_FILE = 'data/raw/LAPS_OUTPUT/lap_1_data.csv'      # Original lap data with all columns
KAFKA_TOPIC = 'f1-telemetry'                          # Specialized channel for F1 data only
KAFKA_SERVERS = 'localhost:9092'                      # Address of our Kafka broker
DEMO_ROWS = 814                                        # Process all available rows (full lap)
STREAM_DELAY = 0.1 


def load_and_examine_data():
    """
    Task 2.1: Load CSV and examine telemetry structure
    Updated for lap_1_data.csv with original column names
    """
    print("📊 Task 2.1: Loading lap 1 telemetry data...")

    try:
        # Load lap 1 telemetry CSV file
        df = pd.read_csv(CSV_FILE)

        # Display structure information for verification
        print("Available columns:")
        print(df.columns.tolist())
        print(f"\nTotal rows: {len(df)}")
        print("\nFirst 5 rows:")
        print(df.head())

        # Field mapping for lap_1_data.csv (original column names)
        selected_fields = [
            'Distance', 'Timestamp', 'Speed_kmh', 'RPM', 'Throttle', 'Brake', 'Steering', 'Gear',
            'CompletedLaps', 'iCurrentTime_ms', 'CurrentLapTime_str', 'iLastTime_ms', 'iBestTime_ms',
            'LapNumberTotal', 'CurrentSectorIndex', 'LastSectorTime_ms', 'IsInPit', 'IsInPitLane',
            'TyreCompound', 'X', 'Y', 'Z', 'Flag', 'SurfaceGrip'
        ]

        # Verify all required fields exist in CSV
        available_fields = [field for field in selected_fields if field in df.columns]
        missing_fields = [field for field in selected_fields if field not in df.columns]
        
        if missing_fields:
            print(f"⚠️ Missing fields: {missing_fields}")
            print(f"✅ Available fields: {available_fields}")
            # Use only available fields
            selected_fields = available_fields
        else:
            print("✅ All required fields are available")

        # Show sample of selected data for validation
        print(f"\nSelected fields sample:")
        print(df[selected_fields].head())

        return df, selected_fields

    except FileNotFoundError:
        print(f"❌ CSV file not found: {CSV_FILE}")
        print("Available options:")
        print("  - data/raw/LAPS_OUTPUT/lap_1_data.csv")
        print("  - data/raw/LAPS_OUTPUT/lap_2_telemetry_2025-09-13_16-18-26.csv")
        return None, None
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return None, None


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
    Updated to use lap_1_data.csv with original field names
    """
    print(f"🚀 Task 2.3: Starting telemetry streaming...")

    # Use all rows or limit to DEMO_ROWS
    demo_data = df[selected_fields].head(DEMO_ROWS)

    print(f"Streaming {len(demo_data)} telemetry records...")

    for index, row in demo_data.iterrows():
        # Convert CSV row to structured JSON message
        # Using original column names from lap_1_data.csv
        telemetry_data = {
            # Core telemetry fields (original names)
            'distance': float(row.get('Distance', 0)),            # Track distance
            'timestamp': int(row.get('Timestamp', 0)),            # Unix timestamp
            'speed_kmh': float(row.get('Speed_kmh', 0)),          # Speed in km/h
            'rpm': int(row.get('RPM', 0)),                        # Engine RPM
            'throttle': float(row.get('Throttle', 0)),            # Throttle input (0.0-1.0)
            'brake': float(row.get('Brake', 0)),                  # Brake input (0.0-1.0)
            'steering': float(row.get('Steering', 0)),            # Steering input
            'gear': int(row.get('Gear', 0)),                      # Current gear
            
            # Lap and timing information
            'completed_laps': int(row.get('CompletedLaps', 0)),
            'current_time_ms': int(row.get('iCurrentTime_ms', 0)),
            'current_lap_time': str(row.get('CurrentLapTime_str', '0:00.000')),
            'last_time_ms': int(row.get('iLastTime_ms', 0)),
            'best_time_ms': int(row.get('iBestTime_ms', 0)),
            'lap_number_total': int(row.get('LapNumberTotal', 0)),
            'current_sector_index': int(row.get('CurrentSectorIndex', 0)),
            'last_sector_time_ms': int(row.get('LastSectorTime_ms', 0)),
            
            # Position and environment
            'car_x': float(row.get('X', 0)),                      # X position
            'car_y': float(row.get('Y', 0)),                      # Y position  
            'car_z': float(row.get('Z', 0)),                      # Z position
            'is_in_pit': bool(row.get('IsInPit', False)),
            'is_in_pit_lane': bool(row.get('IsInPitLane', False)),
            'tyre_compound': str(row.get('TyreCompound', 'Unknown')),
            'flag': int(row.get('Flag', 0)),
            'surface_grip': float(row.get('SurfaceGrip', 1.0)),
            
            # Additional timestamp for compatibility
            'kafka_timestamp': int(time.time() * 1000)           # Current timestamp
        }

        # CORE KAFKA OPERATION: Send message to broker
        producer.produce(
            KAFKA_TOPIC,                           # Destination topic
            value=json.dumps(telemetry_data).encode('utf-8'),  # JSON message
            callback=delivery_callback             # Delivery confirmation
        )

        # Show real-time progress with key metrics
        print(f"📡 {index+1}/{DEMO_ROWS} - Speed: {telemetry_data['speed_kmh']:.1f}km/h, "
              f"RPM: {telemetry_data['rpm']}, Gear: {telemetry_data['gear']}, "
              f"Steering: {telemetry_data['steering']:.3f}, "
              f"Distance: {telemetry_data['distance']:.1f}m, "
              f"Lap: {telemetry_data['completed_laps']}")

        # Poll for delivery reports (async confirmation handling)
        producer.poll(0)

        # Simulate real-time streaming frequency
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
    - Task 2.1: Loads and verifies CSV telemetry data from lap_1_data.csv
    - Task 2.2: Creates topic and configures producer
    - Task 2.3: Streams all 814 messages with complete telemetry data

    Each 📡 line shows a message sent to broker with real F1 metrics including:
    Speed, RPM, Gear, Steering, Distance, and Lap information from original AC data.
    This provides comprehensive telemetry for AI analysis and training.
    """
    print("=" * 60)
    print("F1 AC DIGITAL TWIN - KAFKA TELEMETRY PRODUCER")
    print("HANDS-ON 1: Tasks 2.1, 2.2, 2.3 (Using lap_1_data.csv)")
    print("=" * 60)

    try:
        # Task 2.1: Load and examine data
        # Prepares real F1 telemetry from Assetto Corsa lap_1_data.csv
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
        # Demonstrates Producer→Broker→Topic flow with complete F1 data
        stream_telemetry_data(df, selected_fields, producer)

        print("\n" + "=" * 60)
        print("🏁 PRODUCER TASKS COMPLETED SUCCESSFULLY")
        print("🔍 CHECK CONFLUENT CONTROL CENTER: http://localhost:9021")
        print("📍 Navigate to: Topics → f1-telemetry → Messages")
        print(f"📊 Complete lap data streamed: {DEMO_ROWS} telemetry records")
        print("📈 Data includes: Speed, RPM, Position, Timing, and Environmental data")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure:")
        print("- CSV file 'lap_1_data.csv' exists in data/raw/LAPS_OUTPUT/")
        print("- Kafka is running (docker-compose up)")
        print("- Required packages installed")


if __name__ == "__main__":
    main()