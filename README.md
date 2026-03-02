# Palabra Viva Backend (FastAPI)

## Deploy rápido (Docker)

1. Construir imagen:

```bash
docker build -t palabra-viva-backend .
```

2. Ejecutar contenedor:

```bash
docker run --rm -p 8000:8000 \
  -e ALLOWED_ORIGINS="https://tu-app.vercel.app" \
  -e DATA_DIR="/app/data" \
  palabra-viva-backend
```

3. Verificar health:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/health
```

## Variables de entorno

- `ALLOWED_ORIGINS`: lista separada por comas de orígenes permitidos para CORS.
- `DATA_DIR`: directorio raíz para datos/caches (default `./data`).
  - cache de lecturas: `{DATA_DIR}/readings_cache`
  - cache de TTS: `{DATA_DIR}/tts_cache`
- `PORT`: puerto de Gunicorn/Uvicorn (default `8000`).
- `WEB_CONCURRENCY`: cantidad de workers (default `2`).

## GitHub Actions (prewarm)

El workflow `.github/workflows/prewarm.yml` usa el secret `BACKEND_BASE_URL`.

Para crearlo en GitHub:

1. Ir al repo en GitHub.
2. `Settings` -> `Secrets and variables` -> `Actions`.
3. Click en `New repository secret`.
4. Nombre: `BACKEND_BASE_URL`.
5. Valor ejemplo: `https://palabra-viva-backend.fly.dev`.
