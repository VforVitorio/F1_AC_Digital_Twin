#!/usr/bin/env python3
"""
Automatic Telemetry Streaming for Assetto Corsa
Monitors for Assetto Corsa process and automatically streams telemetry to Kafka
"""

import sys
import time
import psutil
import subprocess
from pathlib import Path
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
ROOT = Path(__file__).resolve().parents[2]
TELEMETRY_SCRIPT = ROOT / 'src' / 'telemetry_collector.py'
KAFKA_SERVERS = 'localhost:9092'
KAFKA_TOPIC = 'f1-telemetry'
AC_PROCESS_NAMES = ['acs.exe', 'ac.exe', 'AssettoCorsa.exe']
CHECK_INTERVAL = 5  # seconds

# State
telemetry_process = None


def is_ac_running():
    """Check if Assetto Corsa is running."""
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] in AC_PROCESS_NAMES:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def check_kafka_connection():
    """Check if Kafka broker is accessible."""
    try:
        admin = AdminClient({'bootstrap.servers': KAFKA_SERVERS})
        metadata = admin.list_topics(timeout=5)
        return True
    except Exception as e:
        logger.warning(f"Kafka connection failed: {e}")
        return False


def ensure_kafka_topic():
    """Ensure Kafka topic exists."""
    try:
        admin = AdminClient({'bootstrap.servers': KAFKA_SERVERS})

        # Check if topic exists
        metadata = admin.list_topics(timeout=5)
        if KAFKA_TOPIC in metadata.topics:
            logger.info(f"Kafka topic '{KAFKA_TOPIC}' already exists")
            return True

        # Create topic
        topic = NewTopic(
            topic=KAFKA_TOPIC,
            num_partitions=1,
            replication_factor=1
        )

        fs = admin.create_topics([topic])
        for topic_name, future in fs.items():
            try:
                future.result()
                logger.info(f"Created Kafka topic '{topic_name}'")
                return True
            except Exception as e:
                logger.error(f"Failed to create topic '{topic_name}': {e}")
                return False
    except Exception as e:
        logger.error(f"Kafka topic setup failed: {e}")
        return False


def start_telemetry_collector():
    """Start the telemetry collector process."""
    global telemetry_process

    if telemetry_process and telemetry_process.poll() is None:
        logger.info("Telemetry collector already running")
        return True

    try:
        # Find Python executable
        python_exe = sys.executable

        # Start telemetry collector
        logger.info("Starting telemetry collector...")
        telemetry_process = subprocess.Popen(
            [python_exe, str(TELEMETRY_SCRIPT), '--kafka', '--kafka-servers', KAFKA_SERVERS],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        # Wait a bit to check if it started successfully
        time.sleep(2)
        if telemetry_process.poll() is None:
            logger.info("Telemetry collector started successfully")
            return True
        else:
            stdout, stderr = telemetry_process.communicate()
            logger.error(f"Telemetry collector failed to start:")
            logger.error(f"STDOUT: {stdout}")
            logger.error(f"STDERR: {stderr}")
            return False
    except Exception as e:
        logger.error(f"Failed to start telemetry collector: {e}")
        return False


def stop_telemetry_collector():
    """Stop the telemetry collector process."""
    global telemetry_process

    if not telemetry_process or telemetry_process.poll() is not None:
        logger.info("Telemetry collector not running")
        return

    try:
        logger.info("Stopping telemetry collector...")
        telemetry_process.terminate()

        # Wait for graceful shutdown
        try:
            telemetry_process.wait(timeout=10)
            logger.info("Telemetry collector stopped")
        except subprocess.TimeoutExpired:
            logger.warning("Telemetry collector didn't stop gracefully, killing...")
            telemetry_process.kill()
            telemetry_process.wait()
            logger.info("Telemetry collector killed")

        telemetry_process = None
    except Exception as e:
        logger.error(f"Error stopping telemetry collector: {e}")


def main():
    """Main monitoring loop."""
    logger.info("=" * 70)
    logger.info("AUTOMATIC TELEMETRY STREAMING FOR ASSETTO CORSA")
    logger.info("=" * 70)
    logger.info(f"Monitoring for Assetto Corsa process...")
    logger.info(f"Kafka servers: {KAFKA_SERVERS}")
    logger.info(f"Kafka topic: {KAFKA_TOPIC}")
    logger.info(f"Check interval: {CHECK_INTERVAL}s")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 70)

    # Check Kafka connection
    logger.info("\nChecking Kafka connection...")
    if not check_kafka_connection():
        logger.error("Cannot connect to Kafka. Please ensure Docker containers are running.")
        logger.error("Run: docker-compose up -d")
        return 1

    logger.info("Kafka connection OK")

    # Ensure Kafka topic exists
    logger.info("Ensuring Kafka topic exists...")
    if not ensure_kafka_topic():
        logger.error("Failed to setup Kafka topic")
        return 1

    ac_was_running = False

    try:
        while True:
            ac_running = is_ac_running()

            if ac_running and not ac_was_running:
                # AC just started
                logger.info("")
                logger.info("=" * 70)
                logger.info("ASSETTO CORSA DETECTED - STARTING TELEMETRY STREAMING")
                logger.info("=" * 70)
                start_telemetry_collector()
                ac_was_running = True

            elif not ac_running and ac_was_running:
                # AC just stopped
                logger.info("")
                logger.info("=" * 70)
                logger.info("ASSETTO CORSA STOPPED - STOPPING TELEMETRY STREAMING")
                logger.info("=" * 70)
                stop_telemetry_collector()
                ac_was_running = False

            # Check if telemetry collector is still running when it should be
            if ac_running and telemetry_process and telemetry_process.poll() is not None:
                logger.warning("Telemetry collector stopped unexpectedly, restarting...")
                start_telemetry_collector()

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        logger.info("\n\nShutdown requested...")
        stop_telemetry_collector()
        logger.info("Monitoring stopped")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        stop_telemetry_collector()
        return 1


if __name__ == "__main__":
    sys.exit(main())
