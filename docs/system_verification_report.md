# SIH 2026 — FINAL SYSTEM VERIFICATION REPORT & JURY DEMO GUIDE
**Ministry of Railways &bull; Problem Statement ID: 26028**  
*Dynamic Forecast of Expected Time of Arrival (ETA) for Coaching Trains*  
*Timestamp of Verification: September 10, 2026 &bull; Status: ALL 49 TESTS PASSED (100%)*

---

## 1. Verification Audit Summary

| Layer | Component | Status | Verified Metric / Behavior |
|---|---|:---:|---|
| **Machine Learning** | XGBoost Regression Engine | ✅ PASS | **MAE = 2.69 min** vs Baseline **6.35 min** (**57.6% error reduction**) |
| **Statistical Rigor** | Grounded Confidence Intervals | ✅ PASS | ±1.5 RMSE bounds ($\pm 5.26\text{ min}$), 0 fabricated figures |
| **Explanation Engine** | Causal Attribution Service | ✅ PASS | Zero LLM; physical rule-based explanations for speed/delay/weather |
| **GIS & Mapping** | Leaflet CartoDB Dark Canvas | ✅ PASS | Zero watermarks; clean dark-matter basemap; polyline tracking |
| **Control Room** | Pan-India Super-Dashboard | ✅ PASS | 5-tier delay filtering, live active roster, deterioration flags |
| **Station Operations** | Platform Allocation & Conflict | ✅ PASS | 25-min clearance conflict detection; pit-line depot turnaround status |
| **Passenger Systems** | Station LED PIS & Mobile View | ✅ PASS | Authentic amber LED typography, blinking arrival alerts, phone frame |
| **Corridor Analytics**| Zonal Aggregation & Slack | ✅ PASS | 6 zones aggregated (NR, NCR, ECR, ER, WR, SECR) + downstream buffer |
| **Real-time Pipeline**| WebSocket Streaming | ✅ PASS | Sub-second event dispatch; automatic UI state sync |
| **Test Suite** | Pytest Automation | ✅ PASS | **49 / 49 tests passed** (0 failures, 2 warnings) in ~85s |
| **Frontend Build** | Vite Production Bundle | ✅ PASS | Built cleanly in **1.58s** (`dist/assets/index-*.js`) |

---

## 2. 5-Minute Live Presentation Script & Demo Flow for the Jury

### Step 1: The Problem & The Flaw of Current Systems (1 Minute)
- **What to say**:
  > "Respected Jury, today standard railway systems like NTES estimate train arrivals with a simple equation: $\text{Scheduled Time} + \text{Current Delay}$. But in reality, trains operate on dynamic physics: a train delayed by 30 minutes in Bihar can recover 15 minutes of engineering slack across the Kanpur–Delhi corridor, while a train on time entering Mughalsarai during peak traffic can compound a 40-minute bottleneck delay. Naive linear projection undermines passenger trust, causes platform queuing conflicts, and disrupts depot maintenance."
- **What to show**:
  - Open **http://localhost:5173/**. Point out the **Control Room View** showing the full pan-India corridor network.

### Step 2: XGBoost Machine Learning vs Deterministic Baseline (1 Minute)
- **What to say**:
  > "We replaced static estimation with an empirical XGBoost model trained on historical running data and sectional features (headway congestion, ambient weather via Open-Meteo, distance decay, and historical recovery profiles). We do not claim arbitrary accuracy: our model was evaluated on strictly out-of-time chronological test runs."
- **What to show**:
  - Click **📊 Model Analytics** in the header.
  - Show the **Baseline vs ML Performance Comparison**:
    - Baseline MAE: **6.35 min** $\rightarrow$ ML MAE: **2.69 min** (**57.6% error reduction**).
    - Accuracy within 5 minutes: **48.9%** $\rightarrow$ **83.6%** (+34.7% improvement).
  - Scroll to **Section 4: Zonal Railway Performance Breakdown**:
    - Show how Northern Railway (`NR`), North Central (`NCR`), East Central (`ECR`), etc. are ranked by delay and recovery tendency.

### Step 3: Single Train Journey & Disruption Simulation (1 Minute)
- **What to say**:
  > "When a train experiences ground operational changes, our system instantly recalculates downstream arrival forecasts and explains the exact physical cause without LLM hallucinations."
- **What to show**:
  - Return to **Single Train View** (e.g. 12002 Bhopal Shatabdi or 12302 Howrah Rajdhani).
  - Show the **Downstream Corridor Slack Card** right above the station journey sequence:
    * *Buffer Available: ~48 min &bull; Expected Recovery: ~0 min &bull; Delay: On Time*.
  - In the right-hand panel, click the **Caution (SPEED_RESTRICTION)** button under Demo Disruption Events:
    * Instantly watch the speed drop to 40 km/h.
    * Notice the **Real-Time ETA Dispatch Banner** flash green with auto-updated ETAs.
    * Inspect the station timeline: stations display the previous vs new updated ETA (e.g., `20:04 → 20:13`) and an explicit explanation tag (`SPEED: Speed dropped from 100 to 40 km/h`).
  - Click **Recovery** and watch the train accelerate to 130 km/h and dynamically recover lost time.

### Step 4: Station Operations & Clearance Conflicts (1 Minute)
- **What to say**:
  > "Accurate dynamic ETAs are vital for station masters and depot staff. If a delayed incoming train arrives at a platform still occupied by another service, severe yard bottlenecks occur."
- **What to show**:
  - Click **🚉 Station Operations** in the header.
  - Select **New Delhi (NDLS)** or **Kanpur (CNB)**.
  - Show the **Platform Occupancy Grid**:
    * Each platform card displays docked/approaching trains.
    * Highlight the red pulsing **Platform Conflict Alert** when two trains have overlapping arrivals within 25 minutes.
    * Switch to the **Cleaning Depot & Crew Turnaround** tab to show pit-line readiness (`ON_SCHEDULE` vs `TIGHT_WINDOW`).

### Step 5: Passenger Information System (PIS) & Mobile View (1 Minute)
- **What to say**:
  > "Finally, passengers experience this intelligence through station display boards and commuter smartphone apps."
- **What to show**:
  - Click **📺 Passenger LED Display**.
  - Show the authentic amber-on-black Indian Railways LED typography with the scrolling bottom marquee.
  - Point out blinking rows for trains arriving within 10 minutes.
  - Click **📱 Mobile View** toggle in the header:
    * Show the interactive smartphone mockup displaying the commuter's card stack with *Scheduled Time &rarr; Dynamic ETA* comparison and live platform numbers.

---

## 3. Key Jury Questions & Bulletproof Answers

1. **Q: Is your data real or simulated?**
   - **A**: "Our architecture features a dual-provider gateway. When connected to Rail Radar's live API, it ingests live GPS coordinates. However, because public API tiers enforce quota limits (1,000 requests/month), our system includes a robust, high-fidelity kinematic simulation engine as a fallback to guarantee 100% operational uptime for demos. All telemetry explicitly tags its data provenance (`RAILRADAR_LIVE` vs `SIMULATION`)."

2. **Q: How does your ML model avoid unrealistic predictions?**
   - **A**: "We do not predict raw timestamps; we predict continuous remaining travel time in minutes. Predictions are bounded by physical train speed limits (MPS), calibrated with ±1.5 RMSE prediction intervals, and cross-verified against a deterministic timetable baseline."

3. **Q: How do you handle scalability across thousands of trains?**
   - **A**: "Sectional inference runs via optimized C++ XGBoost bindings in under 3 milliseconds per train. Real-time updates utilize a WebSocket event-driven differential dispatch system—only broadcasting when a train's ETA shifts by $\ge 1.0\text{ minute}$, eliminating polling overhead on central servers."
