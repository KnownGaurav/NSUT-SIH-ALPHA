from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_db
from src.db.models import Station
from src.models.api_schemas import StationResponse

router = APIRouter()


@router.get("", response_model=List[StationResponse])
async def list_stations(db: AsyncSession = Depends(get_db)):
    """
    Retrieve all registered railway stations with geographical coordinates, zone, and state.
    """
    result = await db.execute(select(Station).order_by(Station.station_code))
    stations = result.scalars().all()
    return stations


@router.get("/{station_code}", response_model=StationResponse)
async def get_station_detail(station_code: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieve station geographic coordinates, state, and railway operational zone.
    """
    code_upper = station_code.strip().upper()
    result = await db.execute(select(Station).where(Station.station_code == code_upper))
    station = result.scalar_one_or_none()

    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station with code '{station_code}' not found"
        )

    return station


from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import selectinload
from src.db.models import Train, Route, RouteStation
from src.models.api_schemas import StationArrivalsResponse, StationArrivalItem, TurnaroundImpact
from src.services.data_providers.factory import get_data_provider


@router.get("/{station_code}/arrivals", response_model=StationArrivalsResponse)
async def get_station_arrivals(
    station_code: str,
    window_hours: int = 4,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve real-time and scheduled upcoming train arrivals/departures for a specific station,
    including dynamic predicted ETAs, platform occupancy, platform conflict detection,
    and turnaround/cleaning depot impact.
    """
    code_upper = station_code.strip().upper()
    stn_res = await db.execute(select(Station).where(Station.station_code == code_upper))
    station = stn_res.scalar_one_or_none()

    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station with code '{station_code}' not found"
        )

    # Station total platforms mapping (realistic terminal capacities)
    platform_capacities = {
        "NDLS": 16, "HWH": 23, "CNB": 10, "PRYJ": 10, "BSB": 9,
        "MMCT": 8, "DBG": 5, "TPTY": 6, "NZM": 8, "GKP": 10
    }
    total_platforms = platform_capacities.get(code_upper, 8)

    # Query all routes that pass through or terminate/originate at this station
    rs_stmt = (
        select(RouteStation)
        .options(
            selectinload(RouteStation.route).selectinload(Route.train)
        )
        .where(RouteStation.station_code == code_upper)
    )
    rs_res = await db.execute(rs_stmt)
    route_stations = rs_res.scalars().all()

    provider = get_data_provider()
    now_utc = datetime.now(timezone.utc)
    arrival_items = []

    # Map station names cache
    all_stn_res = await db.execute(select(Station.station_code, Station.station_name))
    stn_name_map = {r[0]: r[1] for r in all_stn_res.all()}

    for rs in route_stations:
        route = rs.route
        if not route or not route.train:
            continue
        train = route.train
        t_num = train.train_number

        # Telemetry from provider
        state = await provider.get_train_position(t_num)
        current_delay = float(state.current_delay if state else 0.0)

        # Scheduled Arrival / Departure strings
        sched_arr = rs.scheduled_arrival
        sched_dep = rs.scheduled_departure
        is_origin = (train.source == code_upper) or (rs.station_sequence == 1)
        is_dest = (train.destination == code_upper)
        is_intermediate = not is_origin and not is_dest

        # Assign realistic platform based on train number hash
        assigned_pf = f"PF-{((int(t_num) % total_platforms) + 1)}"

        # Compute dynamic predicted ETA timestamp
        # Base on scheduled time adjusted by current delay
        ref_time_str = sched_arr if sched_arr else sched_dep
        dyn_eta_str = None
        sim_arrival_dt = None

        if ref_time_str:
            try:
                parts = [int(p) for p in ref_time_str.split(":")[:2]]
                base_dt = now_utc.replace(hour=parts[0], minute=parts[1], second=0, microsecond=0)
                # Apply current delay
                sim_arrival_dt = base_dt + timedelta(minutes=current_delay)
                dyn_eta_str = sim_arrival_dt.strftime("%I:%M %p")
            except Exception:
                dyn_eta_str = ref_time_str

        # Delay status category
        if current_delay <= 5.0:
            delay_status = "on_time"
        elif current_delay <= 30.0:
            delay_status = "moderate"
        else:
            delay_status = "severe"

        # Determine current operational status
        curr_status = "APPROACHING"
        if state and state.current_station == code_upper:
            curr_status = "DOCKED"
        elif state and is_origin and state.speed == 0.0:
            curr_status = "SCHEDULED"

        # Turnaround and cleaning readiness calculations
        sched_turnaround = 120 if is_dest else 15
        available_turnaround = max(10, int(sched_turnaround - current_delay))
        
        if available_turnaround >= 60:
            depot_status = "ON_SCHEDULE"
        elif available_turnaround >= 30:
            depot_status = "TIGHT_WINDOW"
        else:
            depot_status = "DELAYED_HANDOVER"

        crew_ready = available_turnaround >= 25
        est_depot_dep = (now_utc + timedelta(minutes=available_turnaround)).strftime("%I:%M %p")

        arrival_items.append({
            "train_number": t_num,
            "train_name": train.train_name,
            "train_type": train.train_type,
            "source": train.source,
            "destination": train.destination,
            "source_name": stn_name_map.get(train.source, train.source),
            "destination_name": stn_name_map.get(train.destination, train.destination),
            "scheduled_arrival": sched_arr,
            "scheduled_departure": sched_dep,
            "dynamic_predicted_eta": dyn_eta_str,
            "delay_minutes": current_delay,
            "delay_status": delay_status,
            "assigned_platform": assigned_pf,
            "platform_conflict_flag": False,
            "conflict_with_train": None,
            "conflict_reason": None,
            "turnaround_impact": TurnaroundImpact(
                scheduled_turnaround_minutes=sched_turnaround,
                available_turnaround_minutes=available_turnaround,
                cleaning_depot_status=depot_status,
                crew_handover_ready=crew_ready,
                estimated_depot_departure=est_depot_dep
            ),
            "is_origin": is_origin,
            "is_destination": is_dest,
            "is_intermediate": is_intermediate,
            "current_status": curr_status,
            "_arrival_dt": sim_arrival_dt
        })

    # Platform Conflict Detection Logic:
    # If two trains share the same assigned_platform and their dynamic arrival/dwell overlaps within 20 minutes
    active_conflicts = 0
    for i in range(len(arrival_items)):
        for j in range(i + 1, len(arrival_items)):
            item_a = arrival_items[i]
            item_b = arrival_items[j]

            if item_a["assigned_platform"] == item_b["assigned_platform"]:
                dt_a = item_a.get("_arrival_dt")
                dt_b = item_b.get("_arrival_dt")
                if dt_a and dt_b:
                    diff_mins = abs((dt_a - dt_b).total_seconds()) / 60.0
                    if diff_mins < 25.0:  # Conflict threshold: < 25 min clearance window
                        item_a["platform_conflict_flag"] = True
                        item_a["conflict_with_train"] = item_b["train_number"]
                        item_a["conflict_reason"] = f"Dynamic ETA overlaps on {item_a['assigned_platform']} with {item_b['train_number']} (Clearance: {int(diff_mins)} min)"
                        
                        item_b["platform_conflict_flag"] = True
                        item_b["conflict_with_train"] = item_a["train_number"]
                        item_b["conflict_reason"] = f"Dynamic ETA overlaps on {item_b['assigned_platform']} with {item_a['train_number']} (Clearance: {int(diff_mins)} min)"
                        active_conflicts += 1

    # Cleanup temporary sorting keys
    final_items = []
    for itm in arrival_items:
        itm.pop("_arrival_dt", None)
        final_items.append(StationArrivalItem(**itm))

    return StationArrivalsResponse(
        station_code=code_upper,
        station_name=station.station_name,
        zone=station.zone,
        state=station.state,
        total_platforms=total_platforms,
        query_window_hours=window_hours,
        generated_at=now_utc.isoformat(),
        active_conflicts_count=active_conflicts,
        arrivals=final_items
    )

