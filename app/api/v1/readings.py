import re
from fastapi import APIRouter, HTTPException, Response

from app.core.config import settings
from app.core.cache import etag_for_file, last_modified_http
from app.services.storage import FileStorage
from app.services.readings_service import ReadingsService

router = APIRouter(tags=["readings"])

storage = FileStorage(settings.data_dir)
service = ReadingsService(storage)

RE_MONTH = re.compile(r"^\d{4}-\d{2}$")
RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def apply_cache_headers(response: Response, filename: str):
    path = storage.path(filename)
    stat = storage.stat(filename)
    response.headers["ETag"] = etag_for_file(path)
    response.headers["Last-Modified"] = last_modified_http(stat)
    response.headers["Cache-Control"] = "public, max-age=300"

@router.get("/readings/latest")
def get_latest(response: Response):
    try:
        apply_cache_headers(response, "latest.json")
        return service.get_latest()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="latest.json not found")

@router.get("/readings/month/{yyyy_mm}")
def get_month(yyyy_mm: str, response: Response):
    if not RE_MONTH.match(yyyy_mm):
        raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")

    filename = f"month-{yyyy_mm}.json"
    try:
        apply_cache_headers(response, filename)
        return service.get_month(yyyy_mm)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"{filename} not found")

@router.get("/readings/date/{yyyy_mm_dd}")
def get_by_date(yyyy_mm_dd: str, response: Response):
    if not RE_DATE.match(yyyy_mm_dd):
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    yyyy_mm = yyyy_mm_dd[:7]
    filename = f"month-{yyyy_mm}.json"
    try:
        apply_cache_headers(response, filename)
        return service.get_by_date(yyyy_mm_dd)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"{filename} not found")
    except KeyError:
        raise HTTPException(status_code=404, detail=f"{yyyy_mm_dd} not found in {filename}")