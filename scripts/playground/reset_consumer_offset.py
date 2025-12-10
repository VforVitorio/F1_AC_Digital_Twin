"""
Reset consumer group offset to latest position
This will make the consumer skip old messages and start reading new ones
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config import KAFKA_SERVERS, KAFKA_TOPIC, KAFKA_CONSUMER_GROUP
from confluent_kafka import Consumer, TopicPartition
from confluent_kafka.admin import AdminClient

def reset_consumer_offset_to_latest():
    """Reset consumer group offset to latest (end of topic)"""
    print("=" * 60)
    print("RESETTING CONSUMER OFFSET TO LATEST")
    print("=" * 60)
    print(f"Consumer Group: {KAFKA_CONSUMER_GROUP}")
    print(f"Topic: {KAFKA_TOPIC}")
    print(f"Kafka Servers: {KAFKA_SERVERS}\n")

    # Create consumer
    consumer = Consumer({
        'bootstrap.servers': KAFKA_SERVERS,
        'group.id': KAFKA_CONSUMER_GROUP,
        'enable.auto.commit': False
    })

    # Get topic metadata
    admin_client = AdminClient({'bootstrap.servers': KAFKA_SERVERS})
    metadata = admin_client.list_topics(timeout=5)

    if KAFKA_TOPIC not in metadata.topics:
        print(f"❌ Topic '{KAFKA_TOPIC}' not found!")
        return False

    topic_metadata = metadata.topics[KAFKA_TOPIC]

    print(f"Found {len(topic_metadata.partitions)} partition(s)\n")

    # Reset offset for each partition
    for partition_id in topic_metadata.partitions:
        tp = TopicPartition(KAFKA_TOPIC, partition_id)

        # Get current watermarks
        low, high = consumer.get_watermark_offsets(tp, timeout=5.0)

        print(f"Partition {partition_id}:")
        print(f"  Current low offset: {low}")
        print(f"  Current high offset: {high}")

        # Set offset to high (latest)
        tp.offset = high
        consumer.commit(offsets=[tp])

        print(f"  ✅ Reset to offset: {high}")
        print()

    consumer.close()

    print("=" * 60)
    print("✅ OFFSET RESET COMPLETE!")
    print("=" * 60)
    print("Now restart your consumer - it will read only NEW messages")
    print()

    return True

if __name__ == "__main__":
    try:
        reset_consumer_offset_to_latest()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
