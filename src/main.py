import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.api.health import router as health_router
from src.api.trains import router as trains_router
from src.api.stations import router as stations_router
from src.api.simulator import router as simulator_router
from src.api.weather import router as weather_router
from src.db.session import init_db, AsyncSessionLocal
from src.db.seed import seed_database
from src.db.models import Route, RouteStation
from src.simulator.train_simulator import simulator

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("railway_eta")


async def register_simulator_trains():
    """Load route geometries and populate the simulation engine."""
    async with AsyncSessionLocal() as session:
        routes_stmt = (
            select(Route)
            .options(
                selectinload(Route.route_stations).selectinload(RouteStation.station)
            )
        )
        res = await session.execute(routes_stmt)
        routes = res.scalars().all()

        initial_delays = {"12302": 12.0, "22436": 3.0, "12952": 38.0, "12301": 4.0}
        initial_segments = {"12302": 1, "22436": 0, "12952": 1, "12301": 2}

        for r in routes:
            stops = []
            for rs in sorted(r.route_stations, key=lambda x: x.station_sequence):
                stops.append({
                    "sequence": rs.station_sequence,
                    "station_code": rs.station_code,
                    "station_name": rs.station.station_name if rs.station else rs.station_code,
                    "latitude": rs.station.latitude if rs.station else 0.0,
                    "longitude": rs.station.longitude if rs.station else 0.0,
                })
            if len(stops) > 1:
                simulator.register_train(
                    train_number=r.train_number,
                    stops=stops,
                    initial_delay=initial_delays.get(r.train_number, 5.0),
                    start_segment=initial_segments.get(r.train_number, 0)
                )


async def simulation_ticker_task():
    """Background loop advancing simulated train positions and broadcasting real-time ETAs."""
    logger.info("Simulation background ticker started.")
    from src.services.realtime_service import recalculate_and_broadcast_train_eta
    from src.services.websocket_manager import ws_manager

    ticker_count = 0
    try:
        while True:
            await asyncio.sleep(2.0)
            simulator.tick(delta_seconds=2.0, speed_multiplier=2.5)
            ticker_count += 1

            # Recalculate & broadcast active train ETAs to connected WebSocket clients
            active_trains = list(ws_manager._active_connections.keys())
            if active_trains:
                for train_num in active_trains:
                    try:
                        await recalculate_and_broadcast_train_eta(train_num, reason="Periodic simulation kinematic update")
                    except Exception as e:
                        logger.warning(f"Error in background ETA broadcast for {train_num}: {e}")
    except asyncio.CancelledError:
        logger.info("Simulation background ticker cancelled.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Railway ETA Prediction Platform...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Data Provider Mode: {settings.DATA_PROVIDER.upper()}")
    
    # 1. Initialize DB schema
    await init_db()
    logger.info("Database schema initialized.")

    # 2. Seed initial reference data if required
    async with AsyncSessionLocal() as session:
        await seed_database(session)

    # 3. Register trains in simulation engine
    await register_simulator_trains()
    logger.info("Simulation engine loaded with active train route networks.")

    # 4. Start background ticker if simulation mode is active
    ticker_task = None
    if settings.is_simulation:
        ticker_task = asyncio.create_task(simulation_ticker_task())

    yield

    if ticker_task:
        ticker_task.cancel()
        try:
            await ticker_task
        except asyncio.CancelledError:
            pass

    logger.info("Shutting down Railway ETA Prediction Platform...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Dynamic Forecast of Expected Time of Arrival (ETA) for Indian Railways Coaching Trains",
    lifespan=lifespan,
)

# Middleware Configuration
from src.core.middleware import OperationalLoggingMiddleware

app.add_middleware(OperationalLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
from src.api.ws import router as ws_router

app.include_router(health_router, prefix=settings.API_PREFIX, tags=["Health"])
app.include_router(trains_router, prefix=f"{settings.API_PREFIX}/trains", tags=["Trains"])
app.include_router(stations_router, prefix=f"{settings.API_PREFIX}/stations", tags=["Stations"])
app.include_router(weather_router, prefix=f"{settings.API_PREFIX}/weather", tags=["Weather"])
app.include_router(simulator_router, prefix=f"{settings.API_PREFIX}/simulator", tags=["Simulator"])
app.include_router(simulator_router, prefix=f"{settings.API_PREFIX}/simulation", tags=["Simulator"])
app.include_router(ws_router, tags=["WebSocket"])


@app.get("/")
async def root():
    return {
        "message": "Indian Railways Dynamic Train ETA Prediction System API",
        "version": settings.VERSION,
        "docs_url": "/docs",
        "health_check": f"{settings.API_PREFIX}/health",
        "endpoints": [
            f"{settings.API_PREFIX}/trains",
            f"{settings.API_PREFIX}/trains/{{train_number}}",
            f"{settings.API_PREFIX}/trains/{{train_number}}/route",
            f"{settings.API_PREFIX}/trains/{{train_number}}/position",
            f"{settings.API_PREFIX}/stations/{{station_code}}",
            f"{settings.API_PREFIX}/simulator/status",
            f"{settings.API_PREFIX}/simulator/event",
            f"{settings.API_PREFIX}/simulator/tick",
            f"{settings.API_PREFIX}/simulator/reset"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=(settings.ENVIRONMENT == "development")
    )
