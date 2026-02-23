from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_latest():
    r = client.get("/api/v1/readings/latest")
    assert r.status_code == 200
    data = r.json()
    assert "date" in data
    assert "gospel" in data
    assert r.headers.get("ETag")
    assert r.headers.get("Last-Modified")
    assert "Cache-Control" in r.headers


def test_month_ok():
    r = client.get("/api/v1/readings/month/2026-02")
    assert r.status_code == 200
    assert r.json()["month"] == "2026-02"


def test_month_bad_format():
    r = client.get("/api/v1/readings/month/2026_02")
    assert r.status_code == 400


def test_date_ok():
    r = client.get("/api/v1/readings/date/2026-02-23")
    assert r.status_code == 200
    assert r.json()["date"] == "2026-02-23"


def test_date_not_found():
    r = client.get("/api/v1/readings/date/2026-02-24")
    assert r.status_code == 404