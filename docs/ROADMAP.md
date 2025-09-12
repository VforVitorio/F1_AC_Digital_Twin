# ROADMAP - F1 AC Digital Twin

This document describes the roadmap for the F1 AC Digital Twin project, including objectives, planned features, and technical documentation for autonomous driving AI training in Assetto Corsa.

---

## Project Objectives

- Create a digital twin for Assetto Corsa focused on F1 racing
- Implement real-time telemetry analysis using AssettoCorsaGym
- Develop machine learning models for driving prediction and optimization
- Create an intuitive interface for data visualization and AI training
- Enable distributed training across multiple instances and machines

---

## 1️⃣ Introduction

**Goal**: Train an autonomous driving AI in Assetto Corsa (AC), specifically on tracks like Monza, using telemetry and controls without images.

The strategy is based on AssettoCorsaGym, which connects real AC with Gym-like environments for reinforcement learning (RL).

We aim to accelerate training through:

- Running multiple AC instances in parallel
- Distributed training across Windows and Linux machines
- Efficient use of local hardware: Ryzen 8945HS + RTX 4060 (8 GB VRAM)

---

## 2️⃣ AssettoCorsaGym Integration

**Features**

Plugin installed in your real Assetto Corsa that allows:

- Reading telemetry and car state: speed, RPM, steering angle, throttle, brake, gear, lap progress
- Controlling the vehicle via Python (throttle, brake, steering, gears)
- Communication via UDP/TCP for each instance
- Distributed training with multiple instances and machines
- Capturing telemetry data for supervised training (behavior cloning) or RL

Compatible with RL algorithms like SAC, PPO, and TD3.
Includes basic reward shaping: track progress, speed, penalty for collisions.

**Key Links and Resources**

- GitHub AssettoCorsaGym: https://github.com/dasGringuen/assetto_corsa_gym
- Official documentation and examples: https://assetto-corsa-gym.github.io
- Reference paper on architecture and training: https://arxiv.org/abs/2407.16680
- vJoy for applying actions from Python: https://vjoystick.sourceforge.net/site/
- AC shared memory (telemetry): https://www.assettocorsa.net/forum/index.php?threads/shared-memory-interface.40892/

---

## 3️⃣ Distributed Training Architecture

```
┌─────────────────────────┐
│       Central Trainer   │
│  (Python + GPU)         │
│  trains the RL network  │
└──────────┬──────────────┘
          │
 ┌────────┴───────────────┐
 │                    │
┌──────────────┐   ┌────────────────┐
│ Worker 1     │   │ Worker 2       │
│ Windows AC   │   │ Linux AC       │
│ Plugin + AC  │   │ Plugin + AC    │
│ 1 instance   │   │ 1 instance     │
└──────────────┘   └────────────────┘
```

- Each worker runs AC + plugin and communicates with the central Trainer
- The Trainer trains the RL policy and distributes weights to the workers
- Workers can run on Windows or Linux, connected on the same LAN

---

## 4️⃣ Multi-Instance Setup

### Windows (local)

- Create separate AC copies to run multiple instances
- Configure minimum resolution (320×240) and disable graphics effects: shadows, crowd, post-processing, AI opponents
- Assign _different UDP/TCP ports_ for each instance
- With Ryzen + 4060, start with 2–3 instances
- Batch scripts can automate launching

### Native Linux

- Steam + AC + Proton, headless mode or virtual desktops
- Launch several additional instances (4–6 or more depending on hardware)
- Each instance with its own plugin port connected to the central Trainer

### Note on WSL

- WSL2 _is not suitable_ for running AC with Proton and headless mode

---

## 5️⃣ Data and Variables for Behavior Cloning

Variables to collect into CSV or a database:

- `vel` (speed)
- `rpm` (engine revolutions)
- `steer_angle` (steering angle)
- `throttle` (0–1)
- `brake` (0–1)
- `gear` (gear)
- `lap_progress` (lap percentage)

Optional: lateral and longitudinal acceleration.

Each row represents the car state and the action performed by the AI or human driver.

---

## 6️⃣ Pipeline BC → RL

### 1. Behavior Cloning (supervised)

- Train an MLP network with telemetry variables as input and actions as output
- Loss function: MSE for continuous actions, cross-entropy for gear
- Result: a network that can complete laps reasonably following the track

### 2. RL (refinement)

- Use the BC-trained network as initial policy
- Workers send observations `[vel, rpm, steer_angle, throttle, brake, gear, lap_progress]` to the trainer
- The trainer computes actions and sends them back to the AC plugin
- Reward shaping: track progress, staying within limits, minimizing hard braking, completing laps quickly

### 3. Scalability

- Multiple AC Gym instances, distributed across Windows and Linux
- Central trainer gathers experiences from all workers and updates policy weights

### 4. Final inference

- A vanilla AC instance + plugin in inference mode
- The trained network controls the car without further training

---

## 7️⃣ Advantages of Using Only Telemetry

- Less data and processing → faster training
- Smaller network → less GPU and memory required
- Enables running more instances in parallel, accelerating data collection and training
- Sufficient for learning curves and throttle/brake control robustly

---

## Development Phases

### Phase 1: Telemetry Integration 🚧

- [ ] AssettoCorsaGym plugin installation and configuration
- [ ] Shared memory reading implementation
- [ ] Telemetry field decoding
- [ ] Real-time data collection system
- [ ] Data validation and cleaning

### Phase 2: Behavior Cloning

- [ ] MLP network architecture design
- [ ] Training data preparation and preprocessing
- [ ] Supervised learning implementation
- [ ] Model evaluation and validation
- [ ] Initial driving policy creation

### Phase 3: Reinforcement Learning

- [ ] RL algorithm implementation (SAC/PPO/TD3)
- [ ] Reward function design and tuning
- [ ] Distributed training setup
- [ ] Multi-instance coordination
- [ ] Policy refinement and optimization

### Phase 4: Multi-Instance & Distributed Training

- [ ] Multiple AC instances configuration
- [ ] Windows and Linux worker setup
- [ ] Central trainer implementation
- [ ] Network communication protocols
- [ ] Load balancing and scalability optimization

### Phase 5: Advanced Features

- [ ] Performance analysis and optimization
- [ ] Advanced driving pattern recognition
- [ ] Vehicle setup optimization
- [ ] Lap and sector comparison tools
- [ ] Real-time inference system

---

## Technical Implementation

### Project Structure

```
F1_AC_Digital_Twin/
├── src/
│   ├── telemetry/
│   │   ├── ac_reader.py          # Shared memory reading
│   │   ├── data_processor.py     # Data processing
│   │   └── models.py            # ctypes structures
│   ├── training/
│   │   ├── behavior_cloning.py  # Supervised learning
│   │   ├── reinforcement.py     # RL algorithms
│   │   └── distributed.py       # Distributed training
│   ├── gym_integration/
│   │   ├── ac_gym.py           # AssettoCorsaGym wrapper
│   │   ├── workers.py          # Training workers
│   │   └── coordinator.py      # Central trainer
│   └── dashboard/
│       ├── components/          # UI components
│       └── pages/              # Streamlit pages
├── data/
│   ├── raw/                    # Raw telemetry data
│   ├── processed/              # Processed datasets
│   ├── models/                 # Trained models
│   └── logs/                   # Training logs
├── config/
│   ├── settings.py             # General configuration
│   ├── ac_config.py           # AC-specific settings
│   └── training_config.py     # Training parameters
└── scripts/
    ├── setup_instances.py      # Multi-instance setup
    ├── launch_training.py      # Training launcher
    └── inference.py           # Real-time inference
```

---

## Hardware Requirements

### Minimum Requirements

- CPU: Ryzen 5 or Intel i5 (8 cores recommended)
- GPU: GTX 1060 / RTX 3060 (8GB VRAM recommended)
- RAM: 16GB (32GB for multiple instances)
- Storage: 50GB free space

### Recommended for Distributed Training

- CPU: Ryzen 7/9 or Intel i7/i9
- GPU: RTX 4060/4070 or better
- RAM: 32GB+
- Network: Gigabit Ethernet for multi-machine setup

---

## Development Considerations

### Technical Notes

- Use `ctypes.c_wchar` for UTF-16 strings
- Validate structure offsets before production
- Implement robust error handling
- Consider performance optimizations for real-time reading
- Plan for different AC versions and mod compatibility

### Testing Strategy

- Test with different Assetto Corsa versions
- Validate telemetry data accuracy
- Verify compatibility with mods
- Performance testing with multiple instances
- Network latency testing for distributed setup

### Documentation

- Maintain updated guides and API documentation
- Document configuration changes
- Provide usage examples and tutorials
- Keep troubleshooting guides current
