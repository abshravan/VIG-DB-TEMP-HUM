from fastapi import APIRouter

from app.api.v1 import alarms, auth, history, live, sensors, settings, system, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(live.router)
api_router.include_router(history.router)
api_router.include_router(alarms.router)
api_router.include_router(sensors.router)
api_router.include_router(settings.router)
api_router.include_router(users.router)
api_router.include_router(system.router)
