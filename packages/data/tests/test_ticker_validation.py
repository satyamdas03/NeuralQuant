from nq_data.ticker_validation import is_valid_ticker


def test_valid_us_tickers():
    for t in ("AAPL", "MSFT", "NVDA", "BRK.B"):
        assert is_valid_ticker(t), t


def test_valid_long_nse_tickers():
    """Bug: old quantfactor_sync copy rejected len > 8, dropping these."""
    for t in ("HINDUNILVR", "BAJFINANCE", "ADANIPORTS", "TATACONSUM",
              "APOLLOHOSP", "ICICIPRULI"):
        assert is_valid_ticker(t), t


def test_valid_nse_specials():
    for t in ("M&M", "BAJAJ-AUTO", "L&TFH"):
        assert is_valid_ticker(t), t


def test_suffixed_input_accepted():
    assert is_valid_ticker("TCS.NS")
    assert is_valid_ticker("RELIANCE.BO")


def test_legend_rows_rejected():
    for t in ("LIGHT GREEN (+0.5)", "DARK RED", "SCORING", "GROWTH SCORE",
              "MARKET CAP", "EV/EBITDA", "Q1(FY27)", "YOY", "SOURCE"):
        assert not is_valid_ticker(t), t


def test_garbage_rejected():
    assert not is_valid_ticker(None)
    assert not is_valid_ticker("")
    assert not is_valid_ticker("A")           # too short
    assert not is_valid_ticker("X" * 13)      # too long
    assert not is_valid_ticker("123")         # no letters
    assert not is_valid_ticker("+0.5")        # numeric fragment
