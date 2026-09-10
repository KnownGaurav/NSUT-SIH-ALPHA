import math
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from src.services.data_providers.base import NormalizedTrainState

logger = logging.getLogger("railway_eta.simulator")


class SimulationEvent(str, Enum):
    NORMAL_OPERATION = "NORMAL_OPERATION"
    SPEED_RESTRICTION = "SPEED_RESTRICTION"
    CONGESTION = "CONGESTION"
    UNSCHEDULED_HALT = "UNSCHEDULED_HALT"
    RECOVERY = "RECOVERY"


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate initial compass bearing from point 1 to point 2 in degrees (0-360)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)

    bearing_rad = math.atan2(y, x)
    bearing_deg = (math.degrees(bearing_rad) + 360.0) % 360.0
    return round(bearing_deg, 1)


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two GPS coordinates in kilometers."""
    R = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class TrainSimulationState:
    """Encapsulates runtime physical state and segment progression for a simulated train."""
    def __init__(self, train_number: str, stops: List[dict]):
        self.train_number = train_number
        self.stops = stops  # [{sequence, station_code, station_name, latitude, longitude, ...}]
        self.current_segment_idx = 0
        self.progress = 0.0  # 0.0 to 1.0 along the segment
        self.speed = 115.0  # km/h
        self.delay = 5.0    # minutes
        self.event = SimulationEvent.NORMAL_OPERATION
        self.updated_at = datetime.now(timezone.utc)

        # Set initial starting position
        if stops and len(stops) > 1:
            self.lat = stops[0]["latitude"]
            self.lon = stops[0]["longitude"]
            self.bearing = calculate_bearing(
                stops[0]["latitude"], stops[0]["longitude"],
                stops[1]["latitude"], stops[1]["longitude"]
            )
        else:
            self.lat = 28.6424
            self.lon = 77.2195
            self.bearing = 0.0


class RailwaySimulator:
    """
    Core Railway Simulation Engine.
    Simulates train kinematic movement along authentic track networks,
    modulates speed and delay in response to operational disruption events.
    """

    def __init__(self):
        self._trains: Dict[str, TrainSimulationState] = {}

    def register_train(self, train_number: str, stops: List[dict], initial_delay: float = 0.0, start_segment: int = 0):
        """Initializes or resets a train along its scheduled route stops."""
        state = TrainSimulationState(train_number, stops)
        state.delay = initial_delay
        state.current_segment_idx = min(start_segment, max(0, len(stops) - 2))
        state.progress = 0.35  # Mid-section by default for demonstration

        # Compute position for initial segment
        if len(stops) > 1 and state.current_segment_idx < len(stops) - 1:
            s1 = stops[state.current_segment_idx]
            s2 = stops[state.current_segment_idx + 1]
            state.lat = s1["latitude"] + (s2["latitude"] - s1["latitude"]) * state.progress
            state.lon = s1["longitude"] + (s2["longitude"] - s1["longitude"]) * state.progress
            state.bearing = calculate_bearing(s1["latitude"], s1["longitude"], s2["latitude"], s2["longitude"])

        self._trains[train_number] = state
        logger.info(f"Registered train {train_number} in simulator on segment {state.current_segment_idx}")

    def trigger_event(self, train_number: str, event: SimulationEvent) -> bool:
        """Applies an operational simulation event to a registered train."""
        if train_number not in self._trains:
            logger.warning(f"Cannot trigger event: train {train_number} not found in simulator")
            return False

        state = self._trains[train_number]
        state.event = event

        if event == SimulationEvent.NORMAL_OPERATION:
            state.speed = 115.0
        elif event == SimulationEvent.SPEED_RESTRICTION:
            state.speed = 40.0
        elif event == SimulationEvent.CONGESTION:
            state.speed = 20.0
        elif event == SimulationEvent.UNSCHEDULED_HALT:
            state.speed = 0.0
        elif event == SimulationEvent.RECOVERY:
            state.speed = 130.0

        state.updated_at = datetime.now(timezone.utc)
        logger.info(f"Train {train_number} simulation event updated to {event.value}, speed: {state.speed} km/h")
        return True

    def tick(self, delta_seconds: float = 3.0, speed_multiplier: float = 1.0):
        """
        Advances the physical simulation clock by delta_seconds.
        Updates coordinates, modulates delay, and transitions station segments.
        """
        for train_number, state in self._trains.items():
            stops = state.stops
            if len(stops) < 2 or state.current_segment_idx >= len(stops) - 1:
                continue

            s1 = stops[state.current_segment_idx]
            s2 = stops[state.current_segment_idx + 1]

            segment_dist = haversine_distance_km(s1["latitude"], s1["longitude"], s2["latitude"], s2["longitude"])
            if segment_dist <= 0:
                segment_dist = 1.0

            # 1. Update Delays based on active event
            if state.event == SimulationEvent.NORMAL_OPERATION:
                # Small random variation ±0.1 min
                pass
            elif state.event == SimulationEvent.SPEED_RESTRICTION:
                state.delay += (delta_seconds / 60.0) * 0.75
            elif state.event == SimulationEvent.CONGESTION:
                state.delay += (delta_seconds / 60.0) * 1.5
            elif state.event == SimulationEvent.UNSCHEDULED_HALT:
                state.delay += (delta_seconds / 60.0) * 2.0
            elif state.event == SimulationEvent.RECOVERY:
                # Train running fast, gradually recovers delay
                state.delay = max(0.0, state.delay - (delta_seconds / 60.0) * 0.8)

            # 2. Advance train progress
            distance_covered_km = (state.speed * (delta_seconds / 3600.0)) * speed_multiplier
            progress_delta = distance_covered_km / segment_dist
            state.progress += progress_delta

            # Check if arrived at next station
            if state.progress >= 1.0:
                if state.current_segment_idx < len(stops) - 2:
                    state.current_segment_idx += 1
                    state.progress = 0.0
                    s1 = stops[state.current_segment_idx]
                    s2 = stops[state.current_segment_idx + 1]
                else:
                    # Reached terminal destination; wrap around to beginning for endless demo
                    state.current_segment_idx = 0
                    state.progress = 0.0
                    s1 = stops[0]
                    s2 = stops[1]

            # 3. Interpolate current GPS coordinates and bearing
            state.lat = s1["latitude"] + (s2["latitude"] - s1["latitude"]) * state.progress
            state.lon = s1["longitude"] + (s2["longitude"] - s1["longitude"]) * state.progress
            state.bearing = calculate_bearing(state.lat, state.lon, s2["latitude"], s2["longitude"])
            state.updated_at = datetime.now(timezone.utc)

    def get_state(self, train_number: str) -> Optional[NormalizedTrainState]:
        """Returns normalized train state for the specified train."""
        if train_number not in self._trains:
            return None

        state = self._trains[train_number]
        stops = state.stops
        curr_stn = stops[state.current_segment_idx]["station_code"] if stops else None
        next_stn = stops[state.current_segment_idx + 1]["station_code"] if len(stops) > state.current_segment_idx + 1 else None

        return NormalizedTrainState(
            train_number=state.train_number,
            timestamp=state.updated_at,
            latitude=round(state.lat, 5),
            longitude=round(state.lon, 5),
            speed=round(state.speed, 1),
            bearing=state.bearing,
            current_delay=round(state.delay, 1),
            current_station=curr_stn,
            next_station=next_stn,
            data_source="SIMULATION",
            operational_event=state.event.value
        )

    def get_all_states(self) -> List[NormalizedTrainState]:
        """Returns normalized train states for all registered trains."""
        return [self.get_state(t) for t in self._trains if self.get_state(t) is not None]

    def reset_train(self, train_number: str):
        """Resets a train's progress to segment 0 and normal operation."""
        if train_number in self._trains:
            state = self._trains[train_number]
            state.current_segment_idx = 0
            state.progress = 0.05
            state.speed = 115.0
            state.delay = 0.0
            state.event = SimulationEvent.NORMAL_OPERATION
            state.updated_at = datetime.now(timezone.utc)


# Singleton simulator instance
simulator = RailwaySimulator()
