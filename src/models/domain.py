from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class DataSourceType(str, Enum):
    SIMULATION = "simulation"
    THIRD_PARTY = "third_party"
    CRIS_NTES = "cris_ntes"


class DelayStatus(str, Enum):
    ON_TIME = "on_time"          # <= 5 mins delay
    MODERATE_DELAY = "moderate"   # 5 - 30 mins delay
    SEVERE_DELAY = "severe"       # > 30 mins delay


class TrainPosition(BaseModel):
    latitude: float
    longitude: float
    current_speed_kmh: float
    heading_deg: Optional[float] = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StationStop(BaseModel):
    station_code: str
    station_name: str
    distance_from_origin_km: float
    scheduled_arrival: Optional[datetime] = None
    scheduled_departure: Optional[datetime] = None
    scheduled_dwell_minutes: float = 2.0
    actual_arrival: Optional[datetime] = None
    actual_departure: Optional[datetime] = None
    is_passed: bool = False


class StationPrediction(BaseModel):
    station_code: str
    station_name: str
    scheduled_arrival: datetime
    baseline_eta: datetime
    dynamic_eta: datetime
    delay_minutes: float
    confidence_pct: float
    eta_lower_bound: datetime
    eta_upper_bound: datetime
    delay_factors: List[str] = Field(default_factory=list)


class TrainState(BaseModel):
    train_number: str
    train_name: str
    source_station: str
    destination_station: str
    source_type: DataSourceType = DataSourceType.SIMULATION
    current_position: TrainPosition
    current_delay_minutes: float
    delay_status: DelayStatus
    next_station_code: str
    distance_to_next_station_km: float
    stops: List[StationStop] = Field(default_factory=list)
    predictions: List[StationPrediction] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
