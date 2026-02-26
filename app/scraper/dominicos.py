from __future__ import annotations

import random
import time
from datetime import date
from typing import List

import requests

BASE = "https://www.dominicos.org"
TODAY_URL = f"{BASE}/predicacion/evangelio-del-dia/hoy/"


def candidate_urls_for_date(d: date) -> List[str]:
    """
    - Entre semana: /predicacion/evangelio-del-dia/{d-m-y}/
    - Domingos/festivos: /predicacion/homilia/{d-m-y}/lecturas/
    """
    evangelio = f"{BASE}/predicacion/evangelio-del-dia/{d.day}-{d.month}-{d.year}/"
    homilia_lecturas = f"{BASE}/predicacion/homilia/{d.day}-{d.month}-{d.year}/lecturas/"
    return [evangelio, homilia_lecturas]


def polite_get(url: str, session: requests.Session, timeout: int = 25) -> str:
    headers = {
        "User-Agent": "PalabraVivaBot/1.0 (contact: github.com/tuuser) requests",
        "Accept-Language": "es-ES,es;q=0.9",
    }

    last_exc = None
    for attempt in range(3):
        try:
            r = session.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r.text
        except Exception as e:
            last_exc = e
            time.sleep((1.5 * (2 ** attempt)) + random.uniform(0.2, 0.8))
    raise last_exc