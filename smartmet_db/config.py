"""Database settings, read from the .env file in the project folder."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"

load_dotenv(ENV_FILE)

# Superuser connection, only used by `setup` to create the app role and databases.
# Works without a password because pg_hba.conf trusts connections from localhost.
ADMIN_DATABASE_URL = os.environ.get(
    "ADMIN_DATABASE_URL", "postgresql+psycopg://postgres@localhost:5432/postgres"
)

APP_USER = "smartmet"
APP_DATABASE = "smartmet4qc"
TEST_DATABASE = "smartmet4qc_test"


def database_url(test: bool = False) -> str:
    name = "TEST_DATABASE_URL" if test else "DATABASE_URL"
    url = os.environ.get(name)
    if not url:
        raise RuntimeError(f"{name} is not set. Run `python -m smartmet_db setup` first.")
    return url
