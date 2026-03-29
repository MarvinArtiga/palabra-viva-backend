# Guia Logica Completa - Palabra Viva Backend

## 1) Que problema resuelve este backend
Este backend expone una API de lecturas liturgicas y audio (TTS) para que el frontend pueda:
- consultar lecturas por fecha, mes, semana y ultima lectura,
- listar meses disponibles en archivo,
- reproducir audio generado desde el texto de las lecturas.

La idea central es:
1. tener datos JSON locales/cacheados para responder rapido,
2. actualizar esos datos con un scraper (`app/jobs/update_readings.py`),
3. generar audio bajo demanda y guardarlo en cache (`data/tts_cache`),
4. servir todo via FastAPI.

---

## 2) Arquitectura mental (de extremo a extremo)

### Flujo de lecturas (texto)
1. Cliente (frontend) llama `GET /api/v1/readings/...`.
2. Router en `app/api/v1/readings.py` valida formato de fecha.
3. `ReadingsService` busca JSON en disco usando `FileStorage`.
4. Respuesta JSON vuelve al frontend con headers de cache (`ETag`, `Last-Modified`, `Cache-Control`).

### Flujo de audio TTS
1. Cliente llama `GET /api/v1/tts/date/{fecha}?section=gospel...`.
2. Endpoint busca el texto de esa lectura.
3. Construye ruta de cache de audio (nombre deterministico por fecha+seccion+voz+rate+formato).
4. Si ya existe archivo, lo reutiliza.
5. Si no existe, lo genera con `edge-tts` (y `ffmpeg` si pides `ogg`).
6. Devuelve `FileResponse` para streaming/descarga.

### Flujo de actualizacion de datos
1. Job `app/jobs/update_readings.py` scrapea Dominicos por dias.
2. Limpia/normaliza texto, referencias y color liturgico.
3. Guarda/actualiza `month-YYYY-MM.json`.
4. Guarda `latest.json` con el primer dia procesado.

---

## 3) Estructura de carpetas y por que existe cache

## `app/`
Codigo fuente de la API.

## `app/data/`
Datos semilla que vienen dentro del repositorio/imagen Docker (`latest.json`, `month-*.json`).

## `data/`
Datos persistentes en runtime (fuera del codigo):
- `data/readings_cache` -> cache real de lecturas JSON
- `data/tts_cache` -> mp3/ogg generados

Separar `app/data` (semilla) de `data/` (runtime) evita perder cache al redeploy y permite volumen persistente en Fly (`/app/data`).

---

## 4) Explicacion archivo por archivo

## Raiz del proyecto

### `requirements.txt`
Dependencias Python del proyecto (`fastapi`, `uvicorn`, `gunicorn`, `requests`, `beautifulsoup4`, `edge-tts`, `pytest`, etc).

### `README.md`
Guia de deploy rapido (Docker), variables de entorno y secret para prewarm.

### `Dockerfile`
- Usa `python:3.11-slim`.
- Instala dependencias.
- Copia codigo `app/`.
- Crea `/app/data/readings_cache` y `/app/data/tts_cache`.
- Copia semilla desde `app/data` hacia `/app/data/readings_cache`.
- Arranca con Gunicorn + Uvicorn worker.

### `fly.toml`
Config de despliegue en Fly.io:
- `DATA_DIR=/app/data`
- mount persistente `data -> /app/data`
- servicio HTTP en puerto 8000.

### `.github/workflows/prewarm.yml`
Workflow semanal/manual que:
1. valida secret `BACKEND_BASE_URL`,
2. calcula fecha UTC actual,
3. llama `/api/v1/readings/week/{today}` para conocer dias,
4. llama TTS para cada dia (`gospel` y `psalm`) y precalienta cache.

Objetivo: reducir latencia y evitar primer request lento en frontend.

### `.gitignore`
Ignora artefactos locales: `.venv`, `__pycache__`, `.pytest_cache`, etc.

### `.dockerignore`
Evita meter al build Docker cosas innecesarias (`.git`, `.venv`, `tests`, caches).

---

## `app/main.py`
Punto de entrada FastAPI:
- configura logging,
- crea app y CORS,
- asegura carpetas de cache al boot (`ensure_cache_dirs`),
- si no hay cache de lecturas, copia semilla (`seed_readings_cache_if_empty`),
- expone `/health`,
- handlers globales de excepcion (HTTP y generales),
- monta router v1 con prefijo `/api/v1`.

## `app/core/config.py`
Configuracion central via `pydantic-settings`:
- `DATA_DIR`,
- `ALLOWED_ORIGINS`,
- `api_prefix`.
Tambien convierte `ALLOWED_ORIGINS` (string CSV) a lista usable por CORS.

## `app/core/paths.py`
Gestion de rutas fisicas:
- `data_dir()`, `readings_cache_dir()`, `tts_cache_dir()`,
- crea carpetas si no existen,
- si cache de lecturas esta vacio, copia seed desde `app/data`.

## `app/core/cache.py`
Helpers HTTP cache:
- `etag_for_file(path)` -> hash SHA-256 del archivo,
- `last_modified_http(stat)` -> formato HTTP para `Last-Modified`.

## `app/models/readings.py`
Modelos Pydantic de dominio:
- `ReadingItem`,
- `DailyReadings`.
Sirve para validar estructura de lecturas al cargar JSON.

## `app/services/storage.py`
Capa minima de acceso a archivos:
- leer JSON (`read_json`),
- obtener `stat`,
- resolver `path`.

## `app/services/readings_service.py`
Logica de negocio de lecturas:
- `get_latest`,
- `get_month`,
- `get_by_date`,
- `list_months`.

## `app/services/tts_service.py`
Logica TTS reusable:
- limpiar HTML a texto (`html_to_text`),
- construir nombre/ruta de cache (`build_cache_path`),
- generar audio con `edge-tts`,
- conversion opcional a `ogg` via `ffmpeg`.

## `app/scraper/dominicos.py`
Utilidades del scraper:
- URLs candidatas por fecha (evangelio/homilia),
- `polite_get` con retries + backoff.

## `app/jobs/update_readings.py`
Job de scraping y guardado:
- parsea HTML con BeautifulSoup,
- limpia ruido/cookies,
- normaliza referencias biblicas,
- infiere color liturgico,
- guarda de forma atomica en JSON,
- actualiza `month-*.json` y `latest.json`.

Se ejecuta manualmente como script:
`python -m app.jobs.update_readings`

## `app/api/v1/router.py`
Router agregador que incluye subrouters.

## `app/api/v1/health.py`
`GET /api/v1/health`.

## `app/api/v1/readings.py`
Endpoints:
- `GET /readings/latest`
- `GET /readings/month/{YYYY-MM}`
- `GET /readings/date/{YYYY-MM-DD}`
Valida formato y agrega headers HTTP cache.

## `app/api/v1/week.py`
`GET /readings/week/{YYYY-MM-DD}`:
- calcula lunes de esa semana,
- devuelve siempre 7 dias (lun->dom).

## `app/api/v1/archive.py`
`GET /archive/months` para listar meses disponibles.

## `app/api/v1/tts.py`
`GET /tts/date/{YYYY-MM-DD}`:
- valida fecha/seccion,
- obtiene texto segun seccion (`first`, `psalm`, `gospel`, `second`, `all`),
- normaliza alias de seccion (`evangelio`, `salmo`, etc),
- reutiliza o genera audio,
- devuelve archivo mp3/ogg.

Incluye ruta alias `"/api/v1/tts/date/{...}"` dentro del mismo router (compatibilidad hacia atras), por eso en tests aparece `/api/v1/api/v1/...`.

## `app/data/latest.json`
Ultima lectura disponible (snapshot diario).

## `app/data/month-2026-02.json`, `app/data/month-2026-03.json`
Meses de ejemplo/semilla con estructura:
```json
{
  "month": "2026-03",
  "days": {
    "2026-03-01": { "...": "DailyReadings" }
  }
}
```

## `data/tts_cache/*.mp3`
Audios ya generados (cache runtime).

## `tests/conftest.py`
Setea variables de entorno de test (`DATA_DIR`, `ALLOWED_ORIGINS`).

## `tests/test_health.py`
Pruebas de salud (`/health` y `/api/v1/health`).

## `tests/test_readings.py`
Pruebas de lecturas (ok, formato invalido, no encontrado, headers cache).

## `tests/test_archive.py`
Prueba de listado de meses.

## `tests/test_tts.py`
Pruebas TTS:
- 404 cuando no hay lectura,
- reuse de cache,
- alias de ruta,
- manejo de errores dependencia,
- alias de secciones.

## `__init__.py` (varios)
Estan vacios en este repo, pero su funcion es marcar directorios como paquetes Python importables (`app`, `app.api`, etc).

### Para que sirve `__init__.py`
- permitir imports estables (`from app.services...`),
- inicializar paquete (si agregas codigo adentro),
- controlar exportaciones (`__all__`) en paquetes mas grandes.

### Cuando usarlo
- casi siempre en carpetas que quieres tratar como paquete Python,
- especialmente si compartes codigo entre modulos.

---

## 5) Por que hay cache en carpetas

### Cache de lecturas (`readings_cache`)
Evita scrapear en cada request. El backend responde JSON desde disco local.

### Cache de audio (`tts_cache`)
Generar TTS cuesta tiempo. Se guarda el archivo una vez y se reutiliza.

### Beneficios
- menor latencia,
- menos carga a servicios externos,
- menos costo computacional,
- mas estabilidad para frontend.

---

## 6) `.venv`: que es, como crearlo y usarlo

`.venv` es un entorno virtual Python local del proyecto. Aisla dependencias para que no choquen con otros proyectos.

### Crear
```bash
python3 -m venv .venv
```

### Activar (Linux/macOS)
```bash
source .venv/bin/activate
```

### Instalar dependencias
```bash
pip install -r requirements.txt
```

### Ejecutar API
```bash
uvicorn app.main:app --reload --port 8000
```

### Ejecutar tests
```bash
pytest -q
```

### Salir del venv
```bash
deactivate
```

---

## 7) Como consumirlo desde frontend

## Lecturas
```ts
const res = await fetch("http://localhost:8000/api/v1/readings/date/2026-03-02");
const data = await res.json();
```

## Semana completa (sidebar calendario)
```ts
const res = await fetch("http://localhost:8000/api/v1/readings/week/2026-03-02");
const week = await res.json(); // week.days tiene 7 elementos
```

## Audio TTS (reproducir en `<audio>`)
```ts
const res = await fetch("http://localhost:8000/api/v1/tts/date/2026-03-02?section=gospel&rate=1.0&format=mp3");
const blob = await res.blob();
const url = URL.createObjectURL(blob);
audioElement.src = url;
audioElement.play();
```

### CORS
Si frontend esta en otro dominio/puerto, agrega su origen en `ALLOWED_ORIGINS`.
Ejemplo:
`ALLOWED_ORIGINS="http://localhost:5173,https://tu-frontend.vercel.app"`

---

## 8) Como replicar el proyecto desde cero (paso a paso)
1. Clonar repo.
2. Crear y activar `.venv`.
3. Instalar `requirements.txt`.
4. Exportar variables:
   - `DATA_DIR=./data`
   - `ALLOWED_ORIGINS=http://localhost:5173`
5. Ejecutar API con `uvicorn`.
6. Probar endpoints health/readings/tts.
7. (Opcional) correr `python -m app.jobs.update_readings` para refrescar lecturas.
8. Correr tests con `pytest`.
9. Para produccion, usar Docker/Fly y volumen persistente en `/app/data`.

---

## 9) Detalles importantes para entender la logica de diseno
- El backend es file-based (JSON en disco), no DB.
- `ReadingsService` desacopla negocio de transporte HTTP.
- `FileStorage` desacopla lectura de archivos del resto.
- `ETag` y `Last-Modified` ayudan a cache HTTP del lado cliente/CDN.
- TTS esta pensado para ser idempotente: misma entrada, mismo archivo cache.
- El workflow prewarm precalienta semana + audio para evitar cold-start de experiencia.

---

## 10) Mejoras futuras (si quieres escalar)
1. Agregar base de datos para historico/versionado.
2. Invalidacion de cache mas fina (por fecha/seccion).
3. Colas para TTS async (Redis/Celery).
4. Observabilidad (metrics/tracing).
5. Job programado server-side para `update_readings`.

