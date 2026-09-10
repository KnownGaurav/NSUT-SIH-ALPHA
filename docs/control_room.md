# PHASE 12 — RAILWAY CONTROL ROOM DASHBOARD

## 1. Overview & Operational Philosophy

The Railway Control Room Dashboard is a dedicated **network supervision interface** designed for Chief Controllers, Section Controllers, and Traffic Supervisors. It is **NOT** a generic SaaS analytics dashboard with rounded cards, decorative graphs, or marketing visuals. 

### Key Design Pillars:
1. **MAP & TRAIN STATE DOMINANCE**: The interface is dominated by a pan-network geographical overview showing active routes, track blocks, and live train positions across Indian Railways corridors (e.g., Delhi–Howrah, Delhi–Varanasi, Delhi–Mumbai).
2. **OPERATIONAL STATUS COLOR SEMANTICS**: Status colors are used strictly where operationally meaningful:
   - **Green (`#22c55e`)**: On time (delay $\le 5$ min).
   - **Amber (`#f59e0b`)**: Moderate delay ($5$ to $30$ min).
   - **Red (`#ef4444`)**: Severe / critical delay ($> 30$ min).
   - **Pink/Magenta (`#f472b6`)**: Active deteriorating ETA trend.
3. **STRICT DISCIPLINE**: Zero gradients, zero neon glowing borders, zero unnecessary charts, and zero decorative AI graphics. High data density and utilitarian industrial dark UI (`#06090e`, `#0f1622`).
4. **EXPLICIT PROVENANCE**: Unambiguously displays `DATA SOURCE: SIMULATION` in the global header and telemetry cards.

---

## 2. Layout Structure

The Control Room features a 3-column operational command grid:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ [IR-COA] CENTRAL RAILWAY TRAFFIC CONTROL ROOM    [FILTERS]   [DATA SOURCE: SIMULATION]  │
├─────────────────────┬──────────────────────────────────────────┬───────────────────────┤
│ TRAIN ROSTER (290px)│ PAN-INDIA RAILWAY MAP (DOMINANT)         │ SELECTED TELEMETRY    │
│ • Search bar        │ • All active coaching trains plotted     │ • Train number & name │
│ • Filters:          │ • Corridors & route tracks rendered      │ • Speed & delay       │
│   - All             │ • Station nodes & tooltips               │ • Next station        │
│   - On time         │ • Click to focus and select train        │ • ML Dynamic ETA      │
│   - Moderate        │ • Color-coded operational status markers │ • Range & Confidence  │
│   - Severe delay    │                                          │ • ETA Change Reason   │
│   - Deteriorating   │                                          │ • Causal breakdown    │
└─────────────────────┴──────────────────────────────────────────┴───────────────────────┘
```

---

## 3. Architecture & API Endpoints

### Endpoint: `GET /api/trains/control-room/summary`
Returns an aggregated status of all registered trains, dynamic ETAs, delay classifications, and deterioration flags.

#### Response Structure (`ControlRoomSummary`):
```json
{
  "total_active_trains": 4,
  "on_time_count": 2,
  "delayed_count": 1,
  "severe_delay_count": 1,
  "deteriorating_count": 1,
  "data_source": "SIMULATION",
  "generated_at": "2026-09-10T13:45:00.000Z",
  "trains": [
    {
      "train_number": "12302",
      "train_name": "New Delhi - Howrah Rajdhani Express",
      "train_type": "Rajdhani Express",
      "source": "NDLS",
      "destination": "HWH",
      "source_name": "New Delhi",
      "destination_name": "Howrah Junction",
      "latitude": 27.1821,
      "longitude": 79.0123,
      "speed_kmh": 115.0,
      "current_delay_minutes": 12.0,
      "delay_status": "moderate",
      "current_station": "CNB",
      "next_station": "PRYJ",
      "next_station_name": "Prayagraj Junction",
      "operational_event": "NORMAL_OPERATION",
      "data_source": "SIMULATION",
      "predicted_eta": "2026-09-10T23:43:00",
      "baseline_eta": "2026-09-10T23:43:00",
      "eta_difference_minutes": 0.0,
      "eta_confidence": 0.88,
      "lower_bound": "2026-09-10T23:37:00",
      "upper_bound": "2026-09-10T23:49:00",
      "has_deteriorating_eta": false,
      "explanation_summary": "Sectional run on schedule within calibrated model tolerance.",
      "contributing_factors": []
    }
  ]
}
```

---

## 4. Frontend Component Breakdown

1. **`ControlRoomView.jsx`**:
   - Manages control room polling (every 3 seconds).
   - Pre-fetches route geometries across all active trains to draw multi-corridor network polylines.
   - Filter strip: All, On time ($\le 5$m), Moderate ($5\text{--}30$m), Severe ($>30$m), Deteriorating ETA.
   - Search box with instantaneous filtering by train number, train name, or station code.
   - Seamless two-way switching between **Control Room View** and **Single Train Tracking View**.

2. **`ControlRoomMap.jsx`**:
   - Pan-India extent (`[23.5, 80.0]` zoom 5) on CartoDB Dark Matter tiles.
   - Renders corridor railway tracks and station markers.
   - Interactive SVG train markers with operational status colors.
   - Click-to-select and automatic panning on train selection.

3. **Selected Train Telemetry Card**:
   - Train identity, current speed, and delay badge.
   - Block section & next stop indicator.
   - Dynamic ML Predicted ETA, baseline comparison, interval range, and statistical confidence.
   - ETA change attribution and deterministic contributing factors.
   - Direct button to inspect detailed timeline and simulator controls in single-train view.
