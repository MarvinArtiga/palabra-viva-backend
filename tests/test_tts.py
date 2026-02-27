from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_tts_404_when_reading_not_found():
    r = client.get("/api/v1/tts/date/2099-01-01")
    assert r.status_code == 404


def test_tts_cache_reuses_existing_file(monkeypatch, tmp_path: Path):
    from app.api.v1 import tts as tts_router_module

    call_count = {"n": 0}
    cache_dir = tmp_path / "tts_cache"
    monkeypatch.setattr(tts_router_module, "TTS_CACHE_DIR", cache_dir)

    async def fake_generate_tts_file(text: str, output_path: Path, voice: str, rate: float, output_format: str):
        call_count["n"] += 1
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-audio")

    monkeypatch.setattr(tts_router_module, "generate_tts_file", fake_generate_tts_file)

    url = "/api/v1/tts/date/2026-02-23?section=gospel&format=mp3"
    r1 = client.get(url)
    r2 = client.get(url)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert call_count["n"] == 1


def test_tts_alias_duplicate_prefix_route(monkeypatch, tmp_path: Path):
    from app.api.v1 import tts as tts_router_module

    cache_dir = tmp_path / "tts_cache_alias"
    monkeypatch.setattr(tts_router_module, "TTS_CACHE_DIR", cache_dir)

    async def fake_generate_tts_file(text: str, output_path: Path, voice: str, rate: float, output_format: str):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-audio")

    monkeypatch.setattr(tts_router_module, "generate_tts_file", fake_generate_tts_file)

    r = client.get("/api/v1/api/v1/tts/date/2026-02-23?section=gospel&format=mp3")
    assert r.status_code == 200


def test_tts_dependency_error_returns_503(monkeypatch, tmp_path: Path):
    from app.api.v1 import tts as tts_router_module
    from app.services.tts_service import TTSDependencyError

    cache_dir = tmp_path / "tts_cache_dep"
    monkeypatch.setattr(tts_router_module, "TTS_CACHE_DIR", cache_dir)

    async def fake_generate_tts_file(text: str, output_path: Path, voice: str, rate: float, output_format: str):
        raise TTSDependencyError("edge-tts is not installed")

    monkeypatch.setattr(tts_router_module, "generate_tts_file", fake_generate_tts_file)

    r = client.get("/api/v1/tts/date/2026-02-23?section=gospel&format=mp3")
    assert r.status_code == 503
    assert "edge-tts is not installed" in r.text


def test_tts_invalid_section_returns_400():
    r = client.get("/api/v1/tts/date/2026-02-23?section=invalida&format=mp3")
    assert r.status_code == 400


def test_tts_section_alias_uses_normalized_cache(monkeypatch, tmp_path: Path):
    from app.api.v1 import tts as tts_router_module

    call_count = {"n": 0}
    cache_dir = tmp_path / "tts_cache_alias_norm"
    monkeypatch.setattr(tts_router_module, "TTS_CACHE_DIR", cache_dir)

    async def fake_generate_tts_file(text: str, output_path: Path, voice: str, rate: float, output_format: str):
        call_count["n"] += 1
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-audio")

    monkeypatch.setattr(tts_router_module, "generate_tts_file", fake_generate_tts_file)

    r1 = client.get("/api/v1/tts/date/2026-02-23?section=evangelio&format=mp3")
    r2 = client.get("/api/v1/tts/date/2026-02-23?section=gospel&format=mp3")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert call_count["n"] == 1
