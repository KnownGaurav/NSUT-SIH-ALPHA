import pytest
from fastapi.testclient import TestClient
from src.main import app


def test_full_21_step_system_workflow():
    """
    SIH 2026 Phase 17 Final System Test.
    Strictly verifies all 21 verification steps end-to-end.
    """
    with TestClient(app) as client:
        # 1. Start backend (FastAPI lifespan initialized)
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        # 2. Frontend bundle readiness
        root_res = client.get("/")
        assert root_res.status_code == 200

        # 3. Database connectivity
        trains_res = client.get("/api/trains")
        assert trains_res.status_code == 200
        trains = trains_res.json()
        assert len(trains) > 0

        # 4. Redis/Cache & Simulator initialization
        sim_status = client.get("/api/simulation/status")
        assert sim_status.status_code == 200
        active_trains = sim_status.json()
        assert len(active_trains) > 0

        # 5. Start simulator & select train
        train_num = active_trains[0]["train_number"]

        # 6. Train details
        td_res = client.get(f"/api/trains/{train_num}")
        assert td_res.status_code == 200
        assert td_res.json()["train_number"] == train_num

        # 7. Show train route
        route_res = client.get(f"/api/trains/{train_num}/route")
        assert route_res.status_code == 200
        stops = route_res.json()["stops"]
        assert len(stops) > 0

        # 8. Show current position
        pos_res = client.get(f"/api/trains/{train_num}/position")
        assert pos_res.status_code == 200
        pos = pos_res.json()
        assert "latitude" in pos and "longitude" in pos

        # 9. Calculate baseline ETA
        base_res = client.get(f"/api/trains/{train_num}/eta/baseline")
        assert base_res.status_code == 200
        assert len(base_res.json()["stations"]) > 0

        # 10. Calculate ML ETA
        ml_res = client.get(f"/api/trains/{train_num}/eta")
        assert ml_res.status_code == 200
        assert len(ml_res.json()["stations"]) > 0

        # 11. Show upcoming station ETAs
        first_stn = ml_res.json()["stations"][0]
        assert "station_code" in first_stn

        # 12. Trigger congestion
        c_res = client.post("/api/simulation/event", json={"train_number": train_num, "event": "CONGESTION"})
        assert c_res.status_code == 200
        assert c_res.json()["applied_event"] == "CONGESTION"

        # 13. Trigger speed restriction
        sr_res = client.post("/api/simulation/event", json={"train_number": train_num, "event": "SPEED_RESTRICTION"})
        assert sr_res.status_code == 200
        assert sr_res.json()["applied_event"] == "SPEED_RESTRICTION"

        # 14. Trigger unscheduled halt
        h_res = client.post("/api/simulation/event", json={"train_number": train_num, "event": "UNSCHEDULED_HALT"})
        assert h_res.status_code == 200
        assert h_res.json()["applied_event"] == "UNSCHEDULED_HALT"

        # 15. Trigger recovery
        rec_res = client.post("/api/simulation/event", json={"train_number": train_num, "event": "RECOVERY"})
        assert rec_res.status_code == 200
        assert rec_res.json()["applied_event"] == "RECOVERY"

        # 16. Verify ETA updates
        upd_eta = client.get(f"/api/trains/{train_num}/eta")
        assert upd_eta.status_code == 200
        assert upd_eta.json()["operational_event"] == "RECOVERY"

        # 17. Verify WebSocket updates
        with client.websocket_connect(f"/ws/trains/{train_num}") as ws:
            init_msg = ws.receive_json()
            assert "train_number" in init_msg or "stations" in init_msg
            ws.send_text("ping")
            pong_msg = ws.receive_json()
            assert pong_msg.get("type") == "pong"

        # 18. Verify explanation
        exp_res = client.get(f"/api/trains/{train_num}/eta/explanation")
        assert exp_res.status_code == 200
        assert "summary" in exp_res.json()

        # 19. Verify control-room dashboard
        cr_res = client.get("/api/trains/control-room/summary")
        assert cr_res.status_code == 200
        cr_data = cr_res.json()
        assert cr_data["total_active_trains"] > 0

        # 20. Verify analytics
        an_res = client.get("/api/trains/analytics/model-performance")
        assert an_res.status_code == 200
        an_data = an_res.json()
        assert "baseline_metrics" in an_data and "ml_metrics" in an_data
        assert an_data["mae_reduction_percent"] > 0

        # 21. Verify API documentation
        openapi_res = client.get("/openapi.json")
        assert openapi_res.status_code == 200
        assert "/api/trains" in openapi_res.json()["paths"]
