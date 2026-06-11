"""bug-110 class regression: NaN/Inf in any JSON response must serialize as null,
never 500. Exercises the global NaNSanitizerMiddleware."""
import json

from fastapi.testclient import TestClient
from starlette.responses import Response

from nq_api.main import app


@app.get("/_test/nonfinite")
def _nonfinite_route():
    # json.dumps emits literal NaN/Infinity tokens by default — the exact
    # malformed body that used to 500 clients (bug 110).
    payload = json.dumps({"x": float("nan"), "y": [float("inf"), 1.5], "ok": "fine"})
    return Response(payload, media_type="application/json")


client = TestClient(app)


def test_nonfinite_floats_become_null():
    r = client.get("/_test/nonfinite")
    assert r.status_code == 200
    body = r.json()
    assert body["x"] is None
    assert body["y"] == [None, 1.5]
    assert body["ok"] == "fine"
