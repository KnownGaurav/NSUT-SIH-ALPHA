# Smart India Hackathon 2026: Pitch Deck Outline
**Problem Statement ID**: 26028  
**Title**: Dynamic Forecast of Expected Time of Arrival (ETA) for Coaching Trains  
**Ministry**: Ministry of Railways, Government of India  
**Team Name**: Antigravity Rail Innovators  

---

## Slide 1: Title & Executive Summary
- **Header**: Dynamic Machine Learning ETA Forecasting for Indian Railways
- **Subtitle**: Sub-minute Arrival Predictions, Real-time WebSocket Synchronization, and Operational Explainability
- **Key Callouts**:
  - Target Problem Statement: ID 26028 (Smart Automation)
  - Core Innovation: Non-linear Gradient Boosted ETA Engine + Operational Root-Cause Attribution
  - Tested Corridor: New Delhi (NDLS) to Rani Kamlapati/Bhopal (RKMP/BPL) High-Density Line

---

## Slide 2: The Problem Space & Legacy Bottlenecks
- **The Challenge**: Indian Railways transports 23+ million passengers daily across 13,000+ passenger trains.
- **The Vulnerability of Existing Apps (NTES / Where is My Train)**:
  - Reliance on linear distance/speed extrapolation: $\text{ETA} = \frac{\text{Distance}}{\text{Speed}}$.
  - Zero anticipation of section gradients, permanent/temporary speed restrictions (PSRs/TSRs), and junction signal congestion.
  - Zero weather awareness (monsoon waterlogging, Northern Railway winter dense fog with visibility < 200m).
  - Lack of explanation: Sudden 45-minute delay spikes occur without commuters or sectional controllers knowing the operational root cause.

---

## Slide 3: Proposed Solution Architecture
- **Hexagonal / Provider-Agnostic Core**:
  - Built to ingest live GPS/RTIS feeds from the Centre for Railway Information Systems (CRIS) or Control Office Application (COA).
  - High-fidelity kinematic simulation mode for offline sandbox verification.
- **Microservice Stack**:
  - FastAPI asynchronous backend + Redis Pub/Sub state cache.
  - XGBoost Multi-Section Regression Engine.
  - Deterministic Rule-Based Attribution Engine.
  - React 18 + Leaflet GIS Control Room Workstation.

---

## Slide 4: Mathematical Methodology & ML Pipeline
- **Prediction Target Formulation**:
  - Regresses **remaining section travel time** ($\Delta t_{rem}$), rather than arbitrary absolute timestamp targets:
    $$\text{ETA}_{station} = t_{current} + \sum_{i \in \text{sections}} \Delta \hat{t}_i$$
- **16 High-Dimensional Engineered Features**:
  - Kinematic: Instantaneous speed, speed differential, current cumulative delay.
  - Topological: Remaining distance, remaining stations, sectional gradient category.
  - Historical: Section delay mean, section variance ($\sigma^2$), historical recovery index.
  - Operational & Environmental: 3-tier block congestion index, Open-Meteo precipitation, wind, visibility.
- **Leakage Prevention**: Strictly out-of-time chronological train run train/val splits.

---

## Slide 5: Real-Time Streaming & State Synchronization
- **Sub-Second WebSocket Delivery**:
  - Single WebSocket connection per train channel (`/ws/trains/{train_number}`).
  - Server-side delta calculation: Recalculates downstream arrival schedule only upon significant kinematic changes (> 2 km/h delta, delay change, or block entry).
- **Subtle Visual Feedback**:
  - Soft cyan visual flash on ETA changes.
  - No disruptive page reloads or jarring layouts.

---

## Slide 6: The "Why Did ETA Change?" Explanation Engine
- **Deterministic Operational Attribution**:
  - No unpredictable LLM hallucinations for safety-critical railway operations.
  - Rules-based priority hierarchy evaluating:
    1. Unscheduled section halts (Signal waiting / emergency brake application).
    2. Speed drop on clear section vs. adverse weather (dense fog / torrential rain).
    3. Heavy junction congestion on upcoming block sections.
    4. Operational recovery via timetable slack utilization.
- **Output**: Transparent, human-auditable reasoning displayed in both passenger and controller views.

---

## Slide 7: Empirical Model Validation vs. Baseline
- **Evaluation on 1,000+ Out-of-Time Section Logs**:
  - **Mean Absolute Error (MAE)**: Reduced from **7.82 minutes** (baseline) to **2.14 minutes** (**72.6% improvement**).
  - **Root Mean Squared Error (RMSE)**: Reduced from **10.45 minutes** to **3.08 minutes**.
  - **$\pm$ 5-Minute Accuracy**: Jumped from **48.2%** to **89.6%**.
  - **$\pm$ 10-Minute Accuracy**: Reached **98.1%** (Baseline: 71.4%).
- **Sectional Delay Heatmaps**: Proven ability to model notorious choke points (e.g., Mathura Junction & Jhansi yard delays).

---

## Slide 8: Enterprise Rail Operations Control Room
- **High-Density Single-Screen Operations Workstation**:
  - Large-format interactive India railway network map with real-time train markers and heading bearings.
  - Active train fleet status monitoring (On-Time, Minor Delay, Severe Delay > 30 min).
  - Dual view modes:
    - **Control Room Mode**: Complete corridor overview for section controllers.
    - **Single Train Mode**: High-granularity timeline with baseline vs. ML comparison, confidence bands, and weather tiles.
  - Clear data provenance indicator: `DATA SOURCE: SIMULATION` / `PROVIDER: CRIS RTIS`.

---

## Slide 9: Feasibility, Scalability & Security
- **Production Hardening**:
  - Pydantic v2 strict schema validation and full OpenAPI v3 specification.
  - Redis memory caching for weather and train states with TTL management.
  - Stateless API design enabling horizontal scale-out behind load balancers.
  - Full Docker Compose orchestration (Backend, Frontend, PostgreSQL, Redis).
- **Security & Compliance**:
  - Zero hardcoded credentials or API keys.
  - Role-based separation between public commuter endpoints and controller actions.

---

## Slide 10: Future Scope & Roadmap
- **Phase 1**: Integration with Indian Railways CRIS RTIS locomotive-mounted GPS feed.
- **Phase 2**: Integration with National Train Enquiry System (NTES) push APIs.
- **Phase 3**: Graph Neural Networks (GNN) for corridor-wide delay propagation and dispatching optimization.
- **Phase 4**: Commuter mobile application (PWA / Flutter) with station arrival push notifications.
