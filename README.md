# F1 AC Digital Twin

A research prototype for Assetto Corsa telemetry. It combines a temporal convolutional network (TCN) for behavioral learning with a four-expert mixture-of-experts (MoE) anomaly detector.

The live collector reads Assetto Corsa shared memory. A CSV replay script can feed recorded telemetry into the same Kafka pipeline.

## Streaming path

```text
Assetto Corsa shared memory -> Python collector -> Kafka: f1-telemetry
CSV replay ----------------> Kafka: f1-telemetry
Kafka: f1-telemetry -> four GMM experts and a gating network -> Kafka: f1-anomalies
Kafka: f1-anomalies -> InfluxDB -> Grafana
```

The anomaly detector uses Gaussian Mixture Model (GMM) experts for tire, vehicle, driver-control, and power-system features. Docker Compose starts the Kafka, InfluxDB, Grafana, and anomaly-processing services.

## Quick start

Use Python 3.11 and Docker Compose v2. Clone the repository, then run these commands from its root:

```powershell
git clone https://github.com/VforVitorio/F1_AC_Digital_Twin.git
cd F1_AC_Digital_Twin
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
docker compose up -d
python scripts/testing/replay_telemetry_to_kafka.py --limit 1000
```

The replay command reads `data/processed/merged_telemetry_cleaned.csv` by default. Open Grafana at http://localhost:3000 or InfluxDB at http://localhost:8086. Local credentials are defined in `docker-compose.yml`.

Stop the services with `docker compose down`. The Compose file uses development credentials and publishes service ports. Change those settings before exposing the stack to an untrusted network.

## Live telemetry

Live collection requires Assetto Corsa running on Windows. From the repository root, run:

```powershell
python src/telemetry_collector.py --kafka
```

The collector sends data to Kafka at `localhost:9092` by default.

## Model workflows

- `deep-learning/behavioral-learning/N00_BL_data_split.ipynb` prepares lap-level train, validation, and test splits. `N01_BL_training.ipynb` trains the TCN.
- `deep-learning/anomaly-detection/` contains the data-preparation notebook and notebooks for the four experts and gating network.
- `scripts/training/` prepares anomaly data and trains the GMM experts and gating network.
- `models/` contains trained model artifacts and scalers. Telemetry samples and prepared data are under `data/`.

## Project paper

[Read the project paper](docs/F1_AC_Digital_Twin_Paper.pdf).

## Scope

The current code implements behavioral learning and anomaly detection. Reinforcement Learning is future work. See [the changelog](docs/CHANGELOG.md) for the release history.

## License

See [LICENSE](LICENSE).
