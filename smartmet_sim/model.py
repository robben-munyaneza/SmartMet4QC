"""Fermentation model: the "true" values a perfect sensor would read.

All numbers are illustrative values chosen to look plausible for a fermented
fruit beverage. They are not validated process or safety limits.
"""

import math
from dataclasses import dataclass

SCENARIOS = ("normal", "overheat", "stuck", "contamination")


@dataclass(frozen=True)
class BatchProfile:
    """Parameters describing one healthy fermentation batch."""

    brix_start: float = 20.0          # sugar content at the start
    brix_end: float = 6.0             # residual (apparent) Brix when finished
    ethanol_per_brix: float = 0.55    # % ethanol produced per Brix consumed
    ph_start: float = 4.6
    ph_end: float = 3.8
    temp_setpoint_c: float = 26.0
    temp_activity_rise_c: float = 2.0  # extra warmth at peak yeast activity
    turbidity_base_ntu: float = 15.0
    turbidity_peak_ntu: float = 60.0   # extra cloudiness at peak activity
    midpoint_hours: float = 36.0       # time when half the sugar is consumed
    rate_per_hour: float = 0.12        # steepness of the fermentation S-curve
    duration_hours: float = 120.0      # length of one batch


class FermentationModel:
    """Computes true measurement values for a batch at a given elapsed hour."""

    def __init__(self, profile: BatchProfile = BatchProfile(), scenario: str = "normal"):
        if scenario not in SCENARIOS:
            raise ValueError(f"unknown scenario {scenario!r}; choose from {', '.join(SCENARIOS)}")
        self.profile = profile
        self.scenario = scenario

    def _logistic(self, hours: float) -> float:
        p = self.profile
        return 1.0 / (1.0 + math.exp(-p.rate_per_hour * (hours - p.midpoint_hours)))

    def progress(self, hours: float) -> float:
        """Fraction of the fermentable sugar consumed so far (0 at start, ~1 at end)."""
        start = self._logistic(0.0)
        value = (self._logistic(hours) - start) / (1.0 - start)
        if self.scenario == "stuck":
            value *= 0.45  # yeast stops working before half the sugar is used
        return max(0.0, min(1.0, value))

    def activity(self, hours: float) -> float:
        """Yeast activity from 0 (idle) to 1 (peak fermentation)."""
        level = self._logistic(hours)
        value = 4.0 * level * (1.0 - level)
        if self.scenario == "stuck":
            value *= 0.45
        return value

    def true_values(self, hours: float) -> dict:
        p = self.profile
        progress = self.progress(hours)
        activity = self.activity(hours)

        brix = p.brix_start - (p.brix_start - p.brix_end) * progress
        ethanol = (p.brix_start - brix) * p.ethanol_per_brix
        ph = p.ph_start - (p.ph_start - p.ph_end) * progress
        temperature = p.temp_setpoint_c + p.temp_activity_rise_c * activity
        turbidity = p.turbidity_base_ntu + p.turbidity_peak_ntu * activity

        if self.scenario == "overheat" and hours > 24:
            # Cooling fails after one day: temperature climbs, up to +10 C.
            temperature += min(10.0, 0.15 * (hours - 24))
        elif self.scenario == "contamination" and hours > 48:
            # Spoilage organisms after two days: extra acidity and cloudiness.
            ph = max(3.0, ph - 0.02 * (hours - 48))
            turbidity += 1.0 * (hours - 48)

        return {
            "temperature_c": temperature,
            "ph": ph,
            "brix": brix,
            "turbidity_ntu": turbidity,
            "ethanol_percent": ethanol,
        }
