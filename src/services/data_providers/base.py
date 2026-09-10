from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class NormalizedTrainState(BaseModel):
    """
    Standard normalized schema representing atomic real-time train telemetry.
    Independent of underlying feed protocol (Simulation, NTES, or Partner API).
    """
    model_config = ConfigDict(from_attributes=True)

    train_number: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    latitude: float
    longitude: float
    speed: float = Field(..., description="Instantaneous velocity in km/h")
    bearing: float = Field(default=0.0, description="Direction of travel in degrees (0-360)")
    current_delay: float = Field(..., description="Delay in minutes (+ve: late, -ve: ahead of schedule)")
    current_station: Optional[str] = None
    next_station: Optional[str] = None
    data_source: str = "SIMULATION"
    operational_event: str = "NORMAL_OPERATION"

    @property
    def delay_status(self) -> str:
        if self.current_delay <= 5.0:
            return "on_time"
        elif self.current_delay <= 30.0:
            return "moderate"
        return "severe"


class TrainDataProvider(ABC):
    """
    Abstract Base Class defining the contract for all train position and telemetry providers.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the data provider implementation."""
        pass

    @property
    @abstractmethod
    def is_simulation(self) -> bool:
        """True if the data originates from synthetic simulation models."""
        pass

    @abstractmethod
    async def get_train_position(self, train_number: str) -> Optional[NormalizedTrainState]:
        """Fetch the latest normalized position state for a specific train."""
        pass

    @abstractmethod
    async def get_all_train_positions(self) -> List[NormalizedTrainState]:
        """Fetch latest normalized positions for all active trains."""
        pass
