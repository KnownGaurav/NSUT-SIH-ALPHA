import pytest
from starlette.testclient import TestClient
from src.main import app
from src.services.websocket_manager import ws_manager
from src.services.realtime_service import recalculate_and_broadcast_train_eta


def test_websocket_connection_and_echo():
    client = TestClient(app)
    with client.websocket_connect("/ws/trains/12302") as websocket:
        # Send heartbeat ping
        websocket.send_text("ping")
        resp = websocket.receive_text()
        # If server sends initial cached ETA on connect, next text is pong
        if "train_number" in resp:
            resp = websocket.receive_text()
        assert resp == '{"type":"pong"}'


def test_ws_manager_diff_calculation():
    # Test state update & diff calculation in ws_manager
    payload1 = {
        "train_number": "12302",
        "stations": [
            {
                "station_code": "CNB",
                "predicted_eta": "2026-09-10T21:40:00",
                "is_passed": False
            }
        ]
    }
    enriched1 = ws_manager.update_state("12302", payload1)
    assert enriched1["stations"][0]["eta_updated"] is False

    # Simulate updated arrival with delay addition
    payload2 = {
        "train_number": "12302",
        "stations": [
            {
                "station_code": "CNB",
                "predicted_eta": "2026-09-10T21:48:00",
                "is_passed": False
            }
        ]
    }
    enriched2 = ws_manager.update_state("12302", payload2, reason="Signal check at CNB outer")
    stn_diff = enriched2["stations"][0]
    assert stn_diff["eta_updated"] is True
    assert stn_diff["previous_eta"] == "2026-09-10T21:40:00"
    assert stn_diff["eta_shift_minutes"] == 8.0
    assert stn_diff["update_reason"] == "Signal check at CNB outer"
    assert enriched2["has_eta_update"] is True


@pytest.mark.asyncio
async def test_recalculate_and_broadcast_service():
    enriched = await recalculate_and_broadcast_train_eta("12302", reason="Integration test broadcast")
    assert enriched is not None
    assert enriched["train_number"] == "12302"
    assert "stations" in enriched
    assert len(enriched["stations"]) > 0
