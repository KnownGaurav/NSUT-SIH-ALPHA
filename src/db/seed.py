import logging
from datetime import datetime, date, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import (
    Train, Station, Route, RouteStation, TrainRun,
    LivePosition, HistoricalDelay, ETAPrediction, WeatherObservation
)

logger = logging.getLogger("railway_eta.seed")

# High-fidelity authentic Indian Railways station coordinates and codes
STATIONS_DATA = [
    {"station_code": "NDLS", "station_name": "New Delhi", "latitude": 28.6424, "longitude": 77.2195, "state": "Delhi", "zone": "NR"},
    {"station_code": "CNB", "station_name": "Kanpur Central", "latitude": 26.4547, "longitude": 80.3507, "state": "Uttar Pradesh", "zone": "NCR"},
    {"station_code": "PRYJ", "station_name": "Prayagraj Junction", "latitude": 25.4497, "longitude": 81.8282, "state": "Uttar Pradesh", "zone": "NCR"},
    {"station_code": "DDU", "station_name": "Pt. Deen Dayal Upadhyaya Junction", "latitude": 25.2818, "longitude": 83.1187, "state": "Uttar Pradesh", "zone": "ECR"},
    {"station_code": "BSB", "station_name": "Varanasi Junction", "latitude": 25.3284, "longitude": 82.9863, "state": "Uttar Pradesh", "zone": "NR"},
    {"station_code": "GAYA", "station_name": "Gaya Junction", "latitude": 24.8052, "longitude": 84.9996, "state": "Bihar", "zone": "ECR"},
    {"station_code": "DHN", "station_name": "Dhanbad Junction", "latitude": 23.7915, "longitude": 86.4304, "state": "Jharkhand", "zone": "ECR"},
    {"station_code": "ASN", "station_name": "Asansol Junction", "latitude": 23.6871, "longitude": 86.9746, "state": "West Bengal", "zone": "ER"},
    {"station_code": "HWH", "station_name": "Howrah Junction", "latitude": 22.5830, "longitude": 88.3426, "state": "West Bengal", "zone": "ER"},
    {"station_code": "KOTA", "station_name": "Kota Junction", "latitude": 25.2215, "longitude": 75.8648, "state": "Rajasthan", "zone": "WCR"},
    {"station_code": "BRC", "station_name": "Vadodara Junction", "latitude": 22.3107, "longitude": 73.1812, "state": "Gujarat", "zone": "WR"},
    {"station_code": "MMCT", "station_name": "Mumbai Central", "latitude": 18.9696, "longitude": 72.8193, "state": "Maharashtra", "zone": "WR"},
]

# Iconic Coaching Trains
TRAINS_DATA = [
    {
        "train_number": "12301",
        "train_name": "Howrah Rajdhani Express (via Gaya)",
        "train_type": "Rajdhani Express",
        "source": "HWH",
        "destination": "NDLS"
    },
    {
        "train_number": "12302",
        "train_name": "New Delhi - Howrah Rajdhani Express",
        "train_type": "Rajdhani Express",
        "source": "NDLS",
        "destination": "HWH"
    },
    {
        "train_number": "22436",
        "train_name": "New Delhi - Varanasi Vande Bharat Express",
        "train_type": "Vande Bharat Express",
        "source": "NDLS",
        "destination": "BSB"
    },
    {
        "train_number": "12952",
        "train_name": "New Delhi - Mumbai Central Tejas Rajdhani Express",
        "train_type": "Tejas Rajdhani Express",
        "source": "NDLS",
        "destination": "MMCT"
    }
]

# Timetable schedules for RouteStations
# 12302: NDLS -> HWH
ROUTE_12302 = [
    {"seq": 1, "station": "NDLS", "arr": None, "dep": "16:55:00", "dist": 0.0, "dwell": 0.0, "day": 1},
    {"seq": 2, "station": "CNB",  "arr": "21:30:00", "dep": "21:35:00", "dist": 440.0, "dwell": 5.0, "day": 1},
    {"seq": 3, "station": "PRYJ", "arr": "23:43:00", "dep": "23:45:00", "dist": 634.0, "dwell": 2.0, "day": 1},
    {"seq": 4, "station": "DDU",  "arr": "00:45:00", "dep": "00:55:00", "dist": 787.0, "dwell": 10.0, "day": 2},
    {"seq": 5, "station": "GAYA", "arr": "03:10:00", "dep": "03:13:00", "dist": 992.0, "dwell": 3.0, "day": 2},
    {"seq": 6, "station": "DHN",  "arr": "05:55:00", "dep": "06:00:00", "dist": 1193.0, "dwell": 5.0, "day": 2},
    {"seq": 7, "station": "ASN",  "arr": "06:54:00", "dep": "06:56:00", "dist": 1251.0, "dwell": 2.0, "day": 2},
    {"seq": 8, "station": "HWH",  "arr": "09:55:00", "dep": None, "dist": 1450.0, "dwell": 0.0, "day": 2},
]

# 22436: NDLS -> BSB (Vande Bharat)
ROUTE_22436 = [
    {"seq": 1, "station": "NDLS", "arr": None, "dep": "06:00:00", "dist": 0.0, "dwell": 0.0, "day": 1},
    {"seq": 2, "station": "CNB",  "arr": "10:08:00", "dep": "10:10:00", "dist": 440.0, "dwell": 2.0, "day": 1},
    {"seq": 3, "station": "PRYJ", "arr": "12:08:00", "dep": "12:10:00", "dist": 634.0, "dwell": 2.0, "day": 1},
    {"seq": 4, "station": "BSB",  "arr": "14:00:00", "dep": None, "dist": 759.0, "dwell": 0.0, "day": 1},
]

# 12952: NDLS -> MMCT (Tejas Rajdhani)
ROUTE_12952 = [
    {"seq": 1, "station": "NDLS", "arr": None, "dep": "16:55:00", "dist": 0.0, "dwell": 0.0, "day": 1},
    {"seq": 2, "station": "KOTA", "arr": "21:30:00", "dep": "21:40:00", "dist": 465.0, "dwell": 10.0, "day": 1},
    {"seq": 3, "station": "BRC",  "arr": "03:40:00", "dep": "03:50:00", "dist": 992.0, "dwell": 10.0, "day": 2},
    {"seq": 4, "station": "MMCT", "arr": "08:35:00", "dep": None, "dist": 1384.0, "dwell": 0.0, "day": 2},
]


async def seed_database(db: AsyncSession):
    """
    Populates database with authentic Indian Railways timetable and station seed data.
    Note: Explicitly flagged as seed/reference data, not a live railway feed claim.
    """
    # 1. Check if stations already seeded
    existing_stations = await db.execute(select(Station))
    if existing_stations.scalars().first():
        logger.info("Database already seeded. Skipping initial seeding.")
        return

    logger.info("Seeding stations data...")
    for s_data in STATIONS_DATA:
        db.add(Station(**s_data))
    await db.flush()

    logger.info("Seeding trains data...")
    for t_data in TRAINS_DATA:
        db.add(Train(**t_data))
    await db.flush()

    logger.info("Seeding routes and route_stations...")
    # Seed 12302 Route
    r12302 = Route(route_id="R_12302", train_number="12302", direction="DOWN", total_distance_km=1450.0)
    db.add(r12302)
    await db.flush()
    for item in ROUTE_12302:
        db.add(RouteStation(
            route_id=r12302.route_id,
            station_sequence=item["seq"],
            station_code=item["station"],
            scheduled_arrival=item["arr"],
            scheduled_departure=item["dep"],
            distance_from_origin=item["dist"],
            scheduled_dwell_minutes=item["dwell"],
            day_offset=item["day"]
        ))

    # Seed 22436 Route
    r22436 = Route(route_id="R_22436", train_number="22436", direction="DOWN", total_distance_km=759.0)
    db.add(r22436)
    await db.flush()
    for item in ROUTE_22436:
        db.add(RouteStation(
            route_id=r22436.route_id,
            station_sequence=item["seq"],
            station_code=item["station"],
            scheduled_arrival=item["arr"],
            scheduled_departure=item["dep"],
            distance_from_origin=item["dist"],
            scheduled_dwell_minutes=item["dwell"],
            day_offset=item["day"]
        ))

    # Seed 12952 Route
    r12952 = Route(route_id="R_12952", train_number="12952", direction="DOWN", total_distance_km=1384.0)
    db.add(r12952)
    await db.flush()
    for item in ROUTE_12952:
        db.add(RouteStation(
            route_id=r12952.route_id,
            station_sequence=item["seq"],
            station_code=item["station"],
            scheduled_arrival=item["arr"],
            scheduled_departure=item["dep"],
            distance_from_origin=item["dist"],
            scheduled_dwell_minutes=item["dwell"],
            day_offset=item["day"]
        ))

    # 4. Seed TrainRuns and LivePositions
    today = date.today()
    run_12302 = TrainRun(run_id=f"12302_{today.isoformat()}", train_number="12302", run_date=today, status="RUNNING")
    run_22436 = TrainRun(run_id=f"22436_{today.isoformat()}", train_number="22436", run_date=today, status="RUNNING")
    run_12952 = TrainRun(run_id=f"12952_{today.isoformat()}", train_number="12952", run_date=today, status="RUNNING")
    run_12301 = TrainRun(run_id=f"12301_{today.isoformat()}", train_number="12301", run_date=today, status="RUNNING")
    db.add_all([run_12302, run_22436, run_12952, run_12301])
    await db.flush()

    # 5. Seed LivePositions (Demonstrating Green, Amber, and Red delay semantics)
    live_positions = [
        LivePosition(
            train_number="12302",
            run_id=run_12302.run_id,
            timestamp=datetime.now(timezone.utc),
            latitude=25.9520,
            longitude=81.0894,
            speed=118.5,
            current_delay=12.0,  # 12 mins delay: Amber (Moderate)
            current_station="CNB",
            next_station="PRYJ",
            data_source="SIMULATION"
        ),
        LivePosition(
            train_number="22436",
            run_id=run_22436.run_id,
            timestamp=datetime.now(timezone.utc),
            latitude=27.5020,
            longitude=78.8500,
            speed=130.0,
            current_delay=3.0,   # 3 mins delay: Green (On-time)
            current_station="NDLS",
            next_station="CNB",
            data_source="SIMULATION"
        ),
        LivePosition(
            train_number="12952",
            run_id=run_12952.run_id,
            timestamp=datetime.now(timezone.utc),
            latitude=23.7500,
            longitude=74.5000,
            speed=110.0,
            current_delay=38.0,  # 38 mins delay: Red (Severe)
            current_station="KOTA",
            next_station="BRC",
            data_source="SIMULATION"
        ),
        LivePosition(
            train_number="12301",
            run_id=run_12301.run_id,
            timestamp=datetime.now(timezone.utc),
            latitude=23.7400,
            longitude=86.7000,
            speed=105.0,
            current_delay=4.0,   # 4 mins delay: Green (On-time)
            current_station="ASN",
            next_station="DHN",
            data_source="SIMULATION"
        ),
    ]
    db.add_all(live_positions)

    # 6. Seed Historical Delays (Sample historical section delays for analysis)
    base_date = today - timedelta(days=1)
    sample_delays = [
        {"train": "12302", "stn": "CNB", "sched": datetime(2026, 9, 9, 21, 30), "actual": datetime(2026, 9, 9, 21, 38), "delay": 8.0, "sec": "NDLS-CNB"},
        {"train": "12302", "stn": "PRYJ", "sched": datetime(2026, 9, 9, 23, 43), "actual": datetime(2026, 9, 9, 23, 58), "delay": 15.0, "sec": "CNB-PRYJ"},
        {"train": "12302", "stn": "DDU", "sched": datetime(2026, 9, 10, 0, 45), "actual": datetime(2026, 9, 10, 1, 0), "delay": 15.0, "sec": "PRYJ-DDU"},
        {"train": "22436", "stn": "CNB", "sched": datetime(2026, 9, 9, 10, 8), "actual": datetime(2026, 9, 9, 10, 10), "delay": 2.0, "sec": "NDLS-CNB"},
        {"train": "22436", "stn": "BSB", "sched": datetime(2026, 9, 9, 14, 0), "actual": datetime(2026, 9, 9, 14, 1), "delay": 1.0, "sec": "PRYJ-BSB"},
    ]
    for d in sample_delays:
        db.add(HistoricalDelay(
            train_number=d["train"],
            date=d["sched"].date(),
            station_code=d["stn"],
            scheduled_arrival=d["sched"],
            actual_arrival=d["actual"],
            delay_minutes=d["delay"],
            section=d["sec"]
        ))

    # 7. Seed Sample Weather Observations
    sample_weather = [
        {"stn": "NDLS", "lat": 28.6424, "lon": 77.2195, "temp": 31.2, "vis": 6.5, "precip": 0.0, "code": 1, "desc": "Clear / Mild Haze"},
        {"stn": "CNB", "lat": 26.4547, "lon": 80.3507, "temp": 29.8, "vis": 5.0, "precip": 0.0, "code": 2, "desc": "Partly Cloudy"},
        {"stn": "PRYJ", "lat": 25.4497, "lon": 81.8282, "temp": 30.5, "vis": 4.8, "precip": 0.0, "code": 3, "desc": "Overcast"},
        {"stn": "DDU", "lat": 25.2818, "lon": 83.1187, "temp": 28.9, "vis": 4.2, "precip": 1.2, "code": 61, "desc": "Light Rain"},
    ]
    for w in sample_weather:
        db.add(WeatherObservation(
            station_code=w["stn"],
            latitude=w["lat"],
            longitude=w["lon"],
            timestamp=datetime.utcnow(),
            temperature_c=w["temp"],
            visibility_km=w["vis"],
            precipitation_mm=w["precip"],
            weather_code=w["code"],
            condition_description=w["desc"]
        ))

    await db.commit()
    logger.info("Database seeding successfully completed!")
