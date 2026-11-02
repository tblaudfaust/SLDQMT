from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import SessionLocal


@asynccontextmanager
async def lifespan(_: FastAPI):
    db = SessionLocal()
    try:
        init_db(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="SLPHC 2026 Field Monitor Error Follow-up",
    version="0.1.0",
    description="Server for the Field Monitor tablet app: sync, dashboard and reports.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/api/health")
def health():
    # practice_loaded: whether the ToT class practice set is on this server (a plain yes/no for the trainers' checklist)
    from sqlalchemy import select

    from app.models import Setting
    from app.services.tot_practice import VERSION

    db = SessionLocal()
    try:
        loaded = db.execute(select(Setting.value).where(Setting.key == "tot_practice_version")).scalar_one_or_none() == VERSION
    except Exception:  # health must answer even before the schema exists
        loaded = False
    finally:
        db.close()
    return {"status": "ok", "environment": settings.ENVIRONMENT, "practice_loaded": loaded}
