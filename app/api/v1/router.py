from fastapi import APIRouter

from app.api.v1.readings import router as readings_router
from app.api.v1.archive import router as archive_router
from app.api.v1.health import router as health_router
from app.api.v1.week import router as week_router
from app.api.v1.tts import router as tts_router
from .admin import router as admin_router

router = APIRouter()
router.include_router(readings_router)
router.include_router(archive_router)
router.include_router(health_router)
router.include_router(week_router)
router.include_router(tts_router)
router.include_router(admin_router)