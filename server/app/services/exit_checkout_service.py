"""Field Exit Protocol check-outs: CRUD, workflow, listing, summaries, export."""

import json
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CheckoutStatus, ClearanceDecision, District, Enumerator, ExitCheckout, Region, StaffRole, Supervisor, Team, User
from app.models.user import Role
from app.schemas.exit_checkout import (
    APPROVALS,
    CHECKLIST,
    DECISIONS,
    ITEMS,
    ApprovalRow,
    ChecklistRow,
    CheckoutIn,
    CheckoutListRow,
    CheckoutOut,
    ClearanceIn,
    ExitSummary,
    ExitSummaryRow,
    ItemRow,
)
from app.services import report_service
from app.services.scope import district_ids_for

JSON_FIELDS = {"checklist": ChecklistRow, "items": ItemRow, "approvals": ApprovalRow}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _loads(text: str | None, model) -> list:
    try:
        return [model.model_validate(x) for x in json.loads(text or "[]")]
    except (ValueError, TypeError):
        return []


def _geo(db: Session):
    return (
        {d.id: d for d in db.execute(select(District)).scalars()},
        {r.id: r for r in db.execute(select(Region)).scalars()},
        {t.id: t for t in db.execute(select(Team)).scalars()},
    )


def to_out(db: Session, r: ExitCheckout, geo=None) -> CheckoutOut:
    districts, regions, teams = geo or _geo(db)
    d = districts.get(r.district_id)
    reg = regions.get(d.region_id) if d else None
    t = teams.get(r.team_id) if r.team_id else None
    data = {c.key: getattr(r, c.key) for c in r.__table__.columns}
    for f, model in JSON_FIELDS.items():
        data[f] = _loads(getattr(r, f), model)
    data.update(district=d.name if d else "", region_id=reg.id if reg else None, region=reg.name if reg else "", team=f"{t.code} {t.name}" if t else None)
    return CheckoutOut.model_validate(data)


def _need(perms: set[str], code: str) -> None:
    if code not in perms:
        raise HTTPException(403, f"You do not have the right: {code}")


def resolve_district(db: Session, user: User, requested: int | None) -> int:
    scope = district_ids_for(db, user)
    if user.role == Role.DISTRICT_DQM:
        if not scope:
            raise HTTPException(403, "Your account has no district assigned")
        if requested is not None and requested not in scope:
            raise HTTPException(403, "You can only check out staff of your own district")
        return requested if requested is not None else scope[0]
    if requested is None:
        raise HTTPException(400, "district_id is required")
    if scope is not None and requested not in scope:
        raise HTTPException(403, "District outside your scope")
    if db.get(District, requested) is None:
        raise HTTPException(404, "District not found")
    return requested


def get_in_scope(db: Session, user: User, checkout_id: int) -> ExitCheckout:
    r = db.get(ExitCheckout, checkout_id)
    scope = district_ids_for(db, user)
    if r is None or (scope is not None and r.district_id not in scope):
        raise HTTPException(404, "Check-out not found in your scope")
    return r


def _apply(r: ExitCheckout, body: CheckoutIn, district_id: int) -> None:
    if body.team_id is not None and (r.team_id != body.team_id):
        r.team_id = body.team_id
    if body.team_id is None:
        r.team_id = None
    data = body.model_dump(exclude={"district_id", "team_id"})
    for f in JSON_FIELDS:
        data[f] = json.dumps([row.model_dump(mode="json") for row in getattr(body, f)])
    for k, v in data.items():
        setattr(r, k, v)
    r.district_id = district_id


def _check_team(db: Session, team_id: int | None, district_id: int) -> None:
    if team_id is None:
        return
    t = db.get(Team, team_id)
    if t is None or t.district_id != district_id:
        raise HTTPException(400, "Team does not belong to this district")


def create(db: Session, user: User, perms: set[str], body: CheckoutIn) -> ExitCheckout:
    _need(perms, "exit_checkouts.create")
    district_id = resolve_district(db, user, body.district_id)
    _check_team(db, body.team_id, district_id)
    r = ExitCheckout(created_by=user.id, status=CheckoutStatus.DRAFT, district_id=district_id, staff_name=body.staff_name, role=body.role)
    _apply(r, body, district_id)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def update(db: Session, user: User, perms: set[str], checkout_id: int, body: CheckoutIn) -> ExitCheckout:
    _need(perms, "exit_checkouts.edit")
    r = get_in_scope(db, user, checkout_id)
    if r.deleted_at is not None:
        raise HTTPException(409, "This check-out is deleted; restore it first")
    if r.status == CheckoutStatus.CLEARED:
        raise HTTPException(409, "A cleared check-out can no longer be edited")
    if r.status == CheckoutStatus.NATIONAL_SIGNED and "exit_checkouts.sign" not in perms:
        raise HTTPException(409, "Countersigned by National DQM; only National DQM can still edit")
    if body.district_id not in (None, r.district_id):
        raise HTTPException(400, "district cannot be changed")
    _check_team(db, body.team_id, r.district_id)
    _apply(r, body, r.district_id)
    db.commit()
    db.refresh(r)
    return r


def submit(db: Session, user: User, perms: set[str], checkout_id: int) -> ExitCheckout:
    _need(perms, "exit_checkouts.submit")
    r = get_in_scope(db, user, checkout_id)
    if r.deleted_at is not None:
        raise HTTPException(409, "This check-out is deleted")
    if r.status != CheckoutStatus.DRAFT:
        raise HTTPException(409, "Already submitted")
    missing = [n for n, _ in CHECKLIST if not any(c.n == n and c.answer for c in _loads(r.checklist, ChecklistRow))]
    if missing:
        raise HTTPException(400, f"Answer Yes or No for checklist item(s) {', '.join(map(str, missing))} before submitting")
    r.status = CheckoutStatus.SUBMITTED
    r.submitted_by = user.id
    r.submitted_at = _now()
    approvals = _loads(r.approvals, ApprovalRow)
    if not any(a.role == "DISTRICT_DQM" and a.name for a in approvals):
        approvals = [a for a in approvals if a.role != "DISTRICT_DQM"] + [ApprovalRow(role="DISTRICT_DQM", name=user.full_name, signed_on=date.today())]
        r.approvals = json.dumps([a.model_dump(mode="json") for a in approvals])
    db.commit()
    db.refresh(r)
    return r


def national_sign(db: Session, user: User, perms: set[str], checkout_id: int, comment: str | None) -> ExitCheckout:
    _need(perms, "exit_checkouts.sign")
    r = get_in_scope(db, user, checkout_id)
    if r.deleted_at is not None:
        raise HTTPException(409, "This check-out is deleted")
    if r.status == CheckoutStatus.DRAFT:
        raise HTTPException(409, "The district has not submitted this check-out yet")
    if r.status == CheckoutStatus.CLEARED:
        raise HTTPException(409, "Already cleared")
    r.status = CheckoutStatus.NATIONAL_SIGNED
    r.national_signed_by = user.id
    r.national_signed_name = user.full_name
    r.national_signed_at = _now()
    r.national_comment = comment
    approvals = [a for a in _loads(r.approvals, ApprovalRow) if a.role != "NATIONAL_DQM"]
    approvals.append(ApprovalRow(role="NATIONAL_DQM", name=user.full_name, comment=comment or "", signed_on=date.today()))
    r.approvals = json.dumps([a.model_dump(mode="json") for a in approvals])
    db.commit()
    db.refresh(r)
    return r


def clearance(db: Session, user: User, perms: set[str], checkout_id: int, body: ClearanceIn) -> ExitCheckout:
    _need(perms, "exit_checkouts.clear")
    r = get_in_scope(db, user, checkout_id)
    if r.deleted_at is not None:
        raise HTTPException(409, "This check-out is deleted")
    if r.status == CheckoutStatus.DRAFT:
        raise HTTPException(409, "The district has not submitted this check-out yet")
    if body.decision in (ClearanceDecision.CONDITIONAL, ClearanceDecision.NOT_CLEARED) and not (body.outstanding_issues or "").strip():
        raise HTTPException(400, "State the outstanding issues or conditions")
    r.decision = body.decision
    r.outstanding_issues = body.outstanding_issues
    r.deadline = body.deadline
    r.decided_name = body.decided_name or "Director, Data Science Division"
    r.decided_by = user.id
    r.decided_at = _now()
    r.status = CheckoutStatus.CLEARED
    db.commit()
    db.refresh(r)
    return r


def delete(db: Session, user: User, perms: set[str], checkout_id: int, reason: str) -> ExitCheckout:
    _need(perms, "exit_checkouts.delete")
    r = get_in_scope(db, user, checkout_id)
    if r.deleted_at is not None:
        raise HTTPException(409, "Already deleted")
    if not reason.strip():
        raise HTTPException(400, "A reason is required")
    r.deleted_at = _now()
    r.deleted_by = user.id
    r.delete_reason = reason.strip()
    db.commit()
    db.refresh(r)
    return r


def restore(db: Session, user: User, perms: set[str], checkout_id: int) -> ExitCheckout:
    _need(perms, "exit_checkouts.delete")
    r = get_in_scope(db, user, checkout_id)
    if r.deleted_at is None:
        raise HTTPException(409, "Not deleted")
    r.deleted_at = None
    r.deleted_by = None
    r.delete_reason = None
    db.commit()
    db.refresh(r)
    return r


def _scoped_query(db: Session, user: User, districts: dict, district_id: int | None, region_id: int | None):
    scope = district_ids_for(db, user)
    q = select(ExitCheckout)
    if scope is not None:
        q = q.where(ExitCheckout.district_id.in_(scope))
    if district_id:
        q = q.where(ExitCheckout.district_id == district_id)
    if region_id:
        q = q.where(ExitCheckout.district_id.in_([d.id for d in districts.values() if d.region_id == region_id]))
    return q


def list_checkouts(db: Session, user: User, district_id: int | None, region_id: int | None, role: StaffRole | None, status: CheckoutStatus | None, decision: ClearanceDecision | None, search: str | None, deleted: bool = False) -> list[CheckoutListRow]:
    districts, regions, teams = _geo(db)
    q = _scoped_query(db, user, districts, district_id, region_id).order_by(ExitCheckout.updated_at.desc())
    q = q.where(ExitCheckout.deleted_at.is_not(None)) if deleted else q.where(ExitCheckout.deleted_at.is_(None))
    if role:
        q = q.where(ExitCheckout.role == role)
    if status:
        q = q.where(ExitCheckout.status == status)
    if decision:
        q = q.where(ExitCheckout.decision == decision)
    if search:
        like = f"%{search}%"
        q = q.where(ExitCheckout.staff_name.ilike(like) | ExitCheckout.login_id.ilike(like) | ExitCheckout.sa_ea_codes.ilike(like))
    out = []
    for r in db.execute(q).scalars():
        d = districts.get(r.district_id)
        t = teams.get(r.team_id) if r.team_id else None
        out.append(
            CheckoutListRow(
                id=r.id, district_id=r.district_id, district=d.name if d else "", region=regions[d.region_id].name if d and d.region_id in regions else "",
                team=f"{t.code} {t.name}" if t else None, staff_name=r.staff_name, login_id=r.login_id, role=r.role, status=r.status,
                checklist_no=sum(1 for c in _loads(r.checklist, ChecklistRow) if c.answer == "NO"),
                items_missing=sum(1 for i in _loads(r.items, ItemRow) if i.returned is False),
                decision=r.decision, deadline=r.deadline, submitted_at=r.submitted_at, updated_at=r.updated_at, deleted_at=r.deleted_at,
            )
        )
    return out


# ---- Summaries -------------------------------------------------------------


def _zero(key: int, label: str) -> ExitSummaryRow:
    return ExitSummaryRow(key=key, label=label, total=0, enumerators=0, supervisors=0, draft=0, submitted=0, national_signed=0, cleared=0, cleared_payment=0, cleared_redeployment=0, conditional=0, not_cleared=0, checklist_no=[0] * 12, items_missing=[0] * 7, overdue_conditions=0)


def _add(row: ExitSummaryRow, r: ExitCheckout, today: date) -> None:
    row.total += 1
    if r.role == StaffRole.ENUMERATOR:
        row.enumerators += 1
    else:
        row.supervisors += 1
    setattr(row, r.status.value.lower(), getattr(row, r.status.value.lower()) + 1)
    if r.decision:
        setattr(row, r.decision.value.lower(), getattr(row, r.decision.value.lower()) + 1)
        if r.decision in (ClearanceDecision.CONDITIONAL, ClearanceDecision.NOT_CLEARED) and r.deadline and r.deadline < today:
            row.overdue_conditions += 1
    for c in _loads(r.checklist, ChecklistRow):
        if c.answer == "NO" and 1 <= c.n <= 12:
            row.checklist_no[c.n - 1] += 1
    codes = [code for code, _ in ITEMS]
    for i in _loads(r.items, ItemRow):
        if i.returned is False and i.item in codes:
            row.items_missing[codes.index(i.item)] += 1


def _sum_rows(rows: list[ExitSummaryRow], label: str = "Total") -> ExitSummaryRow:
    t = _zero(0, label)
    for row in rows:
        for f in ("total", "enumerators", "supervisors", "draft", "submitted", "national_signed", "cleared", "cleared_payment", "cleared_redeployment", "conditional", "not_cleared", "overdue_conditions"):
            setattr(t, f, getattr(t, f) + getattr(row, f))
        t.checklist_no = [a + b for a, b in zip(t.checklist_no, row.checklist_no)]
        t.items_missing = [a + b for a, b in zip(t.items_missing, row.items_missing)]
    return t


def summary(db: Session, user: User, level: str, district_id: int | None, region_id: int | None) -> ExitSummary:
    districts, regions, _ = _geo(db)
    scope = district_ids_for(db, user)
    today = date.today()
    if level == "national":
        if user.role not in (Role.NATIONAL_DQM, Role.ADMIN):
            raise HTTPException(403, "The national summary is for National DQM")
        in_scope = list(districts.values())
        units = {r.id: r.name for r in regions.values()}
        unit_of = lambda d: d.region_id  # noqa: E731
        unit_label, title = "Region", "National"
    elif level == "region":
        if user.role == Role.REGIONAL:
            mine = {districts[d].region_id for d in (scope or []) if d in districts}
            if region_id is None and len(mine) == 1:
                region_id = next(iter(mine))
            if region_id not in mine:
                raise HTTPException(403, "Region outside your scope")
        if region_id is None or region_id not in regions:
            raise HTTPException(400, "region_id is required")
        in_scope = [d for d in districts.values() if d.region_id == region_id and (scope is None or d.id in scope)]
        units = {d.id: d.name for d in in_scope}
        unit_of = lambda d: d.id  # noqa: E731
        unit_label, title = "District", regions[region_id].name
    else:
        if district_id is None:
            if scope and len(scope) == 1:
                district_id = scope[0]
            else:
                raise HTTPException(400, "district_id is required")
        if district_id not in districts or (scope is not None and district_id not in scope):
            raise HTTPException(403, "District outside your scope")
        in_scope = [districts[district_id]]
        units = {district_id: districts[district_id].name}
        unit_of = lambda d: d.id  # noqa: E731
        unit_label, title = "District", districts[district_id].name

    ids = [d.id for d in in_scope]
    rows = {k: _zero(k, v) for k, v in sorted(units.items(), key=lambda kv: kv[1])}
    per_district = {d.id: _zero(d.id, d.name) for d in sorted(in_scope, key=lambda x: x.name)}
    for r in db.execute(select(ExitCheckout).where(ExitCheckout.district_id.in_(ids), ExitCheckout.deleted_at.is_(None))).scalars():
        d = districts.get(r.district_id)
        if d is None:
            continue
        key = unit_of(d)
        if key in rows:
            _add(rows[key], r, today)
        _add(per_district[r.district_id], r, today)
    expected = None
    if ids:
        team_ids = [t.id for t in db.execute(select(Team).where(Team.district_id.in_(ids))).scalars()]
        if team_ids:
            sup = db.execute(select(func.count()).select_from(Supervisor).where(Supervisor.team_id.in_(team_ids), Supervisor.active.is_(True))).scalar_one()
            enum = db.execute(select(func.count()).select_from(Enumerator).where(Enumerator.team_id.in_(team_ids), Enumerator.active.is_(True))).scalar_one()
            expected = sup + enum
    return ExitSummary(
        level=level, unit_label=unit_label, title=title, rows=list(rows.values()), districts=list(per_district.values()),
        totals=_sum_rows(list(rows.values())), checklist_labels=[t for _, t in CHECKLIST], item_labels=[t for _, t in ITEMS], expected_staff=expected,
    )


# ---- Export -----------------------------------------------------------------


def export_checkout(db: Session, user: User, checkout_id: int) -> report_service.Report:
    r = get_in_scope(db, user, checkout_id)
    o = to_out(db, r)
    f = lambda v: "" if v is None else v  # noqa: E731
    checklist = {c.n: c for c in o.checklist}
    items = {i.item: i for i in o.items}
    approvals = {a.role: a for a in o.approvals}
    sheets = [
        report_service.Sheet("A. Field staff details", ["Field", "Value"], [
            ["Name of field staff", o.staff_name], ["Login ID", f(o.login_id)], ["Role", o.role.value.title()], ["Region / District", f"{o.region} / {o.district}"],
            ["SA / EA code(s)", f(o.sa_ea_codes)], ["Team", f(o.team)], ["Status", o.status.value.replace("_", " ").title()],
        ]),
        report_service.Sheet("B. Workload completion", ["#", "Clearance requirement", "Yes", "No", "Remarks"], [
            [n, text, "X" if checklist.get(n) and checklist[n].answer == "YES" else "", "X" if checklist.get(n) and checklist[n].answer == "NO" else "", checklist[n].remarks if checklist.get(n) else ""] for n, text in CHECKLIST
        ] + [["", "Comment on the integrity, conduct and attitude of the enumerator", "", "", f(o.enumerator_conduct)]]),
        report_service.Sheet("C. Final sync and retrieval", ["Item issued", "Returned", "Condition / remarks", "Final clearance status"], [
            [text, "Yes" if items.get(code) and items[code].returned else ("No" if items.get(code) and items[code].returned is False else ""), items[code].condition if items.get(code) else "", items[code].clearance if items.get(code) else ""] for code, text in ITEMS
        ] + [["Comment on the integrity, conduct and attitude of the supervisor", "", f(o.supervisor_conduct), ""]]),
        report_service.Sheet("Certification and approval", ["Role", "Name", "Comment", "Signed on"], [
            [text, approvals[code].name if approvals.get(code) else "", approvals[code].comment if approvals.get(code) else "", approvals[code].signed_on.isoformat() if approvals.get(code) and approvals[code].signed_on else ""] for code, text in APPROVALS
        ]),
        report_service.Sheet("D. Clearance", ["Decision and approval by Director, Data Science Division", "Value"], [
            [label, "X" if o.decision and o.decision.value == code else ""] for code, label in DECISIONS.items()
        ] + [["Outstanding issues or conditions", f(o.outstanding_issues)], ["Deadline for resolving outstanding issues", o.deadline.isoformat() if o.deadline else ""], ["Decided by", f(o.decided_name)], ["Recorded", report_service._fmt(o.decided_at)]]),
    ]
    return report_service.Report(kind="exit_checkout", title=f"DQM Check-Out - {o.staff_name} ({o.role.value.title()}) - {o.district}", sheets=sheets, generated_at=_now(), filters=f"district={o.district}")


def export_summary(s: ExitSummary) -> report_service.Report:
    headers = ["Unit", "Total", "Enumerators", "Supervisors", "Draft", "Submitted", "Countersigned", "Cleared", "Payment", "Redeployment", "Conditional", "Not cleared", "Overdue conditions"] + [f"No: {i + 1}" for i in range(12)] + [f"Missing: {t}" for t in s.item_labels]
    def row(x: ExitSummaryRow):
        return [x.label, x.total, x.enumerators, x.supervisors, x.draft, x.submitted, x.national_signed, x.cleared, x.cleared_payment, x.cleared_redeployment, x.conditional, x.not_cleared, x.overdue_conditions] + x.checklist_no + x.items_missing
    title = "Field Exit Protocol - National summary" if s.level == "national" else f"Field Exit Protocol - {s.title} summary"
    return report_service.Report(kind="exit_summary", title=title, sheets=[report_service.Sheet("Summary", headers, [row(r) for r in s.rows] + [row(s.totals)], landscape=True), report_service.Sheet("Checklist", ["#", "Requirement"], [[i + 1, t] for i, t in enumerate(s.checklist_labels)])], generated_at=_now(), filters=f"level={s.level}")
