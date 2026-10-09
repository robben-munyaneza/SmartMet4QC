"""Alembic environment: connects with DATABASE_URL from .env (or a URL passed by smartmet_db.db.migrate)."""

from alembic import context
from sqlalchemy import create_engine

from smartmet_db import config as app_config
from smartmet_db.models import Base

target_metadata = Base.metadata


def run_migrations_offline():
    url = context.config.get_main_option("sqlalchemy.url") or app_config.database_url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connection = context.config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    url = context.config.get_main_option("sqlalchemy.url") or app_config.database_url()
    engine = create_engine(url)
    with engine.connect() as connection:
        _run(connection)
    engine.dispose()


def _run(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
