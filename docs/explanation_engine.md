# PHASE 11 — DETERMINISTIC ETA CHANGE EXPLANATION ENGINE

## 1. Executive Summary & Design Principles

In railway operations and traffic control systems (Section Controller / Train Management System), explaining **why an Expected Time of Arrival (ETA) changed** requires operational transparency, physical credibility, and verifiable telemetry evidence.

### Core Architectural Directives
1. **NO LLM FOR CORE PREDICTION OR ATTRIBUTION**: Large Language Models hallucinate, exhibit non-deterministic behavior, and lack real-time causal grounding with track geometry and block signalling. The explanation engine is 100% rule-deterministic, inspecting telemetry metrics directly.
2. **VERIFIED OPERATIONAL EVIDENCE**: An explanation factor is only emitted if supported by concrete physical evidence (e.g. speed drops $\ge 15$ km/h, delay accumulation $\ge 1.0$ min, caution orders, active track block congestion, or extreme meteorological thresholds).
3. **OPERATIONAL TERMINOLOGY**: The engine employs clear Indian Railways operations terminology (block sections, caution orders, sectional headway, red signal aspect, timetable slack recovery) without marketing jargon.

---

## 2. Factor Attribution Rules & Thresholds

The explanation engine (`src/services/explanation_service.py`) evaluates the operational delta across 6 distinct categories:

| Category | Trigger Conditions | Operational Direction | Metric Evidence Example |
| :--- | :--- | :--- | :--- |
| **SPEED** | $\Delta v \le -15\text{ km/h}$ or $v < 45\text{ km/h}$ | `INCREASED_ETA` | `"Speed decreased from 115.0 km/h to 38.0 km/h"` |
| **SPEED** | $\Delta v \ge +15\text{ km/h}$ | `DECREASED_ETA` | `"Speed increased from 40.0 km/h to 105.0 km/h"` |
| **DELAY** | $\Delta d \ge +1.0\text{ min}$ cumulative delay drift | `INCREASED_ETA` | `"Delay increased by +4.0 min (now +14.5 min)"` |
| **DELAY** | $\Delta d \le -1.0\text{ min}$ cumulative delay recovery | `DECREASED_ETA` | `"Delay reduced by 3.5 min (now +4.0 min)"` |
| **CONGESTION** | Event is `CONGESTION` or level is `HIGH` | `INCREASED_ETA` | `"Congestion status: HIGH, Event: CONGESTION"` |
| **CONGESTION** | Event is `SPEED_RESTRICTION` or level is `MEDIUM` | `INCREASED_ETA` | `"Active restriction: SPEED_RESTRICTION"` |
| **STATION_HALT** | Train stalled outside station ($v < 1.0\text{ km/h}$ or `UNSCHEDULED_HALT`) | `INCREASED_ETA` | `"Locomotive halted outside station at red signal aspect"` |
| **RECOVERY** | Operational event is `RECOVERY` with negative delay drift | `DECREASED_ETA` | `"Priority green signal aspect assigned; timetable slack"` |
| **WEATHER** | Visibility $< 2.0\text{ km}$, rain $> 15.0\text{ mm}$, or severe flag | `INCREASED_ETA` | `"Visibility: 0.8 km, Rain: 24.5 mm (Dense Fog)"` |

---

## 3. Data Flow & System Integration

```
[Locomotive GPS / Simulator / Signal State]
                    │
                    ▼
          NormalizedTrainState
                    │
                    ▼
          Dynamic ETA Recalculation (XGBoost)
                    │
                    ▼
       ConnectionManager (WebSocket Manager)
   ┌────────────────────────────────────────────────┐
   │ 1. Compare station ETA against previous cache  │
   │ 2. Detect timestamp drift (|Δt| >= 0.5 min)    │
   │ 3. Evaluate ExplanationEngine.explain_eta_change│
   └────────────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
 WebSocket Push Broadcast    REST API Endpoint
 (/ws/trains/{train_num})    (GET /api/trains/{train_num}/eta/explanation)
        │                       │
        └───────────┬───────────┘
                    ▼
     Frontend Dashboard (React + Leaflet)
   ┌────────────────────────────────────────────────┐
   │ • Compact "WHY DID ETA CHANGE?" Card in Sidebar│
   │ • Station Timeline with Cause Tags & Evidence   │
   │ • Subtle Transition (No Jarring Animations)    │
   └────────────────────────────────────────────────┘
```

---

## 4. API Endpoints and Schema

### Endpoint: `GET /api/trains/{train_number}/eta/explanation`

#### Response Schema (`ETAExplanationResponse`):
```json
{
  "train_number": "12301",
  "station_code": "CNB",
  "station_name": "Kanpur Central",
  "previous_eta": "2026-09-10T21:40:00",
  "new_eta": "2026-09-10T21:49:00",
  "shift_minutes": 9.0,
  "direction": "DELAY_INCREASED",
  "summary": "ETA deferred by approximately 9.0 minutes due to operational factors.",
  "contributing_factors": [
    {
      "category": "SPEED",
      "direction": "INCREASED_ETA",
      "impact_description": "Train speed dropped significantly below permissible sectional velocity",
      "metric_evidence": "Speed decreased from 112.0 km/h to 38.0 km/h"
    },
    {
      "category": "DELAY",
      "direction": "INCREASED_ETA",
      "impact_description": "Cumulative operational delay accumulated along block section",
      "metric_evidence": "Delay increased by +9.0 min (now +14.5 min)"
    },
    {
      "category": "CONGESTION",
      "direction": "INCREASED_ETA",
      "impact_description": "Speed restriction / cautionary order active on track block",
      "metric_evidence": "Active restriction: SPEED_RESTRICTION"
    }
  ],
  "generated_at": "2026-09-10T13:41:20.123456Z"
}
```

---

## 5. UI Presentation Standards

In accordance with strict railway operations ergonomics:
- **No excessive animations**: Only a calm border glow and subtle font badge indicate that an update was received.
- **Color Coding**:
  - `DELAY_INCREASED`: Amber border (`#f59e0b`) indicating timetable slippage.
  - `DELAY_REDUCED`: Emerald border (`#10b981`) indicating positive recovery.
  - `UNCHANGED`: Cyan/Blue border (`#38bdf8`).
- **Compact Telemetry Breakdown**: Displayed in the operational sidebar directly below the active track block indicator, as well as contextual factor tags along the upcoming station journey timeline.
