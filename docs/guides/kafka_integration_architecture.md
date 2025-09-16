# Kafka Integration Architecture for F1 AC Digital Twin

This document outlines the comprehensive architecture and use cases for integrating Apache Kafka into the F1 AC Digital Twin project, enabling real-time telemetry streaming, distributed training, and live dashboard visualization.

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [When to Use Kafka](#when-to-use-kafka)
3. [Kafka Integration Scenarios](#kafka-integration-scenarios)
4. [Real-time Dashboard Architecture](#real-time-dashboard-architecture)
5. [Implementation Examples](#implementation-examples)
6. [Technical Benefits](#technical-benefits)
7. [Future Roadmap](#future-roadmap)

---

## 🎯 Project Overview

The F1 AC Digital Twin project currently consists of:

- **Telemetry Collection**: Real-time data collection from Assetto Corsa via shared memory
- **Data Analysis**: Jupyter notebooks for exploratory data analysis (EDA)
- **Visualization**: Circuit maps and performance analysis using Plotly
- **Future Goals**: Behavioral Learning (BL) and Reinforcement Learning (RL) implementation

---

## ⚖️ When to Use Kafka

### ✅ **Kafka IS Beneficial For:**

1. **Multi-instance RL Training** with AssettoCorsaGym
2. **Real-time Dashboard** with Streamlit for live telemetry
3. **Production AI Deployment** with trained models
4. **Distributed Training** across multiple machines
5. **Live Performance Monitoring** during races

### ❌ **Kafka IS NOT Needed For:**

1. **Current EDA Phase** - CSV files are perfectly adequate
2. **Single-instance Development** - Local file processing is simpler
3. **Behavioral Learning Training** - Batch processing works better
4. **Prototyping and Research** - Adds unnecessary complexity

---

## 🏗️ Kafka Integration Scenarios

### **Scenario 1: RL Training with AssettoCorsaGym**

```
┌─────────────────────────┐
│    Multiple AC Workers  │
│ ┌─────────────────────┐ │
│ │ Worker 1 (AC+Gym)   │ │ ──┐
│ │ Worker 2 (AC+Gym)   │ │ ──┤
│ │ Worker 3 (AC+Gym)   │ │ ──┤ Experiences
│ │ Worker N (AC+Gym)   │ │ ──┘ (s,a,r,s')
│ └─────────────────────┘ │
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│      Kafka Topics       │
│ ┌─────────────────────┐ │
│ │ rl-experiences      │ │ ← Distributed buffer
│ │ model-updates       │ │ ← New weights
│ │ training-metrics    │ │ ← Loss, rewards, etc.
│ └─────────────────────┘ │
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│   Central RL Trainer    │
│ ┌─────────────────────┐ │
│ │ PPO/SAC/TD3 Agent   │ │ ← Trains with all
│ │ Experience Replay   │ │   experiences
│ │ Model Distribution  │ │ ← Distributes weights
│ └─────────────────────┘ │
└─────────────────────────┘
```

**Benefits:**

- **Distributed Experience Buffer**: Each worker contributes experiences asynchronously
- **Model Synchronization**: Updated weights distributed to all workers
- **Fault Tolerance**: Training continues if individual workers fail
- **Horizontal Scaling**: Easy to add/remove workers dynamically

### **Scenario 2: Trained Model in Production**

```
┌─────────────────────────┐
│   Trained RL Agent      │
│ ┌─────────────────────┐ │
│ │ AC + Trained Model  │ │ ── Live telemetry
│ │ Real-time Inference │ │ ── Model decisions
│ │ Performance Monitor │ │ ── Performance metrics
│ └─────────────────────┘ │
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│      Kafka Topics       │
│ ┌─────────────────────┐ │
│ │ live-telemetry      │ │ ← Real-time stream
│ │ ai-decisions        │ │ ← Model actions
│ │ performance-metrics │ │ ← Lap times, sectors
│ │ anomaly-detection   │ │ ← Unusual behaviors
│ └─────────────────────┘ │
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│   Analytics & Monitoring│
│ ┌─────────────────────┐ │
│ │ Real-time Dashboard │ │ ← Live visualization
│ │ Performance Analysis│ │ ← Compare with humans
│ │ Model Drift Monitor │ │ ← Model degradation?
│ │ Strategy Optimization│ │ ← Continuous improvement
│ └─────────────────────┘ │
└─────────────────────────┘
```

**Benefits:**

- **Production Telemetry**: Monitor AI performance in real-time
- **Performance Analytics**: Compare AI vs human drivers
- **Anomaly Detection**: Identify when model behavior degrades
- **Continuous Learning**: Use new experiences for model fine-tuning

---

## 📊 Real-time Dashboard Architecture

### **Current Notebook Analysis**

From the existing notebooks, we identified these key visualizations:

**circuit_telemetry_analysis.ipynb:**

- Circuit map with speed overlay
- Steering analysis on track layout
- Throttle/Brake combined visualization
- Gear mapping across circuit
- RPM distribution
- Surface grip analysis

**lap_telemetry_exploration.ipynb:**

- Lap-by-lap comparisons
- Sector analysis
- Performance metrics

### **Kafka + Streamlit Architecture**

```
┌─────────────────────────┐
│   AC + telemetry_       │
│   collector.py          │
│                         │
│ ┌─────────────────────┐ │
│ │ Kafka Producer      │ │ ── Real-time stream
│ │ (every 0.1s)        │ │ ── 10 msgs/second
│ └─────────────────────┘ │
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│      Kafka Topics       │
│ ┌─────────────────────┐ │
│ │ ac-telemetry-live   │ │ ← Point-by-point data
│ │ ac-lap-events       │ │ ← Lap completion
│ │ ac-sector-times     │ │ ← Sector times
│ │ ac-session-stats    │ │ ← Global statistics
│ └─────────────────────┘ │
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│  Streamlit Dashboard    │
│ ┌─────────────────────┐ │
│ │ Kafka Consumer      │ │ ← Consumes streams
│ │ Real-time Charts    │ │ ← Updates graphics
│ │ Live Circuit Map    │ │ ← Real-time position
│ │ Performance Metrics │ │ ← Instant KPIs
│ └─────────────────────┘ │
└─────────────────────────┘
```

### **Kafka Topics Definition**

```json
{
  "ac-telemetry-live": {
    "description": "Main telemetry stream",
    "frequency": "10 Hz (every 0.1s)",
    "retention": "1 hour",
    "data": {
      "timestamp": "unix_timestamp",
      "speed_kmh": "float",
      "rpm": "int",
      "throttle": "float",
      "brake": "float",
      "steering": "float",
      "gear": "int",
      "car_x": "float",
      "car_z": "float",
      "distance": "float",
      "sector": "int"
    }
  },

  "ac-lap-events": {
    "description": "Lap completion events",
    "frequency": "Per lap (~1-2 min)",
    "retention": "24 hours",
    "data": {
      "lap_number": "int",
      "lap_time_ms": "int",
      "sector_times": "array[int]",
      "best_lap": "boolean",
      "distance_total": "float"
    }
  },

  "ac-session-stats": {
    "description": "Aggregated statistics",
    "frequency": "5 seconds",
    "retention": "6 hours",
    "data": {
      "avg_speed": "float",
      "max_speed": "float",
      "total_distance": "float",
      "current_lap": "int",
      "session_time": "int"
    }
  }
}
```

### **Dashboard Layout Concept**

```python
# Streamlit Dashboard Layout (conceptual)
st.title("🏎️ F1 AC Digital Twin - Live Telemetry")

# Row 1: Key Metrics
col1, col2, col3, col4 = st.columns(4)
with col1: st.metric("Speed", f"{current_speed:.1f} km/h")
with col2: st.metric("RPM", f"{current_rpm}")
with col3: st.metric("Lap", f"{current_lap}")
with col4: st.metric("Best Lap", f"{best_lap_time}")

# Row 2: Circuit map + car position
col1, col2 = st.columns([2, 1])
with col1:
    # Circuit map with speed trail + live car position
    st.plotly_chart(live_circuit_map)
with col2:
    # Live gauges: RPM, Speed, Gear
    st.plotly_chart(live_gauges)

# Row 3: Time series charts
col1, col2 = st.columns(2)
with col1:
    # Speed + Throttle/Brake vs time
    st.plotly_chart(speed_time_chart)
with col2:
    # Steering + G-forces vs time
    st.plotly_chart(steering_time_chart)

# Row 4: Sector analysis
st.plotly_chart(sector_analysis_chart)
```

---

## 💻 Implementation Examples

### **Kafka Producer (Modified src/telemetry_collector.py)**

```python
from kafka import KafkaProducer
import json

# Add to src/telemetry_collector.py
class TelemetryKafkaProducer:
    def __init__(self, bootstrap_servers=['localhost:9092']):
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

    def send_telemetry(self, telemetry_data):
        # Send to live telemetry topic
        self.producer.send('ac-telemetry-live', telemetry_data)

    def send_lap_event(self, lap_data):
        # Send to lap events topic
        self.producer.send('ac-lap-events', lap_data)

    def send_session_stats(self, stats_data):
        # Send to session statistics topic
        self.producer.send('ac-session-stats', stats_data)

# Integration in main telemetry loop
kafka_producer = TelemetryKafkaProducer()

while True:
    # ... existing telemetry collection code ...

    # Prepare Kafka message
    telemetry_message = {
        "timestamp": int(time.time()),
        "speed_kmh": round(data.speedKmh, 2),
        "rpm": data.rpms,
        "throttle": round(data.gas, 2),
        "brake": round(data.brake, 2),
        "steering": round(data.steerAngle, 3),
        "gear": gear,
        "car_x": coords[0],
        "car_z": coords[2],
        "distance": round(data_g.distanceTraveled, 3),
        "sector": data_g.currentSectorIndex
    }

    # Send to Kafka
    kafka_producer.send_telemetry(telemetry_message)

    # ... rest of existing code ...
```

### **Streamlit Consumer Dashboard**

```python
import streamlit as st
from kafka import KafkaConsumer
import json
import plotly.graph_objects as go
from collections import deque

class TelemetryDashboard:
    def __init__(self):
        self.consumer = KafkaConsumer(
            'ac-telemetry-live',
            bootstrap_servers=['localhost:9092'],
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )

        # Buffer for real-time data
        self.telemetry_buffer = deque(maxlen=1000)  # Last 1000 points

    def consume_telemetry(self):
        # Non-blocking consumer
        message_batch = self.consumer.poll(timeout_ms=100)
        for topic_partition, messages in message_batch.items():
            for message in messages:
                self.telemetry_buffer.append(message.value)

    def create_live_circuit_map(self):
        if not self.telemetry_buffer:
            return go.Figure()

        # Extract coordinates and speeds
        x_coords = [point['car_x'] for point in self.telemetry_buffer]
        z_coords = [point['car_z'] for point in self.telemetry_buffer]
        speeds = [point['speed_kmh'] for point in self.telemetry_buffer]

        # Create speed-colored track
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x_coords, y=z_coords,
            mode='markers+lines',
            marker=dict(color=speeds, colorscale='Viridis', size=4),
            name='Track'
        ))

        # Add current car position
        if self.telemetry_buffer:
            current = self.telemetry_buffer[-1]
            fig.add_trace(go.Scatter(
                x=[current['car_x']], y=[current['car_z']],
                mode='markers',
                marker=dict(size=15, color='red', symbol='circle'),
                name='Current Position'
            ))

        return fig

# Streamlit app
st.title("🏎️ F1 AC Digital Twin - Live Telemetry")

# Initialize dashboard
dashboard = TelemetryDashboard()

# Create placeholder for auto-refresh
placeholder = st.empty()

# Main loop
while True:
    # Consume new telemetry data
    dashboard.consume_telemetry()

    # Update dashboard
    with placeholder.container():
        if dashboard.telemetry_buffer:
            current = dashboard.telemetry_buffer[-1]

            # Metrics row
            col1, col2, col3, col4 = st.columns(4)
            with col1: st.metric("Speed", f"{current['speed_kmh']:.1f} km/h")
            with col2: st.metric("RPM", f"{current['rpm']}")
            with col3: st.metric("Gear", f"{current['gear']}")
            with col4: st.metric("Throttle", f"{current['throttle']:.2f}")

            # Live circuit map
            st.plotly_chart(dashboard.create_live_circuit_map(), use_container_width=True)

    # Refresh rate
    time.sleep(0.1)
```

---

## 🚀 Technical Benefits

### **1. Scalability**

- **Horizontal scaling**: Add more AC instances without architectural changes
- **High throughput**: Handle 100+ Hz telemetry from multiple sources
- **Load distribution**: Distribute processing across multiple consumers

### **2. Reliability**

- **Fault tolerance**: System continues if individual components fail
- **Data persistence**: Telemetry preserved even if dashboard crashes
- **Replay capability**: Historical data available for debugging and analysis

### **3. Flexibility**

- **Multiple consumers**: Different dashboards can consume the same data
- **Real-time and batch**: Support both live visualization and offline analysis
- **Technology agnostic**: Easy to integrate with different tools and frameworks

### **4. Performance**

- **Low latency**: Sub-second data propagation from AC to dashboard
- **Efficient buffering**: Kafka handles backpressure and flow control
- **Resource optimization**: Decoupled components can scale independently

---

## 🗓️ Future Roadmap

### **Phase 1: Current (No Kafka)**

- EDA and feature engineering using CSV files
- Behavioral Learning model training
- Static visualization and analysis

### **Phase 2: Single-instance RL (Optional Kafka)**

- AssettoCorsaGym integration
- Single AC instance RL training
- Basic real-time monitoring

### **Phase 3: Multi-instance RL (Kafka Essential)**

- Multiple AC workers for distributed training
- Kafka-based experience sharing
- Advanced model synchronization

### **Phase 4: Production Deployment (Kafka Essential)**

- Trained model in live racing scenarios
- Real-time performance monitoring
- Continuous learning and model updates

### **Phase 5: Advanced Analytics (Kafka Enhanced)**

- Multi-session comparative analysis
- Anomaly detection and alerting
- Machine learning-driven insights

---

## 📝 Conclusion

Kafka integration provides significant value for the F1 AC Digital Twin project, particularly in:

1. **Real-time dashboard visualization** during live sessions
2. **Distributed RL training** with multiple AC instances
3. **Production deployment** of trained models
4. **Scalable analytics** and monitoring systems

The key is implementing Kafka **when appropriate** - not during the current EDA/BL phase, but when moving to distributed systems and real-time applications.

This architecture ensures the project can scale from research prototype to production-grade distributed system while maintaining simplicity during development phases.
