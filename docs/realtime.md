# Real-Time WebSocket ETA Updates Architecture

## Problem Statement ID: 26028 &bull; Ministry of Railways

---

## 1. Overview & Operational Protocol

Phase 10 replaces high-frequency client polling with an event-driven **WebSocket pub/sub dispatch pipeline**. When train state modulates—via kinematic movement, signal check queuing, speed restrictions, weather shifts, or recovery—the system calculates updated dynamic ETAs, evaluates the differential drift from previous station estimates, and pushes updates down the open socket.

```
                    +------------------------------------+
                    |  Train Movement / Disruption Event |
                    +-----------------+------------------+
                                      |
                                      v
                    +------------------------------------+
                    |  Live Train State Updated in Mem   |
                    +-----------------+------------------+
                                      |
                                      v
                    +------------------------------------+
                    |  Recalculate Dynamic ETA (XGBoost) |
                    +-----------------+------------------+
                                      |
                                      v
                    +------------------------------------+
                    |  Calculate Diff vs Previous ETA    |
                    |  - Detect Shifts (e.g. 20:04->20:13)|
                    |  - Attach update reason            |
                    +-----------------+------------------+
                                      |
                                      v
                    +------------------------------------+
                    |  Broadcast WS /ws/trains/{number}  |
                    +-----------------+------------------+
                                      |
                                      v
                    +------------------------------------+
                    |  Frontend UI (Subtle Glow / No     |
                    |  Full Page Refresh)                |
                    +------------------------------------+
```

---

## 2. WebSocket Specification

### Endpoint:
```
WS /ws/trains/{train_number}
```

### Connection Flow:
1. **Handshake**: Client connects to `WS /ws/trains/{train_number}`.
2. **Immediate Cache Dispatch**: `ConnectionManager` sends the latest known ETA state immediately to hydrate the client.
3. **Heartbeat / Ping**: Supports client ping/pong keep-alives (`"ping"` $\rightarrow$ `{"type":"pong"}`).
4. **Automatic Reconnection**: The React frontend client automatically reconnects with backoff if disconnected.

---

## 3. Station ETA Differential Detection

Station ETAs are compared against the previously broadcast prediction map:

```json
{
  "station_code": "CNB",
  "station_name": "Kanpur Central",
  "predicted_eta": "2026-09-10T21:48:00+00:00",
  "previous_eta": "2026-09-10T21:40:00+00:00",
  "eta_updated": true,
  "eta_shift_minutes": 8.0,
  "update_reason": "Section headway congestion & signal check queuing"
}
```

### Display Semantics on Frontend:
- **Station Transition**: Shows explicit time change:
  ```
  Kanpur Central
  21:40 → 21:48
  ```
- **Update Badge**: Displays subtle emerald badge:
  ```
  [ETA UPDATED]
  ```
- **Contextual Reason**: Renders operational explanation below the station name.

---

## 4. Components

- **WebSocket Manager & Diff Engine**: [`src/services/websocket_manager.py`](../src/services/websocket_manager.py)
- **Real-Time Recalculation Service**: [`src/services/realtime_service.py`](../src/services/realtime_service.py)
- **WebSocket Route**: [`src/api/ws.py`](../src/api/ws.py)
- **Frontend Live Subscription**: [`frontend/src/App.jsx`](../frontend/src/App.jsx)
- **Station Timeline Rendering**: [`frontend/src/components/StationTimeline.jsx`](../frontend/src/components/StationTimeline.jsx)
- **Automated Tests**: [`tests/test_realtime_ws.py`](../tests/test_realtime_ws.py)
