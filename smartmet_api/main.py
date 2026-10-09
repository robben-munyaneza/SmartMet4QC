"""SmartMet4QC backend API and dashboard (Phases 3-5).

Run:  python -m uvicorn smartmet_api.main:app --reload
Dashboard: http://127.0.0.1:8000/
API docs:  http://127.0.0.1:8000/docs
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from smartmet_db import db
from smartmet_db.devices import assign_batch, device_for_key, list_devices, mark_seen
from smartmet_db.models import Alert, Batch
from smartmet_db.store import (
    batch_readings,
    batch_summaries,
    first_value,
    latest_values,
    store_readings,
)
from smartmet_qc.config import QCConfig
from smartmet_qc.plausibility import check_manual_values
from smartmet_qc.service import check_batch, list_alerts

from .schemas import (
    AlertOut,
    BatchCreate,
    BatchDetail,
    BatchOut,
    BatchUpdate,
    DeviceOut,
    DeviceUpdate,
    ManualReadingIn,
    ReadingIn,
    ReadingOut,
    StoreResult,
)

STATIC = Path(__file__).parent / "static"
ETHANOL_PER_BRIX = 0.55  # rough rule of thumb for the on-screen estimate only
QC = QCConfig()
ONLINE_WITHIN = timedelta(minutes=5)  # a device that sent nothing for longer is shown as offline


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = db.get_engine()
    db.migrate(engine)
    app.state.sessionmaker = db.get_sessionmaker(engine)
    yield
    engine.dispose()


app = FastAPI(title="SmartMet4QC API", version="0.5.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def get_session():
    with app.state.sessionmaker() as session:
        yield session


def alert_out(alert: Alert, batch_code: str) -> AlertOut:
    return AlertOut.model_validate({
        **{k: getattr(alert, k) for k in AlertOut.model_fields if k != "batch_id"},
        "batch_id": batch_code,
    })


def get_batch_or_404(session: Session, code: str) -> Batch:
    batch = session.scalar(select(Batch).where(Batch.code == code))
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"batch {code!r} not found")
    return batch


def store_and_check(session: Session, reading: dict, response: Response, device_id: int | None = None) -> StoreResult:
    """Store one reading, run the QC checks and commit."""
    inserted, _ = store_readings(session, [reading], device_id)
    new_alerts = check_batch(session, reading["batch_id"]) if inserted else []
    session.commit()
    if not inserted:
        response.status_code = status.HTTP_200_OK
    return StoreResult(
        stored=bool(inserted), duplicate=not inserted, batch_id=reading["batch_id"],
        new_alerts=[alert_out(a, reading["batch_id"]) for a in new_alerts],
    )


# ---------------------------------------------------------------- dashboard pages

@app.get("/", include_in_schema=False)
def dashboard_page():
    return FileResponse(STATIC / "index.html")


@app.get("/batches/{code}", include_in_schema=False)
def batch_page(code: str):
    return FileResponse(STATIC / "batch.html")


# ---------------------------------------------------------------- API

@app.get("/health")
def health(session: Session = Depends(get_session)):
    session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


def simulated_allowed() -> bool:
    return os.environ.get("ALLOW_SIMULATED", "true").strip().lower() != "false"


@app.post("/api/v1/measurements", response_model=StoreResult, status_code=status.HTTP_201_CREATED,
          responses={401: {"description": "Missing or invalid X-API-Key"},
                     409: {"description": "Device has no batch assigned; nothing stored"}})
def post_measurement(
    reading: ReadingIn,
    response: Response,
    api_key: str | None = Header(None, alias="X-API-Key", description="device key (required for source=device)"),
    session: Session = Depends(get_session),
):
    """Store one reading from a device or the simulator and run the QC checks.

    201 = stored, 200 = this reading was already stored (safe to resend).
    `new_alerts` lists the alerts this reading opened.
    Devices send their X-API-Key and may leave out batch_id: the batch assigned
    to the device on the dashboard is used.
    """
    data = reading.model_dump(mode="json", exclude_none=True)
    device = device_for_key(session, api_key)
    if api_key and device is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or revoked API key")

    device_id = None
    if reading.source == "device":
        if device is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "device readings need a valid X-API-Key header")
        mark_seen(device, datetime.now(timezone.utc))
        if "batch_id" not in data:
            if device.batch is None:
                session.commit()  # still record that the device is alive
                raise HTTPException(status.HTTP_409_CONFLICT,
                                    f"device {device.name!r} has no batch assigned; assign one on the dashboard")
            data["batch_id"] = device.batch.code
        device_id = device.id
    elif reading.source == "simulated" and not simulated_allowed():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "simulated readings are switched off (ALLOW_SIMULATED=false)")

    if "batch_id" not in data:
        raise HTTPException(422, "batch_id is required (only devices may leave it out)")
    return store_and_check(session, data, response, device_id)


@app.get("/api/v1/devices", response_model=list[DeviceOut])
def get_devices(session: Session = Depends(get_session)):
    """Devices, their batch and whether they sent anything recently. Add devices with
    `python -m smartmet_db device add NAME` (the key is shown only there)."""
    now = datetime.now(timezone.utc)
    return [device_out(d, now) for d in list_devices(session)]


@app.patch("/api/v1/devices/{name}", response_model=DeviceOut)
def update_device(name: str, update: DeviceUpdate, session: Session = Depends(get_session)):
    """Choose the batch a device measures (null = none)."""
    try:
        device = assign_batch(session, name, update.batch_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    session.commit()
    return device_out(device, datetime.now(timezone.utc))


def device_out(device, now: datetime) -> DeviceOut:
    return DeviceOut(
        name=device.name, active=device.api_key_hash is not None,
        batch_id=device.batch.code if device.batch else None, last_seen_at=device.last_seen_at,
        online=device.last_seen_at is not None and now - device.last_seen_at < ONLINE_WITHIN,
    )


@app.post("/api/v1/manual-readings", response_model=StoreResult, status_code=status.HTTP_201_CREATED,
          responses={409: {"description": "Possible typo: nothing stored; resend with confirm=true"}})
def post_manual_reading(entry: ManualReadingIn, response: Response, session: Session = Depends(get_session)):
    """Store values typed in by a person, after a typo check against the batch's previous values."""
    batch = get_batch_or_404(session, entry.batch_id)
    measured_at = entry.timestamp or datetime.now(timezone.utc).replace(microsecond=0)
    values = {k: v for k, v in entry.measurements.model_dump().items() if v is not None}
    if not values:
        raise HTTPException(422, "enter at least one value")

    if not entry.confirm:
        warnings = check_manual_values(values, measured_at, latest_values(session, batch.id, measured_at), QC)
        if warnings:
            return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"warnings": warnings})

    reading = {"timestamp": measured_at.isoformat(), "batch_id": batch.code,
               "source": "manual", "measurements": values}
    return store_and_check(session, reading, response)


@app.get("/api/v1/alerts", response_model=list[AlertOut])
def get_alerts(
    status_filter: Literal["open", "resolved", "all"] = Query("open", alias="status"),
    batch: str | None = Query(None, description="only this batch code"),
    limit: int = Query(200, ge=1, le=5000),
    session: Session = Depends(get_session),
):
    """Alerts, newest first. Default: only open alerts."""
    rows = list_alerts(session, None if status_filter == "all" else status_filter, batch, limit)
    return [alert_out(alert, code) for alert, code in rows]


@app.get("/api/v1/batches", response_model=list[BatchOut])
def list_batches(session: Session = Depends(get_session)):
    return batch_summaries(session)


@app.post("/api/v1/batches", response_model=BatchDetail, status_code=status.HTTP_201_CREATED)
def create_batch(new: BatchCreate, session: Session = Depends(get_session)):
    """Start a new batch. Readings for an unknown batch code also create it automatically."""
    if session.scalar(select(Batch.id).where(Batch.code == new.code)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"batch {new.code!r} already exists")
    session.add(Batch(code=new.code, product=new.product, notes=new.notes, status="active",
                      started_at=datetime.now(timezone.utc).replace(microsecond=0)))
    session.commit()
    return get_batch(new.code, session)


@app.get("/api/v1/batches/{code}", response_model=BatchDetail)
def get_batch(code: str, session: Session = Depends(get_session)):
    """Batch details, latest value of each measurement, and the QC limits for charts."""
    batch = get_batch_or_404(session, code)
    latest = latest_values(session, batch.id)
    ethanol = None
    if "brix" in latest:
        start_brix = first_value(session, batch.id, "brix")
        ethanol = round(max(0.0, start_brix - latest["brix"][1]) * ETHANOL_PER_BRIX, 1)
    return BatchDetail(
        code=batch.code, product=batch.product, status=batch.status,
        started_at=batch.started_at, ended_at=batch.ended_at, notes=batch.notes,
        latest={k: {"measured_at": t, "value": v} for k, (t, v) in latest.items()},
        ethanol_estimate=ethanol,
        limits={"temp_max_c": QC.temp_max_c, "temp_min_c": QC.temp_min_c, "ph_min": QC.ph_min,
                "turbidity_max_ntu": QC.turbidity_max_ntu, "brix_done": QC.brix_done},
    )


@app.patch("/api/v1/batches/{code}", response_model=BatchDetail)
def update_batch(code: str, update: BatchUpdate, session: Session = Depends(get_session)):
    """Change a batch's status (finished / aborted / active again) or notes."""
    batch = get_batch_or_404(session, code)
    if update.status is not None and update.status != batch.status:
        batch.status = update.status
        batch.ended_at = None if update.status == "active" else datetime.now(timezone.utc).replace(microsecond=0)
    if update.notes is not None:
        batch.notes = update.notes
    session.commit()
    return get_batch(code, session)


@app.get("/api/v1/batches/{code}/readings", response_model=list[ReadingOut])
def get_batch_readings(
    code: str,
    limit: int = Query(1000, ge=1, le=10000, description="newest readings to return"),
    session: Session = Depends(get_session),
):
    get_batch_or_404(session, code)
    return batch_readings(session, code, limit)
