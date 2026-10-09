"""Running the QC rules against the database (used by the API and the import command)."""

from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from smartmet_db.models import MEASUREMENTS, Alert, Batch, Reading

from .alerts import reconcile, replay
from .config import QCConfig
from .rules import Observation, evaluate


def _observations(session: Session, batch_id: int, since=None) -> list[Observation]:
    stmt = select(Reading).where(Reading.batch_id == batch_id)
    if since is not None:
        stmt = stmt.where(Reading.measured_at >= since)
    rows = session.scalars(stmt.order_by(Reading.measured_at, Reading.id))
    return [Observation(r.measured_at, r.source, {m: getattr(r, m) for m in MEASUREMENTS}) for r in rows]


def check_batch(session: Session, code: str, cfg: QCConfig = QCConfig()) -> list[Alert]:
    """Evaluate the batch at its latest reading and open/update/resolve alerts.

    Returns the alerts opened by this check. The caller commits.
    """
    # Lock the batch row so two readings arriving together cannot both open the same alert.
    batch = session.scalar(select(Batch).where(Batch.code == code).with_for_update())
    latest = session.scalar(select(func.max(Reading.measured_at)).where(Reading.batch_id == batch.id))
    if latest is None:
        return []
    history = _observations(session, batch.id, since=latest - timedelta(hours=cfg.history_hours))
    conditions = evaluate(history, batch.started_at or history[0].measured_at, cfg)

    open_alerts = {
        (a.rule, a.measurement): a
        for a in session.scalars(select(Alert).where(Alert.batch_id == batch.id, Alert.status == "open"))
    }
    to_open, to_update, to_close = reconcile(open_alerts, conditions)
    for key in to_close:
        open_alerts[key].status = "resolved"
        open_alerts[key].resolved_at = latest
    for c in to_update:
        alert = open_alerts[c.key]
        alert.last_seen_at, alert.value, alert.message = latest, c.value, c.message
    opened = [
        Alert(batch_id=batch.id, rule=c.rule, measurement=c.measurement, severity=c.severity,
              message=c.message, value=c.value, opened_at=latest, last_seen_at=latest)
        for c in to_open
    ]
    session.add_all(opened)
    session.flush()
    return opened


def rebuild_batch_alerts(session: Session, code: str, cfg: QCConfig = QCConfig()) -> int:
    """Delete a batch's alerts and replay all its readings in order. Returns the number of alerts."""
    batch = session.scalar(select(Batch).where(Batch.code == code).with_for_update())
    session.execute(delete(Alert).where(Alert.batch_id == batch.id))
    records = replay(_observations(session, batch.id), batch.started_at, cfg)
    session.add_all(
        Alert(batch_id=batch.id, rule=r.rule, measurement=r.measurement, severity=r.severity,
              status=r.status, message=r.message, value=r.value, opened_at=r.opened_at,
              last_seen_at=r.last_seen_at, resolved_at=r.resolved_at)
        for r in records
    )
    session.flush()
    return len(records)


def list_alerts(session: Session, status: str | None = None, batch_code: str | None = None,
                limit: int = 200) -> list[tuple[Alert, str]]:
    stmt = select(Alert, Batch.code).join(Batch)
    if status:
        stmt = stmt.where(Alert.status == status)
    if batch_code:
        stmt = stmt.where(Batch.code == batch_code)
    return list(session.execute(stmt.order_by(Alert.opened_at.desc(), Alert.id.desc()).limit(limit)))
