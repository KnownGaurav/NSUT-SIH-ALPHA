import pytest
from fastapi.testclient import TestClient
from src.main import app


def test_model_performance_analytics_api():
    client = TestClient(app)
    response = client.get("/api/trains/analytics/model-performance")
    assert response.status_code == 200
    data = response.json()

    # Verify model details
    assert data["model_name"] == "XGBoost Dynamic Railway ETA Predictor"
    assert data["model_version"] == "1.0.0"
    assert data["total_evaluation_samples"] == 1400
    assert data["validation_samples"] == 280
    assert data["validation_split_method"] == "chronological_by_run_date"

    # Verify baseline metrics
    base = data["baseline_metrics"]
    assert base["mae_minutes"] == 6.35
    assert base["rmse_minutes"] == 7.98
    assert base["accuracy_within_5_min_percent"] == 48.9
    assert base["accuracy_within_10_min_percent"] == 74.3
    assert base["accuracy_within_15_min_percent"] == 94.3

    # Verify XGBoost ML metrics
    ml = data["ml_metrics"]
    assert ml["mae_minutes"] == 2.69
    assert ml["rmse_minutes"] == 3.51
    assert ml["accuracy_within_5_min_percent"] == 83.6
    assert ml["accuracy_within_10_min_percent"] == 99.3
    assert ml["accuracy_within_15_min_percent"] == 100.0

    # Verify measured gains
    assert data["mae_reduction_minutes"] == 3.66
    assert data["mae_reduction_percent"] == 57.6
    assert data["acc_within_5m_gain_percent"] == 34.7

    # Verify section performance list
    sections = data["sections"]
    assert len(sections) > 0
    first_sec = sections[0]
    assert "section_id" in first_sec
    assert "from_station" in first_sec
    assert "to_station" in first_sec
    assert "average_delay_minutes" in first_sec
    assert "average_running_time_minutes" in first_sec
    assert "delay_variance" in first_sec
    assert "recovery_tendency_minutes" in first_sec
    assert "recovery_status" in first_sec
    assert first_sec["recovery_status"] in ["RECOVERING", "DELAY_ACCUMULATING", "NEUTRAL"]
