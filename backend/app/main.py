import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import Base, SessionLocal, engine
from . import models
from .routers import auth, elders, internal, monitoring, simulator, webhook
from .services import checkins as checkin_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("lder")

settings = get_settings()
settings.prompt_dir.mkdir(parents=True, exist_ok=True)


def scheduled_tick() -> None:
    db = SessionLocal()
    try:
        checkin_service.run_tick(db)
    except Exception:
        log.exception("Scheduled tick failed")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    scheduler = None
    if settings.enable_scheduler:
        scheduler = BackgroundScheduler(timezone="UTC")
        scheduler.add_job(
            scheduled_tick,
            "interval",
            minutes=settings.tick_interval_minutes,
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Lder", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

for module in (auth, elders, monitoring, simulator, webhook, internal):
    app.include_router(module.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}