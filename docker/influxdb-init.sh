#!/bin/bash
# Script to initialize InfluxDB with additional buckets
# This runs after InfluxDB starts

set -e

# Wait for InfluxDB to be ready
echo "Waiting for InfluxDB to be ready..."
until curl -s http://localhost:8086/health | grep -q "pass"; do
    sleep 2
done
echo "InfluxDB is ready!"

# Create f1-anomalies bucket if it doesn't exist
echo "Creating f1-anomalies bucket..."
influx bucket create \
    --name f1-anomalies \
    --org f1-org \
    --token f1-telemetry-token-super-secret \
    --retention 0 \
    2>/dev/null || echo "Bucket f1-anomalies already exists or error occurred"

echo "InfluxDB setup complete!"
