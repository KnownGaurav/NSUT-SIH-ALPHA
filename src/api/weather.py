from fastapi import APIRouter, Query, HTTPException, status
from src.services.weather_service import weather_service
from src.models.api_schemas import WeatherInfoResponse

router = APIRouter()


@router.get("", response_model=WeatherInfoResponse)
async def get_weather_at_coordinates(
    latitude: float | None = Query(None, ge=-90.0, le=90.0, description="Latitude in decimal degrees"),
    longitude: float | None = Query(None, ge=-180.0, le=180.0, description="Longitude in decimal degrees"),
    lat: float | None = Query(None, ge=-90.0, le=90.0, description="Alias for latitude"),
    lon: float | None = Query(None, ge=-180.0, le=180.0, description="Alias for longitude")
):
    """
    Retrieve real-time environmental weather conditions (temperature, precipitation,
    wind speed, visibility, weather condition) for arbitrary geographic coordinates.
    Grounded with Open-Meteo API and in-memory TTL caching.
    """
    final_lat = latitude if latitude is not None else lat
    final_lon = longitude if longitude is not None else lon

    if final_lat is None or final_lon is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both latitude (or lat) and longitude (or lon) parameters are required."
        )

    weather = await weather_service.get_weather(final_lat, final_lon)
    if not weather:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve weather observations from meteorological provider"
        )

    return WeatherInfoResponse(
        temperature_c=weather.temperature_c,
        precipitation_mm=weather.precipitation_mm,
        wind_speed_kmh=weather.wind_speed_kmh,
        visibility_km=weather.visibility_km,
        weather_condition=weather.weather_condition,
        is_severe_weather=weather.is_severe_weather,
        data_source=weather.data_source,
        cached=weather.cached
    )
