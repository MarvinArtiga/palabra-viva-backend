import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.core.paths import readings_cache_dir, tts_cache_dir
from app.models.readings import DailyReadings, ReadingItem
from app.services.readings_service import ReadingsService
from app.services.storage import FileStorage
from app.services.tts_service import (
    DEFAULT_VOICE,
    TTSDependencyError,
    TTSGenerationError,
    build_cache_path,
    generate_tts_file,
    html_to_text,
)

router = APIRouter(tags=["tts"])
logger = logging.getLogger(__name__)

storage = FileStorage(str(readings_cache_dir()))
service = ReadingsService(storage)

RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TTS_CACHE_DIR = Path(tts_cache_dir())
SECTION_ALIASES = {
    "gospel": "gospel",
    "evangelio": "gospel",
    "first": "first",
    "primera": "first",
    "lectura1": "first",
    "psalm": "psalm",
    "salmo": "psalm",
    "second": "second",
    "segunda": "second",
    "lectura2": "second",
    "all": "all",
}


def _validate_date_or_400(yyyy_mm_dd: str) -> None:
    if not RE_DATE.match(yyyy_mm_dd):
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    try:
        datetime.strptime(yyyy_mm_dd, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD") from exc


def _item_text(item: ReadingItem | None) -> str:
    if item is None:
        return ""
    return html_to_text(item.text)


def _normalize_section_or_400(section: str) -> str:
    normalized = SECTION_ALIASES.get(section.strip().lower())
    if not normalized:
        valid = "gospel, first, psalm, second, all"
        raise HTTPException(status_code=400, detail=f"Invalid section. Use one of: {valid}")
    return normalized


def _build_section_text(reading: DailyReadings, section: str) -> str:
    first_text = _item_text(reading.firstReading)
    psalm_text = _item_text(reading.psalm)
    gospel_text = _item_text(reading.gospel)
    second_text = _item_text(reading.secondReading)

    if section == "first":
        return first_text
    if section == "psalm":
        return psalm_text
    if section == "second":
        if not second_text:
            raise HTTPException(status_code=404, detail="Second reading not available for this date")
        return second_text
    if section == "gospel":
        return gospel_text

    # section == "all"
    blocks = [
        f"Primera lectura. {first_text}" if first_text else "",
        f"Salmo. {psalm_text}" if psalm_text else "",
        f"Segunda lectura. {second_text}" if second_text else "",
        f"Evangelio. {gospel_text}" if gospel_text else "",
    ]
    return " ".join(part for part in blocks if part).strip()


@router.get("/tts/date/{yyyy_mm_dd}")
@router.get("/api/v1/tts/date/{yyyy_mm_dd}", include_in_schema=False)
async def get_tts_by_date(
    yyyy_mm_dd: str,
    section: str = Query(default="gospel"),
    voice: str = Query(default=DEFAULT_VOICE),
    rate: float = Query(default=1.0, gt=0.1, le=3.0),
    format: Literal["mp3", "ogg"] = Query(default="mp3"),
):
    """
    TTS endpoint para reproducir lecturas desde frontend.

    Ejemplo:
    curl -L "http://localhost:8000/api/v1/tts/date/2026-02-27?section=gospel&voice=es-ES-AlvaroNeural&rate=1.0&format=mp3" --output evangelio.mp3
    """
    _validate_date_or_400(yyyy_mm_dd)
    normalized_section = _normalize_section_or_400(section)

    try:
        reading = service.get_by_date(yyyy_mm_dd)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Missing month file for {yyyy_mm_dd}")
    except KeyError:
        raise HTTPException(status_code=404, detail=f"{yyyy_mm_dd} not found")

    tts_text = _build_section_text(reading, normalized_section)
    if not tts_text:
        raise HTTPException(status_code=404, detail=f"No text available for section '{normalized_section}'")

    cache_path = build_cache_path(
        cache_dir=TTS_CACHE_DIR,
        date_str=yyyy_mm_dd,
        section=normalized_section,
        voice=voice,
        rate=rate,
        output_format=format,
    )

    if not (cache_path.exists() and cache_path.stat().st_size > 0):
        try:
            await generate_tts_file(
                text=tts_text,
                output_path=cache_path,
                voice=voice,
                rate=rate,
                output_format=format,
            )
        except TTSDependencyError as exc:
            logger.exception(
                "TTS dependency error for date=%s section=%s voice=%s rate=%s format=%s",
                yyyy_mm_dd,
                normalized_section,
                voice,
                rate,
                format,
            )
            raise HTTPException(status_code=503, detail=str(exc))
        except TTSGenerationError:
            logger.exception(
                "TTS generation error for date=%s section=%s voice=%s rate=%s format=%s",
                yyyy_mm_dd,
                normalized_section,
                voice,
                rate,
                format,
            )
            raise HTTPException(status_code=500, detail="TTS generation failed")
        except Exception:
            logger.exception(
                "TTS generation failed for date=%s section=%s voice=%s rate=%s format=%s",
                yyyy_mm_dd,
                normalized_section,
                voice,
                rate,
                format,
            )
            raise HTTPException(status_code=500, detail="TTS generation failed")

    media_type = "audio/mpeg" if format == "mp3" else "audio/ogg"
    return FileResponse(
        path=cache_path,
        media_type=media_type,
        filename=cache_path.name,
        headers={"Accept-Ranges": "bytes"},
    )
