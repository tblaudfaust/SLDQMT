"""Downloadable resources (user manual, tablet app) for signed-in users.

Files live in settings.RESOURCES_DIR on the server (mounted from /opt/sldqmt/downloads
in production). A signed-in user asks for a short-lived link, which the browser can then
open in a new tab or download without a bearer header; the link is bound to the user and
the file and expires after ten minutes. Every link issued is written to the audit log.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import audit, get_current_user, get_db
from app.core.config import settings
from app.models.user import User

router = APIRouter(prefix="/resources", tags=["resources"])

LINK_MINUTES = 10

# key -> (file name on disk, media type, disposition, title, description)
RESOURCES: dict[str, tuple[str, str, str, str, str]] = {
    "manual-pdf": (
        "SLPHC-2026-Field-Monitor-User-Manual.pdf",
        "application/pdf",
        "inline",
        "User Operational Manual (PDF)",
        "Opens in a new tab. How to use the tablet app, the dashboard, the Daily DQM Reporting Tool and the Field Exit Protocol, with screenshots.",
    ),
    "manual-docx": (
        "SLPHC-2026-Field-Monitor-User-Manual.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "attachment",
        "User Operational Manual (Word)",
        "The same manual as an editable Word document.",
    ),
    "app-apk": (
        "SLPHC-FieldMonitor.apk",
        "application/vnd.android.package-archive",
        "attachment",
        "Tablet app for Field Monitors (Android APK)",
        "Install on the tablet, then sign in once online and choose a PIN. Android 8.0 or newer.",
    ),
}


class ResourceOut(BaseModel):
    key: str
    title: str
    description: str
    file_name: str
    kind: str  # pdf | docx | apk
    opens_in_tab: bool
    available: bool
    size_bytes: int | None = None
    updated_at: datetime | None = None


class LinkOut(BaseModel):
    url: str
    expires_in_seconds: int


def _path(key: str) -> Path:
    if key not in RESOURCES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown resource")
    return Path(settings.RESOURCES_DIR) / RESOURCES[key][0]


@router.get("", response_model=list[ResourceOut])
def list_resources(_: User = Depends(get_current_user)):
    out = []
    for key, (name, _media, disposition, title, description) in RESOURCES.items():
        p = Path(settings.RESOURCES_DIR) / name
        exists = p.is_file()
        out.append(
            ResourceOut(
                key=key,
                title=title,
                description=description,
                file_name=name,
                kind=name.rsplit(".", 1)[-1],
                opens_in_tab=disposition == "inline",
                available=exists,
                size_bytes=p.stat().st_size if exists else None,
                updated_at=datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc) if exists else None,
            )
        )
    return out


@router.post("/{key}/link", response_model=LinkOut)
def make_link(key: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    path = _path(key)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This file has not been uploaded to the server yet")
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": str(user.id), "type": "resource", "file": key, "iat": now, "exp": now + timedelta(minutes=LINK_MINUTES)},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    audit(db, user, "resource.download", "file", RESOURCES[key][0], {"resource": key}, request)
    db.commit()
    return LinkOut(url=f"{settings.API_V1_PREFIX}/resources/{key}/file?t={token}", expires_in_seconds=LINK_MINUTES * 60)


@router.get("/{key}/file")
def get_file(key: str, t: str = Query(..., description="Link token from POST /resources/{key}/link")):
    path = _path(key)
    try:
        claims = jwt.decode(t, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This download link has expired. Open the resource again from the dashboard.")
    if claims.get("type") != "resource" or claims.get("file") != key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid download link")
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This file has not been uploaded to the server yet")
    name, media, disposition, _title, _desc = RESOURCES[key]
    return FileResponse(path, media_type=media, filename=name, content_disposition_type=disposition)
