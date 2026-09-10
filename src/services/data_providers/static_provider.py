from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import select
from src.db.session import AsyncSessionLocal
from src.db.models import LivePosition
from src.services.data_providers.base import TrainDataProvider, NormalizedTrainState


class MockStaticProvider(TrainDataProvider):
    """
    Static/Mock Provider reading fixed baseline telemetry snapshots from the database.
    Useful for offline testing, golden unit tests, and deterministic benchmarks.
    """

    @property
    def provider_name(self) -> str:
        return "MockStaticProvider"

    @property
    def is_simulation(self) -> bool:
        return True

    async def get_train_position(self, train_number: str) -> Optional[NormalizedTrainState]:
        async with AsyncSessionLocal() as session:
            stmt = (
                select(LivePosition)
                .where(LivePosition.train_number == train_number)
                .order_by(LivePosition.timestamp.desc())
                .limit(1)
            )
            res = await session.execute(stmt)
            pos = res.scalar_one_or_none()

            if not pos:
                return None

            return NormalizedTrainState(
                train_number=pos.train_number,
                timestamp=pos.timestamp or datetime.now(timezone.utc),
                latitude=pos.latitude,
                longitude=pos.longitude,
                speed=pos.speed,
                bearing=0.0,
                current_delay=pos.current_delay,
                current_station=pos.current_station,
                next_station=pos.next_station,
                data_source="SIMULATION",
                operational_event="STATIC_SNAPSHOT"
            )

    async def get_all_train_positions(self) -> List[NormalizedTrainState]:
        async with AsyncSessionLocal() as session:
            stmt = select(LivePosition).order_by(LivePosition.timestamp.desc())
            res = await session.execute(stmt)
            positions = res.scalars().all()

            seen = set()
            results = []
            for pos in positions:
                if pos.train_number not in seen:
                    seen.add(pos.train_number)
                    results.append(NormalizedTrainState(
                        train_number=pos.train_number,
                        timestamp=pos.timestamp or datetime.now(timezone.utc),
                        latitude=pos.latitude,
                        longitude=pos.longitude,
                        speed=pos.speed,
                        bearing=0.0,
                        current_delay=pos.current_delay,
                        current_station=pos.current_station,
                        next_station=pos.next_station,
                        data_source="SIMULATION",
                        operational_event="STATIC_SNAPSHOT"
                    ))
            return results
