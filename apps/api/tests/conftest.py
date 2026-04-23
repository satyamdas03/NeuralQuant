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
    """Bypass Supabase auth in all tests."""
    from nq_api.main import app
    from nq_api.auth.deps import get_current_user
    from nq_api.auth.models import User

    app.dependency_overrides[get_current_user] = lambda: User(
        id="test-user-123", email="test@test.com", tier="pro"
    )
    yield
    app.dependency_overrides.pop(get_current_user, None)
