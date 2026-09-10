import math
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Union
from src.services.data_providers.base import NormalizedTrainState
from src.models.api_schemas import StationBaselineETA, BaselineETAResponse, RouteStopResponse

logger = logging.getLogger("railway_eta.services.eta")

# Standard timetable slack recovery rate per section on Indian Railways coaching routes (approx 4%)
SLACK_RECOVERY_RATE = 0.04
MAX_RECOVERY_FRACTION = 0.25  # Max 25% of current delay recoverable over subsequent sections


def parse_time_to_minutes(time_str: Optional[str]) -> Optional[float]:
    """Parse 'HH:MM:SS' or 'HH:MM' into total minutes from midnight."""
    if not time_str:
        return None
    try:
        parts = list(map(int, time_str.strip().split(":")))
        if len(parts) == 3:
            return parts[0] * 60.0 + parts[1] + parts[2] / 60.0
        elif len(parts) == 2:
            return parts[0] * 60.0 + parts[1]
    except Exception:
        pass
    return None


class BaselineETAService:
    """
    Deterministic Baseline ETA Engine.
    
    FORMULATION:
    Baseline Remaining Travel Time = Remaining Scheduled Travel Time + Current Delay - Timetable Recovery Adjustment
    Baseline ETA = Current Timestamp + Baseline Remaining Travel Time
    """

    @classmethod
    def calculate_baseline(
        cls,
        train_state: NormalizedTrainState,
        stops: List[Union[RouteStopResponse, dict]],
        reference_time: Optional[datetime] = None
    ) -> BaselineETAResponse:
        """
        Calculates deterministic baseline ETAs for all stations along a train route.
        """
        now = reference_time or train_state.timestamp or datetime.now(timezone.utc)
        current_delay = float(train_state.current_delay)

        # Normalize stops to uniform dicts
        normalized_stops = []
        for s in stops:
            if isinstance(s, dict):
                normalized_stops.append(s)
            else:
                normalized_stops.append({
                    "sequence": s.sequence,
                    "station_code": s.station_code,
                    "station_name": s.station_name,
                    "scheduled_arrival": s.scheduled_arrival,
                    "scheduled_departure": s.scheduled_departure,
                    "distance_from_origin_km": s.distance_from_origin_km,
                    "scheduled_dwell_minutes": s.scheduled_dwell_minutes,
                    "day_offset": s.day_offset
                })

        normalized_stops.sort(key=lambda x: x["sequence"])

        # 1. Identify active segment
        curr_code = train_state.current_station
        next_code = train_state.next_station

        curr_idx = -1
        next_idx = -1

        for i, s in enumerate(normalized_stops):
            if curr_code and s["station_code"] == curr_code:
                curr_idx = i
            if next_code and s["station_code"] == next_code:
                next_idx = i

        if next_idx == -1:
            # Fallback: if not set, next station is the one after curr_idx, or sequence 2
            next_idx = curr_idx + 1 if curr_idx >= 0 and curr_idx < len(normalized_stops) - 1 else 1

        # Train current approximate distance along route
        if curr_idx >= 0 and next_idx > curr_idx:
            d_curr = normalized_stops[curr_idx]["distance_from_origin_km"]
            d_next = normalized_stops[next_idx]["distance_from_origin_km"]
            train_dist = d_curr + (d_next - d_curr) * 0.4
        elif curr_idx >= 0:
            train_dist = normalized_stops[curr_idx]["distance_from_origin_km"]
        else:
            train_dist = 0.0

        station_results: List[StationBaselineETA] = []
        cumulative_recovery = 0.0
        max_allowed_recovery = max(0.0, current_delay * MAX_RECOVERY_FRACTION)

        # 2. Iterate through stations
        for i, stop in enumerate(normalized_stops):
            seq = stop["sequence"]
            code = stop["station_code"]
            name = stop["station_name"]
            stn_dist = float(stop["distance_from_origin_km"])
            is_passed = (i < next_idx)

            if is_passed:
                # Station already cleared
                station_results.append(StationBaselineETA(
                    station_code=code,
                    station_name=name,
                    sequence=seq,
                    distance_from_origin_km=stn_dist,
                    scheduled_arrival=stop["scheduled_arrival"],
                    baseline_eta=None,
                    baseline_delay_minutes=0.0,
                    remaining_travel_time_minutes=0.0,
                    remaining_distance_km=0.0,
                    recovery_adjustment_minutes=0.0,
                    is_passed=True
                ))
            else:
                # Upcoming station
                rem_dist = max(0.0, stn_dist - train_dist)

                # Compute scheduled travel time from current segment to this station
                # 1. First sub-segment: from train position to next station
                sub_seg_dist = max(1.0, normalized_stops[next_idx]["distance_from_origin_km"] - train_dist)
                # Approximate scheduled travel time at 80-100 km/h timetable average
                sched_sub_seg_min = (sub_seg_dist / 95.0) * 60.0

                # 2. Intermediate full segments between next_idx and current stop i
                sched_intermediate_min = 0.0
                for mid in range(next_idx, i):
                    seg_d = normalized_stops[mid + 1]["distance_from_origin_km"] - normalized_stops[mid]["distance_from_origin_km"]
                    # Timetable difference if available, else standard section speed
                    t1 = parse_time_to_minutes(normalized_stops[mid]["scheduled_departure"])
                    t2 = parse_time_to_minutes(normalized_stops[mid + 1]["scheduled_arrival"])
                    if t1 is not None and t2 is not None:
                        diff = t2 - t1
                        if diff < 0:
                            diff += 24.0 * 60.0  # Overnight transit
                        sched_intermediate_min += diff
                    else:
                        sched_intermediate_min += (seg_d / 95.0) * 60.0

                sched_rem_travel_time = round(sched_sub_seg_min + sched_intermediate_min, 1)

                # 3. Basic Recovery Adjustment:
                # If train is currently delayed, allow modest timetable recovery based on distance
                if current_delay > 0:
                    potential_recovery = (rem_dist / 100.0) * 1.5  # ~1.5 min recovered per 100 km
                    recovery_step = min(potential_recovery, max_allowed_recovery - cumulative_recovery)
                    recovery_step = max(0.0, recovery_step)
                    cumulative_recovery += recovery_step

                projected_delay = max(0.0, round(current_delay - cumulative_recovery, 1))

                # Baseline remaining travel time: scheduled remaining + projected delay
                baseline_rem_travel_time = round(sched_rem_travel_time + projected_delay, 1)

                # Compute baseline ETA timestamp:
                baseline_eta_dt = now + timedelta(minutes=baseline_rem_travel_time)

                station_results.append(StationBaselineETA(
                    station_code=code,
                    station_name=name,
                    sequence=seq,
                    distance_from_origin_km=stn_dist,
                    scheduled_arrival=stop["scheduled_arrival"],
                    baseline_eta=baseline_eta_dt.isoformat(),
                    baseline_delay_minutes=projected_delay,
                    remaining_travel_time_minutes=baseline_rem_travel_time,
                    remaining_distance_km=round(rem_dist, 1),
                    recovery_adjustment_minutes=round(cumulative_recovery, 1),
                    is_passed=False
                ))

        return BaselineETAResponse(
            train_number=train_state.train_number,
            generated_at=now.isoformat(),
            current_delay_minutes=current_delay,
            current_station=curr_code,
            next_station=next_code,
            model_name="Deterministic Baseline Engine (v1.0)",
            is_simulation=train_state.data_source == "SIMULATION",
            stations=station_results
        )


eta_service = BaselineETAService()
