"""Request and response shapes. ReadingIn is the data contract from PLAN.md."""

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Measurements(BaseModel):
    # strict: numbers only, so "26.1" or true are rejected instead of converted.
    model_config = ConfigDict(extra="forbid", strict=True)

    # Physical sanity ranges, same as the database checks. Quality limits come in Phase 4.
    temperature_c: float | None = Field(None, ge=-50, le=150)
    ph: float | None = Field(None, ge=0, le=14)
    brix: float | None = Field(None, ge=0, le=100)
    turbidity_ntu: float | None = Field(None, ge=0)
    ethanol_percent: float | None = Field(None, ge=0, le=100)

    @model_validator(mode="after")
    def at_least_one(self):
        if not self.model_fields_set:
            raise ValueError("at least one measurement is required (null means sensor gave no value)")
        return self


class ReadingIn(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "timestamp": "2026-10-09T10:00:00+00:00",
                "source": "device",
                "measurements": {"temperature_c": 26.1, "ph": 4.5},
            }
        },
    )

    timestamp: AwareDatetime
    # Optional for devices: the server uses the batch assigned to the device on the dashboard.
    batch_id: str | None = Field(None, min_length=1, max_length=50)
    source: Literal["simulated", "device", "manual"]
    measurements: Measurements
    simulation: dict | None = None  # simulator answer key; real devices leave it out


class StoreResult(BaseModel):
    stored: bool
    duplicate: bool
    batch_id: str
    new_alerts: list["AlertOut"] = []  # alerts this reading opened


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    batch_id: str
    rule: str
    measurement: str
    severity: str
    status: str
    message: str
    value: float | None
    opened_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None


class ManualReadingIn(BaseModel):
    """A value typed in by a person. Checked for typos before it is stored."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"batch_id": "BATCH-001", "measurements": {"brix": 13.2}}},
    )

    batch_id: str = Field(min_length=1, max_length=50)
    timestamp: AwareDatetime | None = None  # default: now
    measurements: Measurements
    confirm: bool = False  # true = store even if the typo check has warnings


class BatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    product: str = Field("banana beverage", max_length=100)
    notes: str | None = None


class BatchUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["active", "finished", "aborted"] | None = None
    notes: str | None = None


class LatestValue(BaseModel):
    value: float
    measured_at: datetime


class BatchDetail(BaseModel):
    code: str
    product: str
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    notes: str | None
    latest: dict[str, LatestValue]
    ethanol_estimate: float | None  # rough: 0.55 x Brix drop; confirm in a lab
    limits: dict[str, float]


class DeviceOut(BaseModel):
    name: str
    active: bool  # false = key revoked
    batch_id: str | None
    last_seen_at: datetime | None
    online: bool  # sent something in the last few minutes


class DeviceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: str | None  # batch code, or null to stop measuring


class BatchOut(BaseModel):
    code: str
    status: str
    readings: int
    first: datetime | None
    last: datetime | None


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    measured_at: datetime
    received_at: datetime
    source: str
    temperature_c: float | None
    ph: float | None
    brix: float | None
    turbidity_ntu: float | None
    ethanol_percent: float | None
    simulation: dict | None
