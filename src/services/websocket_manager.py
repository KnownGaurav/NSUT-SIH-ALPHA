import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Set, Optional, Any, List
from fastapi import WebSocket, WebSocketDisconnect

from src.services.explanation_service import explanation_service, ETAChangeExplanation

logger = logging.getLogger("railway_eta.websocket")


class ConnectionManager:
    """
    Manages active client WebSocket subscriptions per train.
    Supports in-memory state store with deterministic change explanations.
    """

    def __init__(self):
        # train_number -> Set[WebSocket]
        self._active_connections: Dict[str, Set[WebSocket]] = {}
        # train_number -> latest calculated state / ETA cache
        self._latest_eta_state: Dict[str, Dict[str, Any]] = {}
        # train_number -> {station_code: prev_eta_str}
        self._previous_etas: Dict[str, Dict[str, str]] = {}
        # train_number -> {"speed": float, "delay": float, "event": str}
        self._previous_telemetry: Dict[str, Dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket, train_number: str):
        await websocket.accept()
        if train_number not in self._active_connections:
            self._active_connections[train_number] = set()
        self._active_connections[train_number].add(websocket)
        logger.info(f"Client connected to WS for train {train_number}. Active connections: {len(self._active_connections[train_number])}")

        if train_number in self._latest_eta_state:
            try:
                await websocket.send_text(json.dumps(self._latest_eta_state[train_number]))
            except Exception as e:
                logger.warning(f"Failed to send initial cached ETA to client: {e}")

    def disconnect(self, websocket: WebSocket, train_number: str):
        if train_number in self._active_connections:
            self._active_connections[train_number].discard(websocket)
            if not self._active_connections[train_number]:
                del self._active_connections[train_number]
        logger.info(f"Client disconnected from WS for train {train_number}")

    def update_state(self, train_number: str, eta_payload: Dict[str, Any], reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Updates train state cache and calculates diffs from previous station ETAs:
        - Detects station ETA modifications
        - Computes deterministic causal factor explanation using explanation_service
        - Enriches payload with previous_eta, delta_minutes, reason, and structured explanation
        """
        prev_map = self._previous_etas.get(train_number, {})
        new_prev_map = {}
        stations_diff = []
        any_eta_changed = False
        primary_explanation: Optional[Dict[str, Any]] = None

        curr_speed = float(eta_payload.get("speed_kmh", 100.0))
        curr_delay = float(eta_payload.get("current_delay_minutes", 0.0))
        op_event = str(eta_payload.get("operational_event", "NORMAL_OPERATION"))
        cong_obj = eta_payload.get("congestion") or {}
        cong_level = cong_obj.get("level", "LOW")
        weather_obj = eta_payload.get("weather") or {}

        prev_telemetry = self._previous_telemetry.get(train_number, {})
        prev_speed = prev_telemetry.get("speed")
        prev_delay = prev_telemetry.get("delay")

        stations = eta_payload.get("stations", [])
        for stn in stations:
            code = stn.get("station_code")
            name = stn.get("station_name", code)
            curr_eta = stn.get("predicted_eta") or stn.get("dynamic_eta")
            is_passed = stn.get("is_passed", False)

            prev_eta = prev_map.get(code)
            stn_copy = dict(stn)

            if not is_passed and curr_eta:
                new_prev_map[code] = curr_eta
                if prev_eta and prev_eta != curr_eta:
                    try:
                        t_prev = datetime.fromisoformat(prev_eta)
                        t_curr = datetime.fromisoformat(curr_eta)
                        diff_sec = (t_curr - t_prev).total_seconds()
                        diff_min = round(diff_sec / 60.0, 1)

                        if abs(diff_min) >= 0.5:
                            # Generate deterministic causal explanation
                            expl = explanation_service.explain_eta_change(
                                train_number=train_number,
                                station_code=code,
                                station_name=name,
                                previous_eta_iso=prev_eta,
                                new_eta_iso=curr_eta,
                                shift_minutes=diff_min,
                                current_speed=curr_speed,
                                previous_speed=prev_speed,
                                current_delay=curr_delay,
                                previous_delay=prev_delay,
                                operational_event=op_event,
                                congestion_level=cong_level,
                                weather_info=weather_obj,
                                is_halted=(curr_speed < 1.0)
                            )
                            expl_dict = expl.model_dump()

                            stn_copy["eta_updated"] = True
                            stn_copy["previous_eta"] = prev_eta
                            stn_copy["eta_shift_minutes"] = diff_min
                            stn_copy["update_reason"] = reason or expl.summary
                            stn_copy["explanation"] = expl_dict
                            any_eta_changed = True

                            if primary_explanation is None:
                                primary_explanation = expl_dict
                        else:
                            stn_copy["eta_updated"] = False
                            stn_copy["previous_eta"] = prev_eta
                            stn_copy["eta_shift_minutes"] = 0.0
                    except Exception as e:
                        logger.warning(f"Error computing diff for {code}: {e}")
                        stn_copy["eta_updated"] = False
                else:
                    stn_copy["eta_updated"] = False
                    stn_copy["previous_eta"] = prev_eta or curr_eta
                    stn_copy["eta_shift_minutes"] = 0.0
            else:
                stn_copy["eta_updated"] = False

            stations_diff.append(stn_copy)

        self._previous_etas[train_number] = new_prev_map
        self._previous_telemetry[train_number] = {
            "speed": curr_speed,
            "delay": curr_delay,
            "event": op_event
        }

        # If no station triggered a shift, construct general operational explanation
        if primary_explanation is None and any_eta_changed:
            first_up = next((s for s in stations_diff if not s.get("is_passed")), None)
            if first_up:
                primary_explanation = first_up.get("explanation")

        enriched_payload = dict(eta_payload)
        enriched_payload["stations"] = stations_diff
        enriched_payload["has_eta_update"] = any_eta_changed
        enriched_payload["update_reason"] = reason or ("Dynamic recalculation" if any_eta_changed else "Periodic telemetry synchronization")
        enriched_payload["explanation"] = primary_explanation
        enriched_payload["pushed_at"] = datetime.now(timezone.utc).isoformat()

        self._latest_eta_state[train_number] = enriched_payload
        return enriched_payload

    async def broadcast_train_update(self, train_number: str, payload: Dict[str, Any]):
        """Broadcasts updated payload to all active subscribers for the train."""
        conns = self._active_connections.get(train_number, set())
        if not conns:
            return

        msg = json.dumps(payload)
        to_remove = set()
        for ws in conns:
            try:
                await ws.send_text(msg)
            except Exception as e:
                logger.warning(f"Error broadcasting to WebSocket: {e}")
                to_remove.add(ws)

        for dead_ws in to_remove:
            self.disconnect(dead_ws, train_number)


ws_manager = ConnectionManager()
