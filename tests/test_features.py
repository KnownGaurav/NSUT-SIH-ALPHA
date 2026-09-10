import pytest
import pandas as pd
from datetime import datetime, timezone
from src.ml.features import (
    RailwayFeaturePipeline, HistoricalRunInput, FEATURE_COLUMNS
)


def test_input_validation():
    # Valid input
    valid_rec = HistoricalRunInput(
        train_number="12302",
        run_date="2026-09-10",
        station_code="CNB",
        sequence=2,
        scheduled_arrival="2026-09-10 21:30:00",
        actual_arrival="2026-09-10 21:42:00",
        scheduled_departure="2026-09-10 21:35:00",
        actual_departure="2026-09-10 21:46:00",
        distance_km=440.0
    )
    assert valid_rec.train_number == "12302"
    assert valid_rec.sequence == 2

    # Invalid train number
    with pytest.raises(ValueError):
        HistoricalRunInput(
            train_number=" ",
            run_date="2026-09-10",
            station_code="CNB",
            sequence=1,
            distance_km=0.0
        )


def test_process_historical_runs():
    pipeline = RailwayFeaturePipeline()

    sample_data = pd.DataFrame([
        {
            "train_number": "12301",
            "run_date": "2026-09-01",
            "station_code": "NDLS",
            "sequence": 1,
            "scheduled_arrival": "",
            "actual_arrival": "",
            "scheduled_departure": "2026-09-01 16:55:00",
            "actual_departure": "2026-09-01 17:00:00",  # +5m dep delay
            "distance_km": 0.0
        },
        {
            "train_number": "12301",
            "run_date": "2026-09-01",
            "station_code": "CNB",
            "sequence": 2,
            "scheduled_arrival": "2026-09-01 21:30:00",
            "actual_arrival": "2026-09-01 21:40:00",    # +10m arr delay
            "scheduled_departure": "2026-09-01 21:35:00",
            "actual_departure": "2026-09-01 21:48:00",  # dwell = 8m (sched dwell = 5m, deviation = +3m)
            "distance_km": 440.0
        },
        {
            "train_number": "12301",
            "run_date": "2026-09-01",
            "station_code": "PRYJ",
            "sequence": 3,
            "scheduled_arrival": "2026-09-01 23:43:00",
            "actual_arrival": "2026-09-01 23:51:00",    # +8m arr delay (recovered 5m vs departure from CNB +13m)
            "scheduled_departure": "2026-09-01 23:45:00",
            "actual_departure": "2026-09-01 23:53:00",
            "distance_km": 634.0
        }
    ])

    processed = pipeline.process_historical_runs(sample_data)

    # 1. Delays
    assert processed.loc[0, "departure_delay_min"] == 5.0
    assert processed.loc[1, "arrival_delay_min"] == 10.0
    assert processed.loc[1, "departure_delay_min"] == 13.0

    # 2. Dwell & Deviation
    assert processed.loc[1, "station_dwell_time_min"] == 8.0
    assert processed.loc[1, "scheduled_dwell_time_min"] == 5.0
    assert processed.loc[1, "dwell_deviation_min"] == 3.0

    # 3. Sectional running time (NDLS -> CNB)
    assert processed.loc[1, "section_id"] == "NDLS->CNB"
    assert processed.loc[1, "section_distance_km"] == 440.0
    # Scheduled running time: 16:55 to 21:30 = 275 min
    assert processed.loc[1, "scheduled_running_time_min"] == 275.0
    # Actual running time: 17:00 to 21:40 = 280 min
    assert processed.loc[1, "sectional_running_time_min"] == 280.0

    # 4. Delay recovery on section CNB -> PRYJ
    # CNB departure delay was +13m, PRYJ arrival delay was +8m -> recovered 5m!
    assert processed.loc[2, "delay_recovery_min"] == 5.0


def test_feature_matrix_and_reusability():
    pipeline = RailwayFeaturePipeline()
    pipeline.load_profiles("./models/section_profiles.json")

    # Verify profiles loaded
    assert len(pipeline.section_profiles) > 0
    assert "NDLS->CNB" in pipeline.section_profiles
    sec_info = pipeline.section_profiles["NDLS->CNB"]
    assert sec_info["avg_delay"] > 0
    assert sec_info["avg_travel_time"] > 200

    # Test inference feature extraction
    now = datetime(2026, 9, 10, 18, 30, tzinfo=timezone.utc)
    feat_df = pipeline.build_inference_vector(
        train_number="12302",
        from_station="NDLS",
        to_station="CNB",
        section_dist_km=440.0,
        scheduled_run_min=275.0,
        current_delay_min=12.0,
        current_speed_kmh=118.0,
        timestamp=now
    )

    # Assert column schema matching
    assert list(feat_df.columns) == FEATURE_COLUMNS
    assert feat_df.loc[0, "section_dist_km"] == 440.0
    assert feat_df.loc[0, "scheduled_run_min"] == 275.0
    assert feat_df.loc[0, "current_delay_min"] == 12.0
    assert feat_df.loc[0, "hour_of_day"] == 18.0
    assert feat_df.loc[0, "is_rush_hour"] == 1.0
    assert feat_df.loc[0, "speed_restriction_flag"] == 0.0
    assert not feat_df.isna().any().any()
