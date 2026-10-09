"""Shared setup for API tests: one TestClient on the smartmet4qc_test database.

Importing this raises unittest.SkipTest when the libraries or the test database
are not available, so the importing test module is skipped.
"""

import atexit
import os
import unittest

try:
    from fastapi.testclient import TestClient
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    from smartmet_api.main import app
    from smartmet_db import config, db
    from smartmet_db.models import Base
except ImportError as exc:
    raise unittest.SkipTest(f"API libraries not installed: {exc}")

_client = None
_engine = None


def _close():
    _client.__exit__(None, None, None)
    _engine.dispose()


def client_for_tests() -> TestClient:
    """Return the shared client with an empty test database."""
    global _client, _engine
    if _client is None:
        try:
            _engine = db.get_engine(test=True)
            _engine.connect().close()
        except (RuntimeError, OperationalError) as exc:
            raise unittest.SkipTest(f"test database not available: {exc}")
        # Start empty, so the API's startup migration builds the schema from scratch.
        Base.metadata.drop_all(_engine)
        with _engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        # The API reads DATABASE_URL on startup; point it at the test database.
        os.environ["DATABASE_URL"] = config.database_url(test=True)
        _client = TestClient(app)
        _client.__enter__()  # runs the app's startup (lifespan)
        atexit.register(_close)
    Base.metadata.drop_all(_engine)
    Base.metadata.create_all(_engine)
    return _client
