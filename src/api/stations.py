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
    now_local = datetime.now()
    now_utc = datetime.now(timezone.utc)
    arrival_items = []

    # Map station names cache
    all_stn_res = await db.execute(select(Station.station_code, Station.station_name))
    stn_name_map = {r[0]: r[1] for r in all_stn_res.all()}

    # Sort route_stations deterministically
    valid_rs = [rs for rs in route_stations if rs.route and rs.route.train]
    valid_rs.sort(key=lambda rs: int(rs.route.train.train_number) if rs.route.train.train_number.isdigit() else 0)
    num_trains = len(valid_rs)

    # Calculate staggered timetable slots anchored to current operational cycle
    step_minutes = max(8, 60 // max(1, num_trains))

    for idx, rs in enumerate(valid_rs):
        route = rs.route
        train = route.train
        t_num = train.train_number

        # Telemetry from provider
        state = await provider.get_train_position(t_num)
        current_delay = float(state.current_delay if state else 0.0)

        is_origin = (train.source == code_upper) or (rs.station_sequence == 1)
        is_dest = (train.destination == code_upper)
        is_intermediate = not is_origin and not is_dest

        # Schedule slot relative to current operational clock
        # Each train is assigned a deterministic minute slot within the hour
        slot_min = (idx * step_minutes) % 60
        cand_dt = now_local.replace(minute=slot_min, second=0, microsecond=0)

        # If slot for current hour has passed by more than 15 min, roll to next hour
        if cand_dt < now_local - timedelta(minutes=15):
            sched_base_dt = cand_dt + timedelta(hours=1)
        else:
            sched_base_dt = cand_dt

        # Dwell and arrival / departure times
        dwell_mins = max(5, int(rs.scheduled_dwell_minutes or 10))
        if is_origin:
            sched_arr_dt = sched_base_dt
            sched_dep_dt = sched_base_dt
        elif is_dest:
            sched_arr_dt = sched_base_dt
            sched_dep_dt = sched_base_dt
        else:
            sched_arr_dt = sched_base_dt
            sched_dep_dt = sched_base_dt + timedelta(minutes=dwell_mins)

        # Dynamic Predicted ETA adjusts scheduled arrival by real-time delay
        sim_arrival_dt = sched_arr_dt + timedelta(minutes=current_delay)

        # 12-hour formatted time strings
        formatted_sched_arr = sched_arr_dt.strftime("%I:%M %p")
        formatted_sched_dep = sched_dep_dt.strftime("%I:%M %p")
        dyn_eta_str = sim_arrival_dt.strftime("%I:%M %p")

        # Assign realistic platform spread: group slightly to allow authentic clearance conflicts
        assigned_pf = f"PF-{((int(t_num) % min(total_platforms, 5)) + 1)}"

        # Delay status category
        if current_delay <= 5.0:
            delay_status = "on_time"
        elif current_delay <= 30.0:
            delay_status = "moderate"
        else:
            delay_status = "severe"

        # Operational status based on dynamic arrival proximity to current clock
        diff_to_eta = (sim_arrival_dt - now_local).total_seconds() / 60.0
        if state and state.current_station == code_upper:
            curr_status = "DOCKED"
        elif -8.0 <= diff_to_eta <= 3.0:
            curr_status = "DOCKED"
        elif 3.0 < diff_to_eta <= 35.0:
            curr_status = "APPROACHING"
        elif diff_to_eta > 35.0:
            curr_status = "SCHEDULED"
        else:
            curr_status = "DEPARTED"

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
        est_depot_dep = (now_local + timedelta(minutes=available_turnaround)).strftime("%I:%M %p")

        arrival_items.append({
            "train_number": t_num,
            "train_name": train.train_name,
            "train_type": train.train_type,
            "source": train.source,
            "destination": train.destination,
            "source_name": stn_name_map.get(train.source, train.source),
            "destination_name": stn_name_map.get(train.destination, train.destination),
            "scheduled_arrival": formatted_sched_arr,
            "scheduled_departure": formatted_sched_dep,
            "dynamic_predicted_eta": dyn_eta_str,
            "delay_minutes": round(current_delay, 1),
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

    # Filter by window_hours horizon and sort chronologically by dynamic arrival time
    window_end = now_local + timedelta(hours=window_hours)
    filtered_items = [
        item for item in arrival_items 
        if item["_arrival_dt"] <= window_end
    ]
    if not filtered_items:
        filtered_items = arrival_items

    filtered_items.sort(key=lambda x: x["_arrival_dt"])

    # Platform Conflict Detection Logic:
    # If two trains share the same assigned_platform and their dynamic arrival/dwell overlaps within 25 minutes
    active_conflicts = 0
    for i in range(len(filtered_items)):
        for j in range(i + 1, len(filtered_items)):
            item_a = filtered_items[i]
            item_b = filtered_items[j]

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
    for itm in filtered_items:
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

