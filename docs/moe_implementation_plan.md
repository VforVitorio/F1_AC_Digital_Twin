Perfecto! Ya tengo toda la información. Te voy a dar un **plan completo y detallado** para integrar el modelo de detección de anomalías MoE con Assetto Corsa y el dashboard de Grafana.

## 📋 PLAN DE INTEGRACIÓN: MoE Anomaly Detection → Kafka → Grafana

---

## 🎯 ARQUITECTURA PROPUESTA

```
Assetto Corsa (Shared Memory)
    ↓
Kafka Producer [EXISTENTE] → Topic: 'f1-telemetry' (datos RAW, 156 vars, 10 Hz)
    ↓
    ├──→ Consumer InfluxDB [EXISTENTE] → Grafana Telemetry Dashboard
    │
    └──→ [NUEVO] MoE Anomaly Consumer
            ↓
         1. Extrae features por experto (20+15+12+10 vars)
         2. Normaliza/escala datos
         3. Ejecuta modelo MoE (4 expertos + gating network)
         4. Calcula anomaly scores
            ↓
         Kafka Producer → Topic: 'f1-anomalies'
            ↓
         [NUEVO] Anomaly InfluxDB Consumer
            ↓
         InfluxDB (bucket: f1-anomalies)
            ↓
         [NUEVO] Grafana Anomaly Dashboard
```

---

## 📝 PASOS A SEGUIR

### **FASE 1: Preparación del Modelo MoE para Producción**

#### **Paso 1.1: Crear clase wrapper del modelo MoE**
**Archivo NUEVO**: `src/moe_inference.py`

**Funcionalidad**:
- Cargar los 4 expertos GMM + gating network desde `models/anomaly-detection/`
- Cargar configuración (`moe_config.json`) con features, thresholds, normalization params
- Método `predict()` que recibe telemetría raw y devuelve:
  - Anomaly score por experto
  - Anomaly score global (weighted)
  - Expert weights del gating network
  - Boolean: `is_anomaly` (True/False)
  - Tipo de anomalía detectada (tire, dynamics, control, power)

**Por qué**: El modelo está entrenado en notebooks, necesitamos una interfaz Python productiva que pueda usarse en streaming.

---

#### **Paso 1.2: Crear preprocesador de features en tiempo real**
**Archivo NUEVO**: `src/feature_processor.py`

**Funcionalidad**:
- Clase `RealTimeFeatureExtractor` que toma telemetría raw (dict con 156 vars)
- Extrae las 57 features del MoE organizadas por experto:
  - **Expert 1 (Tire)**: 20 features (TireTemp_*, TireWear_*, TirePressure_*, SlipRatio_*, SlipAngle_*)
  - **Expert 2 (Dynamics)**: 15 features (AccG_*, LocalVelocity_*, AngularVel_*, Heading, Pitch, Roll, TireLoad_*)
  - **Expert 3 (Control)**: 12 features (Speed_kmh, RPM, Throttle, Brake, Steering, Gear, TC_InAction, ABS_InAction, BrakeBias, BrakeTemp_*)
  - **Expert 4 (Power)**: 10 features (Fuel, TurboBoost, EngineTemp_Oil, CurrentMaxRpm, EngineBrake, KERS_*, ERS_*, DRS_Enabled)
- Normaliza usando los parámetros guardados en `*_metadata.json` (mean, std, scaler)
- Maneja valores faltantes/NaN (forward fill o interpolación)

**Por qué**: Los datos de Assetto Corsa vienen sin procesar. El modelo MoE espera features específicas y normalizadas.

---

### **FASE 2: Pipeline de Detección de Anomalías en Kafka**

#### **Paso 2.1: Crear consumidor MoE**
**Archivo NUEVO**: `scripts/streaming/kafka_moe_consumer.py`

**Funcionalidad**:
- Consume del topic `f1-telemetry` (consumer group: `moe-anomaly-detector`)
- Para cada mensaje (telemetría raw a 10 Hz):
  1. Extrae features usando `RealTimeFeatureExtractor`
  2. Ejecuta modelo MoE usando `MoEInference.predict()`
  3. Genera mensaje de anomalía con formato:
     ```json
     {
       "timestamp": "2025-12-07T17:48:04.123Z",
       "lap": 5,
       "distance": 1234.56,
       "is_anomaly": true,
       "anomaly_type": "tire_overheat",
       "expert_scores": {
         "tire": -120.45,      // Debajo del threshold → anomalía
         "dynamics": 15.23,
         "control": -25.10,
         "power": -22.34
       },
       "expert_weights": [0.65, 0.15, 0.10, 0.10],
       "global_score": -95.67,
       "severity": "high",     // high/medium/low
       "affected_component": "FL_tire",
       "details": {
         "TireTemp_FL_Avg": 125.5,
         "TireWear_FL": 0.92
       }
     }
     ```
  4. Publica al topic `f1-anomalies`

**Por qué**: Este es el cerebro del sistema, procesa streaming y detecta anomalías en tiempo real.

---

#### **Paso 2.2: Crear topic de anomalías**
**Archivo MODIFICADO**: `src/kafka_handlers.py`

Añadir función:
```python
def setup_anomaly_topic():
    """Crea topic 'f1-anomalies' con configuración optimizada"""
    # 1 partition, retention 7 días, cleanup policy delete
```

**Por qué**: Necesitamos un canal separado para anomalías (no mezclar con telemetría raw).

---

#### **Paso 2.3: Crear consumidor de anomalías → InfluxDB**
**Archivo NUEVO**: `scripts/streaming/kafka_anomaly_to_influxdb.py`

**Funcionalidad**:
- Consume del topic `f1-anomalies`
- Escribe a InfluxDB en bucket `f1-anomalies`:
  - **Measurement**: `anomaly_detection`
  - **Tags**: `anomaly_type`, `severity`, `expert`, `lap`, `session`
  - **Fields**: `global_score`, `expert_scores`, `expert_weights`, `is_anomaly`, `affected_component`
  - **Timestamp**: de la telemetría original

**Por qué**: Grafana lee de InfluxDB, necesitamos persistir las anomalías.

---

### **FASE 3: Visualización en Grafana**

#### **Paso 3.1: Crear dashboard de anomalías**
**Archivo NUEVO**: `grafana/dashboards/anomaly_dashboard.json`

**Paneles a incluir**:

1. **Anomaly Alert Bar** (arriba, destacado)
   - Muestra alertas activas en rojo/amarillo
   - Texto: "🚨 TIRE OVERHEAT DETECTED - FL Tire 125°C"
   - Query: `from(bucket: "f1-anomalies") |> filter(fn: (r) => r.is_anomaly == true)`

2. **Anomaly Timeline** (gráfico de líneas)
   - Eje Y: Anomaly score global
   - Líneas de threshold por experto
   - Anotaciones cuando `is_anomaly = true`

3. **Expert Scores Heatmap**
   - 4 filas (tire, dynamics, control, power)
   - Color: verde (normal) → rojo (anomalía)

4. **Expert Weights Bar Chart**
   - Muestra qué experto está "atendiendo" la situación actual
   - Actualización en tiempo real

5. **Anomaly Statistics** (contadores)
   - Total anomalías detectadas (última vuelta, sesión)
   - Anomalías por tipo (tire, dynamics, control, power)
   - Severity distribution

6. **Affected Components Table**
   - Lista de componentes con anomalías (FL tire, FR brake, etc.)
   - Última vez detectada

7. **Integration with Telemetry Dashboard** (panel combinado)
   - Superponer bandas rojas en gráficos de Speed/RPM cuando hay anomalía
   - Query secundaria que marca timestamps anómalos

**Por qué**: Visualización es clave para que los ingenieros vean anomalías en contexto.

---

#### **Paso 3.2: Modificar dashboard de telemetría existente**
**Archivo MODIFICADO**: `grafana/dashboards/telemetry_dashboard.json`

**Cambios**:
- Añadir query secundaria en paneles de Speed, RPM, TireTemp que consulte `f1-anomalies`
- Marcar regiones anómalas con bandas de color rojo/transparente
- Añadir variable `$anomaly_filter` para filtrar por tipo de anomalía

**Por qué**: Ver telemetría Y anomalías juntos ayuda a diagnosticar causas.

---

#### **Paso 3.3: Crear datasource de InfluxDB para anomalías**
**Archivo NUEVO**: `grafana/provisioning/datasources/influxdb_anomalies.yml`

```yaml
apiVersion: 1
datasources:
  - name: InfluxDB-Anomalies
    type: influxdb
    access: proxy
    url: http://influxdb:8086
    jsonData:
      version: Flux
      organization: f1-org
      defaultBucket: f1-anomalies
      tlsSkipVerify: true
    secureJsonData:
      token: f1-telemetry-token-super-secret
```

**Por qué**: Separar datos de telemetría y anomalías en buckets diferentes.

---

### **FASE 4: Configuración de Servicios Docker**

#### **Paso 4.1: Añadir servicio MoE al Docker Compose**
**Archivo MODIFICADO**: `docker-compose.yml`

Añadir servicio:
```yaml
  moe-anomaly-detector:
    build:
      context: .
      dockerfile: docker/Dockerfile.moe
    container_name: moe-detector
    depends_on:
      - kafka
      - schema-registry
    environment:
      KAFKA_SERVERS: kafka:9092
      KAFKA_INPUT_TOPIC: f1-telemetry
      KAFKA_OUTPUT_TOPIC: f1-anomalies
      MODEL_PATH: /app/models/anomaly-detection
    volumes:
      - ./models:/app/models:ro
      - ./src:/app/src:ro
    command: python scripts/streaming/kafka_moe_consumer.py
    restart: unless-stopped

  anomaly-to-influx:
    build:
      context: .
      dockerfile: docker/Dockerfile.anomaly_consumer
    container_name: anomaly-influx-writer
    depends_on:
      - kafka
      - influxdb
    environment:
      KAFKA_SERVERS: kafka:9092
      KAFKA_TOPIC: f1-anomalies
      INFLUX_URL: http://influxdb:8086
      INFLUX_BUCKET: f1-anomalies
    command: python scripts/streaming/kafka_anomaly_to_influxdb.py
    restart: unless-stopped
```

**Por qué**: Automatizar despliegue, los servicios se inician con `docker-compose up`.

---

#### **Paso 4.2: Crear Dockerfile para servicio MoE**
**Archivo NUEVO**: `docker/Dockerfile.moe`

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY scripts/ ./scripts/
COPY config.py .

# Los modelos se montan como volumen

CMD ["python", "scripts/streaming/kafka_moe_consumer.py"]
```

**Por qué**: Contenedorizar el servicio de detección.

---

### **FASE 5: Testing y Validación**

#### **Paso 5.1: Script de testing offline**
**Archivo NUEVO**: `scripts/testing/test_moe_pipeline.py`

**Funcionalidad**:
- Lee CSV de telemetría (ej. `data/raw/telemetry_2025-12-07_17-48-04.csv`)
- Simula streaming línea por línea
- Ejecuta pipeline completo:
  1. Feature extraction
  2. MoE inference
  3. Generación de mensajes de anomalía
- Guarda resultados en `data/testing/anomaly_results.csv`
- Visualiza scores con plotly

**Por qué**: Validar que el pipeline funciona ANTES de conectar a Kafka.

---

#### **Paso 5.2: Validación en Kafka con datos históricos**
**Archivo NUEVO**: `scripts/testing/replay_telemetry_to_kafka.py`

**Funcionalidad**:
- Lee CSV histórico
- Publica mensajes a `f1-telemetry` a 10 Hz (simulando Assetto Corsa)
- Permite probar todo el pipeline sin correr el juego

**Por qué**: Testing end-to-end del sistema de streaming.

---

### **FASE 6: Configuración y Documentación**

#### **Paso 6.1: Actualizar configuración**
**Archivo MODIFICADO**: `config.py`

Añadir:
```python
# MoE Anomaly Detection
MOE_MODEL_PATH = 'models/anomaly-detection'
KAFKA_ANOMALY_TOPIC = 'f1-anomalies'
KAFKA_MOE_CONSUMER_GROUP = 'moe-anomaly-detector'
INFLUX_ANOMALY_BUCKET = 'f1-anomalies'

# Anomaly thresholds (override si necesario)
ANOMALY_THRESHOLDS = {
    'tire': -94.07,
    'dynamics': 20.86,
    'control': -32.55,
    'power': -28.00
}
```

---

#### **Paso 6.2: Crear guía de uso**
**Archivo NUEVO**: `docs/guides/moe-real-time-integration.md`

**Contenido**:
- Arquitectura del sistema
- Cómo arrancar los servicios
- Cómo interpretar anomalías en Grafana
- Troubleshooting
- Cómo reentrenar modelos

---

## 📦 RESUMEN DE ARCHIVOS A CREAR/MODIFICAR

### **ARCHIVOS NUEVOS (10)**

| Archivo | Propósito |
|---------|-----------|
| `src/moe_inference.py` | Wrapper del modelo MoE para inferencia |
| `src/feature_processor.py` | Extracción y normalización de features |
| `scripts/streaming/kafka_moe_consumer.py` | Consumer que ejecuta MoE y detecta anomalías |
| `scripts/streaming/kafka_anomaly_to_influxdb.py` | Consumer que escribe anomalías a InfluxDB |
| `grafana/dashboards/anomaly_dashboard.json` | Dashboard principal de anomalías |
| `grafana/provisioning/datasources/influxdb_anomalies.yml` | Datasource para bucket de anomalías |
| `docker/Dockerfile.moe` | Dockerfile para servicio MoE |
| `scripts/testing/test_moe_pipeline.py` | Testing offline del pipeline |
| `scripts/testing/replay_telemetry_to_kafka.py` | Replay de datos históricos a Kafka |
| `docs/guides/moe-real-time-integration.md` | Documentación |

### **ARCHIVOS MODIFICADOS (3)**

| Archivo | Cambios |
|---------|---------|
| `docker-compose.yml` | Añadir servicios `moe-anomaly-detector` y `anomaly-to-influx` |
| `src/kafka_handlers.py` | Función `setup_anomaly_topic()` |
| `config.py` | Variables para MoE, topics, buckets |
| `grafana/dashboards/telemetry_dashboard.json` | Overlay de bandas de anomalías (opcional) |

---

## ⚙️ PROCESAMIENTO DE DATOS RAW

### **Problema**: Assetto Corsa envía 156 variables raw sin procesar

### **Solución por fases**:

#### **1. Feature Extraction** (`feature_processor.py`)
```python
def extract_moe_features(raw_telemetry: dict) -> dict:
    """
    Extrae las 57 features necesarias para MoE desde las 156 variables raw
    """
    features = {
        'expert1_tire': [
            raw['TireTemp_FL_Avg'], raw['TireTemp_FR_Avg'], ...  # 20 vars
        ],
        'expert2_dynamics': [
            raw['AccG_Lateral'], raw['LocalVelocity_X'], ...  # 15 vars
        ],
        'expert3_control': [
            raw['Speed_kmh'], raw['RPM'], ...  # 12 vars
        ],
        'expert4_power': [
            raw['Fuel'], raw['TurboBoost'], ...  # 10 vars
        ]
    }
    return features
```

#### **2. Normalización** (usar parámetros de training)
```python
# Cargar desde expert1_tire_metadata.json:
# { "feature_means": [...], "feature_stds": [...], "scaler_params": {...} }

def normalize_features(features, metadata):
    """Normaliza usando mean/std del training set"""
    return (features - metadata['feature_means']) / metadata['feature_stds']
```

#### **3. Inferencia MoE**
```python
def predict_anomalies(normalized_features):
    # 1. Pasar features a gating network → weights [0.6, 0.2, 0.1, 0.1]
    # 2. Ejecutar cada experto GMM → scores [-120, 15, -25, -22]
    # 3. Combinar: global_score = sum(weights * scores)
    # 4. Comparar con thresholds
    # 5. Clasificar anomalía
```

**NO necesitas Kafka para el preprocesamiento**, todo se hace **en memoria** en el consumer de MoE.

---

## 🚀 ORDEN DE IMPLEMENTACIÓN RECOMENDADO

### **Semana 1: Core MoE**
1. ✅ `src/moe_inference.py`
2. ✅ `src/feature_processor.py`
3. ✅ `scripts/testing/test_moe_pipeline.py` (validar offline)

### **Semana 2: Kafka Streaming**
4. ✅ Modificar `src/kafka_handlers.py` (topic de anomalías)
5. ✅ `scripts/streaming/kafka_moe_consumer.py`
6. ✅ `scripts/streaming/kafka_anomaly_to_influxdb.py`
7. ✅ `scripts/testing/replay_telemetry_to_kafka.py` (testing)

### **Semana 3: Visualización**
8. ✅ `grafana/provisioning/datasources/influxdb_anomalies.yml`
9. ✅ `grafana/dashboards/anomaly_dashboard.json`
10. ✅ (Opcional) Modificar `telemetry_dashboard.json`

### **Semana 4: Despliegue**
11. ✅ `docker/Dockerfile.moe`
12. ✅ Modificar `docker-compose.yml`
13. ✅ `docs/guides/moe-real-time-integration.md`
14. ✅ Testing end-to-end

---

## 🎯 RESULTADO FINAL

Una vez completado, tendrás:

✅ **Detección en tiempo real**: Anomalías detectadas cada 100ms (10 Hz)
✅ **Múltiples expertos**: 4 especialistas (tire, dynamics, control, power)
✅ **Dashboard profesional**: Visualización de anomalías en Grafana con alertas
✅ **Explicabilidad**: Sabes QUÉ experto detectó QUÉ anomalía y POR QUÉ
✅ **Escalabilidad**: Arquitectura basada en Kafka + Docker
✅ **Historicidad**: Todas las anomalías persistidas en InfluxDB
✅ **Testing**: Pipelines de validación offline y replay

---

¿Te parece bien este plan? ¿Quieres que empiece a implementar alguna fase en particular? Te recomendaría empezar por la **Fase 1** (core del modelo MoE) para validar que funciona offline antes de conectarlo a Kafka.
