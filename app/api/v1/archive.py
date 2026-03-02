from fastapi import APIRouter

from app.core.paths import readings_cache_dir
from app.services.readings_service import ReadingsService
from app.services.storage import FileStorage

router = APIRouter(tags=["archive"])

storage = FileStorage(str(readings_cache_dir()))
service = ReadingsService(storage)


@router.get("/archive/months")
def list_months():
    return {"months": service.list_months()}
