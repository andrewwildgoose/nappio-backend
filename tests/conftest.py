"""
Shared test fixtures and app setup.

conftest.py is loaded by pytest before any test modules are collected, which
means we can patch external dependencies here and the patches will be in place
when the application modules are first imported.
"""
import os
import sys
from unittest.mock import MagicMock, patch
import pytest

# ---------------------------------------------------------------------------
# 1. Set dummy environment variables BEFORE any application code is imported.
# ---------------------------------------------------------------------------
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_dummy")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_dummy")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault("ADMIN_DASHBOARD_URL", "http://localhost:5173")
os.environ.setdefault("EMAIL_API_TOKEN", "test-email-token")

# ---------------------------------------------------------------------------
# 2. Replace the real Supabase client factory with a MagicMock so that
#    repository modules can be imported without a real Supabase project.
#    This must happen before any `repositories.*` module is imported.
# ---------------------------------------------------------------------------
_mock_supabase_client = MagicMock()

_supabase_module_mock = MagicMock()
_supabase_module_mock.get_supabase.return_value = _mock_supabase_client
_supabase_module_mock.get_supabase_service_role.return_value = _mock_supabase_client

sys.modules.setdefault("config.supabase", _supabase_module_mock)

# Patch the real module in-place so later imports (e.g. `from config.supabase
# import get_supabase`) also get the mock.
_get_supabase_patcher = patch("config.supabase.get_supabase", return_value=_mock_supabase_client)
_get_supabase_patcher.start()

# ---------------------------------------------------------------------------
# 3. Mock the mailersend / email_serv.email_processor module so tests don't
#    need a real email provider or a specific version of mailersend.
# ---------------------------------------------------------------------------
_mock_email_processor = MagicMock()
_mock_email_processor.send_confirmation_email.return_value = {"status": 200}
_mock_email_processor.send_newsletter_signup_to_team.return_value = {"status": 200}
sys.modules.setdefault("email_serv.email_processor", _mock_email_processor)

# Also mock mailersend itself in case it gets imported directly
_mock_mailersend = MagicMock()
_mock_mailersend.emails = MagicMock()
sys.modules.setdefault("mailersend", _mock_mailersend)
sys.modules.setdefault("mailersend.emails", _mock_mailersend.emails)


@pytest.fixture(autouse=True)
def reset_supabase_mock():
    """Reset call history on the shared Supabase mock between tests."""
    _mock_supabase_client.reset_mock()
    yield


@pytest.fixture
def mock_supabase():
    """Return the shared mock Supabase client."""
    return _mock_supabase_client
