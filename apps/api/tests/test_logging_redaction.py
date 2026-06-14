import logging
from nq_api.logging_redaction import redact, RedactingFilter


def test_redacts_apikey_query():
    assert redact("GET https://x.com/q?symbol=AAPL&apikey=pBgk4hR1ikd8c1llnvNhR7gKjafv8Fn2") \
        == "GET https://x.com/q?symbol=AAPL&apikey=***"


def test_redacts_bearer():
    assert redact("Authorization: Bearer eyJhbG.cit.zzz") == "Authorization: Bearer ***"


def test_redacts_email():
    assert "***@***" in redact("user satyamdas03@gmail.com logged in")


def test_clean_text_unchanged():
    assert redact("nothing secret here") == "nothing secret here"


def test_filter_mutates_record():
    f = RedactingFilter()
    rec = logging.LogRecord("n", logging.INFO, __file__, 1,
                            "key apikey=SECRETVALUE1234567890", None, None)
    assert f.filter(rec) is True
    assert "SECRETVALUE1234567890" not in rec.getMessage()
