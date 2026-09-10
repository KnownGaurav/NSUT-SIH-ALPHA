import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Union, Dict, Any

import numpy as np
import pandas as pd
import xgboost as xgb

from src.services.data_providers.base import NormalizedTrainState
from src.services.eta_service import eta_service, parse_time_to_minutes
from src.services.weather_service import WeatherData
from src.models.api_schemas import (
    DynamicETAResponse,
    StationDynamicETA,
    RouteStopResponse,
    WeatherInfoResponse,
    CongestionInfoResponse
)
from src.ml.features import (
    feature_pipeline,
    REMAINING_TIME_FEATURE_COLUMNS
)

logger = logging.getLogger("railway_eta.ml.predict")

DEFAULT_MODEL_PATH = "./models/xgboost_eta.json"
DEFAULT_METADATA_PATH = "./models/model_metadata.json"


def compute_prototype_congestion(
    operational_event: str,
    current_speed: float,
    current_delay: float
) -> CongestionInfoResponse:
    """
    Computes transparent prototype congestion score based on operational status,
    instantaneous speed, and delay accumulation.
    Explicitly labeled as prototype simulation/network estimation, NOT internal railway signalling.
    """
    if operational_event == "CONGESTION":
        return CongestionInfoResponse(
            level="HIGH",
            score=0.88,
            factor_description="High corridor density & signal check queuing (Simulated Network Condition)",
            active_event=operational_event
        )
    elif operational_event == "UNSCHEDULED_HALT":
        return CongestionInfoResponse(
            level="HIGH",
            score=0.95,
            factor_description="Unscheduled operational halt / signal red aspect (Simulated Network Condition)",
            active_event=operational_event
        )
    elif operational_event == "SPEED_RESTRICTION":
        return CongestionInfoResponse(
            level="MEDIUM",
            score=0.55,
            factor_description="Cautionary speed restriction / track maintenance block (Simulated Network Condition)",
            active_event=operational_event
        )
    elif operational_event == "RECOVERY":
        return CongestionInfoResponse(
            level="LOW",
            score=0.15,
            factor_description="Clear corridor / priority routing under timetable slack recovery",
            active_event=operational_event
        )
    else:
        # NORMAL_OPERATION - infer from delay and speed
        if current_delay > 30.0 or current_speed < 45.0:
            return CongestionInfoResponse(
                level="MEDIUM",
                score=0.45,
                factor_description="Moderate sectional latency / speed caution",
                active_event=operational_event
            )
        else:
            return CongestionInfoResponse(
                level="LOW",
                score=0.12,
                factor_description="Normal line throughput & permissible sectional headway",
                active_event=operational_event
            )


class DynamicETAPredictor:
    """
    Inference service for real-time Dynamic Railway ETA predictions.
    
    Principles:
    1. Loads serialized XGBoost regression model trained on historical train runs.
    2. Modulates predictions dynamically based on operational events (SPEED_RESTRICTION, CONGESTION, UNSCHEDULED_HALT, RECOVERY).
    3. Integrates environmental weather factors (precipitation, wind, visibility, severe weather).
    4. Computes grounded confidence scores and prediction intervals [lower_bound, upper_bound].
    5. Falls back gracefully to deterministic baseline if model is unavailable.
    """

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        metadata_path: str = DEFAULT_METADATA_PATH
    ):
        self.model_path = model_path
        self.metadata_path = metadata_path
        self.model: Optional[xgb.XGBRegressor] = None
        self.metadata: Dict[str, Any] = {}
        self.rmse: float = 3.51  # Validation RMSE fallback
        self.acc_5m: float = 83.6
        self.acc_10m: float = 99.3

        self._load_model_and_metadata()

    def _load_model_and_metadata(self):
        profiles_path = "./models/section_profiles.json"
        if os.path.exists(profiles_path):
            feature_pipeline.load_profiles(profiles_path)

        if os.path.exists(self.metadata_path):
            try:
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                    eval_ml = self.metadata.get("evaluation", {}).get("xgboost_model", {})
                    self.rmse = float(eval_ml.get("rmse_minutes", 3.51))
                    self.acc_5m = float(eval_ml.get("accuracy_within_5_min_percent", 83.6))
                    self.acc_10m = float(eval_ml.get("accuracy_within_10_min_percent", 99.3))
            except Exception as e:
                logger.warning(f"Could not parse model metadata from {self.metadata_path}: {e}")

        if os.path.exists(self.model_path):
            try:
                self.model = xgb.XGBRegressor()
                self.model.load_model(self.model_path)
                logger.info(f"Loaded XGBoost model successfully from {self.model_path}")
            except Exception as e:
                logger.error(f"Failed to load XGBoost model from {self.model_path}: {e}")
                self.model = None
        else:
            logger.warning(f"XGBoost model file not found at {self.model_path}. Will use fallback.")

    def predict_upcoming_etas(
        self,
        train_state: NormalizedTrainState,
        stops: List[Union[RouteStopResponse, dict]],
        train_type: str = "Rajdhani Express",
        weather_data: Optional[WeatherData] = None,
        reference_time: Optional[datetime] = None
    ) -> DynamicETAResponse:
        """
        Generates dynamic ML-based ETA predictions, environmental weather adjustments,
        and prototype congestion metrics for all upcoming stations.
        """
        now = reference_time or train_state.timestamp or datetime.now(timezone.utc)
        current_delay = float(train_state.current_delay)
        op_event = train_state.operational_event or "NORMAL_OPERATION"

        # 1. Compute prototype congestion info
        congestion_info = compute_prototype_congestion(
            operational_event=op_event,
            current_speed=float(train_state.speed),
            current_delay=current_delay
        )

        # 2. Weather response encapsulation
        weather_resp = None
        weather_penalty_rate = 0.0  # extra minutes per 100km due to weather
        if weather_data:
            weather_resp = WeatherInfoResponse(
                temperature_c=weather_data.temperature_c,
                precipitation_mm=weather_data.precipitation_mm,
                wind_speed_kmh=weather_data.wind_speed_kmh,
                visibility_km=weather_data.visibility_km,
                weather_condition=weather_data.weather_condition,
                is_severe_weather=weather_data.is_severe_weather,
                data_source=weather_data.data_source,
                cached=weather_data.cached
            )
            # Physical railway speed caution under poor weather (e.g. dense fog or torrential monsoon rain)
            if weather_data.is_severe_weather or weather_data.visibility_km < 2.0:
                weather_penalty_rate = 2.0  # ~2.0 min extra delay per 100 km under caution
            elif weather_data.precipitation_mm > 5.0 or weather_data.wind_speed_kmh > 50.0:
                weather_penalty_rate = 0.8

        # 3. Deterministic Baseline calculation
        baseline_res = eta_service.calculate_baseline(
            train_state=train_state,
            stops=stops,
            reference_time=now
        )
        baseline_lookup = {s.sequence: s for s in baseline_res.stations}

        # Normalize stops
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

        total_dest_dist = float(normalized_stops[-1]["distance_from_origin_km"]) if normalized_stops else 0.0

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
            next_idx = curr_idx + 1 if (0 <= curr_idx < len(normalized_stops) - 1) else 1

        # Train approximate distance along route
        if curr_idx >= 0 and next_idx > curr_idx:
            d_curr = float(normalized_stops[curr_idx]["distance_from_origin_km"])
            d_next = float(normalized_stops[next_idx]["distance_from_origin_km"])
            train_dist = d_curr + (d_next - d_curr) * 0.4
        elif curr_idx >= 0:
            train_dist = float(normalized_stops[curr_idx]["distance_from_origin_km"])
        else:
            train_dist = 0.0

        next_sec_id = f"{curr_code}->{next_code}" if curr_code and next_code else None

        station_results: List[StationDynamicETA] = []

        for i, stop in enumerate(normalized_stops):
            seq = stop["sequence"]
            code = stop["station_code"]
            name = stop["station_name"]
            stn_dist = float(stop["distance_from_origin_km"])
            is_passed = (i < next_idx)

            base_item = baseline_lookup.get(seq)
            base_eta_str = base_item.baseline_eta if base_item else None
            base_rem_min = base_item.remaining_travel_time_minutes if base_item else 0.0

            if is_passed:
                station_results.append(StationDynamicETA(
                    station_code=code,
                    station_name=name,
                    sequence=seq,
                    distance_from_origin_km=stn_dist,
                    scheduled_arrival=stop["scheduled_arrival"],
                    baseline_eta=None,
                    predicted_eta=None,
                    dynamic_eta=None,
                    predicted_remaining_minutes=0.0,
                    baseline_remaining_minutes=0.0,
                    predicted_delay_minutes=0.0,
                    delta_vs_baseline_minutes=0.0,
                    confidence=None,
                    confidence_method="empirical_validation_tolerance",
                    lower_bound=None,
                    upper_bound=None,
                    confidence_lower_minutes=0.0,
                    confidence_upper_minutes=0.0,
                    is_passed=True
                ))
            else:
                rem_dist = max(0.0, stn_dist - train_dist)
                dist_to_dest = max(0.0, total_dest_dist - train_dist)
                stations_rem = i - max(0, curr_idx)

                # Compute scheduled remaining travel time
                sub_seg_dist = max(1.0, float(normalized_stops[next_idx]["distance_from_origin_km"]) - train_dist)
                sched_sub_min = (sub_seg_dist / 95.0) * 60.0

                sched_mid_min = 0.0
                for mid in range(next_idx, i):
                    seg_d = float(normalized_stops[mid + 1]["distance_from_origin_km"]) - float(normalized_stops[mid]["distance_from_origin_km"])
                    t1 = parse_time_to_minutes(normalized_stops[mid]["scheduled_departure"])
                    t2 = parse_time_to_minutes(normalized_stops[mid + 1]["scheduled_arrival"])
                    if t1 is not None and t2 is not None:
                        diff = t2 - t1
                        if diff < 0:
                            diff += 24.0 * 60.0
                        sched_mid_min += diff
                    else:
                        sched_mid_min += (seg_d / 95.0) * 60.0

                sched_rem_time = round(sched_sub_min + sched_mid_min, 1)

                # Extract features for XGBoost model
                feat_dict = feature_pipeline.extract_remaining_time_inference_features(
                    scheduled_remaining_time_min=sched_rem_time,
                    distance_to_station_km=rem_dist,
                    distance_to_destination_km=dist_to_dest,
                    current_delay_min=current_delay,
                    current_speed_kmh=float(train_state.speed),
                    stations_remaining=stations_rem,
                    next_section_id=next_sec_id,
                    train_type_str=train_type,
                    timestamp=now
                )

                # Predict remaining travel time using XGBoost
                if self.model is not None:
                    X_infer = pd.DataFrame([feat_dict])[REMAINING_TIME_FEATURE_COLUMNS]
                    pred_arr = self.model.predict(X_infer)
                    pred_remaining = float(pred_arr[0])

                    # Apply operational condition adjustments dynamically:
                    if op_event == "SPEED_RESTRICTION":
                        # Caution speed: +15% travel time on immediate segment
                        immediate_dist = min(rem_dist, 50.0)
                        pred_remaining += (immediate_dist / 40.0 - immediate_dist / 100.0) * 60.0
                    elif op_event == "CONGESTION":
                        # Queuing in block section: +25% travel time
                        immediate_dist = min(rem_dist, 70.0)
                        pred_remaining += (immediate_dist / 25.0 - immediate_dist / 100.0) * 60.0
                    elif op_event == "UNSCHEDULED_HALT":
                        # Stalled train: +6 min halt delay buffer
                        pred_remaining += 6.0
                    elif op_event == "RECOVERY":
                        # Train priority running: recover up to 10%
                        pred_remaining = max(sched_rem_time, pred_remaining * 0.96)

                    # Apply environmental weather adjustment
                    if weather_penalty_rate > 0:
                        pred_remaining += (rem_dist / 100.0) * weather_penalty_rate

                    # Physical boundary constraint: train cannot travel faster than 135 km/h broad-gauge peak
                    min_phys_time = (rem_dist / 135.0) * 60.0
                    pred_remaining = max(min_phys_time, pred_remaining)
                else:
                    pred_remaining = base_rem_min

                pred_remaining = round(pred_remaining, 1)
                delta_vs_base = round(pred_remaining - base_rem_min, 1)

                pred_delay = max(0.0, round(pred_remaining - sched_rem_time, 1))

                # Dynamic ETA timestamp
                dyn_eta_dt = now + timedelta(minutes=pred_remaining)
                dyn_eta_iso = dyn_eta_dt.isoformat()

                # Prediction interval
                interval_half_width = round(1.5 * self.rmse * (1.0 + (rem_dist / 1200.0) * 0.5), 1)
                lower_min = max(0.0, round(pred_remaining - interval_half_width, 1))
                upper_min = round(pred_remaining + interval_half_width, 1)

                lower_bound_dt = now + timedelta(minutes=lower_min)
                upper_bound_dt = now + timedelta(minutes=upper_min)

                # Grounded confidence score:
                # Based on validation accuracy, reduced slightly under severe operational/weather conditions
                base_confidence = (self.acc_10m / 100.0) * 0.92
                decay = (rem_dist / 1500.0) * 0.15
                if op_event in ["CONGESTION", "UNSCHEDULED_HALT"] or (weather_data and weather_data.is_severe_weather):
                    decay += 0.08  # Greater uncertainty during active disruptions

                confidence_val = round(float(np.clip(base_confidence - decay, 0.65, 0.95)), 2)

                station_results.append(StationDynamicETA(
                    station_code=code,
                    station_name=name,
                    sequence=seq,
                    distance_from_origin_km=stn_dist,
                    scheduled_arrival=stop["scheduled_arrival"],
                    baseline_eta=base_eta_str,
                    predicted_eta=dyn_eta_iso,
                    dynamic_eta=dyn_eta_iso,
                    predicted_remaining_minutes=pred_remaining,
                    baseline_remaining_minutes=base_rem_min,
                    predicted_delay_minutes=pred_delay,
                    delta_vs_baseline_minutes=delta_vs_base,
                    confidence=confidence_val,
                    confidence_method="empirical_validation_tolerance",
                    lower_bound=lower_bound_dt.isoformat(),
                    upper_bound=upper_bound_dt.isoformat(),
                    confidence_lower_minutes=lower_min,
                    confidence_upper_minutes=upper_min,
                    is_passed=False
                ))

        return DynamicETAResponse(
            train_number=train_state.train_number,
            generated_at=now.isoformat(),
            current_delay_minutes=current_delay,
            current_station=curr_code,
            next_station=next_code,
            model_name=self.metadata.get("model_name", "XGBoost Dynamic Railway ETA Predictor"),
            model_version=self.metadata.get("model_version", "1.0.0"),
            is_simulation=train_state.data_source == "SIMULATION",
            operational_event=op_event,
            weather=weather_resp,
            congestion=congestion_info,
            stations=station_results
        )


# Global singleton predictor
dynamic_eta_predictor = DynamicETAPredictor()
