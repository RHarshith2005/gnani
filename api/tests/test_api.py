from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app


def test_health_reports_capabilities_without_secrets():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["capabilities"]["stt"] in {"gnani", "browser"}
        serialised = str(body).lower()
        assert "api_key" not in serialised
        assert "supabase_service_key" not in serialised


def test_vendors_do_not_leak_floor_prices():
    with TestClient(app) as client:
        response = client.get("/api/vendors")
        assert response.status_code == 200
        vendors = response.json()["vendors"]
        assert len(vendors) == 3
        for vendor in vendors:
            assert "floor_price" not in vendor
            assert "open_price" not in vendor


def test_unknown_session_has_no_events():
    with TestClient(app) as client:
        response = client.get("/api/sessions/does-not-exist/events")
        assert response.status_code == 404


def test_sessions_list_is_available():
    with TestClient(app) as client:
        response = client.get("/api/sessions")
        assert response.status_code == 200
        assert isinstance(response.json()["sessions"], list)
