# MoE Anomaly Detection System - Quick Start Guide

**Sistema completo de detección de anomalías en tiempo real para F1 Digital Twin**

---

## 🎯 Resumen del Sistema

El sistema MoE (Mixture of Experts) detecta anomalías en tiempo real usando 4 expertos especializados:
- **Expert 1**: Tire Dynamics (neumáticos)
- **Expert 2**: Vehicle Dynamics (dinámica del vehículo)
- **Expert 3**: Driver Control (control del piloto)
- **Expert 4**: Power Systems (sistemas de potencia)

---

## 📋 Arquitectura del Sistema

```
Assetto Corsa (Shared Memory)
    ↓
Producer Kafka → Topic: f1-telemetry (10 Hz, 156 vars)
    ↓
    ├── MoE Consumer (procesa anomalías)
    │   ↓
    │   Topic: f1-anomalies
    │   ↓
    │   InfluxDB Writer → Bucket: f1-anomalies
    │   ↓
    │   Grafana Dashboard (visualización)
    │
    └── Telemetry Consumer (opcional)
        ↓
        InfluxDB → Bucket: f1-telemetry
        ↓
        Grafana Telemetry Dashboard
```

---

## 🚀 Iniciar el Sistema Completo

### **Paso 1: Iniciar servicios Docker**

```bash
cd "c:\Users\victo\Desktop\Documents\Cuarto Año\Primer Cuatrimestre\F1_AC_Digital_Twin"

# Iniciar todos los servicios (Kafka, InfluxDB, Grafana)
docker-compose up -d
```

Verifica que estén corriendo:
```bash
docker-compose ps
```

### **Paso 2: Crear bucket de InfluxDB para anomalías**

**Opción A: Desde UI de InfluxDB** (recomendado)
1. Abre http://localhost:8086
2. Login: admin / admin
3. Ve a "Buckets" → "Create Bucket"
4. Nombre: `f1-anomalies`
5. Retention: 7 days
6. Clic en "Create"

**Opción B: Desde línea de comandos**
```bash
docker exec -it influxdb influx bucket create \
  -n f1-anomalies \
  -o f1-org \
  -r 7d
```

### **Paso 3: Iniciar Assetto Corsa y Producer**

**Terminal 1 - Producer de telemetría:**
```bash
python scripts/playground/S03_kafka_producer.py
```

Deberías ver:
```
✅ Producer configured successfully
✅ Topic 'f1-telemetry' created successfully
Publishing telemetry at 10 Hz...
```

### **Paso 4: Iniciar MoE Consumer** (NUEVO)

**Terminal 2 - Detector de anomalías:**
```bash
python scripts/streaming/kafka_moe_consumer.py
```

Deberías ver:
```
============================================================
INITIALIZING MoE ANOMALY DETECTOR
============================================================
INFO:feature_processor:Loaded scaler for expert1_tire
INFO:moe_inference:Loaded expert1_tire: gmm_expert1_tire.pkl
...
✅ MoE Anomaly Detector initialized successfully

============================================================
STARTING MoE ANOMALY DETECTION STREAM
============================================================
```

Cuando detecte anomalías:
```
🚨 ANOMALY DETECTED: tire_anomaly (severity: high, lap: 5, prob: 0.987)
📊 Stats: 1000 msgs, 45 anomalies (4.5%), 10.2 msg/s, 0 errors
```

### **Paso 5: Iniciar InfluxDB Writer** (NUEVO)

**Terminal 3 - Escritor de anomalías a InfluxDB:**
```bash
python scripts/streaming/kafka_anomaly_to_influxdb.py
```

Deberías ver:
```
============================================================
INITIALIZING ANOMALY INFLUXDB WRITER
============================================================
✅ Subscribed to Kafka topic: f1-anomalies
✅ Connected to InfluxDB

============================================================
STARTING ANOMALY → INFLUXDB STREAM
============================================================
```

Cuando escriba anomalías:
```
📝 Wrote anomaly to InfluxDB: vehicle_dynamics (severity: medium, lap: 3, prob: 0.756)
```

### **Paso 6 (Opcional): Consumer de telemetría normal**

**Terminal 4 - Para dashboard de telemetría:**
```bash
python scripts/playground/S03_kafka_consumer.py
```

---

## 📊 Ver Dashboards en Grafana

### **Acceder a Grafana**

1. Abre http://localhost:3000
2. Login: `admin` / `admin`
3. Dashboards → Browse

### **Dashboard de Anomalías** (NUEVO)

**Nombre**: F1 MoE Anomaly Detection

**Paneles incluidos:**
1. **🚨 Anomaly Alert** (arriba) - Alerta roja cuando hay anomalía activa
2. **Global Anomaly Score Timeline** - Evolución del score global
3. **Expert Scores** (4 paneles) - Scores individuales de cada experto con thresholds
4. **Recent Anomalies Table** - Tabla de anomalías recientes con timestamp, tipo, severidad
5. **Anomaly Type Distribution** - Gráfico de torta con distribución por tipo
6. **Average Expert Weights** - Gráfico de barras con pesos promedio (atención)
7. **Statistics** (4 stats):
   - Total anomalies detected
   - Last anomaly probability
   - Current severity
   - Current anomaly type

**Refresh rate**: 100ms (actualización en tiempo real)

**Rango de tiempo recomendado**: Last 5 minutes

---

## 🔍 Interpretar los Resultados

### **Tipos de Anomalías**

| Tipo | Qué Significa | Posibles Causas |
|------|---------------|-----------------|
| `tire_anomaly` | Expert 1 detectó problema en neumáticos | Sobrecalentamiento, desgaste excesivo, pérdida de presión, slip excesivo |
| `vehicle_dynamics` | Expert 2 detectó problema en dinámica | G-forces imposibles, pérdida de downforce, vuelta campana, airborne |
| `driver_control` | Expert 3 detectó problema en control | Throttle+brake simultáneo, marcha incorrecta, sobre-steering |
| `power_system` | Expert 4 detectó problema en potencia | Uso subóptimo de ERS, DRS mal usado, motor sobrecalentado |
| `multiple` | Múltiples expertos detectaron anomalías | Situación compleja o crítica |

### **Niveles de Severidad**

- **LOW** (verde): Anomalía menor, score desviado <20% del threshold
- **MEDIUM** (naranja): Anomalía moderada, desviación 20-50%
- **HIGH** (rojo): Anomalía severa, desviación >50% del threshold

### **Expert Weights (Atención)**

Los pesos muestran qué experto está "atendiendo" la situación actual:
- **Tire dominante** → Situación relacionada con neumáticos (curvas, frenadas)
- **Dynamics dominante** → Situación de alta dinámica (G-forces, cambios direccionales)
- **Control dominante** → Situación de control del piloto (aceleración, frenado)
- **Power dominante** → Situación de gestión de potencia (recto, overtake)

### **Scores de Expertos**

Cada experto tiene un threshold diferente:
- **Expert 1 (Tire)**: threshold = -94.075 → anomalía si score **< threshold** (más negativo)
- **Expert 2 (Dynamics)**: threshold = 20.860 → anomalía si score **> threshold**
- **Expert 3 (Control)**: threshold = -32.553 → anomalía si score **< threshold**
- **Expert 4 (Power)**: threshold = -27.998 → anomalía si score **< threshold**

---

## 🛠️ Testing Offline (sin Kafka)

Para probar el pipeline MoE con datos históricos:

```bash
# Test básico con 1000 samples
python scripts/testing/test_moe_pipeline.py --limit 1000 --visualize

# Test completo con archivo específico
python scripts/testing/test_moe_pipeline.py \
  --input "data/raw/telemetry_2025-12-07_17-48-04.csv" \
  --limit 5000 \
  --visualize

# Resultados se guardan en:
# - data/testing/anomaly_results_<timestamp>.csv
# - data/testing/visualizations_<timestamp>/
```

---

## 📈 Queries Útiles en Grafana

### **Contar anomalías por tipo (última hora)**
```flux
from(bucket: "f1-anomalies")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "anomaly_detection")
  |> filter(fn: (r) => r["is_anomaly"] == "True")
  |> filter(fn: (r) => r["_field"] == "global_score")
  |> group(columns: ["anomaly_type"])
  |> count()
```

### **Score promedio de cada experto**
```flux
from(bucket: "f1-anomalies")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "anomaly_detection")
  |> filter(fn: (r) => r["_field"] =~ /expert.*_score/)
  |> mean()
```

### **Últimas 10 anomalías**
```flux
from(bucket: "f1-anomalies")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "anomaly_detection")
  |> filter(fn: (r) => r["is_anomaly"] == "True")
  |> filter(fn: (r) => r["_field"] == "anomaly_probability")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 10)
```

---

## 🐛 Troubleshooting

### **Problem: No aparecen anomalías**

**Solución:**
1. Verifica que el MoE consumer esté corriendo
2. Revisa logs: `📊 Stats: X msgs, Y anomalies`
3. Las anomalías son detectadas por thresholds del 95% percentil, así que son relativamente raras (esperado: 5-20% de anomaly rate)

### **Problem: InfluxDB no tiene datos**

**Solución:**
1. Verifica que el bucket `f1-anomalies` existe
2. Revisa logs del InfluxDB writer
3. Comprueba conexión: `docker logs influxdb`

### **Problem: Grafana no muestra datos**

**Solución:**
1. Verifica que el datasource `InfluxDB-Anomalies` esté configurado
2. Test connection en Settings → Data Sources
3. Revisa que la query use el bucket correcto: `f1-anomalies`
4. Ajusta el time range (prueba con Last 5 minutes)

### **Problem: Scores son NaN o infinitos**

**Solución:**
1. Esto puede ocurrir con datos mock no realistas
2. Usa datos reales de Assetto Corsa
3. Verifica que los scalers carguen correctamente
4. Revisa logs del feature processor

---

## 📝 Archivos Importantes

### **Configuración**
- `config.py` - Configuración central
- `.env` - Variables de entorno
- `docker-compose.yml` - Servicios Docker

### **Modelos MoE**
- `models/anomaly-detection/` - Modelos entrenados (.pkl)
  - `gmm_expert1_tire.pkl` (50.6 KB)
  - `gmm_expert2_dynamics.pkl` (28.7 KB)
  - `gmm_expert3_control.pkl` (19.3 KB)
  - `gmm_expert4_power.pkl` (14.0 KB)
  - `gating_network.pkl` (791 bytes)
  - `moe_config.json` - Configuración de thresholds

### **Scalers**
- `data/processed/MoE-anomaly/scalers/` - StandardScalers (.pkl)
  - Necesarios para normalizar datos en streaming

### **Scripts de Streaming** (NUEVOS)
- `scripts/streaming/kafka_moe_consumer.py` - Consumer MoE
- `scripts/streaming/kafka_anomaly_to_influxdb.py` - Writer InfluxDB

### **Dashboards**
- `grafana/dashboards/anomaly_dashboard.json` - Dashboard de anomalías
- `grafana/dashboards/telemetry_dashboard.json` - Dashboard de telemetría

---

## 🎓 Próximos Pasos

### **Mejoras Sugeridas:**
1. **Alertas automáticas**: Configurar alertas en Grafana para anomalías HIGH
2. **Correlación con telemetría**: Superponer anomalías en dashboard de telemetría
3. **Dashboard combinado**: Panel que muestre telemetría + anomalías juntos
4. **Reentrenamiento**: Actualizar modelos con nuevos datos periódicamente
5. **Exportación**: Guardar anomalías en CSV para análisis offline

### **Análisis Avanzado:**
1. Estudiar patrones de anomalías por circuito
2. Correlación entre anomalías y lap times
3. Detección de degradación de neumáticos
4. Predicción de fallos mecánicos

---

## ✅ Checklist de Deployment

- [ ] Docker services running (kafka, influxdb, grafana)
- [ ] Bucket `f1-anomalies` created in InfluxDB
- [ ] Datasource `InfluxDB-Anomalies` configured in Grafana
- [ ] Dashboard `F1 MoE Anomaly Detection` imported
- [ ] Assetto Corsa running
- [ ] Kafka producer running (S03_kafka_producer.py)
- [ ] MoE consumer running (kafka_moe_consumer.py)
- [ ] InfluxDB writer running (kafka_anomaly_to_influxdb.py)
- [ ] Grafana dashboard showing live data

---

**¡Sistema listo para detectar anomalías en tiempo real!** 🚀
