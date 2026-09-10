import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from src.services.websocket_manager import ws_manager

logger = logging.getLogger("railway_eta.api.ws")
router = APIRouter()


@router.websocket("/ws/trains/{train_number}")
async def websocket_train_eta_endpoint(websocket: WebSocket, train_number: str):
    """
    Real-time WebSocket feed for dynamic train ETA updates, delay alerts,
    and ETA difference broadcasts.
    """
    await ws_manager.connect(websocket, train_number)
    try:
        while True:
            # Keep-alive heartbeat listener from client (e.g. {"type": "ping"})
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, train_number)
    except Exception as e:
        logger.warning(f"WebSocket error on train {train_number}: {e}")
        ws_manager.disconnect(websocket, train_number)
