"""QC settings. The limits are placeholders until real batch data exists (MVP_PLAN.md §7)."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class QCConfig:
    # Process limits: an alert needs `consecutive` valid readings beyond the limit,
    # so one wrong value (a spike) cannot raise a process alert.
    temp_max_c: float = 30.0
    temp_min_c: float = 18.0
    ph_min: float = 3.5
    turbidity_max_ntu: float = 90.0
    consecutive: int = 2

    # Fermentation progress, judged from the Brix trend over `trend_window_hours`.
    trend_window_hours: float = 24.0
    brix_done: float = 9.0                     # below this, fermentation is nearly complete
    stuck_after_hours: float = 36.0            # do not call a batch stuck during its slow start
    stuck_max_drop_per_day: float = 1.0        # Brix/day; less than this while above brix_done = stuck
    finished_max_change_per_day: float = 0.3   # Brix/day; less than this below brix_done = finished

    # Sensor faults.
    stuck_identical_count: int = 6
    # A value is a spike if it is further than base + rate * hours_since_previous
    # from the median of the previous 3 values of the same sensor.
    spike_base: dict = field(default_factory=lambda: {
        "temperature_c": 2.0, "ph": 0.3, "brix": 1.5, "turbidity_ntu": 25.0, "ethanol_percent": 1.5,
    })
    spike_rate_per_hour: dict = field(default_factory=lambda: {
        "temperature_c": 0.2, "ph": 0.03, "brix": 0.5, "turbidity_ntu": 4.0, "ethanol_percent": 0.3,
    })

    # How much history the rules look at.
    history_hours: float = 30.0
