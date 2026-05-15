"""Server-Sent Events (SSE) helpers for streaming query responses."""
import json as _json

from nq_api.services.constants import _PHASE_LABELS


def _sse_event(data: dict | str) -> str:
    """Format a dict or string as an SSE data event line."""
    if isinstance(data, str):
        return f"data: {data}\n\n"
    return f"data: {_json.dumps(data)}\n\n"


def sse_phase(phase: str) -> str:
    """Emit an SSE phase transition event."""
    return _sse_event({
        "status": "phase",
        "phase": phase,
        "label": _PHASE_LABELS.get(phase, phase),
    })


def sse_done(result: dict) -> str:
    """Emit a done event with the final result."""
    return _sse_event({
        "status": "done",
        "result": result,
    })


def sse_ping() -> str:
    """Emit a keep-alive ping."""
    return 'data: {"status":"running"}\n\n'


def sse_done_marker() -> str:
    """Emit the SSE stream termination marker."""
    return "data: [DONE]\n\n"
