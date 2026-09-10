from typing import List, Optional
from src.services.data_providers.base import TrainDataProvider, NormalizedTrainState
from src.simulator.train_simulator import simulator


class SimulatorProvider(TrainDataProvider):
    """
    Simulated Railway Telemetry Provider.
    Drives real-time train movement, disruption simulation, and delay modulation.
    """

    @property
    def provider_name(self) -> str:
        return "SimulatorProvider"

    @property
    def is_simulation(self) -> bool:
        return True

    async def get_train_position(self, train_number: str) -> Optional[NormalizedTrainState]:
        return simulator.get_state(train_number)

    async def get_all_train_positions(self) -> List[NormalizedTrainState]:
        return simulator.get_all_states()
