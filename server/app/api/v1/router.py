from fastapi import APIRouter

from app.api.v1 import admin, auth, dashboard, devices, dqm_reports, exit_checkouts, incidents, me, me_daily, me_fac, me_kpi, mefm, reports, resources, sync

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(devices.router)
api_router.include_router(sync.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
api_router.include_router(resources.router)
api_router.include_router(dqm_reports.router)
api_router.include_router(exit_checkouts.router)
api_router.include_router(me.router)
api_router.include_router(me_daily.router)
api_router.include_router(me_fac.router)
api_router.include_router(me_kpi.router)
api_router.include_router(incidents.router)
api_router.include_router(mefm.router)
api_router.include_router(admin.router)
