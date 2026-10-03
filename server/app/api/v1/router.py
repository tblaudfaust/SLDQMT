from fastapi import APIRouter

from app.api.v1 import admin, auth, dashboard, devices, dqm_reports, exit_checkouts, reports, resources, sync

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(devices.router)
api_router.include_router(sync.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
api_router.include_router(resources.router)
api_router.include_router(dqm_reports.router)
api_router.include_router(exit_checkouts.router)
api_router.include_router(admin.router)
