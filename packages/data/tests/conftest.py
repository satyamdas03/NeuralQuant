# conftest.py — shared fixtures for nq_data tests
import pytest
from nq_data.store import DataStore

@pytest.fixture
def tmp_store(tmp_path):
    return DataStore(db_path=str(tmp_path / "test.duckdb"))
