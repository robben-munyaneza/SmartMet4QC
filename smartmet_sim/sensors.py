"""Sensor layer: turns true values into what imperfect sensors report."""

import random
from dataclasses import dataclass

FAULT_TYPES = ("spike", "dropout", "stuck")
STUCK_READINGS = (6, 12)  # a frozen sensor stays frozen for this many readings


@dataclass(frozen=True)
class SensorSpec:
    noise_std: float   # typical random measurement error
    min_value: float   # physical range the sensor can report
    max_value: float
    spike_size: float  # how far off a spike fault pushes the value
    decimals: int = 2


SENSORS = {
    "temperature_c": SensorSpec(noise_std=0.1, min_value=-10.0, max_value=60.0, spike_size=8.0),
    "ph": SensorSpec(noise_std=0.02, min_value=0.0, max_value=14.0, spike_size=1.0),
    "brix": SensorSpec(noise_std=0.1, min_value=0.0, max_value=40.0, spike_size=4.0),
    "turbidity_ntu": SensorSpec(noise_std=1.5, min_value=0.0, max_value=1000.0, spike_size=80.0),
    "ethanol_percent": SensorSpec(noise_std=0.1, min_value=0.0, max_value=20.0, spike_size=4.0),
}


class SensorArray:
    """Adds noise and, with probability `fault_rate` per sensor, an injected fault."""

    def __init__(self, rng: random.Random, fault_rate: float = 0.0):
        if not 0.0 <= fault_rate <= 1.0:
            raise ValueError("fault_rate must be between 0 and 1")
        self.rng = rng
        self.fault_rate = fault_rate
        self._last = {}
        self._stuck_left = {}  # readings left in an ongoing stuck fault, per sensor

    def read(self, true_values: dict) -> tuple:
        """Return (measurements, injected_faults) for one reading."""
        measurements = {}
        faults = {}
        for name, true_value in true_values.items():
            spec = SENSORS[name]
            value = true_value + self.rng.gauss(0.0, spec.noise_std)

            if self._stuck_left.get(name):
                self._stuck_left[name] -= 1
                faults[name] = "stuck"
                value = self._last[name]
            elif self.rng.random() < self.fault_rate:
                fault = self.rng.choice(FAULT_TYPES)
                if fault == "stuck" and self._last.get(name) is None:
                    fault = "spike"  # nothing to repeat yet
                faults[name] = fault
                if fault == "spike":
                    value += self.rng.choice((-1, 1)) * spec.spike_size
                elif fault == "dropout":
                    value = None
                else:
                    value = self._last[name]
                    self._stuck_left[name] = self.rng.randint(*STUCK_READINGS) - 1

            if value is not None:
                value = round(min(spec.max_value, max(spec.min_value, value)), spec.decimals)
            measurements[name] = value
            if name not in faults:
                self._last[name] = value  # a stuck sensor repeats its last good value
        return measurements, faults
