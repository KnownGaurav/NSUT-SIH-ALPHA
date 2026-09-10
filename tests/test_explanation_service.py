import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.services.explanation_service import explanation_service, ExplanationEngine
from src.services.websocket_manager import ws_manager


def test_explanation_speed_drop_and_delay_increase():
    """Verify deterministic attribution when train decelerates and accumulates delay."""
    explanation = explanation_service.explain_eta_change(
        train_number="12301",
        station_code="CNB",
        station_name="Kanpur Central",
        previous_eta_iso="2026-09-10T21:40:00",
        new_eta_iso="2026-09-10T21:49:00",
        shift_minutes=9.0,
        current_speed=38.0,
        previous_speed=112.0,
        current_delay=14.5,
        previous_delay=5.5,
        operational_event="SPEED_RESTRICTION",
        congestion_level="MEDIUM",
        weather_info={"is_severe_weather": False, "precipitation_mm": 0.0, "visibility_km": 10.0},
        is_halted=False
    )

    assert explanation.train_number == "12301"
    assert explanation.station_code == "CNB"
    assert explanation.direction == "DELAY_INCREASED"
    assert explanation.shift_minutes == 9.0
    assert "deferred by approximately 9.0 minutes" in explanation.summary

    categories = [f.category for f in explanation.contributing_factors]
    assert "SPEED" in categories
    assert "DELAY" in categories
    assert "CONGESTION" in categories

    speed_factor = next(f for f in explanation.contributing_factors if f.category == "SPEED")
    assert "112.0 km/h to 38.0 km/h" in speed_factor.metric_evidence

    delay_factor = next(f for f in explanation.contributing_factors if f.category == "DELAY")
    assert "+9.0 min" in delay_factor.metric_evidence


def test_explanation_unscheduled_halt():
    """Verify deterministic attribution for stalled train / unscheduled halt."""
    explanation = explanation_service.explain_eta_change(
        train_number="12301",
        station_code="ALJN",
        station_name="Aligarh Junction",
        previous_eta_iso="2026-09-10T18:30:00",
        new_eta_iso="2026-09-10T18:37:00",
        shift_minutes=7.0,
        current_speed=0.0,
        previous_speed=85.0,
        current_delay=12.0,
        previous_delay=5.0,
        operational_event="UNSCHEDULED_HALT",
        congestion_level="LOW",
        is_halted=True
    )

    assert explanation.direction == "DELAY_INCREASED"
    categories = [f.category for f in explanation.contributing_factors]
    assert "STATION_HALT" in categories
    assert "SPEED" in categories


def test_explanation_recovery():
    """Verify deterministic attribution when train recovers time via timetable slack."""
    explanation = explanation_service.explain_eta_change(
        train_number="12302",
        station_code="NDLS",
        station_name="New Delhi",
        previous_eta_iso="2026-09-11T10:15:00",
        new_eta_iso="2026-09-11T10:10:00",
        shift_minutes=-5.0,
        current_speed=130.0,
        previous_speed=105.0,
        current_delay=4.0,
        previous_delay=9.0,
        operational_event="RECOVERY",
        congestion_level="LOW",
        is_halted=False
    )

    assert explanation.direction == "DELAY_REDUCED"
    assert "advanced by approximately 5.0 minutes" in explanation.summary

    categories = [f.category for f in explanation.contributing_factors]
    assert "RECOVERY" in categories
    assert "SPEED" in categories
    assert "DELAY" in categories


def test_explanation_severe_weather():
    """Verify deterministic attribution under dense fog / severe monsoon rain."""
    explanation = explanation_service.explain_eta_change(
        train_number="12301",
        station_code="PRYJ",
        station_name="Prayagraj Junction",
        previous_eta_iso="2026-09-10T23:30:00",
        new_eta_iso="2026-09-10T23:36:00",
        shift_minutes=6.0,
        current_speed=65.0,
        previous_speed=65.0,
        current_delay=8.0,
        previous_delay=8.0,
        operational_event="NORMAL_OPERATION",
        congestion_level="LOW",
        weather_info={
            "is_severe_weather": True,
            "precipitation_mm": 24.5,
            "visibility_km": 0.8,
            "weather_condition": "Dense Fog"
        }
    )

    categories = [f.category for f in explanation.contributing_factors]
    assert "WEATHER" in categories
    weather_factor = next(f for f in explanation.contributing_factors if f.category == "WEATHER")
    assert "Dense Fog" in weather_factor.impact_description
    assert "0.8 km" in weather_factor.metric_evidence


def test_ws_manager_enriches_payload_with_explanation():
    """Verify WebSocket manager automatically attaches structured explanation on ETA drift."""
    train_num = "12301"
    
    # 1. First state
    state1 = {
        "train_number": train_num,
        "speed_kmh": 110.0,
        "current_delay_minutes": 2.0,
        "operational_event": "NORMAL_OPERATION",
        "stations": [
            {
                "station_code": "CNB",
                "station_name": "Kanpur Central",
                "predicted_eta": "2026-09-10T21:40:00",
                "is_passed": False
            }
        ]
    }
    ws_manager.update_state(train_num, state1)

    # 2. Updated state with delay and congestion
    state2 = {
        "train_number": train_num,
        "speed_kmh": 35.0,
        "current_delay_minutes": 8.5,
        "operational_event": "CONGESTION",
        "congestion": {"level": "HIGH"},
        "stations": [
            {
                "station_code": "CNB",
                "station_name": "Kanpur Central",
                "predicted_eta": "2026-09-10T21:49:00",
                "is_passed": False
            }
        ]
    }
    enriched = ws_manager.update_state(train_num, state2)
    assert enriched["has_eta_update"] is True
    assert enriched["explanation"] is not None
    assert enriched["explanation"]["train_number"] == train_num
    assert enriched["explanation"]["station_code"] == "CNB"
    assert enriched["explanation"]["direction"] == "DELAY_INCREASED"
    assert len(enriched["explanation"]["contributing_factors"]) >= 2


def test_api_eta_explanation_endpoint():
    """Verify GET /api/trains/{train_number}/eta/explanation returns structured JSON."""
    client = TestClient(app)
    resp = client.get("/api/trains/12301/eta/explanation")
    assert resp.status_code == 200
    data = resp.json()

    assert data["train_number"] == "12301"
    assert "station_code" in data
    assert "new_eta" in data
    assert "direction" in data
    assert "summary" in data
    assert isinstance(data["contributing_factors"], list)
