# app/api/v1/admin.py

from fastapi import APIRouter, HTTPException
import os
from app.jobs.update_readings import update_week

router = APIRouter()

SECRET = os.getenv("CRON_SECRET")

@router.post("/admin/run-scraper")
def run_scraper(secret: str):
    if secret != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    update_week()
    return {"status": "scraper executed"}