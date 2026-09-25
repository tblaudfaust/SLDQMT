from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import audit, require_perm
from app.api.v1.dashboard import filters
from app.db.session import get_db
from app.models import User
from app.schemas.dashboard import Filters
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


require_web = require_perm("reports.export")


@router.get("")
def kinds(user: User = Depends(require_web)):
    return [{"kind": k, "title": v} for k, v in report_service.REPORT_KINDS.items()]


@router.get("/{kind}")
def generate(
    kind: str,
    format: str = Query(default="xlsx", pattern="^(xlsx|pdf)$"),
    error_id: str | None = None,
    f: Filters = Depends(filters),
    db: Session = Depends(get_db),
    user: User = Depends(require_web),
):
    try:
        report = report_service.build(db, user, kind, f, error_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    audit(db, user, "report.generate", "report", kind, report.filters)
    db.commit()
    stamp = report.generated_at.strftime("%Y%m%d-%H%M")
    if format == "pdf":
        data = report_service.to_pdf(report)
        media = "application/pdf"
        name = f"{kind}-{stamp}.pdf"
    else:
        data = report_service.to_xlsx(report)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        name = f"{kind}-{stamp}.xlsx"
    return Response(content=data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})
