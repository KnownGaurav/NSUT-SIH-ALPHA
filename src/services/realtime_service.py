import logging
from typing import Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.db.session import AsyncSessionLocal
from src.db.models import Route, RouteStation
from src.services.data_providers.base import NormalizedTrainState
from src.services.data_providers.factory import get_data_provider
from src.services.weather_service import weather_service
from src.ml.predict import dynamic_eta_predictor
from src.services.websocket_manager import ws_manager

logger = logging.getLogger("railway_eta.services.realtime")


async def recalculate_and_broadcast_train_eta(
    train_number: str,
    reason: Optional[str] = None,
    explicit_state: Optional[NormalizedTrainState] = None
) -> Optional[Dict[str, Any]]:
    """
    Core Real-Time ETA Pipeline:
    1. Obtains latest train state (from provider or passed explicitly)
    2. Retrieves route stops from database
    3. Fetches localized environmental weather
    4. Recalculates dynamic ML ETA
    5. Detects differences vs. previous ETA broadcast
    6. Broadcasts enriched payload to WebSocket clients
    """
    # 1. Retrieve route stops & train metadata
    stops = []
    train_type = "Rajdhani Express"
    async with AsyncSessionLocal() as session:
        route_stmt = (
            select(Route)
            .where(Route.train_number == train_number)
            .options(
                selectinload(Route.route_stations).selectinload(RouteStation.station),
                selectinload(Route.train)
            )
        )
        route_res = await session.execute(route_stmt)
        route = route_res.scalar_one_or_none()
        if not route:
            return None

        train_type = route.train.train_type if route.train else "Rajdhani Express"
        for rs in sorted(route.route_stations, key=lambda x: x.station_sequence):
            stops.append({
                "sequence": rs.station_sequence,
                "station_code": rs.station_code,
                "station_name": rs.station.station_name if rs.station else rs.station_code,
                "scheduled_arrival": rs.scheduled_arrival,
                "scheduled_departure": rs.scheduled_departure,
                "distance_from_origin_km": rs.distance_from_origin,
                "scheduled_dwell_minutes": rs.scheduled_dwell_minutes,
                "day_offset": rs.day_offset
            })

    # 2. Obtain train state
    state = explicit_state
    if not state:
        provider = get_data_provider()
        state = await provider.get_train_position(train_number)

    if not state:
        # Fallback to database live_positions or route origin default
        from src.db.models import LivePosition
        async with AsyncSessionLocal() as session:
            pos_stmt = (
                select(LivePosition)
                .where(LivePosition.train_number == train_number)
                .order_by(LivePosition.timestamp.desc())
                .limit(1)
            )
            pos_res = await session.execute(pos_stmt)
            pos = pos_res.scalar_one_or_none()
            if pos:
                state = NormalizedTrainState(
                    train_number=pos.train_number,
                    timestamp=pos.timestamp or datetime.now(timezone.utc),
                    latitude=pos.latitude,
                    longitude=pos.longitude,
                    speed=pos.speed,
                    bearing=0.0,
                    current_delay=pos.current_delay,
                    current_station=pos.current_station,
                    next_station=pos.next_station,
                    data_source=pos.data_source,
                    operational_event="NORMAL_OPERATION"
                )
            elif stops:
                state = NormalizedTrainState(
                    train_number=train_number,
                    timestamp=datetime.now(timezone.utc),
                    latitude=28.6424,
                    longitude=77.2195,
                    speed=100.0,
                    bearing=0.0,
                    current_delay=0.0,
                    current_station=stops[0]["station_code"],
                    next_station=stops[1]["station_code"] if len(stops) > 1 else stops[0]["station_code"],
                    data_source="SIMULATION",
                    operational_event="NORMAL_OPERATION"
                )

    if not state:
        logger.warning(f"No train state available to broadcast for train {train_number}")
        return None

    # 3. Weather
    weather = await weather_service.get_weather(state.latitude, state.longitude)

    # 4. Recalculate dynamic ETA
    dynamic_resp = dynamic_eta_predictor.predict_upcoming_etas(
        train_state=state,
        stops=stops,
        train_type=train_type,
        weather_data=weather
    )
    eta_dict = dynamic_resp.model_dump()
    eta_dict["latitude"] = state.latitude
    eta_dict["longitude"] = state.longitude
    eta_dict["speed_kmh"] = state.speed

    # 5. Update state store & compute diffs
    enriched_payload = ws_manager.update_state(train_number, eta_dict, reason=reason)

    # 6. Broadcast via WebSocket
    await ws_manager.broadcast_train_update(train_number, enriched_payload)
    return enriched_payload
