# Railway Map & Train Tracking Architecture

## Problem Statement ID: 26028 &bull; Ministry of Railways

---

## 1. Design Principles & Operational Rationale

The primary user interface for railway operations must prioritize **information density**, **spatial clarity**, and **unambiguous state representation** over decorative visual effects.

In transportation control rooms:
1. **Low Distraction Basemap**: A high-contrast, dark-matter basemap (CartoDB Dark Matter / OpenStreetMap) isolates track geometry without competing urban/topographical noise.
2. **Track State Distinction**:
   - **Passed Route**: Rendered as a muted dashed line (`#64748b`), signaling traversed blocks.
   - **Upcoming Route**: Rendered as a crisp, high-contrast solid track line (`#38bdf8`), indicating scheduled path.
3. **Train Beacon & Color Semantics**:
   - The active locomotive marker is visually anchored by a subtle pulse beacon.
   - Color strictly corresponds to delay thresholds:
     - **Green (`#16a34a`)**: On-time ($\le 5$ minutes delay).
     - **Amber (`#d97706`)**: Moderate delay ($5 - 30$ minutes delay).
     - **Red (`#dc2626`)**: Severe / Critical delay ($> 30$ minutes delay).
4. **Provenance Transparency**:
   - If the active telemetry originates from the simulation engine, a high-visibility badge **`DEMO DATA`** is pinned to the header.

---

## 2. Component Hierarchy

```
App.jsx (Root Controller)
 ├── ops-header
 │    ├── Brand & Ministry Identification
 │    ├── Train Search & Selector Dropdown
 │    └── Provenance Badge (DEMO DATA / LIVE DATA)
 ├── ops-workspace
 │    ├── tracking-grid
 │    │    ├── RailwayMap (Leaflet GIS Layer)
 │    │    │    ├── TileLayer (CartoDB Dark Matter)
 │    │    │    ├── Route Polylines (Passed vs Upcoming)
 │    │    │    ├── Station Markers (Origin, Intermediate, Destination)
 │    │    │    └── Live Train Position Marker (DivIcon with Beacon Ring)
 │    │    └── Telemetry Sidebar (Selected Train, Velocity, Delay, GPS Coordinates)
 │    └── StationTimeline (Horizontal Sequenced Journey Progression)
 └── ops-footer
```

---

## 3. Data Flow & Endpoints

1. **Roster Loading**: `GET /api/trains` retrieves all registered coaching trains to populate the search selector.
2. **Route Alignment**: `GET /api/trains/{train_number}/route` returns sequenced station coordinates (`latitude`, `longitude`, `sequence`, `scheduled_arrival`, `scheduled_departure`, `distance_from_origin_km`).
3. **Real-Time Telemetry**: `GET /api/trains/{train_number}/position` returns:
   - Coordinates (`latitude`, `longitude`)
   - Speed in km/h (`speed_kmh`)
   - Delay in minutes (`current_delay_minutes`)
   - Delay status (`on_time`, `moderate`, `severe`)
   - Current and next station codes and resolved names
   - Source provenance (`SIMULATION` / `CRIS_NTES`)
4. **Dynamic Map Framing**: On train selection or route update, Leaflet computes the bounding box encompassing all station nodes and the active train position, executing a smooth `fitBounds()` animation with padding.

---

## 4. Responsive Adaptation

- **Desktop Displays (>1024px)**: 2-column layout with high-density GIS map taking 72% width and telemetry sidebar taking 28% width, followed by the full horizontal station journey line.
- **Tablets & Mobile (<1024px)**: Single-column stack with auto-resizing map container and swipeable horizontal timeline for field accessibility.
