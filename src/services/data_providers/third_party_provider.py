import logging
from typing import List, Optional
from src.services.data_providers.base import TrainDataProvider, NormalizedTrainState

logger = logging.getLogger("railway_eta.providers.third_party")


class ThirdPartyRailwayProvider(TrainDataProvider):
    """
    Adapter for Commercial / Third-Party Railway Telemetry Aggregators.
    
    Supports normalized REST or Webhook ingestion from authorized third-party railway
    data providers during development, without web-scraping or violating terms of service.
    """

    def __init__(self, endpoint_url: Optional[str] = None, api_key: Optional[str] = None):
        self.endpoint_url = endpoint_url
        self.api_key = api_key

    @property
    def provider_name(self) -> str:
        return "ThirdPartyRailwayProvider"

    @property
    def is_simulation(self) -> bool:
        return False

    async def get_train_position(self, train_number: str) -> Optional[NormalizedTrainState]:
        if not self.api_key or not self.endpoint_url:
            logger.warning("ThirdPartyRailwayProvider: API key or endpoint not configured.")
            return None
        
        # Integration logic with third-party REST endpoint
        raise NotImplementedError("Third-party provider API integration requires configured partner API key.")

    async def get_all_train_positions(self) -> List[NormalizedTrainState]:
        if not self.api_key or not self.endpoint_url:
            return []
        raise NotImplementedError("Third-party provider API integration requires configured partner API key.")
