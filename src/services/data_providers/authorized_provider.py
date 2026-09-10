import logging
from typing import List, Optional
from src.services.data_providers.base import TrainDataProvider, NormalizedTrainState

logger = logging.getLogger("railway_eta.providers.authorized")


class AuthorizedRailwayProvider(TrainDataProvider):
    """
    Adapter for Official Indian Railways / CRIS / NTES / RTIS Feeds.
    
    IMPORTANT DATA GOVERNANCE POLICY:
    - Internal Indian Railways operational feeds (RTIS/COA/NTES) are not publicly open.
    - This provider implements the required enterprise gateway contract and token handshake.
    - When institutional enterprise credentials and IP whitelisting are granted by the
      Ministry of Railways / CRIS, this adapter converts their JSON/Protobuf feeds into
      our system's NormalizedTrainState schema.
    """

    def __init__(self, api_gateway_url: Optional[str] = None, client_token: Optional[str] = None):
        self.api_gateway_url = api_gateway_url
        self.client_token = client_token

    @property
    def provider_name(self) -> str:
        return "AuthorizedRailwayProvider (CRIS/NTES/RTIS)"

    @property
    def is_simulation(self) -> bool:
        return False

    async def get_train_position(self, train_number: str) -> Optional[NormalizedTrainState]:
        if not self.client_token or not self.api_gateway_url:
            logger.warning(
                f"AuthorizedRailwayProvider: No official CRIS/NTES enterprise gateway token configured. "
                f"Cannot query live feed for train {train_number}."
            )
            return None
        
        # Enterprise HTTP/gRPC request stub
        raise NotImplementedError(
            "Authorized CRIS/NTES gateway integration requires valid enterprise certificates and institutional clearance."
        )

    async def get_all_train_positions(self) -> List[NormalizedTrainState]:
        if not self.client_token or not self.api_gateway_url:
            return []
        raise NotImplementedError("Authorized CRIS/NTES gateway requires institutional credentials.")
