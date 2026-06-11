from fastapi.testclient import TestClient
from nq_api.main import app

client = TestClient(app)

def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "4.1.0"
    # Freshness fields always present (None when Supabase unreachable)
    assert "score_cache_age_hours" in body
    assert "score_cache_rows" in body
    assert "demo_mode" in body

def test_cors_headers_present():
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
