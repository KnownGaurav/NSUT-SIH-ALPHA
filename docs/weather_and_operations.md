# Weather Integration & Operational Conditions Pipeline

## Problem Statement ID: 26028 &bull; Ministry of Railways

---

## 1. Environmental Weather Provider Architecture

In coaching train operations across Indian Railways, severe environmental phenomena (dense north-Indian winter fog, monsoon cloudbursts, severe cyclonic wind restrictions) directly impact track capacity, visibility restrictions, and permissible section speeds.

### Key Architectural Guidelines
1. **Never Call External Weather APIs from the Frontend**: All weather queries are handled exclusively by the backend via [`src/services/weather_service.py`](../src/services/weather_service.py).
2. **Provider Integration**: Interacts with the **Open-Meteo Weather API** using non-blocking asynchronous HTTP (`httpx.AsyncClient`).
3. **Spatial Grid Quantization & Caching**:
   - Track coordinates are quantized to a 0.1-degree spatial grid (~11 km resolution) to maximize cache hits along identical rail corridors.
   - Cache TTL is set to **15 minutes** (900 seconds) to prevent redundant upstream API requests.
4. **Graceful Operational Fallback**: If Open-Meteo is temporarily unreachable or experiences timeout, the service automatically falls back to an operational baseline estimate without failing the ETA prediction pipeline.

### Normalized Features Extracted:
- `temperature_c`: Ambient temperature in Celsius.
- `precipitation_mm`: Hourly rainfall / precipitation.
- `wind_speed_kmh`: Surface wind velocity (critical for coastal/ghat sections).
- `visibility_km`: Atmospheric visibility distance.
- `weather_condition`: WMO standard weather code description (e.g., Clear sky, Moderate rain, Dense fog).
- `is_severe_weather`: Flag indicating caution conditions ($< 2.0\text{ km}$ visibility or thunderstorms).

---

## 2. Corridor Congestion Estimation & Data Limitations

### Data Provenance & Limitations Statement
> [!IMPORTANT]
> **Data Integrity & Honesty Principle**:
> This platform **does NOT pretend to access internal Indian Railways signalling circuits, axle-counter data, or live COA/NTES block section feeds**, as these are private to the Ministry of Railways/CRIS.
> Instead, corridor congestion is modeled via a transparent **prototype simulation and operational network indicator**:

### Congestion Levels:
- **`LOW`** (Score $\le 0.30$): Normal line throughput, permissible headway, and track block clearance.
- **`MEDIUM`** (Score $0.31 - 0.70$): Sectional latency, cautionary speed restrictions, or moderate delay accumulation.
- **`HIGH`** (Score $> 0.70$): Bottleneck queuing, signal checks, or unscheduled halts.

---

## 3. Dynamic ETA Engine Response to Operational Disruption Events

The Dynamic ETA Engine responds dynamically to the active operational condition:

| Disruption Event | Physical Kinematics | Congestion Level | Dynamic ETA Adjustment |
| :--- | :--- | :---: | :--- |
| **`NORMAL_OPERATION`** | Line speed ($100-120\text{ km/h}$) | `LOW` | Pure XGBoost regression against timetable schedule |
| **`SPEED_RESTRICTION`** | Caution order ($40\text{ km/h}$) | `MEDIUM` | Section running time increased proportionally to speed limit |
| **`CONGESTION`** | Queuing / signal checks ($20\text{ km/h}$) | `HIGH` | $+25\%$ headway latency buffer added |
| **`UNSCHEDULED_HALT`** | Train stalled ($0\text{ km/h}$) | `HIGH` | Instantaneous delay increment $+6.0\text{ min}$ buffer |
| **`RECOVERY`** | High-priority green corridor ($130\text{ km/h}$) | `LOW` | Timetable slack recovery up to $10\%$ duration reduction |
| **Severe Weather** | Low visibility / heavy monsoon rain | `MEDIUM` / `HIGH` | Environmental safety factor added ($+0.8$ to $+2.0\text{ min}/100\text{km}$) |

---

## 4. API Endpoints

### 1. `GET /api/trains/{train_number}/position`
Includes `weather` and `congestion` blocks in real time.

### 2. `GET /api/trains/{train_number}/eta`
Includes `weather`, `congestion`, `operational_event`, and updated station predictions.
