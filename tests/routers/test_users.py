"""
Tests for the users router.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


MOCK_USER = MagicMock()
MOCK_USER.id = "user-123"


def _make_app():
    """Build a minimal FastAPI app with only the users router."""
    from fastapi import FastAPI
    from api.routers.users import router
    from api.dependencies.auth import get_authenticated_user
    app = FastAPI()
    app.dependency_overrides[get_authenticated_user] = lambda: MOCK_USER
    app.include_router(router)
    return app


@pytest.fixture
def client():
    return TestClient(_make_app())


class TestGetSubscriptions:
    def test_get_subscriptions_returns_list(self, client):
        """GET /api/v1/user/subscriptions returns subscription list."""
        with patch("api.routers.users.user_service.get_user_subscriptions", return_value=[]):
            response = client.get("/api/v1/user/subscriptions")
        assert response.status_code == 200
        assert response.json() == []


class TestGetAddresses:
    def test_get_addresses_returns_list(self, client):
        """GET /api/v1/user/addresses returns address list."""
        with patch("api.routers.users.user_service.get_user_addresses", return_value=[]):
            response = client.get("/api/v1/user/addresses")
        assert response.status_code == 200
        assert response.json() == []


class TestDeleteAddress:
    def test_delete_address_success(self, client):
        """DELETE /api/v1/user/addresses/{id} returns success message."""
        with patch("api.routers.users.user_service.delete_user_address", return_value=True):
            response = client.delete("/api/v1/user/addresses/00000000-0000-0000-0000-000000000001")
        assert response.status_code == 200
        assert response.json()["message"] == "Address deleted successfully"

    def test_delete_address_not_found(self, client):
        """DELETE /api/v1/user/addresses/{id} returns 404 when not found."""
        with patch("api.routers.users.user_service.delete_user_address", return_value=False):
            response = client.delete("/api/v1/user/addresses/00000000-0000-0000-0000-000000000001")
        assert response.status_code == 404
