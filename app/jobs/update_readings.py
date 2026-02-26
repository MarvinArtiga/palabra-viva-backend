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

from app.core.config import settings
from app.scraper.dominicos import TODAY_URL, candidate_urls_for_date, polite_get


# --- Helpers IO -------------------------------------------------------------

def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _normalize_ws(text: str) -> str:
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n\n".join(lines)


# --- Reference normalization (para que no se vea feo) -----------------------

BOOK_MAP = {
    # Evangelios
    "mateo": "Mt",
    "san mateo": "Mt",
    "marcos": "Mc",
    "san marcos": "Mc",
    "lucas": "Lc",
    "san lucas": "Lc",
    "juan": "Jn",
    "san juan": "Jn",

    # Salmos
    "salmo": "Sal",
    "salmos": "Sal",

    # Cartas comunes (puedes ir ampliando)
    "corintios": "Co",
    "romanos": "Rm",
    "hebreos": "Hb",
    "santiago": "St",
    "pedro": "Pe",
    "timoteo": "Tm",
    "tito": "Tit",
    "filipenses": "Flp",
    "efesios": "Ef",
    "colosenses": "Col",
    "tesalonicenses": "Ts",
    "gálatas": "Ga",

    # AT básico (ampliable)
    "genesis": "Gn",
    "éxodo": "Ex",
    "exodo": "Ex",
    "levítico": "Lv",
    "numeros": "Nm",
    "deuteronomio": "Dt",
    "isaías": "Is",
    "isaias": "Is",
    "jeremías": "Jr",
    "jeremias": "Jr",
    "ezequiel": "Ez",
    "daniel": "Dn",
    "proverbios": "Pr",
    "sabiduría": "Sab",
    "sabiduria": "Sab",
}

# Encuentra la parte tipo "16, 13-19" o "5, 1-4" o "22"
VERSES_RE = re.compile(r"(\d+\s*,\s*\d+(?:\s*[-–]\s*\d+)?|\b\d+\b)")


def _guess_book_abbrev(headline: str) -> Optional[str]:
    s = headline.lower()
    # Busca por claves largas primero (san mateo antes de mateo)
    for k in sorted(BOOK_MAP.keys(), key=len, reverse=True):
        if k in s:
            return BOOK_MAP[k]
    return None


def _normalize_reference(headline: str, default_book: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """
    headline típico Dominicos:
      "Lectura del santo evangelio según san Mateo 16, 13-19"
      "Salmo 22"
      "Lectura de la primera carta del apóstol san Pedro 5, 1-4"

    Devuelve:
      reference_short: "Mt 16, 13-19" o "Sal 22" o "1 Pe 5, 1-4" (aprox)
      title_clean: el headline original (o una versión más humana si quieres)
    """
    h = " ".join(headline.split()).strip()
    if not h:
        return "", None

    book = _guess_book_abbrev(h) or default_book
    verses_match = VERSES_RE.findall(h)
    verses = verses_match[-1] if verses_match else ""

    # Manejo especial de “primera/segunda carta ... Pedro” etc.
    # Si aparece "primera" y "pedro" -> "1 Pe"
    hl = h.lower()
    if "pedro" in hl and ("primera" in hl or "1ª" in hl or "1a" in hl):
        book = "1 Pe"
    elif "pedro" in hl and ("segunda" in hl or "2ª" in hl or "2a" in hl):
        book = "2 Pe"

    if book and verses:
        # Normaliza guión largo
        verses = verses.replace("–", "-").replace(" - ", "-")
        return f"{book} {verses}".replace(" ,", ","), h

    # Fallback: si no pudo, al menos devuelve el headline (para no romper)
    return h, h


# --- HTML parsing -----------------------------------------------------------

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
    h2_psalm = _find_h2_contains(soup, "Salmo")            # “Salmo de hoy” también entra
    h2_gospel = _find_h2_contains(soup, "Evangelio del día")

    if not (h2_first and h2_psalm and h2_gospel):
        _debug_dump(url, html)
        raise RuntimeError("No encuentro secciones (Primera/Salmo/Evangelio) en esta URL.")

    first_head, first_text = _collect_section_text(h2_first)
    ps_head, ps_text = _collect_section_text(h2_psalm)
    gos_head, gos_text = _collect_section_text(h2_gospel)

    # Normaliza referencias cortas (para que el UI quede bonito)
    first_ref, _ = _normalize_reference(first_head)
    ps_ref, _ = _normalize_reference(ps_head, default_book="Sal")
    gos_ref, _ = _normalize_reference(gos_head)

    # Liturgia (best-effort)
    liturgical_name = None
    h1 = soup.find("h1")
    if h1:
        a = h1.find_next("a")
        if a:
            liturgical_name = a.get_text(" ", strip=True)

    liturgical_title = None
    full_text = soup.get_text("\n", strip=True)
    m = re.search(r"“\s*(.*?)\s*”", full_text)
    if m:
        liturgical_title = m.group(1)

    excerpt = (gos_text.split("\n\n")[0][:160] if gos_text else "")

    return {
        "liturgicalName": liturgical_name,
        "liturgicalTitle": liturgical_title,
        "liturgicalColor": None,
        "gospel": {"reference": gos_ref, "title": None, "excerpt": excerpt, "text": gos_text},
        "firstReading": {"reference": first_ref, "title": None, "text": first_text},
        "psalm": {"reference": ps_ref, "title": None, "text": ps_text},
        "secondReading": None,
    }


# --- “Hoy” correcto: usar canonical URL de /hoy/ ----------------------------

DATE_FROM_URL_RE = re.compile(r"/(\d{1,2})-(\d{1,2})-(\d{4})/")


def _start_date_from_today_page(session: requests.Session) -> date:
    """
    Método robusto:
    - Abre /hoy/
    - Lee <link rel="canonical" href=".../24-2-2026/">
    - Extrae la fecha desde esa URL
    """
    html = polite_get(TODAY_URL, session=session)
    soup = BeautifulSoup(html, "lxml")

    canonical = soup.find("link", rel="canonical")
    href = canonical.get("href") if canonical else None

    if not href:
        # fallback a og:url si no hay canonical
        og = soup.find("meta", attrs={"property": "og:url"})
        href = og.get("content") if og else None

    if href:
        m = DATE_FROM_URL_RE.search(href)
        if m:
            d = int(m.group(1))
            mo = int(m.group(2))
            y = int(m.group(3))
            return date(y, mo, d)

    # último fallback: reloj local
    return date.today()


# --- Job principal ----------------------------------------------------------

def update_week(start: Optional[date] = None, days: int = 7) -> Dict[str, Any]:
    data_dir = Path(settings.data_dir)
    session = requests.Session()

    if start is None:
        start = _start_date_from_today_page(session)

    updated = {"start": start.isoformat(), "fetched": 0, "saved_days": 0, "months_touched": []}

    for i in range(days):
        d = start + timedelta(days=i)

        if i > 0:
            time.sleep(1.5 + random.uniform(0.3, 1.2))

        parsed = None
        used_url = None
        last_error = None

        for url in candidate_urls_for_date(d):
            try:
                html = polite_get(url, session=session)
                parsed = _parse_page(url, html)
                used_url = url
                break
            except Exception as e:
                last_error = e

        if parsed is None:
            raise RuntimeError(f"No se pudo scrapear lecturas para {d.isoformat()}") from last_error

        daily = {
            "date": d.isoformat(),
            **parsed,
            "source": used_url,  # opcional, útil para debug/transparencia
        }

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