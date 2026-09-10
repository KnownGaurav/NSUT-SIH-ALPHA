import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from src.main import app
from src.ml.predict import dynamic_eta_predictor
from src.services.data_providers.base import NormalizedTrainState


@pytest.mark.asyncio
async def test_dynamic_predictor_unit_fields():
    stops = [
        {"sequence": 1, "station_code": "NDLS", "station_name": "New Delhi", "distance_from_origin_km": 0.0, "scheduled_arrival": None, "scheduled_departure": "16:55:00", "scheduled_dwell_minutes": 0.0, "day_offset": 1},
        {"sequence": 2, "station_code": "CNB", "station_name": "Kanpur Central", "distance_from_origin_km": 440.0, "scheduled_arrival": "21:30:00", "scheduled_departure": "21:35:00", "scheduled_dwell_minutes": 5.0, "day_offset": 1},
        {"sequence": 3, "station_code": "PRYJ", "station_name": "Prayagraj Junction", "distance_from_origin_km": 634.0, "scheduled_arrival": "23:43:00", "scheduled_departure": "23:45:00", "scheduled_dwell_minutes": 2.0, "day_offset": 1},
        {"sequence": 4, "station_code": "HWH", "station_name": "Howrah Junction", "distance_from_origin_km": 1450.0, "scheduled_arrival": "09:55:00", "scheduled_departure": None, "scheduled_dwell_minutes": 0.0, "day_offset": 2}
    ]

    state = NormalizedTrainState(
        train_number="12302",
        timestamp=datetime(2026, 9, 10, 17, 30, tzinfo=timezone.utc),
        latitude=28.0,
        longitude=78.0,
        speed=110.0,
        bearing=130.0,
        current_delay=12.0,
        current_station="NDLS",
        next_station="CNB",
        data_source="SIMULATION",
        operational_event="NORMAL_OPERATION"
    )

    pred_res = dynamic_eta_predictor.predict_upcoming_etas(
        train_state=state,
        stops=stops,
        train_type="Rajdhani Express"
    )

    assert pred_res.train_number == "12302"
    assert pred_res.model_version == "1.0.0"
    assert len(pred_res.stations) == 4

    # Station 1 (NDLS) is passed
    assert pred_res.stations[0].is_passed is True
    assert pred_res.stations[0].predicted_eta is None

    # Station 2 (CNB) is upcoming
    cnb = pred_res.stations[1]
    assert cnb.is_passed is False
    assert cnb.station_code == "CNB"
    assert cnb.predicted_remaining_minutes > 0.0
    assert cnb.predicted_eta is not None
    assert cnb.dynamic_eta is not None
    assert cnb.baseline_eta is not None
    assert cnb.predicted_delay_minutes >= 0.0
    assert cnb.confidence is not None
    assert 0.50 <= cnb.confidence <= 1.0
    assert cnb.lower_bound is not None
    assert cnb.upper_bound is not None
    assert cnb.confidence_lower_minutes < cnb.confidence_upper_minutes
    assert cnb.baseline_remaining_minutes > 0.0


@pytest.mark.asyncio
async def test_get_eta_primary_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/trains/12302/eta")
        assert res.status_code == 200
        data = res.json()

        assert data["train_number"] == "12302"
        assert "stations" in data
        assert len(data["stations"]) > 0

        upcoming = [s for s in data["stations"] if not s["is_passed"]]
        assert len(upcoming) > 0
        first_up = upcoming[0]
        
        # Verify required fields from Phase 8 specification
        assert "predicted_eta" in first_up
        assert "baseline_eta" in first_up
        assert "predicted_delay_minutes" in first_up
        assert "predicted_remaining_minutes" in first_up
        assert "confidence" in first_up
        assert "lower_bound" in first_up
        assert "upper_bound" in first_up
        assert "delta_vs_baseline_minutes" in first_up


@pytest.mark.asyncio
async def test_get_eta_dynamic_and_ml_aliases():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res1 = await ac.get("/api/trains/12302/eta/dynamic")
        res2 = await ac.get("/api/trains/12302/eta/ml")
        assert res1.status_code == 200
        assert res2.status_code == 200
        assert res1.json()["train_number"] == res2.json()["train_number"]


@pytest.mark.asyncio
async def test_eta_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/trains/00000/eta")
        assert res.status_code == 404
