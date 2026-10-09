"""Connections, database creation and table creation."""

import os
import re
import secrets

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from . import config
from .models import Base


def get_engine(test: bool = False) -> Engine:
    return create_engine(config.database_url(test))


def get_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def init_tables(engine: Engine) -> None:
    """Create all tables straight from the models. Only for empty test databases;
    real databases are created and updated with migrate()."""
    Base.metadata.create_all(engine)


BASELINE_REVISION = "0001"


def _alembic_config(connection):
    from alembic.config import Config

    cfg = Config(str(config.ROOT / "alembic.ini"))
    cfg.attributes["connection"] = connection
    return cfg


def migrate(engine: Engine) -> None:
    """Bring the database schema up to date (Alembic upgrade to the latest revision).

    A database created before migrations existed (tables present, no version
    recorded) is first marked as being at the baseline revision.
    """
    from alembic import command

    with engine.begin() as connection:
        cfg = _alembic_config(connection)
        tables = inspect(connection)
        if not tables.has_table("alembic_version") and tables.has_table("batches"):
            command.stamp(cfg, BASELINE_REVISION)
        command.upgrade(cfg, "head")


def schema_differences(engine: Engine) -> list:
    """Differences between the database and the models; empty when they match."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        return compare_metadata(context, Base.metadata)


def _existing_password() -> str | None:
    url = os.environ.get("DATABASE_URL")
    return make_url(url).password if url else None


def setup_databases() -> dict:
    """Create the app login role and the app + test databases, then write .env.

    Safe to run more than once: existing role and databases are kept.
    """
    user, databases = config.APP_USER, (config.APP_DATABASE, config.TEST_DATABASE)
    for name in (user, *databases):
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", name):
            raise ValueError(f"unsafe identifier {name!r}")

    password = _existing_password() or secrets.token_urlsafe(24)
    created = []
    admin = create_engine(config.ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        role_exists = conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": user}).scalar()
        # token_urlsafe only uses [A-Za-z0-9_-], so it is safe inside quotes.
        if role_exists:
            conn.execute(text(f"ALTER ROLE {user} WITH LOGIN PASSWORD '{password}'"))
        else:
            conn.execute(text(f"CREATE ROLE {user} WITH LOGIN PASSWORD '{password}'"))
            created.append(f"role {user}")
        for db in databases:
            exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :d"), {"d": db}).scalar()
            if not exists:
                conn.execute(text(f"CREATE DATABASE {db} OWNER {user} ENCODING 'UTF8'"))
                created.append(f"database {db}")
    admin.dispose()

    admin_url = make_url(config.ADMIN_DATABASE_URL)
    host, port = admin_url.host or "localhost", admin_url.port or 5432
    urls = {
        "DATABASE_URL": f"postgresql+psycopg://{user}:{password}@{host}:{port}/{databases[0]}",
        "TEST_DATABASE_URL": f"postgresql+psycopg://{user}:{password}@{host}:{port}/{databases[1]}",
    }
    _write_env(urls)
    return {"created": created, **urls}


def _write_env(values: dict) -> None:
    lines = []
    if config.ENV_FILE.exists():
        lines = [
            line for line in config.ENV_FILE.read_text(encoding="utf-8").splitlines()
            if line.split("=", 1)[0].strip() not in values
        ]
    lines += [f"{key}={value}" for key, value in values.items()]
    config.ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ.update(values)
