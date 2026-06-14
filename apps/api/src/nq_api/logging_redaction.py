"""Scrub secrets and PII from log records before they are emitted."""
from __future__ import annotations

import logging
import re

_PATTERNS = [
    (re.compile(r"(apikey=)[A-Za-z0-9_\-]+", re.I), r"\1***"),
    (re.compile(r"(api[_-]?key\"?\s*[:=]\s*\"?)[A-Za-z0-9_\-]{8,}", re.I), r"\1***"),
    (re.compile(r"(token=)[A-Za-z0-9._\-]+", re.I), r"\1***"),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.I), r"\1***"),
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "***@***"),
]


def redact(text: str) -> str:
    for pat, repl in _PATTERNS:
        text = pat.sub(repl, text)
    return text


class RedactingFilter(logging.Filter):
    """Mutates each record's message in place so no handler emits a secret/PII."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            red = redact(msg)
            if red != msg:
                record.msg = red
                record.args = ()
        except Exception:
            pass
        return True


def install_log_redaction() -> None:
    """Attach the redaction filter to the root logger and all its handlers, and
    silence httpx/httpcore URL logging (which printed apikey= query strings)."""
    root = logging.getLogger()
    f = RedactingFilter()
    root.addFilter(f)
    for h in list(root.handlers):
        h.addFilter(f)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
