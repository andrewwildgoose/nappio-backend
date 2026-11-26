"""
Tests for X-API-Key protection applied to routers in api/main.py.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

FRONTEND_KEY = "test-frontend-key"
ADMIN_KEY = "test-admin-key"

NEWSLETTER = ("post", "/api/v1/newsletter/verify", {"json": {"email": "a@example.com"}})
SERVICE_AREAS = ("get", "/api/v1/service/service-areas", {})
ADMIN_PROGRESS = ("get", "/api/v1/admin/subscription-progress", {})


@pytest.fixture
def client():
    from api.main import app
    return TestClient(app)


def _call(client, endpoint, key=None):
    method, path, kwargs = endpoint
    headers = {"X-API-Key": key} if key is not None else {}
    return getattr(client, method)(path, headers=headers, **kwargs)


def test_health_check_is_open(client):
    assert client.get("/").status_code == 200


@pytest.mark.parametrize("endpoint", [NEWSLETTER, SERVICE_AREAS, ADMIN_PROGRESS])
@pytest.mark.parametrize("key", [None, "", "wrong-key"])
def test_missing_or_wrong_key_rejected(client, endpoint, key):
    assert _call(client, endpoint, key).status_code == 401


def test_frontend_key_cannot_reach_admin(client):
    assert _call(client, ADMIN_PROGRESS, FRONTEND_KEY).status_code == 401


def test_admin_key_cannot_reach_frontend_routes(client):
    assert _call(client, NEWSLETTER, ADMIN_KEY).status_code == 401


def test_frontend_key_allowed(client):
    with patch("api.routers.newsletter.verify_email", return_value=True):
        response = _call(client, NEWSLETTER, FRONTEND_KEY)
    assert response.status_code == 200


def test_admin_key_allowed(client):
    with patch("api.routers.admin.get_all_subscription_progress", return_value=[]):
        response = _call(client, ADMIN_PROGRESS, ADMIN_KEY)
    assert response.status_code == 200


def test_unset_key_fails_closed(client, monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEY")
    assert _call(client, ADMIN_PROGRESS, "").status_code == 401
    assert _call(client, ADMIN_PROGRESS, ADMIN_KEY).status_code == 401


def test_webhook_does_not_require_api_key(client):
    # No API key: should fail on the Stripe signature check, not with 401
    response = client.post("/api/v1/webhooks/stripe", content=b"{}")
    assert response.status_code != 401


def test_docs_disabled_outside_development(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
