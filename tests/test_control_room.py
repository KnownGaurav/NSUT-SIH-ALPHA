import pytest
from fastapi.testclient import TestClient
from src.main import app


def test_control_room_summary_api():
    client = TestClient(app)
    response = client.get("/api/trains/control-room/summary")
    assert response.status_code == 200
    data = response.json()

    # Core control room fields
    assert "total_active_trains" in data
    assert "on_time_count" in data
    assert "delayed_count" in data
    assert "severe_delay_count" in data
    assert "deteriorating_count" in data
    assert data["data_source"] in ["SIMULATION", "RAILRADAR_LIVE"]
    assert "generated_at" in data
    assert "trains" in data
    assert isinstance(data["trains"], list)
    assert len(data["trains"]) > 0

    # Inspect first train in control room roster
    train = data["trains"][0]
    assert "train_number" in train
    assert "train_name" in train
    assert "latitude" in train
    assert "longitude" in train
    assert "speed_kmh" in train
    assert "current_delay_minutes" in train
    assert "delay_status" in train
    assert train["delay_status"] in ["on_time", "moderate", "severe"]
    assert "next_station" in train
    assert "predicted_eta" in train
    assert "has_deteriorating_eta" in train
    assert "data_source" in train
    assert train["data_source"] in ["SIMULATION", "RAILRADAR_LIVE"]
