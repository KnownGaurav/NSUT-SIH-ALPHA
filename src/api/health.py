from fastapi import APIRouter
from pydantic import BaseModel
from src.core.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    provider: str
    is_simulation: bool
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint returning service operational status
    and active data provider mode.
    """
    return HealthResponse(
        status="ok",
        service="railway-eta-api",
        provider=settings.DATA_PROVIDER,
        is_simulation=settings.is_simulation,
        version=settings.VERSION
    )
