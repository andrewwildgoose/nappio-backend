"""
Tests for the newsletter router.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def _make_app():
    """Build a minimal FastAPI app with only the newsletter router."""
    from fastapi import FastAPI
    from api.routers.newsletter import router
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client():
    return TestClient(_make_app())


class TestSubscribeEndpoint:
    def test_subscribe_success(self, client):
        """POST /api/v1/newsletter/subscribe returns 200 on success."""
        mock_result = {
            "id": "00000000-0000-0000-0000-000000000001",
            "first_name": "Alice",
            "email": "alice@example.com",
            "postcode": "SW1",
            "subscribed_at": "2024-01-01T00:00:00",
            "email_verified": False,
        }
        with patch("api.routers.newsletter.subscribe", return_value=mock_result):
            response = client.post(
                "/api/v1/newsletter/subscribe",
                json={"first_name": "Alice", "email": "alice@example.com", "postcode": "SW1"},
            )
        assert response.status_code == 200
        assert response.json()["email"] == "alice@example.com"

    def test_subscribe_duplicate_email_returns_400(self, client):
        """POST /api/v1/newsletter/subscribe returns 400 for duplicate email."""
        with patch("api.routers.newsletter.subscribe", side_effect=ValueError("Email already subscribed")):
            response = client.post(
                "/api/v1/newsletter/subscribe",
                json={"first_name": "Alice", "email": "alice@example.com"},
            )
        assert response.status_code == 400
        assert "already subscribed" in response.json()["detail"]

    def test_subscribe_server_error_returns_500(self, client):
        """POST /api/v1/newsletter/subscribe returns 500 on unexpected error."""
        with patch("api.routers.newsletter.subscribe", side_effect=Exception("db error")):
            response = client.post(
                "/api/v1/newsletter/subscribe",
                json={"first_name": "Alice", "email": "alice@example.com"},
            )
        assert response.status_code == 500


class TestVerifyEndpoint:
    def test_verify_success(self, client):
        """POST /api/v1/newsletter/verify returns 200 when verified."""
        with patch("api.routers.newsletter.verify_email", return_value=True):
            response = client.post(
                "/api/v1/newsletter/verify",
                json={"email": "alice@example.com"},
            )
        assert response.status_code == 200
        assert "verified successfully" in response.json()["message"]

    def test_verify_not_found_returns_404(self, client):
        """POST /api/v1/newsletter/verify returns 404 when subscriber not found."""
        with patch("api.routers.newsletter.verify_email", return_value=False):
            response = client.post(
                "/api/v1/newsletter/verify",
                json={"email": "notfound@example.com"},
            )
        assert response.status_code == 404
