import httpx
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from src.core.config import settings
from src.services.data_providers.base import TrainDataProvider, NormalizedTrainState

logger = logging.getLogger("railway_eta.railradar")


class RailRadarProvider(TrainDataProvider):
    """
    Live Indian Railways train telemetry provider integrating with Rail Radar API v1.
    Provides live locomotive tracking, delays, scheduled halts, and coordinates across all IR trains.
    """

    def __init__(self):
        self._api_key = settings.RAILRADAR_API_KEY
        self._base_url = settings.RAILRADAR_BASE_URL.rstrip("/")
        # In-memory cache: train_number -> {"timestamp": float, "state": NormalizedTrainState}
        self._live_cache: Dict[str, dict] = {}
        # Route cache: train_number -> dict
        self._route_cache: Dict[str, dict] = {}
        # Train details cache: train_number -> dict
        self._train_meta_cache: Dict[str, dict] = {}
        self._cache_ttl_seconds = 20.0  # Respect rate-limits with 20s TTL

    @property
    def provider_name(self) -> str:
        return "RailRadar"

    @property
    def is_simulation(self) -> bool:
        return False

    def _get_headers(self) -> dict:
        headers = {
            "User-Agent": "RailwayETAPlatform/1.0",
            "Accept": "application/json"
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def get_train_details(self, train_number: str) -> Optional[dict]:
        """Fetch general train metadata (name, source, destination, train type, distance)."""
        if train_number in self._train_meta_cache:
            return self._train_meta_cache[train_number]

        url = f"{self._base_url}/trains/{train_number}"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers=self._get_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success") and "data" in data and "train" in data["data"]:
                        train_info = data["data"]["train"]
                        # Attach route with authentic station coordinates to train_info
                        if "route" in data["data"]:
                            train_info["route"] = data["data"]["route"]
                        self._train_meta_cache[train_number] = train_info
                        return train_info
                else:
                    logger.warning(f"RailRadar train details for {train_number} returned {resp.status_code}")
        except Exception as e:
            logger.error(f"Error fetching RailRadar train details for {train_number}: {e}")
        return None

    async def get_train_route_geojson(self, train_number: str) -> Optional[dict]:
        """Fetch high-resolution GeoJSON coordinates for train polyline rendering."""
        if train_number in self._route_cache:
            return self._route_cache[train_number]

        url = f"{self._base_url}/trains/{train_number}/route"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self._get_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success") and "data" in data and "geojson" in data["data"]:
                        self._route_cache[train_number] = data["data"]
                        return data["data"]
        except Exception as e:
            logger.error(f"Error fetching RailRadar route for {train_number}: {e}")
        return None

    async def get_train_live_data(self, train_number: str) -> Optional[dict]:
        """Fetch raw live tracking JSON payload from RailRadar."""
        url = f"{self._base_url}/trains/{train_number}/live"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers=self._get_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success") and "data" in data:
                        return data["data"]
        except Exception as e:
            logger.error(f"Error fetching RailRadar live status for {train_number}: {e}")
        return None

    async def get_train_position(self, train_number: str) -> Optional[NormalizedTrainState]:
        """
        Fetch real-time locomotive telemetry from Rail Radar and normalize it.
        Includes intelligent coordinate mapping along track polyline or station anchors.
        """
        now = datetime.now(timezone.utc).timestamp()

        # 1. Check TTL cache
        cached_entry = self._live_cache.get(train_number)
        if cached_entry and (now - cached_entry["timestamp"] < self._cache_ttl_seconds):
            state = cached_entry["state"].model_copy()
            from src.simulator.train_simulator import simulator
            sim_state = simulator.get_state(train_number)
            if sim_state and sim_state.operational_event != "NORMAL_OPERATION":
                state.operational_event = sim_state.operational_event
                state.speed = sim_state.speed
            return state

        # 2. Query RailRadar live endpoint
        live_data = await self.get_train_live_data(train_number)
        if not live_data:
            # Check simulator as robust fallback for testing and offline development
            from src.simulator.train_simulator import simulator
            sim_state = simulator.get_state(train_number)
            if sim_state:
                return sim_state
            # If rate-limited or live not found, return previous cached state if exists
            if cached_entry:
                return cached_entry["state"]
            return None

        # 3. Extract telemetry
        loc = live_data.get("currentLocation") or {}
        prev_halt = live_data.get("previousHalt") or {}
        next_halt = live_data.get("nextHalt") or {}
        train_meta = live_data.get("train") or {}

        delay_mins = float(live_data.get("delayMinutes") or loc.get("delayMinutes") or 0.0)
        curr_station = loc.get("stationCode") or prev_halt.get("stationCode") or "ORIGIN"
        next_station = next_halt.get("stationCode") or "DEST"

        # Calculate or extract speed
        avg_speed = float(train_meta.get("avgSpeed") or 75.0)
        status = live_data.get("status", "running")
        if status == "not-started":
            speed_kmh = 0.0
        elif status == "completed":
            speed_kmh = 0.0
        else:
            speed_kmh = avg_speed

        # 4. Resolve geographic coordinates
        latitude = None
        longitude = None

        # Check if route polyline is available to interpolate exact coordinate
        total_dist = float(train_meta.get("distance") or 0.0)
        curr_dist = float(loc.get("distanceFromOriginKm") or 0.0)

        route_geojson = await self.get_train_route_geojson(train_number)
        if route_geojson and "geojson" in route_geojson and "geometry" in route_geojson["geojson"]:
            coords = route_geojson["geojson"]["geometry"].get("coordinates", [])
            if coords and total_dist > 0.0 and curr_dist > 0.0:
                fraction = min(1.0, max(0.0, curr_dist / total_dist))
                idx = int(fraction * (len(coords) - 1))
                longitude = float(coords[idx][0])
                latitude = float(coords[idx][1])

        # Fallback to source or destination coords if before departure or near terminal
        if latitude is None or longitude is None:
            if status == "not-started" and "source" in train_meta:
                latitude = float(train_meta["source"].get("lat", 28.6419))
                longitude = float(train_meta["source"].get("lng", 77.2217))
            elif status == "completed" and "destination" in train_meta:
                latitude = float(train_meta["destination"].get("lat", 22.5828))
                longitude = float(train_meta["destination"].get("lng", 88.3428))
            else:
                latitude = 28.6419
                longitude = 77.2217

        # Check if simulator has an operational event triggered for demo/testing
        from src.simulator.train_simulator import simulator
        sim_state = simulator.get_state(train_number)
        active_event = "NORMAL_OPERATION" if delay_mins <= 5.0 else "CONGESTION" if delay_mins <= 30.0 else "SPEED_RESTRICTION"
        if sim_state and sim_state.operational_event != "NORMAL_OPERATION":
            active_event = sim_state.operational_event
            speed_kmh = sim_state.speed

        # 5. Build NormalizedTrainState
        state = NormalizedTrainState(
            train_number=train_number,
            timestamp=datetime.now(timezone.utc),
            latitude=latitude,
            longitude=longitude,
            speed=speed_kmh,
            bearing=0.0,
            current_delay=delay_mins,
            current_station=curr_station,
            next_station=next_station,
            data_source="RAILRADAR_LIVE",
            operational_event=active_event
        )

        # Cache valid state
        self._live_cache[train_number] = {
            "timestamp": now,
            "state": state
        }

        return state

    async def get_all_train_positions(self) -> List[NormalizedTrainState]:
        """Fetch positions for all cached/rostered trains."""
        positions = []
        # Pre-seed trains to track if none cached
        default_trains = ["12301", "12302", "12002", "12952", "22436"]
        for t_num in default_trains:
            pos = await self.get_train_position(t_num)
            if pos:
                positions.append(pos)
        return positions
