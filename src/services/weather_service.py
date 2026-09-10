import os
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger("railway_eta.services.weather")

WMO_WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail"
}


class WeatherData(BaseModel):
    latitude: float
    longitude: float
    temperature_c: float
    precipitation_mm: float
    wind_speed_kmh: float
    visibility_km: float
    weather_code: int
    weather_condition: str
    is_severe_weather: bool
    data_source: str = "Open-Meteo"
    cached: bool = False
    fetched_at: str


class WeatherService:
    """
    Normalized weather integration service with caching and graceful offline fallback.
    Interacts with Open-Meteo API for geographic weather conditions.
    """

    def __init__(self, cache_ttl_seconds: int = 900):  # 15 minutes cache
        self.cache_ttl = cache_ttl_seconds
        # (rounded_lat, rounded_lon) -> (timestamp, WeatherData)
        self._cache: Dict[str, tuple[float, WeatherData]] = {}

    def _cache_key(self, lat: float, lon: float) -> str:
        # Quantize coordinates to ~11km grid (0.1 deg) to maximize cache hits along rail corridors
        return f"{round(lat, 1)}:{round(lon, 1)}"

    def _fallback_weather(self, lat: float, lon: float) -> WeatherData:
        """Standard clear-weather operational baseline fallback if external API is unreachable."""
        return WeatherData(
            latitude=lat,
            longitude=lon,
            temperature_c=28.0,
            precipitation_mm=0.0,
            wind_speed_kmh=12.0,
            visibility_km=10.0,
            weather_code=0,
            weather_condition="Clear sky (Default Fallback)",
            is_severe_weather=False,
            data_source="BASELINE_ESTIMATE",
            cached=False,
            fetched_at=datetime.now(timezone.utc).isoformat()
        )

    async def get_weather(self, lat: float, lon: float) -> WeatherData:
        key = self._cache_key(lat, lon)
        now_ts = time.time()

        # 1. Check in-memory cache
        if key in self._cache:
            cache_time, cached_data = self._cache[key]
            if now_ts - cache_time < self.cache_ttl:
                # Return cached entry marked with cached=True
                res = cached_data.model_copy()
                res.cached = True
                res.latitude = lat
                res.longitude = lon
                return res

        # 2. Query Open-Meteo
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&"
            f"current=temperature_2m,precipitation,weather_code,wind_speed_10m&"
            f"hourly=visibility"
        )

        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(url, headers={"User-Agent": "IndianRailways-DynamicETA/1.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    current = data.get("current", {})
                    temp = float(current.get("temperature_2m", 28.0))
                    precip = float(current.get("precipitation", 0.0))
                    wind = float(current.get("wind_speed_10m", 12.0))
                    code = int(current.get("weather_code", 0))

                    # Hourly visibility nearest current hour
                    visibility_list = data.get("hourly", {}).get("visibility", [])
                    if visibility_list:
                        # meters -> kilometers
                        vis_km = round(float(visibility_list[0]) / 1000.0, 1)
                    else:
                        vis_km = 10.0

                    condition = WMO_WEATHER_CODES.get(code, "Clear / Moderate")
                    # Severe weather condition: heavy rain (>=65), thunderstorm (>=95), dense fog (45, 48), or visibility < 2km
                    is_severe = (code in [45, 48, 65, 82, 95, 96, 99]) or (precip > 15.0) or (vis_km < 2.0)

                    w_data = WeatherData(
                        latitude=lat,
                        longitude=lon,
                        temperature_c=temp,
                        precipitation_mm=precip,
                        wind_speed_kmh=wind,
                        visibility_km=vis_km,
                        weather_code=code,
                        weather_condition=condition,
                        is_severe_weather=is_severe,
                        data_source="Open-Meteo",
                        cached=False,
                        fetched_at=datetime.now(timezone.utc).isoformat()
                    )

                    self._cache[key] = (now_ts, w_data)
                    return w_data
                else:
                    logger.warning(f"Open-Meteo returned status {resp.status_code}. Using fallback.")
                    return self._fallback_weather(lat, lon)
        except Exception as e:
            logger.warning(f"Failed to fetch live weather from Open-Meteo for ({lat}, {lon}): {e}. Using fallback.")
            return self._fallback_weather(lat, lon)


# Global singleton
weather_service = WeatherService()
