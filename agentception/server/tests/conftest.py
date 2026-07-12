"""Test-suite setup.

The unit tests write real rows (search runs, LLM cost records). Until this existed
they wrote them into `data/agentception.db` — the database the running app uses — so
a test run polluted the app's data and the cost dashboard reported spend that never
happened. Every session now gets its own throwaway database.
"""

import os
import tempfile
from pathlib import Path

# Must be set before sql_store is imported anywhere, so it resolves DB_PATH to this.
_TMP_DB = Path(tempfile.gettempdir()) / "agentception_test.db"
os.environ.setdefault("AGENTCEPTION_DB", str(_TMP_DB))

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _isolated_database():
    if _TMP_DB.exists():
        _TMP_DB.unlink()

    from server.memory import sql_store

    assert str(_TMP_DB) in sql_store.DB_PATH, (
        f"tests are pointed at {sql_store.DB_PATH}, not the temp database — refusing "
        f"to run and corrupt real data"
    )
    sql_store.init()

    yield

    if _TMP_DB.exists():
        _TMP_DB.unlink()
