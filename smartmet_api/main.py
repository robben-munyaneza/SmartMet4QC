"""SmartMet4QC backend API (Phases 3-4).

Run:  python -m uvicorn smartmet_api.main:app --reload
Docs: http://127.0.0.1:8000/docs
"""

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from smartmet_db import db
from smartmet_db.models import Alert, Batch
from smartmet_db.store import batch_readings, batch_summaries, store_readings
from smartmet_qc.service import check_batch, list_alerts

from .schemas import AlertOut, BatchOut, ReadingIn, ReadingOut, StoreResult


def alert_out(alert: Alert, batch_code: str) -> AlertOut:
    return AlertOut.model_validate({
        **{k: getattr(alert, k) for k in AlertOut.model_fields if k != "batch_id"},
        "batch_id": batch_code,
    })


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = db.get_engine()
    db.init_tables(engine)
    app.state.sessionmaker = db.get_sessionmaker(engine)
    yield
    engine.dispose()


app = FastAPI(title="SmartMet4QC API", version="0.4.0", lifespan=lifespan)


def get_session():
    with app.state.sessionmaker() as session:
        yield session


@app.get("/health")
def health(session: Session = Depends(get_session)):
    session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


@app.post("/api/v1/measurements", response_model=StoreResult, status_code=status.HTTP_201_CREATED)
def post_measurement(reading: ReadingIn, response: Response, session: Session = Depends(get_session)):
    """Store one reading and run the QC checks.

    201 = stored, 200 = this reading was already stored (safe to resend).
    `new_alerts` lists the alerts this reading opened.
    """
    inserted, _ = store_readings(session, [reading.model_dump(mode="json", exclude_none=True)])
    new_alerts = check_batch(session, reading.batch_id) if inserted else []
    session.commit()
    if not inserted:
        response.status_code = status.HTTP_200_OK
    return StoreResult(
        stored=bool(inserted), duplicate=not inserted, batch_id=reading.batch_id,
        new_alerts=[alert_out(a, reading.batch_id) for a in new_alerts],
    )


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


@app.get("/api/v1/batches/{code}/readings", response_model=list[ReadingOut])
def get_batch_readings(
    code: str,
    limit: int = Query(1000, ge=1, le=10000, description="newest readings to return"),
    session: Session = Depends(get_session),
):
    if session.scalar(select(Batch.id).where(Batch.code == code)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"batch {code!r} not found")
    return batch_readings(session, code, limit)
