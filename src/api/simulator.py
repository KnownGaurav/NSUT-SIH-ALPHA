from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from src.simulator.train_simulator import simulator, SimulationEvent
from src.services.data_providers.base import NormalizedTrainState

router = APIRouter()


class TriggerEventRequest(BaseModel):
    train_number: str
    event: SimulationEvent


class ResetTrainRequest(BaseModel):
    train_number: str


class TickRequest(BaseModel):
    delta_seconds: float = 3.0
    speed_multiplier: float = 2.0


class EventTriggerResponse(BaseModel):
    status: str
    train_number: str
    applied_event: str
    new_speed_kmh: float
    current_delay_minutes: float


@router.post("/event", response_model=EventTriggerResponse)
async def trigger_simulation_event(req: TriggerEventRequest):
    """
    Triggers an operational event (e.g. NORMAL_OPERATION, CONGESTION, UNSCHEDULED_HALT, RECOVERY)
    for a specific simulated train.
    """
    success = simulator.trigger_event(req.train_number, req.event)
    if not success:
        from src.main import register_simulator_trains
        await register_simulator_trains()
        success = simulator.trigger_event(req.train_number, req.event)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Train '{req.train_number}' is not active in the simulation engine"
        )

    state = simulator.get_state(req.train_number)

    # Immediately recalculate and broadcast updated dynamic ETA over WebSocket
    from src.services.realtime_service import recalculate_and_broadcast_train_eta
    event_reason_map = {
        "NORMAL_OPERATION": "Normal line speed restored",
        "SPEED_RESTRICTION": "Caution order applied: Speed restricted to 40 km/h",
        "CONGESTION": "Section headway congestion & signal check queuing",
        "UNSCHEDULED_HALT": "Unscheduled operational halt (train stopped at signal)",
        "RECOVERY": "Priority green corridor assigned: Slack recovery underway"
    }
    reason_text = event_reason_map.get(req.event.value, f"Operational event {req.event.value}")
    await recalculate_and_broadcast_train_eta(req.train_number, reason=reason_text, explicit_state=state)

    return EventTriggerResponse(
        status="ok",
        train_number=req.train_number,
        applied_event=req.event.value,
        new_speed_kmh=state.speed if state else 0.0,
        current_delay_minutes=state.current_delay if state else 0.0
    )


@router.get("/status", response_model=List[NormalizedTrainState])
async def get_simulation_status():
    """
    Retrieve real-time simulation state across all registered trains.
    """
    return simulator.get_all_states()


@router.post("/tick")
async def step_simulation_tick(req: TickRequest):
    """
    Manually advances the simulator physics clock by delta_seconds.
    """
    simulator.tick(delta_seconds=req.delta_seconds, speed_multiplier=req.speed_multiplier)
    return {
        "status": "ok",
        "delta_seconds": req.delta_seconds,
        "speed_multiplier": req.speed_multiplier,
        "active_trains": len(simulator.get_all_states())
    }


@router.post("/reset")
async def reset_simulation_train(req: ResetTrainRequest):
    """
    Resets train to origin segment and 0 delay.
    """
    simulator.reset_train(req.train_number)
    state = simulator.get_state(req.train_number)
    return {
        "status": "ok",
        "train_number": req.train_number,
        "reset_state": state
    }
