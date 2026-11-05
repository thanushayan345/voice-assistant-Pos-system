"""System Maintenance Mode & Feature Flag endpoints + independent FastAPI 503 enforcement."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.system_status import SystemStatus
from app.models.user import User
from app.schemas.system_status import (
    FeatureFlags,
    SystemStatusResponse,
    SystemStatusUpdateRequest,
    sanitize_public_text,
)
from app.utils.security import bearer_scheme, decode_access_token, require_admin_user

router = APIRouter(prefix="/api/system", tags=["System Maintenance & Feature Flags"])

# Monotonic version counter incremented whenever admin updates status (drives live SSE notifications)
_STATUS_REVISION = 1


def get_or_create_system_status(db: Session) -> SystemStatus:
    """Return singleton SystemStatus row (id=1), creating defaults if missing."""
    row = db.query(SystemStatus).filter(SystemStatus.id == 1).first()
    if not row:
        row = SystemStatus(
            id=1,
            maintenance=False,
            blocking=False,
            message="Scheduled system maintenance is currently in progress.",
            estimated_time="15 minutes",
            features_json=FeatureFlags().model_dump_json(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def parse_features(raw_json: Optional[str]) -> FeatureFlags:
    if not raw_json:
        return FeatureFlags()
    try:
        data = json.loads(raw_json)
        return FeatureFlags.model_validate(data)
    except Exception:
        return FeatureFlags()


def serialize_system_status(row: SystemStatus) -> SystemStatusResponse:
    """Serialize sanitized SystemStatus matching Firestore document `system/status` fields."""
    safe_msg = sanitize_public_text(
        row.message,
        fallback="Scheduled system maintenance is currently in progress.",
    )
    safe_est = sanitize_public_text(row.estimated_time, fallback="Shortly")
    updated = row.updated_at or datetime.now(timezone.utc)
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)

    return SystemStatusResponse(
        maintenance=bool(row.maintenance),
        message=safe_msg,
        estimatedTime=safe_est,
        updatedAt=updated,
        blocking=bool(row.blocking),
        features=parse_features(row.features_json),
    )


def _is_request_from_admin(
    credentials: Optional[HTTPAuthorizationCredentials],
    db: Session,
) -> bool:
    """Check if request carries a valid active owner/admin JWT without raising on missing auth."""
    if not credentials or not credentials.credentials:
        return False
    try:
        payload = decode_access_token(credentials.credentials)
        uid = payload.get("sub")
        if not uid:
            return False
        user = db.query(User).filter(User.id == int(uid)).first()
        return bool(
            user and user.is_active and (user.role or "").lower() in ("owner", "admin")
        )
    except Exception:
        return False


def make_maintenance_guard(
    feature_key: Optional[str] = None,
    mutating_only_feature: bool = False,
) -> Callable:
    """
    Create an independent FastAPI dependency enforcing:
    1. HTTP 503 Service Unavailable when `maintenance=True` and `blocking=True`
       (allowing read-only inspection for authenticated administrators while still blocking
        mutating POS/stock operations during active maintenance).
    2. HTTP 503 Service Unavailable when a specific `feature_key` flag is disabled.
    Never trusts frontend flags or client headers.
    """

    def _guard(
        request: Request,
        db: Session = Depends(get_db),
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    ) -> None:
        row = get_or_create_system_status(db)
        status_obj = serialize_system_status(row)
        method = (request.method or "GET").upper()
        is_mutating = method in ("POST", "PUT", "PATCH", "DELETE")
        is_admin = _is_request_from_admin(credentials, db)

        # 1. Blocking Maintenance Enforcement -> HTTP 503 Service Unavailable
        if status_obj.maintenance and status_obj.blocking:
            if not is_admin or is_mutating:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "code": "MAINTENANCE_MODE",
                        "message": status_obj.message,
                        "estimatedTime": status_obj.estimatedTime,
                    },
                )

        # 2. Backend Feature Flag Enforcement -> HTTP 503 Service Unavailable
        if feature_key:
            flags_dict = status_obj.features.model_dump()
            is_enabled = bool(flags_dict.get(feature_key, True))
            if not is_enabled:
                if not mutating_only_feature or is_mutating:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail={
                            "code": "FEATURE_DISABLED",
                            "feature": feature_key,
                            "message": "This feature is temporarily disabled by an administrator.",
                        },
                    )

    return _guard


@router.get("/status", response_model=SystemStatusResponse)
def get_system_status(db: Session = Depends(get_db)):
    """Return current sanitized system maintenance status & feature flags."""
    row = get_or_create_system_status(db)
    return serialize_system_status(row)


@router.put("/status", response_model=SystemStatusResponse)
def update_system_status(
    payload: SystemStatusUpdateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user),
):
    """
    Administrator-only endpoint to enable/disable maintenance mode, update message/duration,
    choose banner-only vs full-screen blocking mode, and toggle feature flags.
    """
    global _STATUS_REVISION
    row = get_or_create_system_status(db)

    if payload.maintenance is not None:
        row.maintenance = payload.maintenance
    if payload.blocking is not None:
        row.blocking = payload.blocking
    if payload.message is not None:
        row.message = payload.message
    if payload.estimatedTime is not None:
        row.estimated_time = payload.estimatedTime
    if payload.features is not None:
        row.features_json = payload.features.model_dump_json()

    row.updated_by_id = admin_user.id
    row.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(row)
    _STATUS_REVISION += 1

    return serialize_system_status(row)


@router.get("/stream")
async def stream_system_status(request: Request):
    """
    Lightweight Server-Sent Events (SSE) stream notifying connected tabs immediately
    whenever backend maintenance status changes (complements Firestore onSnapshot).
    """

    async def event_generator():
        last_payload_json = ""
        ticks = 0
        while True:
            if await request.is_disconnected():
                break
            db = SessionLocal()
            try:
                row = get_or_create_system_status(db)
                payload_json = json.dumps(
                    serialize_system_status(row).model_dump(mode="json"),
                    sort_keys=True,
                )
            finally:
                db.close()

            if payload_json != last_payload_json:
                last_payload_json = payload_json
                yield f"data: {payload_json}\n\n"
            elif ticks % 15 == 0:
                # Keep-alive comment flushes reverse proxies (e.g. Vite dev proxy)
                yield ": keep-alive\n\n"

            ticks += 1
            await asyncio.sleep(1.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
