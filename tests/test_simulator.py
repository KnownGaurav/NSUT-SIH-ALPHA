import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app
from src.simulator.train_simulator import simulator, SimulationEvent, calculate_bearing, haversine_distance_km
from src.services.data_providers.factory import get_data_provider
from src.services.data_providers.base import TrainDataProvider


def test_bearing_and_haversine_math():
    # NDLS (28.6424, 77.2195) to CNB (26.4547, 80.3507)
    dist = haversine_distance_km(28.6424, 77.2195, 26.4547, 80.3507)
    assert 380 < dist < 450  # ~400 km direct

    bearing = calculate_bearing(28.6424, 77.2195, 26.4547, 80.3507)
    assert 110 < bearing < 140  # South-East direction


def test_simulator_kinematics_and_events():
    mock_stops = [
        {"sequence": 1, "station_code": "STN_A", "latitude": 28.0, "longitude": 77.0},
        {"sequence": 2, "station_code": "STN_B", "latitude": 27.0, "longitude": 78.0},
        {"sequence": 3, "station_code": "STN_C", "latitude": 26.0, "longitude": 79.0},
    ]
    simulator.register_train("TEST_99", mock_stops, initial_delay=10.0, start_segment=0)

    state_initial = simulator.get_state("TEST_99")
    assert state_initial is not None
    assert state_initial.train_number == "TEST_99"
    assert state_initial.speed == 115.0
    assert state_initial.current_delay == 10.0
    assert state_initial.data_source == "SIMULATION"

    # Test CONGESTION event
    simulator.trigger_event("TEST_99", SimulationEvent.CONGESTION)
    state_cong = simulator.get_state("TEST_99")
    assert state_cong.speed == 20.0
    assert state_cong.operational_event == "CONGESTION"

    # Tick simulator and verify delay increases
    simulator.tick(delta_seconds=60.0)
    state_after_tick = simulator.get_state("TEST_99")
    assert state_after_tick.current_delay > 10.0

    # Test RECOVERY event
    simulator.trigger_event("TEST_99", SimulationEvent.RECOVERY)
    state_rec = simulator.get_state("TEST_99")
    assert state_rec.speed == 130.0
    assert state_rec.operational_event == "RECOVERY"

    # Tick and verify delay decreases
    prev_delay = state_after_tick.current_delay
    simulator.tick(delta_seconds=60.0)
    state_recovered = simulator.get_state("TEST_99")
    assert state_recovered.current_delay < prev_delay


def test_provider_factory():
    from src.services.data_providers.simulator_provider import SimulatorProvider
    provider = SimulatorProvider()
    assert isinstance(provider, TrainDataProvider)
    assert provider.is_simulation is True
    assert provider.provider_name == "SimulatorProvider"


@pytest.mark.asyncio
async def test_simulator_api_endpoints():
    from src.main import register_simulator_trains
    from src.db.session import init_db, AsyncSessionLocal
    from src.db.seed import seed_database
    
    await init_db()
    async with AsyncSessionLocal() as session:
        await seed_database(session)
    await register_simulator_trains()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Trigger event
        res = await ac.post("/api/simulator/event", json={
            "train_number": "12302",
            "event": "CONGESTION"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["applied_event"] == "CONGESTION"
        assert data["new_speed_kmh"] == 20.0

        # 2. Get status
        status_res = await ac.get("/api/simulator/status")
        assert status_res.status_code == 200
        statuses = status_res.json()
        assert any(t["train_number"] == "12302" for t in statuses)

        # 3. Step tick
        tick_res = await ac.post("/api/simulator/tick", json={
            "delta_seconds": 5.0,
            "speed_multiplier": 3.0
        })
        assert tick_res.status_code == 200

        # 4. Trigger recovery
        rec_res = await ac.post("/api/simulator/event", json={
            "train_number": "12302",
            "event": "RECOVERY"
        })
        assert rec_res.status_code == 200
        assert rec_res.json()["applied_event"] == "RECOVERY"
