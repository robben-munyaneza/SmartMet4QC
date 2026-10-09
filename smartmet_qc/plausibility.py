"""Typo check for manually entered values, run before they are stored.

Unlike the spike rule (which judges a value after it is stored, against the
same sensor's recent values), this compares a hand-typed value with the
batch's previous value of any source, so it works with only a few entries a day.
"""

from datetime import datetime

from .config import QCConfig

BRIX_MAX_RISE = 1.0  # Brix only falls during fermentation; a bigger rise is almost surely a typo


def check_manual_values(values: dict, measured_at: datetime, previous: dict,
                        cfg: QCConfig = QCConfig()) -> list[str]:
    """Return warnings for values that look like typos.

    `previous` maps measurement -> (time, value) of the batch's latest earlier value.
    """
    warnings = []
    for measurement, value in values.items():
        if value is None or measurement not in previous:
            continue
        before_at, before = previous[measurement]
        hours = max(0.0, (measured_at - before_at).total_seconds() / 3600)
        change = value - before

        if measurement == "brix" and change > BRIX_MAX_RISE:
            warnings.append(
                f"Brix {value} is {change:.1f} higher than the previous value {before}. "
                "Brix normally only falls during fermentation. Is this a typo?")
            continue
        allowed = cfg.spike_base[measurement] + cfg.spike_rate_per_hour[measurement] * hours
        if abs(change) > allowed:
            warnings.append(
                f"{measurement} {value} differs by {abs(change):.2f} from the previous value {before} "
                f"({hours:.0f} h ago); more than {allowed:.2f} is unusual. Is this a typo?")
    return warnings
