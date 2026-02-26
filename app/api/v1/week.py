import re
from datetime import datetime, timedelta, date as date_type
from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.services.storage import FileStorage
from app.services.readings_service import ReadingsService

router = APIRouter(tags=["readings"])

RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

storage = FileStorage(settings.data_dir)
service = ReadingsService(storage)


def _week_start_monday(d: date_type) -> date_type:
    # Monday = 0 ... Sunday = 6
    return d - timedelta(days=d.weekday())


@router.get("/readings/week/{yyyy_mm_dd}")
def get_week(yyyy_mm_dd: str):
    """
    Devuelve SIEMPRE 7 días (Lun->Dom) de la semana del date recibido.
    Así el aside no se queda con 1 día cuando seleccionas otro.
    """
    if not RE_DATE.match(yyyy_mm_dd):
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    d = datetime.strptime(yyyy_mm_dd, "%Y-%m-%d").date()
    start = _week_start_monday(d)

    days = []
    for i in range(7):
        day = (start + timedelta(days=i)).isoformat()
        try:
            days.append(service.get_by_date(day))
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Missing month file for {day}")
        except KeyError:
            raise HTTPException(status_code=404, detail=f"{day} not found")

    return {"start": start.isoformat(), "days": days}