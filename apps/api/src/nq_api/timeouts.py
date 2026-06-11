"""Canonical timeout registry. Values are the FINAL tuned values from Sessions
8-81 — do not lower any of these; every one was raised after a production failure.

Some subsystems keep their values inline (with comments) because they are
runtime-conditional; this module is the authoritative map of what the values
are and where they live. New code should import from here.

Live sites:
  PARA-DEBATE agents .... agents/orchestrator.py (runtime @property, Ollama-aware)
  Ask AI streaming ...... routes/query.py (90s LLM guard, 25s inner enrichment, 30s SSE)
  OpenBB proxy .......... routes/terminal.py (httpx connect/read split, bug 67)
  yfinance gateway ...... packages/data/.../yf_guard.py (YF_TIMEOUT_S)
"""

LLM_CLIENT_S        = 120   # bug 19 — Anthropic default was infinite
AGENT_SPECIALIST_S  = 55    # bug 4 (60 when Ollama)
AGENT_ADVERSARIAL_S = 45    # bug 4
AGENT_HEAD_S        = 75    # head analyst synthesis
ENRICHMENT_S        = 45    # bugs 88, 102 — 25s/22s were too short for IN stocks
ASKAI_LLM_GUARD_S   = 90    # routes/query.py — prevents indefinite LLM hangs
ASKAI_FOLLOWUP_S    = 120   # bug 16
YF_CALL_S           = 20    # bug 42
OPENBB_CONNECT_S    = 10    # bug 67 — fast cold-start detection
OPENBB_READ_S       = 60    # bug 67
OPENBB_WARMUP_S     = 90    # bug 67
