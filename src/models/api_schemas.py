from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class StationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    station_code: str
    station_name: str
    latitude: float
    longitude: float
    state: Optional[str] = None
    zone: Optional[str] = None


class TrainSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    train_number: str
    train_name: str
    train_type: str
    source: str
    destination: str


class LivePositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    latitude: float
    longitude: float
    speed_kmh: float
    current_delay_minutes: float
    current_station: Optional[str] = None
    next_station: Optional[str] = None
    data_source: str


class WeatherInfoResponse(BaseModel):
    temperature_c: float
    precipitation_mm: float
    wind_speed_kmh: float
    visibility_km: float
    weather_condition: str
    is_severe_weather: bool
    data_source: str = "Open-Meteo"
    cached: bool = False


class CongestionInfoResponse(BaseModel):
    level: str  # "LOW", "MEDIUM", "HIGH"
    score: float  # 0.0 - 1.0
    factor_description: str
    active_event: str


class TrainPositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    train_number: str
    timestamp: datetime
    latitude: float
    longitude: float
    speed_kmh: float
    current_delay_minutes: float
    delay_status: str  # "on_time", "moderate", "severe"
    current_station: Optional[str] = None
    current_station_name: Optional[str] = None
    next_station: Optional[str] = None
    next_station_name: Optional[str] = None
    data_source: str
    operational_event: Optional[str] = "NORMAL_OPERATION"
    weather: Optional[WeatherInfoResponse] = None
    congestion: Optional[CongestionInfoResponse] = None


class TrainDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    train_number: str
    train_name: str
    train_type: str
    source: str
    destination: str
    source_name: Optional[str] = None
    destination_name: Optional[str] = None
    route_id: Optional[str] = None
    total_distance_km: Optional[float] = None
    live_position: Optional[LivePositionResponse] = None


class RouteStopResponse(BaseModel):
    sequence: int
    station_code: str
    station_name: str
    latitude: float
    longitude: float
    scheduled_arrival: Optional[str] = None
    scheduled_departure: Optional[str] = None
    distance_from_origin_km: float
    scheduled_dwell_minutes: float
    day_offset: int


class TrainRouteResponse(BaseModel):
    train_number: str
    train_name: str
    route_id: str
    direction: str
    total_distance_km: float
    total_stops: int
    stops: List[RouteStopResponse]


class StationBaselineETA(BaseModel):
    station_code: str
    station_name: str
    sequence: int
    distance_from_origin_km: float
    scheduled_arrival: Optional[str] = None
    baseline_eta: Optional[str] = None
    baseline_delay_minutes: float
    remaining_travel_time_minutes: float
    remaining_distance_km: float
    recovery_adjustment_minutes: float = 0.0
    is_passed: bool = False


class BaselineETAResponse(BaseModel):
    train_number: str
    generated_at: str
    current_delay_minutes: float
    current_station: Optional[str] = None
    next_station: Optional[str] = None
    model_name: str = "Deterministic Baseline Engine"
    is_simulation: bool = True
    stations: List[StationBaselineETA]


class StationDynamicETA(BaseModel):
    station_code: str
    station_name: str
    sequence: int
    distance_from_origin_km: float
    scheduled_arrival: Optional[str] = None
    baseline_eta: Optional[str] = None
    predicted_eta: Optional[str] = None  # alias / primary predicted ETA
    dynamic_eta: Optional[str] = None    # backward compatibility
    predicted_remaining_minutes: float
    baseline_remaining_minutes: float
    predicted_delay_minutes: float
    delta_vs_baseline_minutes: float
    confidence: Optional[float] = None   # Grounded statistical confidence (0.0 to 1.0)
    confidence_method: str = "empirical_validation_tolerance"
    lower_bound: Optional[str] = None   # ISO timestamp of prediction interval lower bound
    upper_bound: Optional[str] = None   # ISO timestamp of prediction interval upper bound
    confidence_lower_minutes: float
    confidence_upper_minutes: float
    is_passed: bool = False
    explanation: Optional[Dict[str, Any]] = None


class FactorContributionResponse(BaseModel):
    category: str
    direction: str
    impact_description: str
    metric_evidence: str


class ETAExplanationResponse(BaseModel):
    train_number: str
    station_code: str
    station_name: str
    previous_eta: Optional[str] = None
    new_eta: str
    shift_minutes: float
    direction: str
    summary: str
    contributing_factors: List[FactorContributionResponse] = []
    generated_at: str


class DynamicETAResponse(BaseModel):
    train_number: str
    generated_at: str
    current_delay_minutes: float
    current_station: Optional[str] = None
    next_station: Optional[str] = None
    model_name: str = "XGBoost Dynamic Railway ETA Predictor"
    model_version: str = "1.0.0"
    is_simulation: bool = True
    operational_event: str = "NORMAL_OPERATION"
    weather: Optional[WeatherInfoResponse] = None
    congestion: Optional[CongestionInfoResponse] = None
    explanation: Optional[ETAExplanationResponse] = None
    # Phase 21: downstream corridor slack analytics
    total_slack_minutes_remaining: float = 0.0
    projected_recovery_minutes: float = 0.0
    stations: List[StationDynamicETA]


class ControlRoomTrainItem(BaseModel):
    train_number: str
    train_name: str
    train_type: str
    source: str
    destination: str
    source_name: Optional[str] = None
    destination_name: Optional[str] = None
    latitude: float
    longitude: float
    speed_kmh: float
    current_delay_minutes: float
    delay_status: str  # "on_time", "moderate", "severe"
    current_station: Optional[str] = None
    next_station: Optional[str] = None
    next_station_name: Optional[str] = None
    operational_event: str = "NORMAL_OPERATION"
    data_source: str = "SIMULATION"
    predicted_eta: Optional[str] = None
    baseline_eta: Optional[str] = None
    eta_difference_minutes: float = 0.0
    eta_confidence: Optional[float] = None
    lower_bound: Optional[str] = None
    upper_bound: Optional[str] = None
    has_deteriorating_eta: bool = False
    explanation_summary: Optional[str] = None
    contributing_factors: List[FactorContributionResponse] = []


class ControlRoomSummary(BaseModel):
    total_active_trains: int
    on_time_count: int
    delayed_count: int
    severe_delay_count: int
    deteriorating_count: int
    data_source: str = "SIMULATION"
    generated_at: str
    trains: List[ControlRoomTrainItem]


class ModelMetricDetail(BaseModel):
    mae_minutes: float
    rmse_minutes: float
    mape_percent: float
    r2_score: float
    accuracy_within_5_min_percent: float
    accuracy_within_10_min_percent: float
    accuracy_within_15_min_percent: float


class SectionPerformanceItem(BaseModel):
    section_id: str
    from_station: str
    to_station: str
    from_station_name: str
    to_station_name: str
    sample_count: int
    average_delay_minutes: float
    average_running_time_minutes: float
    delay_variance: float
    recovery_tendency_minutes: float
    recovery_status: str  # "RECOVERING" | "DELAY_ACCUMULATING" | "NEUTRAL"


class FeatureImportanceItem(BaseModel):
    feature_name: str
    importance_score: float


class ModelAnalyticsResponse(BaseModel):
    model_name: str
    model_version: str
    trained_at: str
    total_evaluation_samples: int
    validation_samples: int
    validation_split_method: str
    baseline_metrics: ModelMetricDetail
    ml_metrics: ModelMetricDetail
    mae_reduction_minutes: float
    mae_reduction_percent: float
    acc_within_5m_gain_percent: float
    feature_importances: List[FeatureImportanceItem]
    sections: List[SectionPerformanceItem]
    zonal_breakdown: List['ZonalPerformanceItem'] = []


class ZonalPerformanceItem(BaseModel):
    zone: str
    zone_name: str
    average_delay_minutes: float
    recovery_tendency_percent: float  # % of runs where delay was recovered
    model_mae: float                  # zone-level weighted MAE estimate
    total_sections: int
    sample_count: int
    dominant_status: str              # "RECOVERING" | "DELAY_ACCUMULATING" | "NEUTRAL"



class TurnaroundImpact(BaseModel):
    scheduled_turnaround_minutes: int
    available_turnaround_minutes: int
    cleaning_depot_status: str  # "ON_SCHEDULE" | "TIGHT_WINDOW" | "DELAYED_HANDOVER"
    crew_handover_ready: bool
    estimated_depot_departure: Optional[str] = None


class StationArrivalItem(BaseModel):
    train_number: str
    train_name: str
    train_type: str
    source: str
    destination: str
    source_name: str
    destination_name: str
    scheduled_arrival: Optional[str] = None
    scheduled_departure: Optional[str] = None
    dynamic_predicted_eta: Optional[str] = None
    delay_minutes: float
    delay_status: str  # "on_time" | "moderate" | "severe"
    assigned_platform: str
    platform_conflict_flag: bool
    conflict_with_train: Optional[str] = None
    conflict_reason: Optional[str] = None
    turnaround_impact: TurnaroundImpact
    is_origin: bool
    is_destination: bool
    is_intermediate: bool
    current_status: str  # "APPROACHING" | "DOCKED" | "DEPARTED" | "SCHEDULED"


class StationArrivalsResponse(BaseModel):
    station_code: str
    station_name: str
    zone: Optional[str] = None
    state: Optional[str] = None
    total_platforms: int
    query_window_hours: int
    generated_at: str
    active_conflicts_count: int
    arrivals: List[StationArrivalItem]



