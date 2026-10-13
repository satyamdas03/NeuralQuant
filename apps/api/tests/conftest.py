import os
import pytest
from unittest.mock import patch

os.environ["ENVIRONMENT"] = "development"


@pytest.fixture(autouse=True, scope="session")
def patch_prewarm():
    """Disable cache prewarm — it does real network I/O and hangs tests."""
    with patch("nq_api.data_builder.prewarm_cache"):
        yield


@pytest.fixture(autouse=True, scope="session")
def override_auth():
    """Bypass Supabase auth in all tests.

    The override functions must accept the same keyword args as the real
    dependencies, because require_admin_or_cron calls get_current_user()
    directly with an authorization argument.
    """
    from nq_api.main import app
    from nq_api.auth.deps import get_current_user, require_admin_or_cron
    from nq_api.auth.models import User

    test_user = User(
        id="test-user-123", email="test@test.com", tier="pro"
    )

    def fake_current_user(authorization: str | None = None):
        return test_user

    def fake_admin_or_cron(authorization: str | None = None):
        return test_user

    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[require_admin_or_cron] = fake_admin_or_cron
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_admin_or_cron, None)
