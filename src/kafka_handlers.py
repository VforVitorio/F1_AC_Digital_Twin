"""
Kafka Configuration and Handling Functions
Functions for setting up and managing Kafka producers and consumers
"""

from confluent_kafka import Producer, Consumer
from confluent_kafka.admin import AdminClient, NewTopic


def setup_kafka_topic(bootstrap_servers, topic_name):
    """
    Create Kafka topic if it doesn't exist

    Args:
        bootstrap_servers: Kafka broker addresses
        topic_name: Name of the topic to create

    Returns:
        True if topic exists or was created successfully
    """
    print("🔧 Setting up Kafka topic...")

    admin_client = AdminClient({'bootstrap.servers': bootstrap_servers})

    try:
        topic = NewTopic(topic_name, num_partitions=1, replication_factor=1)
        admin_client.create_topics([topic])
        print(f"✅ Topic '{topic_name}' created successfully")
        return True
    except Exception as e:
        print(f"ℹ️  Topic already exists or error: {e}")
        return True


def configure_producer(bootstrap_servers, client_id='f1-telemetry-producer'):
    """
    Configure Kafka producer

    Args:
        bootstrap_servers: Kafka broker addresses
        client_id: Client identifier for the producer

    Returns:
        Configured Kafka Producer instance
    """
    print("⚙️  Configuring Kafka producer...")

    config = {
        'bootstrap.servers': bootstrap_servers,
        'client.id': client_id
    }

    producer = Producer(config)
    print("✅ Producer configured successfully")
    return producer


def configure_consumer(bootstrap_servers, group_id, topic_name, client_id='f1-telemetry-consumer'):
    """
    Configure Kafka consumer

    Args:
        bootstrap_servers: Kafka broker addresses
        group_id: Consumer group ID
        topic_name: Topic to subscribe to
        client_id: Client identifier for the consumer

    Returns:
        Configured Kafka Consumer instance
    """
    print("🔧 Configuring Kafka consumer...")

    consumer_config = {
        'bootstrap.servers': bootstrap_servers,
        'group.id': group_id,
        'auto.offset.reset': 'latest',
        'enable.auto.commit': True,
        'auto.commit.interval.ms': 1000,
        'client.id': client_id
    }

    consumer = Consumer(consumer_config)
    consumer.subscribe([topic_name])

    print(f"✅ Kafka Consumer configured")
    print(f"✅ Subscribed to topic: {topic_name}")
    print(f"✅ Consumer group: {group_id}")

    return consumer


def delivery_callback(err, msg):
    """
    Callback for message delivery confirmation

    Args:
        err: Error object if delivery failed
        msg: Message object
    """
    if err is not None:
        print(f"❌ Message delivery failed: {err}")
