"""Turning conditions into alerts that open, stay open, and resolve."""

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from .config import QCConfig
from .rules import Condition, Observation, evaluate


def reconcile(open_keys, conditions: list[Condition]) -> tuple[list, list, list]:
    """Compare what is true now with the open alerts.

    Returns (to_open, to_update, to_close): conditions without an open alert,
    conditions whose alert stays open, and keys of open alerts that no longer apply.
    """
    active = {c.key: c for c in conditions}
    open_keys = set(open_keys)
    to_open = [c for key, c in active.items() if key not in open_keys]
    to_update = [c for key, c in active.items() if key in open_keys]
    to_close = [key for key in open_keys if key not in active]
    return to_open, to_update, to_close


@dataclass
class AlertRecord:
    rule: str
    measurement: str
    severity: str
    message: str
    value: float | None
    opened_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None = None

    @property
    def status(self) -> str:
        return "open" if self.resolved_at is None else "resolved"

    def covers(self, moment: datetime) -> bool:
        return self.opened_at <= moment and (self.resolved_at is None or moment < self.resolved_at)


def replay(observations: list[Observation], batch_start: datetime | None = None,
           cfg: QCConfig = QCConfig()) -> list[AlertRecord]:
    """Feed observations one by one, exactly as if they arrived live. Returns every alert."""
    if not observations:
        return []
    batch_start = batch_start or observations[0].measured_at
    history: deque[Observation] = deque()
    open_alerts: dict[tuple, AlertRecord] = {}
    records = []
    for obs in observations:
        history.append(obs)
        while history[0].measured_at < obs.measured_at - timedelta(hours=cfg.history_hours):
            history.popleft()
        to_open, to_update, to_close = reconcile(open_alerts, evaluate(list(history), batch_start, cfg))
        now = obs.measured_at
        for key in to_close:
            open_alerts.pop(key).resolved_at = now
        for c in to_update:
            alert = open_alerts[c.key]
            alert.last_seen_at, alert.value, alert.message = now, c.value, c.message
        for c in to_open:
            alert = AlertRecord(c.rule, c.measurement, c.severity, c.message, c.value, now, now)
            open_alerts[c.key] = alert
            records.append(alert)
    return records
