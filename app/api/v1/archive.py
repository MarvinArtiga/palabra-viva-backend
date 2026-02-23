from fastapi import APIRouter

from app.core.config import settings
from app.services.storage import FileStorage
from app.services.readings_service import ReadingsService

router = APIRouter(tags=["archive"])

storage = FileStorage(settings.data_dir)
service = ReadingsService(storage)


@router.get("/archive/months")
def list_months():
    return {"months": service.list_months()}