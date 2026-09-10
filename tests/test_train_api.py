import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app
from src.db.session import init_db, AsyncSessionLocal
from src.db.seed import seed_database


async def ensure_db_ready():
    await init_db()
    async with AsyncSessionLocal() as session:
        await seed_database(session)


@pytest.mark.asyncio
async def test_list_trains():
    await ensure_db_ready()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/trains")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 3

    train_numbers = [t["train_number"] for t in data]
    assert "12302" in train_numbers
    assert "22436" in train_numbers
    assert "12952" in train_numbers


@pytest.mark.asyncio
async def test_get_train_detail():
    await ensure_db_ready()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/trains/12302")

    assert response.status_code == 200
    data = response.json()
    assert data["train_number"] == "12302"
    assert "Rajdhani" in data["train_name"]
    assert data["source"] == "NDLS"
    assert data["destination"] == "HWH"
    assert data["total_distance_km"] == 1450.0
    assert data["live_position"] is not None
    assert data["live_position"]["data_source"] == "SIMULATION"


@pytest.mark.asyncio
async def test_get_train_detail_not_found():
    await ensure_db_ready()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/trains/99999")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_station_detail():
    await ensure_db_ready()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/stations/NDLS")

    assert response.status_code == 200
    data = response.json()
    assert data["station_code"] == "NDLS"
    assert data["station_name"] == "New Delhi"
    assert data["latitude"] == pytest.approx(28.64, abs=0.01)
    assert data["longitude"] == pytest.approx(77.22, abs=0.01)
    assert data["zone"] == "NR"


@pytest.mark.asyncio
async def test_get_station_not_found():
    await ensure_db_ready()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/stations/NONEXISTENT")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_train_route():
    await ensure_db_ready()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/trains/12302/route")

    assert response.status_code == 200
    data = response.json()
    assert data["train_number"] == "12302"
    assert data["total_stops"] == 8
    assert len(data["stops"]) == 8

    # Verify order and stop sequence
    assert data["stops"][0]["station_code"] == "NDLS"
    assert data["stops"][0]["sequence"] == 1
    assert data["stops"][0]["distance_from_origin_km"] == 0.0

    assert data["stops"][1]["station_code"] == "CNB"
    assert data["stops"][1]["sequence"] == 2
    assert data["stops"][1]["distance_from_origin_km"] == 440.0

    assert data["stops"][-1]["station_code"] == "HWH"
    assert data["stops"][-1]["distance_from_origin_km"] == 1450.0


@pytest.mark.asyncio
async def test_get_train_position():
    await ensure_db_ready()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/trains/12302/position")

    assert response.status_code == 200
    data = response.json()
    assert data["train_number"] == "12302"
    assert 22.0 < data["latitude"] < 30.0
    assert 75.0 < data["longitude"] < 90.0
    assert data["speed_kmh"] >= 0.0
    assert "current_delay_minutes" in data
    assert "delay_status" in data
    assert data["data_source"] in ["SIMULATION", "RAILRADAR_LIVE"]


@pytest.mark.asyncio
async def test_get_train_position_not_found():
    await ensure_db_ready()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/trains/99999/position")

    assert response.status_code == 404
