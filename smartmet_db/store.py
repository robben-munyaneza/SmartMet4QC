"""Saving and reading back data in the SmartMet4QC data-contract shape."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .models import MEASUREMENTS, SOURCES, Batch, Reading


class InvalidReading(ValueError):
    pass


def parse_reading(data: dict) -> dict:
    """Check one reading (see PLAN.md data contract) and turn it into column values."""
    for key in ("timestamp", "batch_id", "source", "measurements"):
        if key not in data:
            raise InvalidReading(f"missing field {key!r}")
    if data["source"] not in SOURCES:
        raise InvalidReading(f"source must be one of {', '.join(SOURCES)}")
    try:
        measured_at = datetime.fromisoformat(data["timestamp"])
    except (TypeError, ValueError):
        raise InvalidReading(f"timestamp {data['timestamp']!r} is not ISO 8601") from None
    if measured_at.tzinfo is None:
        raise InvalidReading("timestamp must include a time zone, e.g. +00:00")

    measurements = data["measurements"]
    unknown = set(measurements) - set(MEASUREMENTS)
    if unknown:
        raise InvalidReading(f"unknown measurements: {', '.join(sorted(unknown))}")
    for name, value in measurements.items():
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise InvalidReading(f"{name} must be a number or null")

    return {
        "batch_code": str(data["batch_id"]),
        "measured_at": measured_at,
        "source": data["source"],
        "simulation": data.get("simulation"),
        **{name: measurements.get(name) for name in MEASUREMENTS},
    }


def get_or_create_batch(session: Session, code: str, started_at: datetime | None = None) -> Batch:
    # ON CONFLICT makes this safe when two devices start the same batch at once.
    session.execute(
        insert(Batch)
        .values(code=code, started_at=started_at, product="banana beverage", status="active")
        .on_conflict_do_nothing(index_elements=["code"])
    )
    return session.scalar(select(Batch).where(Batch.code == code))


def store_readings(session: Session, readings) -> tuple[int, int]:
    """Save readings, creating batches as needed. Returns (inserted, duplicates).

    The caller commits. Invalid readings raise InvalidReading before anything is written.
    """
    rows = [parse_reading(r) for r in readings]
    batch_ids = {}
    inserted = 0
    for row in rows:
        code = row.pop("batch_code")
        if code not in batch_ids:
            batch_ids[code] = get_or_create_batch(session, code, row["measured_at"]).id
        stmt = (
            insert(Reading)
            .values(batch_id=batch_ids[code], **row)
            .on_conflict_do_nothing(constraint="reading_unique")
            .returning(Reading.id)
        )
        # A duplicate is skipped by ON CONFLICT and returns no row.
        if session.execute(stmt).first() is not None:
            inserted += 1
    return inserted, len(rows) - inserted


def batch_summaries(session: Session) -> list[dict]:
    stmt = (
        select(
            Batch.code,
            Batch.status,
            func.count(Reading.id),
            func.min(Reading.measured_at),
            func.max(Reading.measured_at),
        )
        .outerjoin(Reading)
        .group_by(Batch.id)
        .order_by(Batch.code)
    )
    keys = ("code", "status", "readings", "first", "last")
    return [dict(zip(keys, row)) for row in session.execute(stmt)]


def batch_readings(session: Session, code: str, limit: int | None = None) -> list[Reading]:
    """Readings of one batch, oldest first; with `limit`, only the newest `limit`."""
    stmt = (
        select(Reading)
        .join(Batch)
        .where(Batch.code == code)
        .order_by(Reading.measured_at.desc())
        .limit(limit)
    )
    return list(reversed(session.scalars(stmt).all()))
