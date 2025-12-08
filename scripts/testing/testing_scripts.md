# Testing Scripts for MoE Anomaly Detection

Este directorio contiene scripts para validar y probar el pipeline de detección de anomalías.

## 📁 Scripts Disponibles

### 1. `validate_pipeline.py`

Valida que todos los componentes del pipeline estén correctamente configurados.

```powershell
# Validación básica (modelos + procesador)
python scripts/testing/validate_pipeline.py

# Validación completa (incluye Kafka + InfluxDB)
python scripts/testing/validate_pipeline.py --full
```

**Verifica:**

- ✅ Archivos de modelo existen
- ✅ Feature processor se inicializa
- ✅ MoE inference funciona
- ✅ Procesamiento de datos de ejemplo
- ✅ Conectividad Kafka (con `--full`)
- ✅ Conectividad InfluxDB (con `--full`)

---

### 2. `test_moe_pipeline.py`

Prueba offline del pipeline completo con datos históricos.

```powershell
# Procesar archivo de telemetría
python scripts/testing/test_moe_pipeline.py --input data/processed/merged_telemetry_cleaned.csv

# Procesar solo 1000 muestras con visualización
python scripts/testing/test_moe_pipeline.py --input data/raw/telemetry_2025-09-13.csv --limit 1000 --visualize
```

**Genera:**

- `data/testing/anomaly_results.csv`: Resultados de detección
- `data/testing/anomaly_scores.png`: Gráfico de scores (si `--visualize`)

---

### 3. `replay_telemetry_to_kafka.py`

Reproduce datos históricos en Kafka para testing end-to-end sin Assetto Corsa.

```powershell
# Replay a velocidad real (10 Hz)
python scripts/testing/replay_telemetry_to_kafka.py --input data/processed/merged_telemetry_cleaned.csv --rate 10

# Replay acelerado (100 Hz) - 10x más rápido
python scripts/testing/replay_telemetry_to_kafka.py --input data/processed/merged_telemetry_cleaned.csv --rate 100

# Replay solo 500 muestras
python scripts/testing/replay_telemetry_to_kafka.py --input data/processed/merged_telemetry_cleaned.csv --limit 500
```

**Genera:**

- `data/testing/replay_stats.json`: Estadísticas de replay

---

## 🚀 Flujo de Testing Recomendado

### Paso 1: Validar componentes

```powershell
python scripts/testing/validate_pipeline.py
```

### Paso 2: Test offline con datos históricos

```powershell
python scripts/testing/test_moe_pipeline.py --limit 1000 --visualize
```

### Paso 3: Test end-to-end con Kafka

```powershell
# Terminal 1: Iniciar MoE consumer
python scripts/streaming/kafka_moe_consumer.py

# Terminal 2: Iniciar anomaly writer
python scripts/streaming/kafka_anomaly_to_influxdb.py

# Terminal 3: Replay telemetría
python scripts/testing/replay_telemetry_to_kafka.py --rate 50 --limit 1000

# Terminal 4: Ver Grafana
# http://localhost:3000
```

---

## 📊 Archivos de Salida

| Archivo                   | Descripción                           |
| ------------------------- | ------------------------------------- |
| `validation_results.json` | Resultados de validación del pipeline |
| `anomaly_results.csv`     | Resultados de detección offline       |
| `replay_stats.json`       | Estadísticas de replay a Kafka        |
| `anomaly_scores.png`      | Visualización de scores               |

---

## ⚠️ Requisitos

1. **Docker corriendo**: Para tests con Kafka/InfluxDB

   ```powershell
   docker-compose up -d
   ```

2. **Modelos entrenados**: En `models/anomaly-detection/`

   - `gmm_expert*.pkl`
   - `gating_network.pkl`
   - `moe_config.json`
   - `scalers/expert*_scaler.pkl`

3. **Datos de telemetría**: En `data/processed/` o `data/raw/`
