import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Train, Route, RouteStation, Station
from src.services.data_providers.factory import get_data_provider

logger = logging.getLogger("railway_eta.train_service")


async def ensure_train_ingested(train_number: str, db: AsyncSession) -> Train:
    """
    Ensure a train and its route stations exist in the database.
    If not already in local database, fetch from active live provider (e.g. Rail Radar)
    and dynamically persist it so that ETA models, maps, and timelines work seamlessly.
    """
    train_res = await db.execute(
        select(Train)
        .options(selectinload(Train.routes).selectinload(Route.route_stations))
        .where(Train.train_number == train_number)
    )
    existing_train = train_res.scalar_one_or_none()
    if existing_train and existing_train.routes and len(existing_train.routes[0].route_stations) > 0:
        return existing_train

    provider = get_data_provider()
    # Check if provider has live fetch capabilities
    if hasattr(provider, "get_train_details") and hasattr(provider, "get_train_live_data"):
        try:
            logger.info(f"Dynamically ingesting train {train_number} from live provider...")
            details = await provider.get_train_details(train_number)
            live_data = await provider.get_train_live_data(train_number)

            if details:
                train_name = details.get("name", f"Train {train_number}")
                train_type = details.get("type", "Express")
                src_code = details.get("source", {}).get("code", "NDLS")
                dst_code = details.get("destination", {}).get("code", "HWH")
                total_dist = float(details.get("distance") or 1000.0)

                # Ensure source & destination stations exist
                for stn_key in ["source", "destination"]:
                    stn_data = details.get(stn_key, {})
                    code = stn_data.get("code")
                    if code:
                        stn_chk = await db.execute(select(Station).where(Station.station_code == code))
                        if not stn_chk.scalar_one_or_none():
                            db.add(Station(
                                station_code=code,
                                station_name=stn_data.get("name", code),
                                latitude=float(stn_data.get("lat") or 28.6139),
                                longitude=float(stn_data.get("lng") or 77.2090),
                                zone="NR",
                                state="Delhi"
                            ))
                await db.flush()

                # Upsert Train
                if not existing_train:
                    train_obj = Train(
                        train_number=train_number,
                        train_name=train_name,
                        train_type=train_type,
                        source=src_code,
                        destination=dst_code
                    )
                    db.add(train_obj)
                    await db.flush()
                else:
                    train_obj = existing_train

                # Create Route and RouteStations from scheduled halts
                route_id = f"ROUTE_{train_number}_UP"
                route_chk = await db.execute(select(Route).where(Route.route_id == route_id))
                route_obj = route_chk.scalar_one_or_none()

                if not route_obj:
                    route_obj = Route(
                        route_id=route_id,
                        train_number=train_number,
                        direction="UP",
                        total_distance_km=total_dist
                    )
                    db.add(route_obj)
                    await db.flush()

                # Extract scheduled halts from live data
                halts = []
                if live_data and "route" in live_data:
                    halts = [s for s in live_data["route"] if s.get("isHalt")]

                if not halts:
                    # Minimal 2-station fallback if no halt list
                    halts = [
                        {"sequence": 1, "stationCode": src_code, "stationName": details.get("source", {}).get("name", src_code), "distance": 0.0},
                        {"sequence": 2, "stationCode": dst_code, "stationName": details.get("destination", {}).get("name", dst_code), "distance": total_dist}
                    ]

                # Build lookup of authentic station coordinates from metadata route
                stn_coords_lookup = {}
                for r_item in details.get("route", []):
                    stn_meta = r_item.get("station", {})
                    s_code = stn_meta.get("code")
                    if s_code and stn_meta.get("lat") and stn_meta.get("lng"):
                        stn_coords_lookup[s_code] = (float(stn_meta["lat"]), float(stn_meta["lng"]))

                seq_num = 1
                for h in halts:
                    stn_code = h.get("stationCode")
                    stn_name = h.get("stationName", stn_code)
                    dist = float(h.get("distance") or 0.0)

                    # Determine real station latitude & longitude
                    real_lat, real_lng = stn_coords_lookup.get(stn_code, (None, None))
                    if real_lat is None or real_lng is None:
                        real_lat = 28.6139 + (seq_num * 0.1)
                        real_lng = 77.2090 + (seq_num * 0.1)

                    # Ensure station exists
                    stn_chk = await db.execute(select(Station).where(Station.station_code == stn_code))
                    existing_stn = stn_chk.scalar_one_or_none()
                    if not existing_stn:
                        db.add(Station(
                            station_code=stn_code,
                            station_name=stn_name,
                            latitude=real_lat,
                            longitude=real_lng,
                            zone="NR",
                            state="India"
                        ))
                        await db.flush()
                    elif existing_stn and real_lat != existing_stn.latitude and stn_code in stn_coords_lookup:
                        existing_stn.latitude = real_lat
                        existing_stn.longitude = real_lng
                        existing_stn.station_name = stn_name
                        await db.flush()

                    arr_time = h.get("scheduledArrival")
                    if arr_time and "T" in str(arr_time):
                        arr_time = str(arr_time).split("T")[1][:8]

                    dep_time = h.get("scheduledDeparture")
                    if dep_time and "T" in str(dep_time):
                        dep_time = str(dep_time).split("T")[1][:8]

                    rs_chk = await db.execute(
                        select(RouteStation).where(
                            RouteStation.route_id == route_id,
                            RouteStation.station_code == stn_code
                        )
                    )
                    if not rs_chk.scalar_one_or_none():
                        db.add(RouteStation(
                            route_id=route_id,
                            station_code=stn_code,
                            station_sequence=seq_num,
                            distance_from_origin=dist,
                            scheduled_arrival=arr_time or "12:00:00",
                            scheduled_departure=dep_time or "12:05:00",
                            scheduled_dwell_minutes=2.0,
                            day_offset=int(h.get("arrivalDay") or 1) - 1
                        ))
                    seq_num += 1

                await db.commit()
                logger.info(f"Successfully ingested train {train_number} with {seq_num - 1} stops.")

                # Register train in simulator so it advances and modulates delays dynamically
                try:
                    from src.simulator.train_simulator import simulator
                    sim_stops = []
                    for h_idx, h_stop in enumerate(details.get("halts", [])):
                        code = h_stop.get("stationCode", "")
                        lat = float(h_stop.get("lat") or 0.0)
                        lng = float(h_stop.get("lng") or 0.0)
                        if not lat or not lng:
                            if code in stn_coords_lookup:
                                lat, lng = stn_coords_lookup[code]
                        if lat and lng:
                            sim_stops.append({
                                "sequence": h_idx + 1,
                                "station_code": code,
                                "station_name": h_stop.get("stationName", code),
                                "latitude": lat,
                                "longitude": lng
                            })
                    if len(sim_stops) > 1:
                        # Extract initial delay from live data or set realistic default
                        curr_loc = live_data.get("currentLocation") or {} if live_data else {}
                        init_del = float(live_data.get("delayMinutes") or curr_loc.get("delayMinutes") or 14.0) if live_data else 14.0
                        simulator.register_train(
                            train_number=train_number,
                            stops=sim_stops,
                            initial_delay=init_del,
                            start_segment=1
                        )
                        logger.info(f"Registered dynamically ingested train {train_number} in simulation engine with initial delay {init_del}m.")
                except Exception as sim_err:
                    logger.warning(f"Could not register train {train_number} in simulator: {sim_err}")

                # Re-fetch populated train
                re_res = await db.execute(
                    select(Train)
                    .options(selectinload(Train.routes).selectinload(Route.route_stations))
                    .where(Train.train_number == train_number)
                )
                return re_res.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Error during dynamic ingestion of {train_number}: {e}", exc_info=True)
            await db.rollback()

    return existing_train
