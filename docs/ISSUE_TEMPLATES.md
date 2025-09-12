# 📋 Issue Templates for F1_AC_Digital_Twin

## 🐛 TEMPLATE: Bug Report

```markdown
## 🐛 Bug Report

**Affected Component:** [Telemetry Capture / BC Training / RL Training / AC Plugin / Distributed Setup]

### Problem Description

[Describe what's wrong - e.g.: "AC shared memory connection fails after 5 minutes" or "BC model not converging"]

### Steps to Reproduce

1.
2.
3.
4.

### Expected Behavior

[What should happen]

### Actual Behavior

[What actually happens]

### Related Files

- [ ] `test.py` (telemetry capture)
- [ ] `/notebooks/XX_behavior_cloning.ipynb`
- [ ] `/notebooks/XX_rl_training.ipynb`
- [ ] AC plugin files
- [ ] Training data CSV

### Logs/Screenshots
```

[Paste error logs/telemetry output here]

```

### Environment
- OS: [Windows/Linux]
- AC Version:
- Python:
- GPU: [RTX 4060 / other]

**Priority:** [🔥 Critical / 🔴 High / 🟡 Medium / 🟢 Low]
```

## ✨ TEMPLATE: Feature Request

```markdown
## ✨ Feature Request

**Component:** [Telemetry Processing / BC Model / RL Algorithm / Multi-Instance / Distributed Training]

### Feature Description

[What new functionality do you want]

### Use Case

[What racing scenario would this improve]

### Usage Example
```

Example: "Add lap sector time analysis to improve reward shaping"
Result: Better cornering performance in RL training

```

### Implementation Ideas
- [ ] Option 1:
- [ ] Option 2:

**Estimated Complexity:** [🟢 Simple / 🟡 Medium / 🔴 Complex]
```

## 📊 TEMPLATE: Training Data Issue

```markdown
## 📊 Training Data Issue

**Type:** [Telemetry Capture / Data Preprocessing / Model Input/Output / CSV Format]

### Data Problem

[Describe the specific issue with training data]

### Reference Source

[test.py output, specific AC track, driving session, etc.]

### Data Comparison

**Expected:**

- Variables: [vel, rpm, steer_angle, throttle, brake, gear, lap_progress]
- Sample rate: 10Hz
- Lap count: X

**Actual:**

- Variables: [missing/incorrect fields]
- Issues: [data corruption, missing values, wrong format]

### Files Involved

- **Telemetry script:** `test.py`
- **Raw data:** `/TELEMETRIA/telemetria_X.csv`
- **Training notebook:** `/notebooks/XX.ipynb`

### To Investigate

- [ ] Verify AC shared memory connection
- [ ] Check data collection frequency
- [ ] Validate variable ranges
- [ ] Test on different AC tracks
```

## 🏎️ TEMPLATE: AC Integration Issue

```markdown
## 🏎️ AC Integration Issue

**Type:** [Plugin Installation / Shared Memory / Multi-Instance / vJoy Control]

### AC Problem

[Describe AC-specific issue]

### AC Setup

- Track: [Monza/other]
- Car: [F1 car model]
- AC Mode: [Practice/Race]
- Instances: [Single/Multiple]

### Expected AC Behavior

[What should happen in AC]

### Actual AC Behavior

[What AC is doing wrong]

### Hardware Context

- CPU: Ryzen 8945HS
- GPU: RTX 4060 (8GB VRAM)
- RAM: [amount]
- AC instances running: [number]

### Files to Check

- [ ] AC plugin installation
- [ ] vJoy configuration
- [ ] Port assignments for multi-instance
```

## 🤖 TEMPLATE: Model Training Issue

```markdown
## 🤖 Model Training Issue

**Stage:** [Behavior Cloning / RL Training / Model Evaluation]

### Training Problem

[Describe model performance issue]

### Training Data

- Dataset size: [rows]
- Track: [Monza/other]
- Data quality: [clean/noisy]

### Model Details

- Architecture: [MLP/other]
- Input variables: [vel, rpm, steer_angle, ...]
- Output actions: [throttle, brake, steering, gear]

### Training Metrics

**Expected:**

- Loss: [target value]
- Lap completion: [target %]

**Actual:**

- Loss: [current value]
- Issues: [not converging, overfitting, etc.]

### To Debug

- [ ] Check data preprocessing
- [ ] Verify model architecture
- [ ] Test reward function (RL)
- [ ] Validate distributed setup
```

## 🚀 TEMPLATE: Development Task

```markdown
## 🚀 Task: [Task Title]

### Description

[What needs to be implemented]

### Racing Context

[How this improves the AI driver]

### Checklist

- [ ] Code implementation
- [ ] Test with AC
- [ ] Validate on Monza
- [ ] Performance testing
- [ ] Documentation

### Acceptance Criteria

- [ ] AI completes clean laps
- [ ] Performance improvement measurable
- [ ] Works with distributed setup

### Files to Modify

- [ ] `test.py`
- [ ] `/notebooks/XX.ipynb`
- [ ] Training scripts

**Estimation:** [1 day / 1 week / 2 weeks]
**Hardware needed:** [RTX 4060 / Multi-instance setup]
```

## 💡 TEMPLATE: Racing AI Idea

```markdown
## 💡 [Racing Improvement Idea]

**Idea:** [Quick description]
**Racing benefit:** [How this makes the AI faster/better]
**Implementation:** [BC/RL/data preprocessing]
**Next step:** [Test on track/collect data/train model]
**AC tracks:** [Monza/other circuits to test]
```

## 🔧 Usage Tips:

1. **Copy appropriate template** for AC/training issues
2. **Include telemetry data** when reporting bugs
3. **Specify AC track/car** for context
4. **Add labels** : `ac-integration`, `behavior-cloning`, `rl-training`, `telemetry`, `distributed`
5. **Reference hardware** : RTX 4060, multi-instance capability

### Example Usage:

```
Title: [BUG] Shared memory connection drops during long training sessions
Template: 🐛 Bug Report
Labels: bug, ac-integration, telemetry, high-priority
```
