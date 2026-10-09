"""Builds readings in the SmartMet4QC data-contract shape (see PLAN.md)."""

import random
from datetime import datetime, timedelta, timezone

from .model import BatchProfile, FermentationModel
from .sensors import SensorArray


class Simulator:
    def __init__(
        self,
        batch_id: str = "BATCH-001",
        scenario: str = "normal",
        hours_per_reading: float = 1.0,
        fault_rate: float = 0.0,
        seed=None,
        profile: BatchProfile = BatchProfile(),
        start_time=None,
    ):
        if hours_per_reading <= 0:
            raise ValueError("hours_per_reading must be positive")
        self.batch_id = batch_id
        self.model = FermentationModel(profile, scenario)
        self.sensors = SensorArray(random.Random(seed), fault_rate)
        self.hours_per_reading = hours_per_reading
        self.start_time = start_time or datetime.now(timezone.utc)

    def reading_at(self, elapsed_hours: float) -> dict:
        measurements, faults = self.sensors.read(self.model.true_values(elapsed_hours))
        timestamp = self.start_time + timedelta(hours=elapsed_hours)
        return {
            "timestamp": timestamp.isoformat(timespec="seconds"),
            "batch_id": self.batch_id,
            "source": "simulated",
            "measurements": measurements,
            "simulation": {
                "scenario": self.model.scenario,
                "elapsed_hours": round(elapsed_hours, 3),
                "injected_faults": faults,
            },
        }

    def readings(self, count=None):
        """Yield readings; by default until the batch duration is reached."""
        if count is None:
            count = int(self.model.profile.duration_hours / self.hours_per_reading) + 1
        for i in range(count):
            yield self.reading_at(i * self.hours_per_reading)
