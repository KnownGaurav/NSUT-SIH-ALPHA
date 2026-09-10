import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from src.main import app
from src.services.eta_service import BaselineETAService
from src.services.data_providers.base import NormalizedTrainState


def test_baseline_calculation_formula():
    """
    Test deterministic baseline calculation matches core formulation:
    Current: 18:00
    Scheduled remaining time: ~42m
    Current delay: +15m
    Baseline ETA: 18:57 (accounting for slight recovery slack)
    """
    ref_time = datetime(2026, 9, 10, 18, 0, 0, tzinfo=timezone.utc)
    mock_state = NormalizedTrainState(
        train_number="12301",
        timestamp=ref_time,
        latitude=28.0,
        longitude=77.5,
        speed=110.0,
        bearing=130.0,
        current_delay=15.0,
        current_station="NDLS",
        next_station="AGC",
        data_source="SIMULATION"
    )

    mock_stops = [
        {"sequence": 1, "station_code": "NDLS", "station_name": "New Delhi", "distance_from_origin_km": 0.0, "scheduled_arrival": None, "scheduled_departure": "17:00:00", "scheduled_dwell_minutes": 0.0, "day_offset": 1},
        {"sequence": 2, "station_code": "AGC", "station_name": "Agra Cantt", "distance_from_origin_km": 195.0, "scheduled_arrival": "18:42:00", "scheduled_departure": "18:47:00", "scheduled_dwell_minutes": 5.0, "day_offset": 1},
        {"sequence": 3, "station_code": "GWL", "station_name": "Gwalior", "distance_from_origin_km": 313.0, "scheduled_arrival": "20:15:00", "scheduled_departure": "20:17:00", "scheduled_dwell_minutes": 2.0, "day_offset": 1}
    ]

    res = BaselineETAService.calculate_baseline(train_state=mock_state, stops=mock_stops, reference_time=ref_time)

    assert res.train_number == "12301"
    assert res.current_delay_minutes == 15.0
    assert len(res.stations) == 3

    # Origin station NDLS is passed
    assert res.stations[0].station_code == "NDLS"
    assert res.stations[0].is_passed is True

    # Next station AGC is upcoming
    agc = res.stations[1]
    assert agc.station_code == "AGC"
    assert agc.is_passed is False
    assert agc.baseline_eta is not None
    assert agc.remaining_distance_km > 0
    assert agc.remaining_travel_time_minutes > 0
    # Baseline delay is positive around current delay (~13-15 min)
    assert 10.0 <= agc.baseline_delay_minutes <= 15.0

    # Destination GWL is upcoming
    gwl = res.stations[2]
    assert gwl.station_code == "GWL"
    assert gwl.is_passed is False
    assert gwl.remaining_distance_km > agc.remaining_distance_km
    assert gwl.remaining_travel_time_minutes > agc.remaining_travel_time_minutes


@pytest.mark.asyncio
async def test_baseline_eta_api_endpoint():
    from src.main import register_simulator_trains
    from src.db.session import init_db, AsyncSessionLocal
    from src.db.seed import seed_database

    await init_db()
    async with AsyncSessionLocal() as session:
        await seed_database(session)
    await register_simulator_trains()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/trains/12302/eta/baseline")

    assert res.status_code == 200
    data = res.json()
    assert data["train_number"] == "12302"
    assert data["model_name"] == "Deterministic Baseline Engine (v1.0)"
    assert len(data["stations"]) == 8

    # Verify at least one upcoming station has baseline_eta populated
    upcoming = [s for s in data["stations"] if not s["is_passed"]]
    assert len(upcoming) > 0
    for u in upcoming:
        assert u["baseline_eta"] is not None
        assert u["remaining_travel_time_minutes"] > 0
        assert u["remaining_distance_km"] >= 0


@pytest.mark.asyncio
async def test_baseline_eta_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/trains/NONEXISTENT/eta/baseline")

    assert res.status_code == 404
