import pytest
from unittest.mock import AsyncMock, patch
from src.services.data_providers.railradar_provider import RailRadarProvider
from src.services.data_providers.base import NormalizedTrainState


@pytest.mark.asyncio
async def test_railradar_provider_metadata():
    provider = RailRadarProvider()
    assert provider.provider_name == "RailRadar"
    assert provider.is_simulation is False


@pytest.mark.asyncio
async def test_railradar_provider_parsing_mocked():
    provider = RailRadarProvider()

    mock_live_payload = {
        "trainNumber": "12002",
        "trainName": "New Delhi - Bhopal Shatabdi",
        "status": "running",
        "delayMinutes": 14.0,
        "train": {
            "avgSpeed": 88.0,
            "distance": 708.0,
            "source": {"lat": 28.6419, "lng": 77.2217},
            "destination": {"lat": 23.2599, "lng": 77.4126}
        },
        "currentLocation": {
            "stationCode": "MTJ",
            "stationName": "Mathura Jn",
            "distanceFromOriginKm": 141.0,
            "delayMinutes": 14.0
        },
        "previousHalt": {"stationCode": "NDLS"},
        "nextHalt": {"stationCode": "AGC"}
    }

    mock_route_geojson = {
        "format": "geojson",
        "geojson": {
            "geometry": {
                "coordinates": [
                    [77.2217, 28.6419],
                    [77.6737, 27.4924],
                    [77.4126, 23.2599]
                ]
            }
        }
    }

    with patch.object(provider, "get_train_live_data", new_callable=AsyncMock) as mock_live:
        mock_live.return_value = mock_live_payload
        with patch.object(provider, "get_train_route_geojson", new_callable=AsyncMock) as mock_route:
            mock_route.return_value = mock_route_geojson

            state = await provider.get_train_position("12002")
            assert state is not None
            assert isinstance(state, NormalizedTrainState)
            assert state.train_number == "12002"
            assert state.speed == 88.0
            assert state.current_delay == 14.0
            assert state.data_source == "RAILRADAR_LIVE"
            assert state.current_station == "MTJ"
            assert state.next_station == "AGC"
            assert state.latitude > 0.0
            assert state.longitude > 0.0


@pytest.mark.asyncio
async def test_railradar_ttl_cache():
    provider = RailRadarProvider()

    mock_live_payload = {
        "trainNumber": "12952",
        "status": "running",
        "delayMinutes": 0.0,
        "train": {"avgSpeed": 90.0, "distance": 1380.0},
        "currentLocation": {"stationCode": "NDLS", "distanceFromOriginKm": 0.0},
        "previousHalt": {"stationCode": "NDLS"},
        "nextHalt": {"stationCode": "KOTA"}
    }

    with patch.object(provider, "get_train_live_data", new_callable=AsyncMock) as mock_live:
        mock_live.return_value = mock_live_payload
        with patch.object(provider, "get_train_route_geojson", new_callable=AsyncMock) as mock_route:
            mock_route.return_value = None

            # First call -> hits live
            state1 = await provider.get_train_position("12952")
            assert mock_live.call_count == 1

            # Second call immediately after -> hits cache, no second API call
            state2 = await provider.get_train_position("12952")
            assert mock_live.call_count == 1
            assert state1.train_number == state2.train_number
