import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app
from src.services.weather_service import weather_service, WeatherData


@pytest.mark.asyncio
async def test_weather_service_direct():
    # Query coordinates for New Delhi
    w = await weather_service.get_weather(28.6424, 77.2195)
    assert isinstance(w, WeatherData)
    assert w.latitude == 28.6424
    assert w.longitude == 77.2195
    assert w.temperature_c is not None
    assert w.precipitation_mm >= 0.0
    assert w.wind_speed_kmh >= 0.0
    assert w.visibility_km > 0.0
    assert w.weather_condition is not None
    assert w.data_source in ["Open-Meteo", "BASELINE_ESTIMATE"]

    # Test cache hit
    w_cached = await weather_service.get_weather(28.6424, 77.2195)
    assert w_cached.cached is True


@pytest.mark.asyncio
async def test_position_endpoint_with_weather_and_congestion():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/trains/12302/position")
        assert res.status_code == 200
        data = res.json()
        assert "weather" in data
        assert "congestion" in data
        if data["weather"]:
            assert "temperature_c" in data["weather"]
            assert "weather_condition" in data["weather"]
        if data["congestion"]:
            assert data["congestion"]["level"] in ["LOW", "MEDIUM", "HIGH"]
            assert 0.0 <= data["congestion"]["score"] <= 1.0


@pytest.mark.asyncio
async def test_eta_endpoint_with_weather_and_congestion():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/trains/12302/eta")
        assert res.status_code == 200
        data = res.json()
        assert "weather" in data
        assert "congestion" in data
        assert "operational_event" in data
        assert data["congestion"]["level"] in ["LOW", "MEDIUM", "HIGH"]


@pytest.mark.asyncio
async def test_operational_event_impact_on_eta():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Trigger SPEED_RESTRICTION
        res1 = await ac.post("/api/simulator/event", json={
            "train_number": "12302",
            "event": "SPEED_RESTRICTION"
        })
        assert res1.status_code == 200

        # Query ETA
        eta_res = await ac.get("/api/trains/12302/eta")
        assert eta_res.status_code == 200
        eta_data = eta_res.json()
        assert eta_data["operational_event"] == "SPEED_RESTRICTION"
        assert eta_data["congestion"]["level"] == "MEDIUM"

        # Reset back to NORMAL_OPERATION
        await ac.post("/api/simulator/event", json={
            "train_number": "12302",
            "event": "NORMAL_OPERATION"
        })


@pytest.mark.asyncio
async def test_weather_endpoint_lat_lon_aliases():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Full parameter names
        res1 = await ac.get("/api/weather?latitude=28.6424&longitude=77.2195")
        assert res1.status_code == 200
        # Abbreviated aliases
        res2 = await ac.get("/api/weather?lat=28.6424&lon=77.2195")
        assert res2.status_code == 200
        # Missing parameters error
        res3 = await ac.get("/api/weather")
        assert res3.status_code == 400

