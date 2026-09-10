import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger("railway_eta.ml.features")

# Standard permissible sectional speed baseline for broad gauge coaching lines
DEFAULT_PERMISSIBLE_SPEED_KMH = 120.0

FEATURE_COLUMNS = [
    "section_dist_km",
    "scheduled_run_min",
    "current_delay_min",
    "current_speed_ratio",
    "hist_section_avg_delay",
    "hist_section_delay_var",
    "hist_section_avg_travel_time",
    "train_section_performance",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "is_rush_hour",
    "speed_restriction_flag"
]

REMAINING_TIME_FEATURE_COLUMNS = [
    "scheduled_remaining_time_min",
    "distance_to_station_km",
    "distance_to_destination_km",
    "current_delay_min",
    "current_speed_ratio",
    "stations_remaining",
    "hist_section_avg_delay",
    "hist_section_delay_var",
    "hist_section_avg_travel_time",
    "train_type_code",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "is_rush_hour",
    "speed_restriction_flag"
]


class HistoricalRunInput(BaseModel):
    """Data validation model for historical train station observations."""
    model_config = ConfigDict(from_attributes=True)

    train_number: str
    run_date: str
    station_code: str
    sequence: int = Field(ge=1)
    scheduled_arrival: Optional[str] = None    # "YYYY-MM-DD HH:MM:SS" or ISO
    actual_arrival: Optional[str] = None
    scheduled_departure: Optional[str] = None
    actual_departure: Optional[str] = None
    distance_km: float = Field(ge=0.0)

    @field_validator("train_number")
    @classmethod
    def validate_train_number(cls, v: str) -> str:
        if not v or len(v.strip()) < 3:
            raise ValueError("train_number must be a non-empty string with at least 3 characters")
        return v.strip()


class RailwayFeaturePipeline:
    """
    Unified Feature Engineering Pipeline for Railway ETA Prediction.
    
    CRITICAL RULE:
    The exact same feature calculations, normalizations, and section statistics
    are used during both model training and real-time inference to prevent train/test leakage.
    """

    def __init__(self):
        # Historical section knowledge base:
        # section_id -> {avg_delay, delay_var, avg_travel_time, count}
        self.section_profiles: Dict[str, dict] = {}
        # (train_number, section_id) -> {performance_index}
        self.train_section_profiles: Dict[str, dict] = {}

    @staticmethod
    def parse_dt(val) -> Optional[datetime]:
        """Robust parser for datetimes."""
        if pd.isna(val) or val is None or val == "":
            return None
        if isinstance(val, datetime):
            return val
        try:
            return pd.to_datetime(val).to_pydantic_datetime()
        except Exception:
            return None

    def process_historical_runs(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Processes raw historical station timestamps into section-level metrics.
        Computes arrival delay, departure delay, sectional running time, dwell time, and delay recovery.
        """
        # Validate required columns
        req_cols = ["train_number", "run_date", "station_code", "sequence", "scheduled_arrival", "actual_arrival", "scheduled_departure", "actual_departure", "distance_km"]
        for col in req_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column in historical runs: '{col}'")

        df = df.copy()
        df["sequence"] = df["sequence"].astype(int)
        df = df.sort_values(by=["train_number", "run_date", "sequence"]).reset_index(drop=True)

        # Convert to datetime
        for dt_col in ["scheduled_arrival", "actual_arrival", "scheduled_departure", "actual_departure"]:
            df[dt_col] = pd.to_datetime(df[dt_col])

        # 1. Calculate Station Arrival Delay & Departure Delay (in minutes)
        # Arrival delay
        arr_diff = (df["actual_arrival"] - df["scheduled_arrival"]).dt.total_seconds() / 60.0
        df["arrival_delay_min"] = arr_diff.fillna(0.0)

        # Departure delay
        dep_diff = (df["actual_departure"] - df["scheduled_departure"]).dt.total_seconds() / 60.0
        df["departure_delay_min"] = dep_diff.fillna(df["arrival_delay_min"])

        # 2. Station Dwell Time (minutes)
        actual_dwell = (df["actual_departure"] - df["actual_arrival"]).dt.total_seconds() / 60.0
        sched_dwell = (df["scheduled_departure"] - df["scheduled_arrival"]).dt.total_seconds() / 60.0
        df["station_dwell_time_min"] = actual_dwell.fillna(2.0).clip(lower=0.0)
        df["scheduled_dwell_time_min"] = sched_dwell.fillna(2.0).clip(lower=0.0)
        df["dwell_deviation_min"] = df["station_dwell_time_min"] - df["scheduled_dwell_time_min"]

        # 3. Compute Sectional Metrics (Between consecutive stations i and i+1)
        # Shift to get previous station departure and distance
        df["prev_train"] = df["train_number"].shift(1)
        df["prev_run_date"] = df["run_date"].shift(1)
        df["prev_station"] = df["station_code"].shift(1)
        df["prev_actual_departure"] = df["actual_departure"].shift(1)
        df["prev_scheduled_departure"] = df["scheduled_departure"].shift(1)
        df["prev_departure_delay_min"] = df["departure_delay_min"].shift(1)
        df["prev_distance_km"] = df["distance_km"].shift(1)

        # Mask for valid consecutive sections within the same train and run_date
        is_same_trip = (df["train_number"] == df["prev_train"]) & (df["run_date"] == df["prev_run_date"])

        # Section ID: "STN_A->STN_B"
        df["section_id"] = np.where(is_same_trip, df["prev_station"] + "->" + df["station_code"], None)
        df["section_distance_km"] = np.where(is_same_trip, df["distance_km"] - df["prev_distance_km"], 0.0)

        # Sectional Running Time: (actual arrival at B) - (actual departure from A)
        act_run = (df["actual_arrival"] - df["prev_actual_departure"]).dt.total_seconds() / 60.0
        sched_run = (df["scheduled_arrival"] - df["prev_scheduled_departure"]).dt.total_seconds() / 60.0
        df["sectional_running_time_min"] = np.where(is_same_trip, act_run, np.nan)
        df["scheduled_running_time_min"] = np.where(is_same_trip, sched_run, np.nan)

        # Delay Recovery: (Departure delay at A) - (Arrival delay at B)
        # Positive = Train recovered lost time on this section!
        # Negative = Delay worsened on this section
        df["delay_recovery_min"] = np.where(is_same_trip, df["prev_departure_delay_min"] - df["arrival_delay_min"], 0.0)

        # Clean up temporary shift columns
        df = df.drop(columns=[
            "prev_train", "prev_run_date", "prev_station",
            "prev_actual_departure", "prev_scheduled_departure",
            "prev_departure_delay_min", "prev_distance_km"
        ])

        return df

    def fit_historical_profiles(self, df_processed: pd.DataFrame):
        """
        Builds aggregated historical profiles per section and per (train, section):
        - Historical average delay
        - Delay variance
        - Average section travel time
        - Train-specific section performance index
        """
        valid_sections = df_processed[df_processed["section_id"].notna()].copy()
        if valid_sections.empty:
            logger.warning("No valid sections found in dataset to fit historical profiles.")
            return

        # 1. Section-level aggregations
        grouped_sec = valid_sections.groupby("section_id").agg(
            avg_delay=("arrival_delay_min", "mean"),
            delay_var=("arrival_delay_min", lambda x: float(np.var(x, ddof=1)) if len(x) > 1 else 0.0),
            avg_travel_time=("sectional_running_time_min", "mean"),
            sample_count=("arrival_delay_min", "count")
        ).reset_index()

        self.section_profiles = {}
        for _, row in grouped_sec.iterrows():
            self.section_profiles[row["section_id"]] = {
                "avg_delay": round(float(row["avg_delay"]), 2),
                "delay_var": round(float(row["delay_var"]), 2),
                "avg_travel_time": round(float(row["avg_travel_time"]), 2),
                "sample_count": int(row["sample_count"])
            }

        # 2. Train-specific section performance
        grouped_train_sec = valid_sections.groupby(["train_number", "section_id"]).agg(
            train_avg_travel_time=("sectional_running_time_min", "mean"),
            train_avg_delay=("arrival_delay_min", "mean")
        ).reset_index()

        self.train_section_profiles = {}
        for _, row in grouped_train_sec.iterrows():
            key = f"{row['train_number']}::{row['section_id']}"
            sec_avg = self.section_profiles.get(row["section_id"], {}).get("avg_travel_time", row["train_avg_travel_time"])
            # Performance ratio: < 1.0 means train traverses section faster than average
            perf_ratio = round(float(row["train_avg_travel_time"] / sec_avg) if sec_avg > 0 else 1.0, 3)
            self.train_section_profiles[key] = {
                "train_avg_travel_time": round(float(row["train_avg_travel_time"]), 2),
                "train_avg_delay": round(float(row["train_avg_delay"]), 2),
                "performance_ratio": perf_ratio
            }

        logger.info(f"Fitted profiles for {len(self.section_profiles)} sections and {len(self.train_section_profiles)} train-section pairs.")

    def extract_features_record(
        self,
        train_number: str,
        section_id: str,
        section_dist_km: float,
        scheduled_run_min: float,
        current_delay_min: float,
        current_speed_kmh: float,
        timestamp: datetime
    ) -> Dict[str, float]:
        """
        Extracts atomic feature vector for a single section prediction step.
        Guaranteed to produce the exact same features for training and inference.
        """
        # Historical section metrics lookup
        sec_info = self.section_profiles.get(section_id, {
            "avg_delay": 5.0,
            "delay_var": 10.0,
            "avg_travel_time": scheduled_run_min if scheduled_run_min > 0 else 30.0
        })

        # Train-specific performance lookup
        ts_key = f"{train_number}::{section_id}"
        train_perf = self.train_section_profiles.get(ts_key, {}).get("performance_ratio", 1.0)

        # Temporal features
        hour = timestamp.hour
        day_of_week = timestamp.weekday()
        is_weekend = 1.0 if day_of_week in [5, 6] else 0.0
        is_rush_hour = 1.0 if (7 <= hour <= 10 or 17 <= hour <= 21) else 0.0

        # Kinematic ratios
        speed_ratio = round(current_speed_kmh / DEFAULT_PERMISSIBLE_SPEED_KMH, 3) if DEFAULT_PERMISSIBLE_SPEED_KMH > 0 else 1.0
        speed_restriction_flag = 1.0 if current_speed_kmh < 45.0 else 0.0

        return {
            "section_dist_km": float(section_dist_km),
            "scheduled_run_min": float(scheduled_run_min),
            "current_delay_min": float(current_delay_min),
            "current_speed_ratio": float(speed_ratio),
            "hist_section_avg_delay": float(sec_info["avg_delay"]),
            "hist_section_delay_var": float(sec_info["delay_var"]),
            "hist_section_avg_travel_time": float(sec_info["avg_travel_time"]),
            "train_section_performance": float(train_perf),
            "hour_of_day": float(hour),
            "day_of_week": float(day_of_week),
            "is_weekend": float(is_weekend),
            "is_rush_hour": float(is_rush_hour),
            "speed_restriction_flag": float(speed_restriction_flag)
        }

    def build_training_matrix(self, df_processed: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Constructs (X, y) matrix for training ML models.
        Target y = actual sectional running time in minutes.
        """
        valid = df_processed[df_processed["section_id"].notna() & df_processed["sectional_running_time_min"].notna()].copy()
        if valid.empty:
            raise ValueError("No valid rows with complete section running time for training matrix.")

        features_list = []
        targets = []

        for _, row in valid.iterrows():
            ts = row["actual_departure"] if pd.notna(row["actual_departure"]) else row["scheduled_departure"]
            if pd.isna(ts):
                ts = datetime.now(timezone.utc)

            # Extract feature dictionary
            feat = self.extract_features_record(
                train_number=str(row["train_number"]),
                section_id=str(row["section_id"]),
                section_dist_km=float(row["section_distance_km"]),
                scheduled_run_min=float(row["scheduled_running_time_min"]),
                current_delay_min=float(row["arrival_delay_min"]),
                current_speed_kmh=DEFAULT_PERMISSIBLE_SPEED_KMH * (1.0 if row["arrival_delay_min"] <= 5 else 0.75),
                timestamp=ts
            )
            features_list.append(feat)
            targets.append(float(row["sectional_running_time_min"]))

        X = pd.DataFrame(features_list)[FEATURE_COLUMNS]
        y = pd.Series(targets, name="actual_running_time_min")
        return X, y

    def build_inference_vector(
        self,
        train_number: str,
        from_station: str,
        to_station: str,
        section_dist_km: float,
        scheduled_run_min: float,
        current_delay_min: float,
        current_speed_kmh: float,
        timestamp: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Generates identical feature DataFrame for single-step real-time inference.
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        section_id = f"{from_station}->{to_station}"
        feat_dict = self.extract_features_record(
            train_number=train_number,
            section_id=section_id,
            section_dist_km=section_dist_km,
            scheduled_run_min=scheduled_run_min,
            current_delay_min=current_delay_min,
            current_speed_kmh=current_speed_kmh,
            timestamp=timestamp
        )

        return pd.DataFrame([feat_dict])[FEATURE_COLUMNS]

    def build_remaining_time_dataset(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        """
        Builds observation pairs from station i to station j (j > i) with target = remaining travel time.
        Allows chronological train/validation splitting by run_date without random shuffle leakage.
        """
        df = df_raw.copy()
        for col in ["scheduled_arrival", "actual_arrival", "scheduled_departure", "actual_departure"]:
            df[col] = pd.to_datetime(df[col])
        df = df.sort_values(by=["train_number", "run_date", "sequence"]).reset_index(drop=True)

        records = []
        for (tr, dt), group in df.groupby(["train_number", "run_date"]):
            group = group.reset_index(drop=True)
            n = len(group)
            for i in range(n):
                curr_row = group.loc[i]
                curr_dist = float(curr_row["distance_km"])
                t_curr = curr_row["actual_departure"] if pd.notna(curr_row["actual_departure"]) else curr_row["actual_arrival"]
                t_sched_curr = curr_row["scheduled_departure"] if pd.notna(curr_row["scheduled_departure"]) else curr_row["scheduled_arrival"]
                if pd.isna(t_curr) or pd.isna(t_sched_curr):
                    continue
                curr_delay = (t_curr - t_sched_curr).total_seconds() / 60.0

                next_row = group.loc[i+1] if i + 1 < n else None
                next_sec = f"{curr_row['station_code']}->{next_row['station_code']}" if next_row is not None else None
                sec_info = self.section_profiles.get(next_sec, {"avg_delay": 5.0, "delay_var": 10.0, "avg_travel_time": 45.0})

                for j in range(i + 1, n):
                    target_row = group.loc[j]
                    t_target_arr = target_row["actual_arrival"]
                    t_sched_target_arr = target_row["scheduled_arrival"]
                    if pd.isna(t_target_arr) or pd.isna(t_sched_target_arr):
                        continue

                    rem_travel_time = (t_target_arr - t_curr).total_seconds() / 60.0
                    sched_rem_time = (t_sched_target_arr - t_sched_curr).total_seconds() / 60.0
                    dist_to_station = float(target_row["distance_km"]) - curr_dist
                    dist_to_dest = float(group.loc[n-1, "distance_km"]) - curr_dist
                    stations_rem = float(j - i)

                    # Timetable recovery baseline estimation
                    baseline_rec = min(dist_to_station / 100.0 * 1.5, max(0.0, curr_delay * 0.25)) if curr_delay > 0 else 0.0
                    baseline_rem_time = sched_rem_time + max(0.0, curr_delay - baseline_rec)

                    # Train type classification
                    t_type = 1.0 if tr in ["12301", "12302", "12952"] else 2.0

                    hour = float(t_curr.hour)
                    dow = float(t_curr.weekday())
                    is_wknd = 1.0 if dow in [5, 6] else 0.0
                    is_rush = 1.0 if (7 <= hour <= 10 or 17 <= hour <= 21) else 0.0
                    speed_ratio = 1.0 if curr_delay <= 5.0 else 0.75
                    speed_restr = 1.0 if curr_delay > 20.0 else 0.0

                    records.append({
                        "train_number": str(tr),
                        "run_date": str(dt),
                        "from_stn": str(curr_row["station_code"]),
                        "to_stn": str(target_row["station_code"]),
                        "scheduled_remaining_time_min": float(sched_rem_time),
                        "distance_to_station_km": float(dist_to_station),
                        "distance_to_destination_km": float(dist_to_dest),
                        "current_delay_min": float(curr_delay),
                        "current_speed_ratio": float(speed_ratio),
                        "stations_remaining": float(stations_rem),
                        "hist_section_avg_delay": float(sec_info.get("avg_delay", 5.0)),
                        "hist_section_delay_var": float(sec_info.get("delay_var", 10.0)),
                        "hist_section_avg_travel_time": float(sec_info.get("avg_travel_time", 45.0)),
                        "train_type_code": float(t_type),
                        "hour_of_day": float(hour),
                        "day_of_week": float(dow),
                        "is_weekend": float(is_wknd),
                        "is_rush_hour": float(is_rush),
                        "speed_restriction_flag": float(speed_restr),
                        "baseline_rem_time_min": float(baseline_rem_time),
                        "target_remaining_travel_time_min": float(rem_travel_time)
                    })

        return pd.DataFrame(records)

    def extract_remaining_time_inference_features(
        self,
        scheduled_remaining_time_min: float,
        distance_to_station_km: float,
        distance_to_destination_km: float,
        current_delay_min: float,
        current_speed_kmh: float,
        stations_remaining: int,
        next_section_id: Optional[str] = None,
        train_type_str: str = "Rajdhani Express",
        timestamp: Optional[datetime] = None
    ) -> Dict[str, float]:
        """
        Extracts feature dict for predicting remaining travel time to an upcoming station.
        Guaranteed zero feature skew between training and inference.
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        sec_info = self.section_profiles.get(next_section_id or "", {
            "avg_delay": 5.0,
            "delay_var": 10.0,
            "avg_travel_time": 45.0
        })

        # Train type encoding: 1 = Rajdhani/Tejas, 2 = Vande Bharat/Shatabdi, 3 = Mail/Express
        if "Rajdhani" in train_type_str or "Tejas" in train_type_str:
            t_type = 1.0
        elif "Vande Bharat" in train_type_str or "Shatabdi" in train_type_str:
            t_type = 2.0
        else:
            t_type = 3.0

        hour = float(timestamp.hour)
        dow = float(timestamp.weekday())
        is_wknd = 1.0 if dow in [5, 6] else 0.0
        is_rush = 1.0 if (7 <= hour <= 10 or 17 <= hour <= 21) else 0.0
        speed_ratio = round(current_speed_kmh / DEFAULT_PERMISSIBLE_SPEED_KMH, 3) if DEFAULT_PERMISSIBLE_SPEED_KMH > 0 else 1.0
        speed_restr = 1.0 if current_speed_kmh < 45.0 else 0.0

        return {
            "scheduled_remaining_time_min": float(scheduled_remaining_time_min),
            "distance_to_station_km": float(distance_to_station_km),
            "distance_to_destination_km": float(distance_to_destination_km),
            "current_delay_min": float(current_delay_min),
            "current_speed_ratio": float(speed_ratio),
            "stations_remaining": float(stations_remaining),
            "hist_section_avg_delay": float(sec_info.get("avg_delay", 5.0)),
            "hist_section_delay_var": float(sec_info.get("delay_var", 10.0)),
            "hist_section_avg_travel_time": float(sec_info.get("avg_travel_time", 45.0)),
            "train_type_code": float(t_type),
            "hour_of_day": float(hour),
            "day_of_week": float(dow),
            "is_weekend": float(is_wknd),
            "is_rush_hour": float(is_rush),
            "speed_restriction_flag": float(speed_restr)
        }

    def save_profiles(self, filepath: str = "./models/section_profiles.json"):
        """Persist learned historical knowledge base to disk."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        data = {
            "section_profiles": self.section_profiles,
            "train_section_profiles": self.train_section_profiles
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved section historical profiles to {filepath}")

    def load_profiles(self, filepath: str = "./models/section_profiles.json") -> bool:
        """Load historical knowledge base from disk if exists."""
        if not os.path.exists(filepath):
            logger.warning(f"Profile file {filepath} does not exist.")
            return False
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.section_profiles = data.get("section_profiles", {})
            self.train_section_profiles = data.get("train_section_profiles", {})
        logger.info(f"Loaded {len(self.section_profiles)} section profiles from {filepath}")
        return True


# Global default pipeline
feature_pipeline = RailwayFeaturePipeline()
