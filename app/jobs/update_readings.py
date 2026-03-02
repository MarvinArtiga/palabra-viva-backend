from __future__ import annotations

import json
import random
import re
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from app.core.paths import readings_cache_dir
from app.scraper.dominicos import candidate_urls_for_date, polite_get


# ---------------- IO ----------------

def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


# ---------------- Cookie/noise cleanup ----------------

COOKIE_TRASH = (
    "configuración de cookies",
    "usamos cookies",
    "política de cookies",
    "politica de cookies",
    "aceptar todo",
    "rechazar todo",
    "personalizar",
    "selecciona las cookies",
    "cookies técnicas",
    "cookies tecnicas",
    "cookies de análisis",
    "cookies de analisis",
    "cookies",
)


def _is_trash_line(line: str) -> bool:
    l = line.strip().lower()
    if not l:
        return True
    return any(t in l for t in COOKIE_TRASH)


def _clean_inline(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = re.sub(r"\s+", " ", text).strip()
    if _is_trash_line(t):
        return None
    if "aceptar todo" in t.lower():
        t = re.sub(r"(?i)\baceptar todo\b", "", t).strip(" -–—|")
        t = t.strip()
    return t or None


def _normalize_ws(text: str) -> str:
    lines = []
    for ln in text.splitlines():
        clean = re.sub(r"\s+", " ", ln).strip()
        if not clean:
            continue
        if _is_trash_line(clean):
            continue
        lines.append(clean)
    return "\n\n".join(lines)


# ---------------- Liturgical color (based on linksub3 text) ----------------
# Regla exacta: T.O -> verde, Cuaresma/Adviento -> morado, Pascua/Navidad -> blanco, Semana Santa -> rojo.


def _infer_liturgical_color(liturgical_name: Optional[str]) -> Optional[str]:
    if not liturgical_name:
        return None
    s = liturgical_name.lower()

    # Morado
    if "cuaresma" in s:
        return "morado"
    if "adviento" in s:
        return "morado"

    # Rojo (básico)
    if "semana santa" in s or "domingo de ramos" in s or "viernes santo" in s:
        return "rojo"

    # Blanco
    if "pascua" in s:
        return "blanco"
    if "navidad" in s:
        return "blanco"

    # Verde
    if "tiempo ordinario" in s or "t.o." in s or " t.o" in s:
        return "verde"

    return None


# ---------------- Reference normalization ----------------

BOOK_MAP = {
    "san mateo": "Mt",
    "mateo": "Mt",
    "san marcos": "Mc",
    "marcos": "Mc",
    "san lucas": "Lc",
    "lucas": "Lc",
    "san juan": "Jn",
    "juan": "Jn",
    "salmo": "Sal",
    "salmos": "Sal",
    "jonás": "Jon",
    "jonas": "Jon",
    "pedro": "Pe",
}

VERSES_RE = re.compile(r"(\d+\s*,\s*\d+(?:\s*[-–]\s*\d+)?|\b\d+\b)")


def _guess_book_abbrev(headline: str) -> Optional[str]:
    s = headline.lower()
    for k in sorted(BOOK_MAP.keys(), key=len, reverse=True):
        if k in s:
            return BOOK_MAP[k]
    return None


def _normalize_reference(headline: str, default_book: Optional[str] = None) -> Tuple[str, Optional[str]]:
    h = _clean_inline(headline) or ""
    if not h:
        return "", None

    book = _guess_book_abbrev(h) or default_book
    verses_match = VERSES_RE.findall(h)
    verses = verses_match[-1] if verses_match else ""

    hl = h.lower()
    if "pedro" in hl and ("primera" in hl or "1ª" in hl or "1a" in hl):
        book = "1 Pe"
    elif "pedro" in hl and ("segunda" in hl or "2ª" in hl or "2a" in hl):
        book = "2 Pe"

    if book and verses:
        verses = verses.replace("–", "-").replace(" - ", "-")
        return f"{book} {verses}".replace(" ,", ","), h

    return h, h


# ---------------- HTML parsing ----------------


def _find_h2_contains(soup: BeautifulSoup, needle: str):
    n = needle.lower()
    for h2 in soup.find_all("h2"):
        t = h2.get_text(" ", strip=True).lower()
        if n in t:
            return h2
    return None


def _collect_section_text(h2):
    h3 = h2.find_next("h3")
    head = h3.get_text(" ", strip=True) if h3 else ""
    head = _clean_inline(head) or ""

    parts = []
    node = h3 if h3 else h2
    while True:
        node = node.find_next_sibling()
        if node is None:
            break
        if getattr(node, "name", None) == "h2":
            break
        txt = node.get_text("\n", strip=True) if hasattr(node, "get_text") else ""
        if txt:
            parts.append(txt)

    return head, _normalize_ws("\n".join(parts))


def _debug_dump(url: str, html: str) -> None:
    soup = BeautifulSoup(html, "lxml")
    h2s = [h.get_text(" ", strip=True) for h in soup.find_all("h2")]
    print("\n--- DEBUG SCRAPER ---")
    print("URL:", url)
    print("H2 encontrados:", h2s[:30])
    print("Snippet:", soup.get_text("\n", strip=True)[:700])
    print("--- END DEBUG ---\n")


def _parse_page(url: str, html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")

    h2_first = _find_h2_contains(soup, "Primera lectura")
    h2_psalm = _find_h2_contains(soup, "Salmo")
    h2_gospel = _find_h2_contains(soup, "Evangelio del día")

    if not (h2_first and h2_psalm and h2_gospel):
        raise RuntimeError("No encuentro secciones (Primera/Salmo/Evangelio) en esta URL.")

    first_head, first_text = _collect_section_text(h2_first)
    ps_head, ps_text = _collect_section_text(h2_psalm)
    gos_head, gos_text = _collect_section_text(h2_gospel)

    first_ref, _ = _normalize_reference(first_head)
    ps_ref, _ = _normalize_reference(ps_head, default_book="Sal")
    gos_ref, _ = _normalize_reference(gos_head)

    # ✅ Liturgia real desde Dominicos: a.linksub3
    liturgical_name = None
    a = soup.select_one("a.linksub3")
    if a:
        liturgical_name = _clean_inline(a.get_text(" ", strip=True))

    # Opcional: si luego quieres título de celebración, lo sacamos con selector real (no regex de comillas)
    liturgical_title = None

    color = _infer_liturgical_color(liturgical_name)

    excerpt = ""
    if gos_text:
        excerpt = gos_text.split("\n\n")[0][:160]

    return {
        "liturgicalName": liturgical_name,
        "liturgicalTitle": liturgical_title,
        "liturgicalColor": color,
        "gospel": {"reference": gos_ref, "title": None, "excerpt": excerpt, "text": gos_text},
        "firstReading": {"reference": first_ref, "title": None, "text": first_text},
        "psalm": {"reference": ps_ref, "title": None, "text": ps_text},
        "secondReading": None,
    }


# ---------------- Job ----------------


def update_week(start: Optional[date] = None, days: int = 7) -> Dict[str, Any]:
    data_dir = readings_cache_dir()
    session = requests.Session()

    if start is None:
        start = date.today()

    updated = {"start": start.isoformat(), "fetched": 0, "saved_days": 0, "months_touched": []}

    for i in range(days):
        d = start + timedelta(days=i)

        if i > 0:
            time.sleep(1.5 + random.uniform(0.3, 1.2))

        parsed = None
        used_url = None
        last_error = None
        last_html = None
        last_url = None

        for url in candidate_urls_for_date(d):
            try:
                html = polite_get(url, session=session)
                parsed = _parse_page(url, html)
                used_url = url
                break
            except Exception as e:
                last_error = e
                last_html = html if "html" in locals() else None
                last_url = url

        if parsed is None:
            if last_html and last_url:
                _debug_dump(last_url, last_html)
            raise RuntimeError(f"No se pudo scrapear lecturas para {d.isoformat()}") from last_error

        daily = {"date": d.isoformat(), **parsed, "source": used_url}

        month_key = d.strftime("%Y-%m")
        month_path = data_dir / f"month-{month_key}.json"
        if month_path.exists():
            month_obj = json.loads(month_path.read_text(encoding="utf-8"))
        else:
            month_obj = {"month": month_key, "days": {}}

        month_obj.setdefault("days", {})
        month_obj["days"][d.isoformat()] = daily
        _atomic_write_json(month_path, month_obj)

        if month_key not in updated["months_touched"]:
            updated["months_touched"].append(month_key)

        if i == 0:
            _atomic_write_json(data_dir / "latest.json", daily)

        updated["fetched"] += 1
        updated["saved_days"] += 1

    return updated


if __name__ == "__main__":
    result = update_week()
    print(json.dumps(result, ensure_ascii=False, indent=2))
