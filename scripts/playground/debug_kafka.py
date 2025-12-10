"""
Debug script to check Kafka topic and consumer group status
"""
import sys
import json
from pathlib import Path
from confluent_kafka import Consumer, KafkaError
from confluent_kafka.admin import AdminClient

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config import KAFKA_SERVERS, KAFKA_TOPIC, KAFKA_CONSUMER_GROUP

def check_topic_messages():
    """Check if there are messages in the topic"""
    print("=" * 60)
    print("CHECKING KAFKA TOPIC MESSAGES")
    print("=" * 60)
    print(f"Topic: {KAFKA_TOPIC}")
    print(f"Kafka Servers: {KAFKA_SERVERS}\n")

    # Create a temporary consumer to read from beginning
    temp_consumer = Consumer({
        'bootstrap.servers': KAFKA_SERVERS,
        'group.id': 'debug-consumer-temp',
        'auto.offset.reset': 'earliest',  # Read from beginning
        'enable.auto.commit': False
    })

    temp_consumer.subscribe([KAFKA_TOPIC])

    print("📊 Reading last 5 messages from topic...\n")

    messages_read = 0
    max_messages = 5
    timeout_count = 0
    max_timeout = 10

    while messages_read < max_messages and timeout_count < max_timeout:
        msg = temp_consumer.poll(timeout=1.0)

        if msg is None:
            timeout_count += 1
            continue

        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                print("✅ Reached end of partition")
                break
            else:
                print(f"❌ Error: {msg.error()}")
                continue

        # Parse and display message
        try:
            data = json.loads(msg.value().decode('utf-8'))
            print(f"Message {messages_read + 1}:")
            print(f"  Speed: {data.get('speed_kmh', 0):.1f} km/h")
            print(f"  RPM: {data.get('rpm', 0)}")
            print(f"  Gear: {data.get('gear', 0)}")
            print(f"  Distance: {data.get('distance', 0):.1f} m")
            print(f"  Timestamp: {data.get('timestamp', 'N/A')}")
            print()
            messages_read += 1
        except Exception as e:
            print(f"⚠️  Error parsing message: {e}\n")

    temp_consumer.close()

    if messages_read == 0:
        print("❌ NO MESSAGES FOUND IN TOPIC!")
        print("   Make sure the producer is running and sending data.")
    else:
        print(f"✅ Found {messages_read} messages in topic")

    return messages_read > 0

def check_consumer_group():
    """Check consumer group offset status"""
    print("\n" + "=" * 60)
    print("CHECKING CONSUMER GROUP STATUS")
    print("=" * 60)
    print(f"Consumer Group: {KAFKA_CONSUMER_GROUP}\n")

    admin_client = AdminClient({'bootstrap.servers': KAFKA_SERVERS})

    # Create a consumer to check committed offsets
    consumer = Consumer({
        'bootstrap.servers': KAFKA_SERVERS,
        'group.id': KAFKA_CONSUMER_GROUP,
        'enable.auto.commit': False
    })

    # Get topic partitions
    metadata = admin_client.list_topics(timeout=5)
    if KAFKA_TOPIC not in metadata.topics:
        print(f"❌ Topic '{KAFKA_TOPIC}' does not exist!")
        return False

    topic_metadata = metadata.topics[KAFKA_TOPIC]
    print(f"Topic '{KAFKA_TOPIC}' info:")
    print(f"  Partitions: {len(topic_metadata.partitions)}\n")

    # Check committed offsets for each partition
    from confluent_kafka import TopicPartition

    for partition_id in topic_metadata.partitions:
        tp = TopicPartition(KAFKA_TOPIC, partition_id)

        # Get committed offset
        committed = consumer.committed([tp], timeout=5.0)

        # Get high water mark (latest offset)
        low, high = consumer.get_watermark_offsets(tp, timeout=5.0)

        print(f"Partition {partition_id}:")
        print(f"  Low offset: {low}")
        print(f"  High offset (latest): {high}")
        print(f"  Committed offset: {committed[0].offset if committed else 'None'}")

        if committed and committed[0].offset >= 0:
            lag = high - committed[0].offset
            print(f"  Lag: {lag} messages")
            if lag > 0:
                print(f"  ⚠️  Consumer is behind by {lag} messages!")
        else:
            print(f"  ℹ️  No committed offset (consumer hasn't read anything yet)")
        print()

    consumer.close()
    return True

def test_live_consumption():
    """Test consuming messages in real-time"""
    print("\n" + "=" * 60)
    print("TESTING LIVE MESSAGE CONSUMPTION")
    print("=" * 60)
    print("Waiting for new messages for 10 seconds...\n")

    # Create consumer with latest offset (like the actual consumer)
    test_consumer = Consumer({
        'bootstrap.servers': KAFKA_SERVERS,
        'group.id': 'debug-live-test',
        'auto.offset.reset': 'latest',
        'enable.auto.commit': False
    })

    test_consumer.subscribe([KAFKA_TOPIC])

    messages_received = 0
    start_time = 0
    max_wait = 10  # Wait 10 seconds

    import time
    start = time.time()

    while time.time() - start < max_wait:
        msg = test_consumer.poll(timeout=1.0)

        if msg is None:
            continue

        if msg.error():
            if msg.error().code() != KafkaError._PARTITION_EOF:
                print(f"❌ Error: {msg.error()}")
            continue

        # Got a message!
        try:
            data = json.loads(msg.value().decode('utf-8'))
            print(f"✅ RECEIVED MESSAGE #{messages_received + 1}:")
            print(f"   Speed: {data.get('speed_kmh', 0):.1f} km/h")
            print(f"   RPM: {data.get('rpm', 0)}")
            print(f"   Gear: {data.get('gear', 0)}")
            print(f"   Distance: {data.get('distance', 0):.1f} m\n")
            messages_received += 1
        except Exception as e:
            print(f"⚠️  Error parsing message: {e}")

    test_consumer.close()

    if messages_received == 0:
        print("❌ NO NEW MESSAGES RECEIVED in the last 10 seconds!")
        print("   Check if the producer is running and Assetto Corsa is active.")
    else:
        print(f"✅ Successfully received {messages_received} messages in real-time")

    return messages_received > 0

def main():
    print("F1 AC DIGITAL TWIN - KAFKA DEBUG TOOL")
    print()

    try:
        # Step 1: Check if there are any messages in the topic
        has_messages = check_topic_messages()

        # Step 2: Check consumer group status
        check_consumer_group()

        # Step 3: Test live consumption
        is_receiving = test_live_consumption()

        # Summary
        print("\n" + "=" * 60)
        print("DIAGNOSTIC SUMMARY")
        print("=" * 60)

        if has_messages and is_receiving:
            print("✅ Everything looks good!")
            print("   The consumer should be able to read messages.")
        elif has_messages and not is_receiving:
            print("⚠️  Topic has old messages but no new ones are arriving.")
            print("   Solutions:")
            print("   1. Make sure producer is running")
            print("   2. Make sure Assetto Corsa is active")
            print("   3. Restart the producer")
        elif not has_messages:
            print("❌ No messages in topic at all!")
            print("   Solutions:")
            print("   1. Start the producer: python scripts\\playground\\S03_kafka_producer.py")
            print("   2. Make sure Assetto Corsa is running")

    except Exception as e:
        print(f"\n❌ Error during diagnostic: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
