from datetime import datetime, date, timezone
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Date, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from src.db.session import Base


def utc_now():
    return datetime.now(timezone.utc)


class Train(Base):
    __tablename__ = "trains"

    train_number = Column(String(10), primary_key=True, index=True)
    train_name = Column(String(100), nullable=False)
    train_type = Column(String(50), nullable=False)  # e.g., "Rajdhani", "Vande Bharat", "Superfast"
    source = Column(String(10), nullable=False)       # Station Code
    destination = Column(String(10), nullable=False)  # Station Code
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    routes = relationship("Route", back_populates="train", cascade="all, delete-orphan")
    runs = relationship("TrainRun", back_populates="train", cascade="all, delete-orphan")
    live_positions = relationship("LivePosition", back_populates="train")


class Station(Base):
    __tablename__ = "stations"

    station_code = Column(String(10), primary_key=True, index=True)
    station_name = Column(String(100), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    state = Column(String(50), nullable=True)
    zone = Column(String(20), nullable=True)  # e.g., "NR", "ECR", "NCR", "ER"

    # Relationships
    route_stations = relationship("RouteStation", back_populates="station")


class Route(Base):
    __tablename__ = "routes"

    route_id = Column(String(20), primary_key=True, index=True)
    train_number = Column(String(10), ForeignKey("trains.train_number", ondelete="CASCADE"), nullable=False)
    direction = Column(String(10), default="UP")  # UP or DOWN
    total_distance_km = Column(Float, default=0.0)

    # Relationships
    train = relationship("Train", back_populates="routes")
    route_stations = relationship("RouteStation", back_populates="route", cascade="all, delete-orphan", order_by="RouteStation.station_sequence")


class RouteStation(Base):
    __tablename__ = "route_stations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(String(20), ForeignKey("routes.route_id", ondelete="CASCADE"), nullable=False, index=True)
    station_sequence = Column(Integer, nullable=False)
    station_code = Column(String(10), ForeignKey("stations.station_code", ondelete="CASCADE"), nullable=False, index=True)
    scheduled_arrival = Column(String(8), nullable=True)   # "HH:MM:SS" or null if origin
    scheduled_departure = Column(String(8), nullable=True) # "HH:MM:SS" or null if destination
    distance_from_origin = Column(Float, default=0.0)
    scheduled_dwell_minutes = Column(Float, default=2.0)
    day_offset = Column(Integer, default=1)

    # Relationships
    route = relationship("Route", back_populates="route_stations")
    station = relationship("Station", back_populates="route_stations")

    __table_args__ = (
        Index("idx_route_sequence", "route_id", "station_sequence"),
    )


class TrainRun(Base):
    __tablename__ = "train_runs"

    run_id = Column(String(50), primary_key=True, index=True)  # e.g. "12301_2026-09-10"
    train_number = Column(String(10), ForeignKey("trains.train_number", ondelete="CASCADE"), nullable=False, index=True)
    run_date = Column(Date, nullable=False)
    status = Column(String(20), default="SCHEDULED")  # "SCHEDULED", "RUNNING", "COMPLETED", "CANCELLED"
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    train = relationship("Train", back_populates="runs")
    live_positions = relationship("LivePosition", back_populates="train_run")


class LivePosition(Base):
    __tablename__ = "live_positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    train_number = Column(String(10), ForeignKey("trains.train_number", ondelete="CASCADE"), nullable=False, index=True)
    run_id = Column(String(50), ForeignKey("train_runs.run_id", ondelete="SET NULL"), nullable=True)
    timestamp = Column(DateTime, default=utc_now, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    speed = Column(Float, default=0.0)               # km/h
    current_delay = Column(Float, default=0.0)       # in minutes (+ve: late, -ve: early)
    current_station = Column(String(10), nullable=True)
    next_station = Column(String(10), nullable=True)
    data_source = Column(String(20), default="SIMULATION")  # "SIMULATION", "CRIS_NTES", "THIRD_PARTY"

    # Relationships
    train = relationship("Train", back_populates="live_positions")
    train_run = relationship("TrainRun", back_populates="live_positions")

    __table_args__ = (
        Index("idx_train_timestamp", "train_number", "timestamp"),
    )


class HistoricalDelay(Base):
    __tablename__ = "historical_delays"

    id = Column(Integer, primary_key=True, autoincrement=True)
    train_number = Column(String(10), ForeignKey("trains.train_number", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    station_code = Column(String(10), ForeignKey("stations.station_code", ondelete="CASCADE"), nullable=False, index=True)
    scheduled_arrival = Column(DateTime, nullable=False)
    actual_arrival = Column(DateTime, nullable=False)
    delay_minutes = Column(Float, nullable=False)
    section = Column(String(50), nullable=True)  # e.g., "DDU-CNB", "NDLS-CNB"

    __table_args__ = (
        Index("idx_train_station_date", "train_number", "station_code", "date"),
    )


class ETAPrediction(Base):
    __tablename__ = "eta_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    train_number = Column(String(10), ForeignKey("trains.train_number", ondelete="CASCADE"), nullable=False, index=True)
    station_code = Column(String(10), ForeignKey("stations.station_code", ondelete="CASCADE"), nullable=False, index=True)
    prediction_timestamp = Column(DateTime, default=utc_now, index=True)
    predicted_eta = Column(DateTime, nullable=False)
    lower_bound = Column(DateTime, nullable=False)
    upper_bound = Column(DateTime, nullable=False)
    confidence = Column(Float, default=0.90)          # 0.0 - 1.0 (e.g., 0.90 for 90% confidence)
    model_version = Column(String(50), default="xgb_v1.0.0")

    __table_args__ = (
        Index("idx_pred_train_station", "train_number", "station_code", "prediction_timestamp"),
    )


class WeatherObservation(Base):
    __tablename__ = "weather_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_code = Column(String(10), nullable=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=utc_now, index=True)
    temperature_c = Column(Float, nullable=True)
    visibility_km = Column(Float, nullable=True)
    precipitation_mm = Column(Float, default=0.0)
    weather_code = Column(Integer, nullable=True)
    condition_description = Column(String(100), nullable=True)
