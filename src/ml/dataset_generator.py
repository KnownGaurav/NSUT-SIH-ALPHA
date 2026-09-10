import os
import random
from datetime import datetime, timedelta, timezone
import pandas as pd
from src.ml.features import feature_pipeline

# Seed for reproducibility
random.seed(42)

TRAIN_SCHEDULES = {
    "12302": [  # Howrah Rajdhani: NDLS -> HWH
        {"stn": "NDLS", "seq": 1, "arr": None, "dep": "16:55:00", "dist": 0.0, "day": 1},
        {"stn": "CNB",  "seq": 2, "arr": "21:30:00", "dep": "21:35:00", "dist": 440.0, "day": 1},
        {"stn": "PRYJ", "seq": 3, "arr": "23:43:00", "dep": "23:45:00", "dist": 634.0, "day": 1},
        {"stn": "DDU",  "seq": 4, "arr": "00:45:00", "dep": "00:55:00", "dist": 787.0, "day": 2},
        {"stn": "GAYA", "seq": 5, "arr": "03:10:00", "dep": "03:13:00", "dist": 992.0, "day": 2},
        {"stn": "DHN",  "seq": 6, "arr": "05:55:00", "dep": "06:00:00", "dist": 1193.0, "day": 2},
        {"stn": "ASN",  "seq": 7, "arr": "06:54:00", "dep": "06:56:00", "dist": 1251.0, "day": 2},
        {"stn": "HWH",  "seq": 8, "arr": "09:55:00", "dep": None, "dist": 1450.0, "day": 2},
    ],
    "22436": [  # Vande Bharat: NDLS -> BSB
        {"stn": "NDLS", "seq": 1, "arr": None, "dep": "06:00:00", "dist": 0.0, "day": 1},
        {"stn": "CNB",  "seq": 2, "arr": "10:08:00", "dep": "10:10:00", "dist": 440.0, "day": 1},
        {"stn": "PRYJ", "seq": 3, "arr": "12:08:00", "dep": "12:10:00", "dist": 634.0, "day": 1},
        {"stn": "BSB",  "seq": 4, "arr": "14:00:00", "dep": None, "dist": 759.0, "day": 1},
    ],
    "12952": [  # Tejas Rajdhani: NDLS -> MMCT
        {"stn": "NDLS", "seq": 1, "arr": None, "dep": "16:55:00", "dist": 0.0, "day": 1},
        {"stn": "KOTA", "seq": 2, "arr": "21:30:00", "dep": "21:40:00", "dist": 465.0, "day": 1},
        {"stn": "BRC",  "seq": 3, "arr": "03:40:00", "dep": "03:50:00", "dist": 992.0, "day": 2},
        {"stn": "MMCT", "seq": 4, "arr": "08:35:00", "dep": None, "dist": 1384.0, "day": 2},
    ]
}


def generate_historical_dataset(num_days: int = 30) -> pd.DataFrame:
    """
    Generates realistic historical train run observations over the past `num_days`
    modeling authentic delay propagation, dwell deviations, and recovery.
    """
    records = []
    base_date = datetime.now(timezone.utc).date() - timedelta(days=num_days + 1)

    for day_idx in range(num_days):
        current_date = base_date + timedelta(days=day_idx)

        for train_number, stops in TRAIN_SCHEDULES.items():
            cumulative_delay = random.choice([0.0, 0.0, 2.0, 5.0, 10.0])  # Initial origin delay

            for s in stops:
                seq = s["seq"]
                stn = s["stn"]
                dist = s["dist"]
                day_offset = s["day"] - 1
                run_day = current_date + timedelta(days=day_offset)

                # 1. Base scheduled arrival & departure
                sched_arr_dt = None
                if s["arr"]:
                    h, m, sec = map(int, s["arr"].split(":"))
                    sched_arr_dt = datetime(run_day.year, run_day.month, run_day.day, h, m, sec)

                sched_dep_dt = None
                if s["dep"]:
                    h, m, sec = map(int, s["dep"].split(":"))
                    sched_dep_dt = datetime(run_day.year, run_day.month, run_day.day, h, m, sec)

                # Sectional delay drift
                if seq > 1:
                    # Section behavior:
                    # e.g., CNB->PRYJ and DDU are busy junctions with occasional congestion
                    if stn in ["CNB", "DDU"]:
                        drift = random.gauss(4.0, 3.0)  # Moderate junction congestion
                    elif stn in ["PRYJ", "DHN", "ASN"]:
                        drift = random.gauss(-1.5, 2.0)  # Recovery section
                    else:
                        drift = random.gauss(0.5, 1.5)

                    cumulative_delay = max(0.0, cumulative_delay + drift)

                # Actual arrival
                act_arr_dt = None
                if sched_arr_dt:
                    act_arr_dt = sched_arr_dt + timedelta(minutes=round(cumulative_delay, 1))

                # Dwell time variation
                dwell_variation = random.choice([0.0, 0.5, 1.0, 2.0, -0.5])
                act_dep_dt = None
                if sched_dep_dt:
                    if act_arr_dt:
                        act_dep_dt = act_arr_dt + timedelta(minutes=max(1.0, (sched_dep_dt - sched_arr_dt).total_seconds() / 60.0 + dwell_variation))
                    else:
                        # Origin station
                        act_dep_dt = sched_dep_dt + timedelta(minutes=round(cumulative_delay, 1))

                records.append({
                    "train_number": train_number,
                    "run_date": current_date.isoformat(),
                    "station_code": stn,
                    "sequence": seq,
                    "scheduled_arrival": sched_arr_dt.isoformat() if sched_arr_dt else "",
                    "actual_arrival": act_arr_dt.isoformat() if act_arr_dt else "",
                    "scheduled_departure": sched_dep_dt.isoformat() if sched_dep_dt else "",
                    "actual_departure": act_dep_dt.isoformat() if act_dep_dt else "",
                    "distance_km": dist
                })

    df = pd.DataFrame(records)
    return df


def generate_and_save_data():
    os.makedirs("./data", exist_ok=True)
    os.makedirs("./models", exist_ok=True)

    df_raw = generate_historical_dataset(num_days=35)
    csv_path = "./data/historical_train_runs.csv"
    df_raw.to_csv(csv_path, index=False)
    print(f"Generated {len(df_raw)} historical train run records -> {csv_path}")

    # Process features and fit historical profiles
    df_proc = feature_pipeline.process_historical_runs(df_raw)
    proc_path = "./data/processed_sections.csv"
    df_proc.to_csv(proc_path, index=False)
    print(f"Processed sectional metrics -> {proc_path}")

    # Fit and save profiles
    feature_pipeline.fit_historical_profiles(df_proc)
    feature_pipeline.save_profiles("./models/section_profiles.json")
    print("Section historical profiles saved to ./models/section_profiles.json")


if __name__ == "__main__":
    generate_and_save_data()
