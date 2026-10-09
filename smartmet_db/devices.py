"""Devices and their API keys."""

import hashlib
import secrets
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Batch, Device

KEY_PREFIX = "smk_"


def hash_key(api_key: str) -> str:
    # Keys are long random strings, so a plain SHA-256 is enough (no password hashing needed).
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def new_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


def add_device(session: Session, name: str) -> str:
    """Create a device and return its API key. The key is not stored and cannot be shown again."""
    if session.scalar(select(Device.id).where(Device.name == name)) is not None:
        raise ValueError(f"device {name!r} already exists")
    key = new_key()
    session.add(Device(name=name, api_key_hash=hash_key(key)))
    session.flush()
    return key


def rotate_key(session: Session, name: str) -> str:
    """Give a device a new key (the old one stops working). Returns the new key."""
    device = get_device(session, name)
    key = new_key()
    device.api_key_hash = hash_key(key)
    return key


def revoke_key(session: Session, name: str) -> None:
    """The device can no longer send readings. Its history is kept."""
    get_device(session, name).api_key_hash = None


def get_device(session: Session, name: str) -> Device:
    device = session.scalar(select(Device).where(Device.name == name))
    if device is None:
        raise ValueError(f"no device named {name!r}")
    return device


def device_for_key(session: Session, api_key: str | None) -> Device | None:
    if not api_key:
        return None
    return session.scalar(select(Device).where(Device.api_key_hash == hash_key(api_key)))


def assign_batch(session: Session, name: str, batch_code: str | None) -> Device:
    """Point a device at a batch (or at no batch with None)."""
    device = get_device(session, name)
    if batch_code is None:
        device.batch_id = None
    else:
        batch = session.scalar(select(Batch).where(Batch.code == batch_code))
        if batch is None:
            raise ValueError(f"no batch named {batch_code!r}")
        device.batch_id = batch.id
    session.flush()
    return device


def list_devices(session: Session) -> list[Device]:
    return list(session.scalars(select(Device).order_by(Device.name)))


def mark_seen(device: Device, moment: datetime) -> None:
    device.last_seen_at = moment
