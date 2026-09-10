import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app, register_simulator_trains
from src.db.session import init_db, AsyncSessionLocal
from src.db.seed import seed_database


async def ensure_ready():
    await init_db()
    async with AsyncSessionLocal() as session:
        await seed_database(session)
    await register_simulator_trains()


@pytest.mark.asyncio
async def test_api_health():
    await ensure_ready()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert "X-Process-Time-Ms" in resp.headers


@pytest.mark.asyncio
async def test_api_trains_list_and_detail():
    await ensure_ready()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # List trains
        resp = await client.get("/api/trains")
        assert resp.status_code == 200
        trains = resp.json()
        assert len(trains) > 0
        t_num = "12302"

        # Train detail
        d_resp = await client.get(f"/api/trains/{t_num}")
        assert d_resp.status_code == 200
        assert d_resp.json()["train_number"] == t_num

        # Train route
        r_resp = await client.get(f"/api/trains/{t_num}/route")
        assert r_resp.status_code == 200
        assert len(r_resp.json()["stops"]) > 0

        # Train position
        p_resp = await client.get(f"/api/trains/{t_num}/position")
        assert p_resp.status_code == 200
        assert "latitude" in p_resp.json()

        # Train dynamic ETA
        e_resp = await client.get(f"/api/trains/{t_num}/eta")
        assert e_resp.status_code == 200
        assert "stations" in e_resp.json()

        # Train baseline ETA
        b_resp = await client.get(f"/api/trains/{t_num}/eta/baseline")
        assert b_resp.status_code == 200
        assert "stations" in b_resp.json()


@pytest.mark.asyncio
async def test_api_stations():
    await ensure_ready()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # All stations
        resp = await client.get("/api/stations")
        assert resp.status_code == 200
        stations = resp.json()
        assert len(stations) > 0

        # Single station
        s_resp = await client.get("/api/stations/NDLS")
        assert s_resp.status_code == 200
        assert s_resp.json()["station_code"] == "NDLS"

        # Station Arrivals & Platform Operations
        arr_resp = await client.get("/api/stations/NDLS/arrivals")
        assert arr_resp.status_code == 200
        arr_data = arr_resp.json()
        assert arr_data["station_code"] == "NDLS"
        assert "total_platforms" in arr_data
        assert "arrivals" in arr_data
        assert len(arr_data["arrivals"]) > 0
        first_arr = arr_data["arrivals"][0]
        assert "assigned_platform" in first_arr
        assert "platform_conflict_flag" in first_arr
        assert "turnaround_impact" in first_arr

        # Non-existent station 404
        n_resp = await client.get("/api/stations/ZZZZZ")
        assert n_resp.status_code == 404


@pytest.mark.asyncio
async def test_api_weather():
    await ensure_ready()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Weather at Delhi coords
        resp = await client.get("/api/weather?latitude=28.6424&longitude=77.2195")
        assert resp.status_code == 200
        data = resp.json()
        assert "temperature_c" in data
        assert "precipitation_mm" in data
        assert "visibility_km" in data
        assert "weather_condition" in data


@pytest.mark.asyncio
async def test_api_simulation_endpoints():
    await ensure_ready()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Status
        resp = await client.get("/api/simulation/status")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

        # Trigger event
        e_resp = await client.post("/api/simulation/event", json={
            "train_number": "12302",
            "event": "NORMAL_OPERATION"
        })
        assert e_resp.status_code == 200
        assert e_resp.json()["status"] == "ok"
