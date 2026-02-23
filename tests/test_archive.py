from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_archive_months():
    r = client.get("/api/v1/archive/months")
    assert r.status_code == 200
    assert "months" in r.json()