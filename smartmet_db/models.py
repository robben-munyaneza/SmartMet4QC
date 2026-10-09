"""Database tables (see PLAN.md, Phase 2)."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

SOURCES = ("simulated", "device", "manual")
BATCH_STATUSES = ("active", "finished", "aborted")
MEASUREMENTS = ("temperature_c", "ph", "brix", "turbidity_ntu", "ethanol_percent")
ALERT_SEVERITIES = ("info", "warning", "critical")
ALERT_STATUSES = ("open", "resolved")


def _in(column: str, values: tuple) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Base(DeclarativeBase):
    pass


class Batch(Base):
    __tablename__ = "batches"
    __table_args__ = (CheckConstraint(_in("status", BATCH_STATUSES), name="batch_status_valid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    product: Mapped[str] = mapped_column(String(100), default="banana beverage")
    status: Mapped[str] = mapped_column(String(20), default="active")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    readings: Mapped[list["Reading"]] = relationship(back_populates="batch", passive_deletes=True)
    alerts: Mapped[list["Alert"]] = relationship(back_populates="batch", passive_deletes=True)


class Reading(Base):
    __tablename__ = "readings"
    __table_args__ = (
        # Re-sending or re-importing the same reading must not create a duplicate.
        UniqueConstraint("batch_id", "measured_at", "source", name="reading_unique"),
        CheckConstraint(_in("source", SOURCES), name="reading_source_valid"),
        # Physical sanity limits only; quality limits come in Phase 4.
        CheckConstraint("temperature_c BETWEEN -50 AND 150", name="temperature_range"),
        CheckConstraint("ph BETWEEN 0 AND 14", name="ph_range"),
        CheckConstraint("brix BETWEEN 0 AND 100", name="brix_range"),
        CheckConstraint("turbidity_ntu >= 0", name="turbidity_range"),
        CheckConstraint("ethanol_percent BETWEEN 0 AND 100", name="ethanol_range"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source: Mapped[str] = mapped_column(String(20))

    # One column per measurement; NULL means the sensor sent no value.
    temperature_c: Mapped[float | None] = mapped_column(Float)
    ph: Mapped[float | None] = mapped_column(Float)
    brix: Mapped[float | None] = mapped_column(Float)
    turbidity_ntu: Mapped[float | None] = mapped_column(Float)
    ethanol_percent: Mapped[float | None] = mapped_column(Float)

    # Simulator answer key (scenario, injected faults); NULL for real devices.
    simulation: Mapped[dict | None] = mapped_column(JSONB)

    batch: Mapped[Batch] = relationship(back_populates="readings")


class Alert(Base):
    """A QC problem found by smartmet_qc. Open while the problem lasts, then resolved."""

    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint(_in("severity", ALERT_SEVERITIES), name="alert_severity_valid"),
        CheckConstraint(_in("status", ALERT_STATUSES), name="alert_status_valid"),
        # At most one open alert per batch, rule and measurement.
        Index("one_open_alert", "batch_id", "rule", "measurement", unique=True,
              postgresql_where=text("status = 'open'")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"), index=True)
    rule: Mapped[str] = mapped_column(String(40))
    measurement: Mapped[str] = mapped_column(String(30))
    severity: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(10), default="open")
    message: Mapped[str] = mapped_column(Text)
    value: Mapped[float | None] = mapped_column(Float)
    # Times are reading times (the batch clock), not the time the server ran the check.
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    batch: Mapped[Batch] = relationship(back_populates="alerts")
