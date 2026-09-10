from src.core.config import settings
from src.services.data_providers.base import TrainDataProvider
from src.services.data_providers.simulator_provider import SimulatorProvider
from src.services.data_providers.static_provider import MockStaticProvider
from src.services.data_providers.authorized_provider import AuthorizedRailwayProvider
from src.services.data_providers.third_party_provider import ThirdPartyRailwayProvider
from src.services.data_providers.railradar_provider import RailRadarProvider

_active_provider: TrainDataProvider = None


def get_data_provider() -> TrainDataProvider:
    """
    Factory function returning the active train data provider according to DATA_PROVIDER config.
    """
    global _active_provider
    if _active_provider is None:
        mode = settings.DATA_PROVIDER.lower().strip()
        if mode == "simulation":
            _active_provider = SimulatorProvider()
        elif mode == "railradar":
            _active_provider = RailRadarProvider()
        elif mode == "static" or mode == "mock":
            _active_provider = MockStaticProvider()
        elif mode == "cris_ntes" or mode == "authorized":
            _active_provider = AuthorizedRailwayProvider()
        elif mode == "third_party":
            _active_provider = ThirdPartyRailwayProvider()
        else:
            # Default fallback to Simulator
            _active_provider = SimulatorProvider()

    return _active_provider

