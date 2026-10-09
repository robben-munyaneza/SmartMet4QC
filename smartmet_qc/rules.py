"""QC rules: given the recent history of one batch, which problems are true right now?"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import combinations
from statistics import median

from .config import QCConfig

MANUAL = "manual"


@dataclass(frozen=True)
class Observation:
    """One reading. `values` maps measurement -> number, or None when the sensor sent no value.
    A measurement that is not in `values` was not part of this reading at all."""

    measured_at: datetime
    source: str
    values: dict


@dataclass(frozen=True)
class Condition:
    rule: str
    measurement: str
    severity: str  # info | warning | critical
    message: str
    value: float | None

    @property
    def key(self) -> tuple:
        return (self.rule, self.measurement)


def _hours(delta) -> float:
    return delta.total_seconds() / 3600


def _series(history, measurement, source=None, since=None) -> list[tuple]:
    return [
        (o.measured_at, o.values[measurement])
        for o in history
        if o.values.get(measurement) is not None
        and (source is None or o.source == source)
        and (since is None or o.measured_at >= since)
    ]


def theil_sen_slope(points: list[tuple]) -> float:
    """Robust slope (units per hour) of (time, value) points: the median of all pairwise slopes."""
    slopes = [
        (v2 - v1) / _hours(t2 - t1)
        for (t1, v1), (t2, v2) in combinations(points, 2)
        if t2 != t1
    ]
    return median(slopes) if slopes else 0.0


LIMIT_RULES = (
    # rule, measurement, too high?, config attribute, severity, message
    ("temperature_high", "temperature_c", True, "temp_max_c", "warning", "Temperature above {limit} C"),
    ("temperature_low", "temperature_c", False, "temp_min_c", "warning", "Temperature below {limit} C"),
    ("ph_low", "ph", False, "ph_min", "critical", "pH below {limit}: possible souring or contamination"),
    ("turbidity_high", "turbidity_ntu", True, "turbidity_max_ntu", "warning", "Turbidity above {limit} NTU"),
)


def _limit_rules(history, cfg: QCConfig) -> list[Condition]:
    found = []
    for rule, measurement, high, attr, severity, message in LIMIT_RULES:
        recent = [v for _, v in _series(history, measurement)[-cfg.consecutive:]]
        limit = getattr(cfg, attr)
        if len(recent) == cfg.consecutive and all(v > limit if high else v < limit for v in recent):
            found.append(Condition(rule, measurement, severity, message.format(limit=limit), recent[-1]))
    return found


def _fermentation_rules(history, batch_start, now, cfg: QCConfig) -> list[Condition]:
    window = cfg.trend_window_hours
    points = _series(history, "brix", since=now - timedelta(hours=window))
    # Need at least 3 values that cover most of the window, or the trend means nothing.
    if len(points) < 3 or _hours(now - points[0][0]) < 0.75 * window:
        return []
    per_day = theil_sen_slope(points) * 24
    level = median(v for _, v in points[-3:])
    if level > cfg.brix_done and _hours(now - batch_start) >= cfg.stuck_after_hours \
            and -per_day < cfg.stuck_max_drop_per_day:
        return [Condition("fermentation_stuck", "brix", "warning",
                          f"Brix {level:.1f} fell only {-per_day:.2f}/day over the last {window:g} h", level)]
    if level <= cfg.brix_done and abs(per_day) < cfg.finished_max_change_per_day:
        return [Condition("batch_finished", "brix", "info",
                          f"Brix stable at {level:.1f} for {window:g} h: fermentation looks finished", level)]
    return []


def _sensor_rules(history, cfg: QCConfig) -> list[Condition]:
    found = {}
    for source in {o.source for o in history}:
        latest = next(o for o in reversed(history) if o.source == source)
        for measurement in cfg.spike_base:
            series = _series(history, measurement, source=source)
            value = latest.values.get(measurement)

            if value is None:
                # Sensor reported nothing although it worked earlier in the window.
                if source != MANUAL and measurement in latest.values and series:
                    found[("sensor_missing", measurement)] = Condition(
                        "sensor_missing", measurement, "warning",
                        f"No {measurement} value from {source} sensor", None)
                continue

            previous = series[-4:-1]
            if len(previous) == 3:
                base = median(v for _, v in previous)
                # Time since the middle previous value: the median represents that moment,
                # so the value may legitimately have changed this much since then.
                gap = _hours(series[-1][0] - previous[1][0])
                threshold = cfg.spike_base[measurement] + cfg.spike_rate_per_hour[measurement] * gap
                if abs(value - base) > threshold:
                    found[("sensor_spike", measurement)] = Condition(
                        "sensor_spike", measurement, "warning",
                        f"{measurement} jumped to {value} (recent values around {base})", value)

            recent = [v for _, v in series[-cfg.stuck_identical_count:]]
            if source != MANUAL and len(recent) == cfg.stuck_identical_count and len(set(recent)) == 1:
                found[("sensor_stuck", measurement)] = Condition(
                    "sensor_stuck", measurement, "warning",
                    f"{measurement} sensor repeated {value} {len(recent)} times: it may be frozen", value)
    return list(found.values())


def evaluate(history: list[Observation], batch_start: datetime, cfg: QCConfig = QCConfig()) -> list[Condition]:
    """Conditions that are true at the time of the last observation. `history` is sorted by time."""
    if not history:
        return []
    now = history[-1].measured_at
    return (
        _limit_rules(history, cfg)
        + _fermentation_rules(history, batch_start, now, cfg)
        + _sensor_rules(history, cfg)
    )
