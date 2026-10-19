"""M&E Field Tool: the KPI reports the M&E team syncs from the field, the geography bundle they cache
for offline use, and the summary by district, phase, week and officer with its export."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import me_kpi_form as form
from app.models import District, Enumerator, EnumerationArea, MeKpiReport, Region, Supervisor, Team, User
from app.models.mefm import MefmChiefdom, MefmSection
from app.schemas.me_kpi import Attention, CountRow, GeoBundle, GeoChiefdom, GeoDistrict, GeoEa, GeoSection, GeoTeam, GroupRow, ReportIn, ReportOut, Summary, SyncIn, SyncOut, SyncResult
from app.services import report_service
from app.services.scope import district_ids_for

R = MeKpiReport


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _mean(values, digits=1) -> float | None:
    xs = [v for v in values if v is not None]
    return round(sum(xs) / len(xs), digits) if xs else None


def _share(rows, pred) -> float | None:
    xs = [pred(x) for x in rows]
    xs = [x for x in xs if x is not None]
    return round(100.0 * sum(1 for x in xs if x) / len(xs), 1) if xs else None


# ---- geography bundle --------------------------------------------------------------------------------


def geo_version(db: Session, scope: list[int] | None) -> str:
    parts = []
    for model in (District, MefmChiefdom, MefmSection, Team, Supervisor, Enumerator, EnumerationArea):
        count, latest = db.execute(select(func.count(), func.max(model.updated_at))).one()
        parts.append(f"{model.__tablename__}:{count}:{latest}")
    parts.append("scope:" + (",".join(map(str, scope)) if scope is not None else "all"))
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


def geo(db: Session, user: User) -> GeoBundle:
    """Regions, districts, chiefdoms, sections and SAs (with EA and enumerator counts) in the officer's scope."""
    scope = district_ids_for(db, user)
    dq = select(District).order_by(District.name)
    if scope is not None:
        dq = dq.where(District.id.in_(scope))
    districts = db.execute(dq).scalars().all()
    ids = [d.id for d in districts]
    regions = {r.id: r.name for r in db.execute(select(Region)).scalars()}
    if not ids:
        return GeoBundle(version=geo_version(db, scope), generated_at=_now(), districts=[], chiefdoms=[], sections=[], teams=[])
    chiefdoms = db.execute(select(MefmChiefdom).where(MefmChiefdom.district_id.in_(ids), MefmChiefdom.active.is_(True)).order_by(MefmChiefdom.name)).scalars().all()
    sections = db.execute(select(MefmSection).where(MefmSection.district_id.in_(ids), MefmSection.active.is_(True)).order_by(MefmSection.name)).scalars().all()
    teams = db.execute(select(Team).where(Team.district_id.in_(ids), Team.active.is_(True)).order_by(Team.code)).scalars().all()
    team_ids = [t.id for t in teams]
    sup: dict[int, str] = {}
    enums: dict[int, int] = defaultdict(int)
    eas: dict[int, dict] = defaultdict(lambda: {"eas": 0, "urban": 0, "rural": 0, "hh": 0, "hh_known": False})
    if team_ids:
        for s in db.execute(select(Supervisor).where(Supervisor.team_id.in_(team_ids), Supervisor.active.is_(True))).scalars():
            sup.setdefault(s.team_id, s.name)
        for tid, n in db.execute(select(Enumerator.team_id, func.count()).where(Enumerator.team_id.in_(team_ids), Enumerator.active.is_(True)).group_by(Enumerator.team_id)):
            enums[tid] = n
        for e in db.execute(select(EnumerationArea.team_id, EnumerationArea.loc_status, EnumerationArea.expected_households, EnumerationArea.households).where(EnumerationArea.team_id.in_(team_ids), EnumerationArea.active.is_(True))):
            d = eas[e.team_id]
            d["eas"] += 1
            if e.loc_status == "2":
                d["urban"] += 1
            elif e.loc_status == "1":
                d["rural"] += 1
            hh = e.expected_households if e.expected_households is not None else e.households
            if hh is not None:
                d["hh"] += hh
                d["hh_known"] = True
    # the EA list travels with the bundle for a district or a region (a few thousand rows); nationally it is fetched per SA
    on_demand = len(teams) > EAS_INLINE_MAX_TEAMS
    ea_rows = [] if on_demand or not team_ids else [_geo_ea(e) for e in db.execute(select(EnumerationArea).where(EnumerationArea.team_id.in_(team_ids), EnumerationArea.active.is_(True)).order_by(EnumerationArea.code)).scalars()]
    return GeoBundle(
        version=geo_version(db, scope), generated_at=_now(), eas=ea_rows, eas_on_demand=on_demand,
        districts=[GeoDistrict(id=d.id, code=d.code, name=d.name, region=regions.get(d.region_id, "")) for d in districts],
        chiefdoms=[GeoChiefdom(id=c.id, district_id=c.district_id, code=c.code, name=c.name) for c in chiefdoms],
        sections=[GeoSection(id=s.id, district_id=s.district_id, chiefdom_id=s.chiefdom_id, code=s.code, name=s.name) for s in sections],
        teams=[GeoTeam(id=t.id, district_id=t.district_id, code=t.code, name=t.name, chiefdom=t.chiefdom, supervisor=sup.get(t.id), enumerators=enums.get(t.id, 0), eas=eas[t.id]["eas"], eas_urban=eas[t.id]["urban"], eas_rural=eas[t.id]["rural"], expected_households=eas[t.id]["hh"] if eas[t.id]["hh_known"] else None) for t in teams],
    )


EAS_INLINE_MAX_TEAMS = 1500


def _geo_ea(e: EnumerationArea) -> GeoEa:
    hh = e.expected_households if e.expected_households is not None else e.households
    return GeoEa(team_id=e.team_id, code=e.code, name=e.name, locality=e.locality, urban=None if e.loc_status not in ("1", "2") else e.loc_status == "2", households=hh)


def eas_for_team(db: Session, user: User, team_id: int) -> list[GeoEa]:
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(404, "SA not found")
    _scope_check(db, user, team.district_id)
    return [_geo_ea(e) for e in db.execute(select(EnumerationArea).where(EnumerationArea.team_id == team_id, EnumerationArea.active.is_(True)).order_by(EnumerationArea.code)).scalars()]


# ---- reports -----------------------------------------------------------------------------------------


def _scope_check(db: Session, user: User, district_id: int | None) -> None:
    scope = district_ids_for(db, user)
    if scope is not None and (district_id is None or district_id not in scope):
        raise HTTPException(403, "This district is outside your area")


def _apply(x: R, body: ReportIn, user: User) -> list[str]:
    if body.report_date > date.today():
        return ["The report date cannot be in the future"]
    clean, errors = form.validate(body.phase, body.answers)
    if body.phase in ("L", "E") and not body.team_id and not body.sa_code:
        errors.append("Choose the SA")
    if body.lat is None or body.lng is None:
        errors.append("GPS position is required")
    if errors:
        return errors
    m = form.metrics(clean)
    x.phase, x.report_date, x.week = body.phase, body.report_date, body.week
    x.district_id, x.chiefdom, x.section, x.team_id = body.district_id, (body.chiefdom or "").strip() or None, (body.section or "").strip() or None, body.team_id
    x.sa_code, x.practice_team = (body.sa_code or "").strip() or None, (body.practice_team or "").strip() or None
    x.ea_codes = json.dumps(sorted({c.strip() for c in body.ea_codes if c and c.strip()})[:60]) if body.ea_codes else None
    x.respondent_name, x.respondent_role = (body.respondent_name or "").strip() or None, body.respondent_role or None
    x.eas_urban, x.eas_rural, x.enumerators, x.capi_version = body.eas_urban, body.eas_rural, body.enumerators, (body.capi_version or "").strip() or None
    x.lat, x.lng, x.device = body.lat, body.lng, (body.device or "").strip() or None
    x.answers = json.dumps(clean)
    x.coverage_pct, x.synced_pct, x.error_pct, x.tablets_pct = m["coverage_pct"], m["synced_pct"], m["error_pct"], m["tablets_pct"]
    x.overall, x.safety_concern, x.escalation = m["overall"], m["safety_concern"], m["escalation"]
    return []


def sync(db: Session, user: User, body: SyncIn, can_manage: bool) -> SyncOut:
    """Upsert by client_id: a device may send the same report again after a lost connection, or a correction."""
    out = SyncOut(results=[])
    for rep in body.reports:
        try:
            if rep.district_id is not None:
                _scope_check(db, user, rep.district_id)
            elif rep.phase in ("L", "E"):
                raise HTTPException(422, "Choose the district")
            x = db.execute(select(R).where(R.client_id == rep.client_id)).scalars().first()
            if x is None:
                x = R(client_id=rep.client_id, user_id=user.id, submitted_at=rep.submitted_at or _now())
                status = "created"
            else:
                if x.user_id != user.id and not can_manage:
                    raise HTTPException(403, "This report belongs to another officer")
                if x.deleted:
                    x.deleted = False
                x.edited_by = user.id if x.user_id != user.id else None
                status = "updated"
            errors = _apply(x, rep, user)
            if errors:
                raise HTTPException(422, "; ".join(errors))
            db.add(x)
            db.flush()
            out.results.append(SyncResult(client_id=rep.client_id, id=x.id, status=status))
            if status == "created":
                out.created += 1
            else:
                out.updated += 1
        except HTTPException as e:
            db.rollback() if False else None  # per-report errors do not undo the others; nothing was added for this one
            out.results.append(SyncResult(client_id=rep.client_id, status="error", message=str(e.detail)))
            out.errors += 1
    return out


def get(db: Session, user: User, report_id: int) -> R:
    x = db.get(R, report_id)
    if x is None or x.deleted:
        raise HTTPException(404, "Report not found")
    scope = district_ids_for(db, user)
    if scope is not None and x.district_id not in scope and x.user_id != user.id:
        raise HTTPException(403, "This report is outside your area")
    return x


def edit(db: Session, user: User, x: R, body: ReportIn) -> R:
    if body.district_id is not None:
        _scope_check(db, user, body.district_id)
    errors = _apply(x, body, user)
    if errors:
        raise HTTPException(422, "; ".join(errors))
    x.edited_by = user.id
    db.flush()
    return x


def delete(db: Session, x: R) -> None:
    x.deleted = True
    db.flush()


class Names:
    def __init__(self, db: Session, rows: list[R]):
        dids = {x.district_id for x in rows if x.district_id}
        tids = {x.team_id for x in rows if x.team_id}
        uids = {x.user_id for x in rows} | {x.edited_by for x in rows if x.edited_by}
        regions = {r.id: r.name for r in db.execute(select(Region)).scalars()}
        self.districts = {d.id: (d.name, regions.get(d.region_id, "")) for d in db.execute(select(District).where(District.id.in_(dids))).scalars()} if dids else {}
        self.teams = {t.id: (t.code, t.name) for t in db.execute(select(Team).where(Team.id.in_(tids))).scalars()} if tids else {}
        self.users = {u.id: u.full_name for u in db.execute(select(User).where(User.id.in_(uids))).scalars()} if uids else {}


def to_out(x: R, n: Names) -> ReportOut:
    answers = json.loads(x.answers or "{}")
    d = n.districts.get(x.district_id or 0)
    t = n.teams.get(x.team_id or 0)
    return ReportOut(
        id=x.id, client_id=x.client_id, phase=x.phase, phase_label=form.PHASE_LABEL.get(x.phase, x.phase), report_date=x.report_date, week=x.week, district_id=x.district_id,
        district=d[0] if d else None, region=d[1] if d else None, chiefdom=x.chiefdom, section=x.section, team_id=x.team_id, sa_code=x.sa_code or (t[0] if t else None), sa_name=t[1] if t else None, ea_codes=json.loads(x.ea_codes) if x.ea_codes else [],
        practice_team=x.practice_team, respondent_name=x.respondent_name, respondent_role=x.respondent_role, respondent_role_label=form.ROLE_LABEL.get(x.respondent_role or "", x.respondent_role),
        eas_urban=x.eas_urban, eas_rural=x.eas_rural, enumerators=x.enumerators, capi_version=x.capi_version, lat=x.lat, lng=x.lng, answers=answers, metrics=form.metrics(answers),
        officer=n.users.get(x.user_id), user_id=x.user_id, submitted_at=x.submitted_at, updated_at=x.updated_at, edited_by_name=n.users.get(x.edited_by or 0),
    )


def query(db: Session, user: User, phase: str | None = None, district_id: int | None = None, team_id: int | None = None, week: int | None = None, officer_id: int | None = None,
          date_from: date | None = None, date_to: date | None = None, mine: bool = False) -> list[R]:
    q = select(R).where(R.deleted.is_(False))
    scope = district_ids_for(db, user)
    if scope is not None:
        q = q.where((R.district_id.in_(scope)) | (R.user_id == user.id))
    if mine:
        q = q.where(R.user_id == user.id)
    if phase:
        q = q.where(R.phase == phase)
    if district_id:
        q = q.where(R.district_id == district_id)
    if team_id:
        q = q.where(R.team_id == team_id)
    if week:
        q = q.where(R.week == week)
    if officer_id:
        q = q.where(R.user_id == officer_id)
    if date_from:
        q = q.where(R.report_date >= date_from)
    if date_to:
        q = q.where(R.report_date <= date_to)
    return db.execute(q.order_by(R.report_date.desc(), R.submitted_at.desc())).scalars().all()


# ---- summary -----------------------------------------------------------------------------------------


def _answers(x: R) -> dict:
    return json.loads(x.answers or "{}")


def _group(rows: list[R], key, label, n: Names) -> list[GroupRow]:
    buckets: dict[str, list[R]] = defaultdict(list)
    labels: dict[str, str] = {}
    for x in rows:
        k = key(x)
        buckets[k].append(x)
        labels.setdefault(k, label(x))
    out = []
    for k, xs in buckets.items():
        ans = [_answers(x) for x in xs]
        out.append(GroupRow(
            key=k, label=labels[k], reports=len(xs), sas=len({(x.team_id, x.sa_code, x.practice_team) for x in xs}), officers=len({x.user_id for x in xs}),
            coverage_pct=_mean([x.coverage_pct for x in xs]), synced_pct=_mean([x.synced_pct for x in xs]), error_pct=_mean([x.error_pct for x in xs]), tablets_pct=_mean([x.tablets_pct for x in xs]),
            informed_pct=_share(ans, lambda a: (a.get("k1_1") == "1") if a.get("k1_1") else None), support_pct=_share(ans, lambda a: (a.get("k2_5") == "1") if a.get("k2_5") else None),
            on_schedule_pct=_share(ans, lambda a: (a.get("k5_2") == "1") if a.get("k5_2") else None), overall=_mean([x.overall for x in xs], 2),
            safety_concerns=sum(1 for x in xs if x.safety_concern), escalations=sum(1 for x in xs if x.escalation),
        ))
    return out


def _counts(ans: list[dict], code: str) -> list[CountRow]:
    it = form.ITEMS[code]
    n = len(ans)
    return [CountRow(code=o["value"], label=o["label"], count=sum(1 for a in ans if o["value"] in (a.get(code) or [])), pct=round(100.0 * sum(1 for a in ans if o["value"] in (a.get(code) or [])) / n, 1) if n else None) for o in it["options"]]


def summary(db: Session, user: User, **filters) -> Summary:
    rows = query(db, user, **filters)
    n = Names(db, rows)
    ans = [_answers(x) for x in rows]
    scope = district_ids_for(db, user)
    attention: list[Attention] = []
    for x, a in zip(rows, ans):
        reasons = []
        if x.synced_pct is not None and x.synced_pct < 80:
            reasons.append(f"Only {x.synced_pct}% synced")
        if x.error_pct is not None and x.error_pct > 5:
            reasons.append(f"Error rate {x.error_pct}%")
        if x.tablets_pct is not None and x.tablets_pct < 90:
            reasons.append(f"Tablets working {x.tablets_pct}%")
        if a.get("k5_2") == "3":
            reasons.append("Behind by 3 days or more")
        if a.get("k3_6") == "1":
            reasons.append("Enumerator will not finish on time")
        if x.safety_concern:
            reasons.append("Safety / security concern")
        if a.get("k2_2") == "2":
            reasons.append("Respondents do not trust the enumerators")
        if x.escalation:
            reasons.append("Escalation requested")
        if x.overall is not None and x.overall <= 2:
            reasons.append("Rated weak or poor")
        if reasons:
            t = n.teams.get(x.team_id or 0)
            attention.append(Attention(report_id=x.id, report_date=x.report_date, phase=x.phase, district=(n.districts.get(x.district_id or 0) or (None,))[0], sa=x.sa_code or (t[0] if t else x.practice_team), officer=n.users.get(x.user_id), reasons=reasons))
    district_of = lambda x: (n.districts.get(x.district_id or 0) or ("No district",))[0]  # noqa: E731
    overall_counts = [CountRow(code=v, label=lb, count=sum(1 for x in rows if x.overall == int(v)), pct=round(100.0 * sum(1 for x in rows if x.overall == int(v)) / len(rows), 1) if rows else None) for v, lb in form.RATING]
    return Summary(
        scope="national" if scope is None else ", ".join(sorted((n.districts.get(i) or (str(i),))[0] for i in scope) if False else [d.name for d in db.execute(select(District).where(District.id.in_(scope))).scalars()]) or "no district",
        reports=len(rows), sas=len({(x.team_id, x.sa_code, x.practice_team) for x in rows}), districts=len({x.district_id for x in rows if x.district_id}), officers=len({x.user_id for x in rows}),
        last_date=max((x.report_date for x in rows), default=None),
        coverage_pct=_mean([x.coverage_pct for x in rows]), synced_pct=_mean([x.synced_pct for x in rows]), error_pct=_mean([x.error_pct for x in rows]), tablets_pct=_mean([x.tablets_pct for x in rows]),
        reinterview_pct=_mean([form.metrics(a)["reinterview_pct"] for a in ans]),
        informed_pct=_share(ans, lambda a: (a.get("k1_1") == "1") if a.get("k1_1") else None), aware_pct=_share(ans, lambda a: (a.get("k2_1") in ("1", "2")) if a.get("k2_1") else None),
        trust_pct=_share(ans, lambda a: (a.get("k2_2") == "1") if a.get("k2_2") else None), support_pct=_share(ans, lambda a: (a.get("k2_5") == "1") if a.get("k2_5") else None),
        channel_pct=_share(ans, lambda a: (a.get("k1_5") == "1") if a.get("k1_5") else None), on_schedule_pct=_share(ans, lambda a: (a.get("k5_2") == "1") if a.get("k5_2") else None),
        overall=_mean([x.overall for x in rows], 2), safety_concerns=sum(1 for x in rows if x.safety_concern), escalations=sum(1 for x in rows if x.escalation), follow_ups=sum(1 for a in ans if a.get("b3") == "1"),
        by_phase=sorted(_group(rows, lambda x: x.phase, lambda x: form.PHASE_LABEL.get(x.phase, x.phase), n), key=lambda g: ["MT", "TOT", "L", "E"].index(g.key) if g.key in ("MT", "TOT", "L", "E") else 9),
        by_district=sorted(_group(rows, lambda x: str(x.district_id or 0), district_of, n), key=lambda g: g.label),
        by_week=sorted(_group([x for x in rows if x.week], lambda x: str(x.week), lambda x: f"Week {x.week}", n), key=lambda g: int(g.key)),
        by_officer=sorted(_group(rows, lambda x: str(x.user_id), lambda x: n.users.get(x.user_id, "?"), n), key=lambda g: g.label),
        channels=_counts(ans, "k1_2"), blockers=_counts(ans, "k6_2"), error_types=_counts(ans, "k7_3"), risks=_counts(ans, "k11_6"), overall_counts=overall_counts,
        attention=attention[:50], latest=[to_out(x, n) for x in rows[:20]],
    )


def export(db: Session, user: User, **filters) -> report_service.Report:
    d = summary(db, user, **filters)
    rows = query(db, user, **filters)
    n = Names(db, rows)
    outs = [to_out(x, n) for x in rows]
    g_headers = ["Group", "Reports", "SAs", "Officers", "Coverage %", "Synced %", "Error rate %", "Tablets working %", "Community informed %", "Leaders support %", "On schedule %", "Overall (1-4)", "Safety concerns", "Escalations"]
    g_rows = lambda gs: [[g.label, g.reports, g.sas, g.officers, g.coverage_pct, g.synced_pct, g.error_pct, g.tablets_pct, g.informed_pct, g.support_pct, g.on_schedule_pct, g.overall, g.safety_concerns, g.escalations] for g in gs]  # noqa: E731
    item_cols = [(code, it["text"]) for s in form.SECTIONS for it in s["items"] for code in [it["code"]]]
    headers = ["Date", "Phase", "Week", "Region", "District", "Chiefdom", "Section", "SA code", "SA name", "EAs visited", "Practice team", "Respondent", "Role", "EAs urban", "EAs rural", "Enumerators", "CAPI version", "Officer", "Coverage %", "Synced %", "Error rate %", "Tablets %", "Overall", *[t for _, t in item_cols], *[f"{t} · detail" for c, t in item_cols if form.ITEMS[c].get("detail")], "Sent"]
    reg = []
    for x in outs:
        a = x.answers
        reg.append([x.report_date, x.phase_label, x.week, x.region, x.district, x.chiefdom, x.section, x.sa_code, x.sa_name, ", ".join(x.ea_codes), x.practice_team, x.respondent_name, x.respondent_role_label, x.eas_urban, x.eas_rural, x.enumerators, x.capi_version, x.officer,
                    x.metrics.get("coverage_pct"), x.metrics.get("synced_pct"), x.metrics.get("error_pct"), x.metrics.get("tablets_pct"), x.metrics.get("overall"),
                    *[form.label(c, a.get(c)) for c, _ in item_cols], *[a.get(c + "_detail", "") for c, _ in item_cols if form.ITEMS[c].get("detail")], x.submitted_at])
    summary_rows = [["Scope", d.scope], ["Reports", d.reports], ["SAs / teams", d.sas], ["Districts", d.districts], ["Officers", d.officers], ["Coverage %", d.coverage_pct], ["Synced %", d.synced_pct], ["Error rate %", d.error_pct],
                    ["Tablets working %", d.tablets_pct], ["Re-interviews completed %", d.reinterview_pct], ["Community informed %", d.informed_pct], ["Households aware (all / most) %", d.aware_pct], ["Respondents trust enumerators %", d.trust_pct],
                    ["Leaders support %", d.support_pct], ["Feedback channel exists %", d.channel_pct], ["Teams on schedule %", d.on_schedule_pct], ["Overall rating (1-4)", d.overall], ["Safety concerns", d.safety_concerns], ["Escalations", d.escalations], ["Follow-up visits needed", d.follow_ups]]
    fl = {k: v for k, v in filters.items() if v}
    counts = lambda cs: [[c.label, c.count, c.pct] for c in cs]  # noqa: E731
    return report_service.Report(
        kind="me-kpi", title="M&E Field Tool · KPI reports", generated_at=_now(), filters="; ".join(f"{k}={v}" for k, v in fl.items()) or "none",
        sheets=[
            report_service.Sheet("Summary", ["Measure", "Value"], summary_rows),
            report_service.Sheet("By district", g_headers, g_rows(d.by_district), landscape=True),
            report_service.Sheet("By phase", g_headers, g_rows(d.by_phase), landscape=True),
            report_service.Sheet("By week", g_headers, g_rows(d.by_week), landscape=True),
            report_service.Sheet("By officer", g_headers, g_rows(d.by_officer), landscape=True),
            report_service.Sheet("Needs attention", ["Date", "Phase", "District", "SA", "Officer", "Reasons"], [[a.report_date, form.PHASE_LABEL.get(a.phase, a.phase), a.district or "", a.sa or "", a.officer or "", "; ".join(a.reasons)] for a in d.attention]),
            report_service.Sheet("Channels", ["Channel", "Reports", "%"], counts(d.channels)),
            report_service.Sheet("Blockers", ["Blocker", "Reports", "%"], counts(d.blockers)),
            report_service.Sheet("Error types", ["Error type", "Reports", "%"], counts(d.error_types)),
            report_service.Sheet("Risks", ["Risk", "Reports", "%"], counts(d.risks)),
            report_service.Sheet("Reports", headers, reg, landscape=True),
        ],
    )
