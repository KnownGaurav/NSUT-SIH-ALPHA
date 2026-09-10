# Railway Simulation Engine & Operational Disruption Modeling

## Problem Statement ID: 26028 &bull; Ministry of Railways

---

## 1. Objectives of the Simulation Engine

Live train tracking and dynamic ETA predictions require continuous high-frequency telemetry. When developing without live enterprise access to CRIS/NTES internal feeds, the **Railway Simulation Engine** provides authentic physical train movement and delay dynamics.

### Key Capabilities
- Accurate kinematic movement along authentic Indian Railways route stops (e.g. Howrah Rajdhani via Gaya, Vande Bharat, Tejas Rajdhani).
- Spherical great-circle bearing computation and coordinate interpolation.
- Real-time event injection to simulate real-world railway conditions (bottlenecks, speed restrictions, signals, and slack recovery).

---

## 2. Mathematical Kinematics

### 1. Great-Circle Distance (Haversine Formula)
Given two station coordinates $(\phi_1, \lambda_1)$ and $(\phi_2, \lambda_2)$:
$$a = \sin^2\left(\frac{\Delta \phi}{2}\right) + \cos \phi_1 \cdot \cos \phi_2 \cdot \sin^2\left(\frac{\Delta \lambda}{2}\right)$$
$$d = 2 R \cdot \text{atan2}\left(\sqrt{a}, \sqrt{1 - a}\right)$$
where $R = 6371.0\text{ km}$.

### 2. Forward Bearing
The compass heading $\theta \in [0^\circ, 360^\circ)$ along the track segment is computed as:
$$y = \sin(\Delta \lambda) \cdot \cos \phi_2$$
$$x = \cos \phi_1 \cdot \sin \phi_2 - \sin \phi_1 \cdot \cos \phi_2 \cdot \cos(\Delta \lambda)$$
$$\theta = (\text{atan2}(y, x) \cdot \frac{180}{\pi} + 360) \pmod{360}$$

### 3. Track Segment Interpolation
Train progress $t \in [0.0, 1.0]$ between Station $S_i$ and Station $S_{i+1}$:
$$\Delta d = \text{Speed} \times \Delta t_{\text{seconds}} \times \text{Multiplier}$$
$$t_{\text{new}} = t_{\text{old}} + \frac{\Delta d}{d_{\text{segment}}}$$
$$\phi(t) = \phi_1 + (\phi_2 - \phi_1) \cdot t$$
$$\lambda(t) = \lambda_1 + (\lambda_2 - \lambda_1) \cdot t$$

When $t \ge 1.0$, the locomotive triggers station arrival and advances to segment $i+1$.

---

## 3. Disruption Events & Delay Modulation

The simulator supports 5 operational events:

| Event | Speed Behavior | Delay Impact per Minute | Operational Realism |
| :--- | :--- | :--- | :--- |
| `NORMAL_OPERATION` | Cruising (~115 km/h) | Nominal ($\pm 0.0$ min) | Clear block signals on electrified double line. |
| `SPEED_RESTRICTION` | Decelerates to 40 km/h | Accumulates $+0.75$ min | Track maintenance, monsoon caution, or fog visibility restrictions. |
| `CONGESTION` | Queues at 20 km/h | Accumulates $+1.50$ min | Junction bottleneck, precedence crossing, or platform waiting outside terminal. |
| `UNSCHEDULED_HALT` | Dead stop (0 km/h) | Accumulates $+2.00$ min | Red signal check, loco failure, or emergency stop. |
| `RECOVERY` | Accelerates to 130 km/h | Recovers $-0.80$ min (down to 0) | High-speed priority run utilizing timetable slack and make-up margin. |

---

## 4. REST API Simulation Control

### 1. Trigger Simulation Event
`POST /api/simulator/event`
```json
{
  "train_number": "12302",
  "event": "CONGESTION"
}
```
**Response**:
```json
{
  "status": "ok",
  "train_number": "12302",
  "applied_event": "CONGESTION",
  "new_speed_kmh": 20.0,
  "current_delay_minutes": 14.5
}
```

### 2. Inspect Simulator State
`GET /api/simulator/status`
Returns all active trains, GPS coordinates, bearings, and delay states.

### 3. Advance Simulator Clock
`POST /api/simulator/tick`
```json
{
  "delta_seconds": 3.0,
  "speed_multiplier": 2.5
}
```

### 4. Reset Train to Origin
`POST /api/simulator/reset`
```json
{
  "train_number": "12302"
}
```
