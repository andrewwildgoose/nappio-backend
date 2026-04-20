"""
Tests for the payments router.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


MOCK_USER = MagicMock()
MOCK_USER.id = "user-123"
MOCK_USER.email = "user@example.com"


def _make_app():
    """Build a minimal FastAPI app with only the payments router."""
    from fastapi import FastAPI
    from api.routers.payments import router
    from api.dependencies.auth import get_authenticated_user
    app = FastAPI()
    app.dependency_overrides[get_authenticated_user] = lambda: MOCK_USER
    app.include_router(router)
    return app


@pytest.fixture
def client():
    return TestClient(_make_app())


class TestGetPaymentDetails:
    def test_get_payment_details_success(self, client):
        """POST /api/v1/payments/details returns payment info."""
        mock_response = MagicMock()
        mock_response.amount_total = 1000
        mock_response.customer_email = "user@example.com"
        mock_response.checkout_type = "start_up"

        with patch("api.routers.payments.pa.get_payment_completed_details", return_value=mock_response):
            response = client.post(
                "/api/v1/payments/details",
                json={"session_id": "cs_test_123"},
            )
        assert response.status_code == 200
