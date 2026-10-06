"""Monitoring & Evaluation: evaluations, public registration and submission, results, export."""

import hashlib
import json
import secrets
from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import me_form
from app.core.config import settings
from app.models import MeEvaluation, MeRespondent, MeResponse, User
from app.schemas.me import (
    Breakdown,
    DistrictRow,
    DomainStat,
    EvaluationIn,
    EvaluationOut,
    EvaluationUpdate,
    ItemStat,
    OpenAnswer,
    RegisterIn,
    RegisterOut,
    RespondentOut,
    Results,
    SubmitIn,
    SubmitOut,
)
from app.services import report_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---- evaluations -------------------------------------------------------------


def _counts(db: Session, evaluation_id: int) -> dict[str, int]:
    registered = db.execute(select(func.count()).select_from(MeRespondent).where(MeRespondent.evaluation_id == evaluation_id)).scalar_one()
    rows = db.execute(select(MeResponse.role, func.count()).where(MeResponse.evaluation_id == evaluation_id, MeResponse.deleted.is_(False)).group_by(MeResponse.role)).all()
    by_role = {role: n for role, n in rows}
    return {"registered": registered, "submitted": sum(by_role.values()), "trainees": by_role.get("TRAINEE", 0), "trainers": by_role.get("TRAINER", 0)}


def to_out(db: Session, e: MeEvaluation) -> EvaluationOut:
    out = EvaluationOut.model_validate(e)
    for k, v in _counts(db, e.id).items():
        setattr(out, k, v)
    base = settings.ME_PUBLIC_BASE_URL.rstrip("/")
    out.share_url = f"{base}/evaluate/{e.token}" if base else None
    return out


def list_evaluations(db: Session) -> list[EvaluationOut]:
    rows = db.execute(select(MeEvaluation).order_by(MeEvaluation.created_at.desc())).scalars().all()
    return [to_out(db, e) for e in rows]


def get_evaluation(db: Session, evaluation_id: int) -> MeEvaluation:
    e = db.get(MeEvaluation, evaluation_id)
    if e is None:
        raise HTTPException(404, "Evaluation not found")
    return e


def create_evaluation(db: Session, user: User, body: EvaluationIn) -> MeEvaluation:
    if body.period_start and body.period_end and body.period_end < body.period_start:
        raise HTTPException(400, "The period ends before it starts")
    dup = db.execute(select(MeEvaluation).where(func.lower(MeEvaluation.title) == body.title.strip().lower())).scalars().first()
    if dup:
        raise HTTPException(409, f"An evaluation called '{dup.title}' already exists (created {dup.created_at:%d %b %Y}). Give each training round a distinct title, or reopen the existing one.")
    e = MeEvaluation(
        title=body.title.strip(), training_mode=body.training_mode, period_start=body.period_start, period_end=body.period_end,
        description=(body.description or "").strip() or None, token=secrets.token_urlsafe(18), status="OPEN", created_by=user.id,
    )
    db.add(e)
    db.flush()
    return e


def update_evaluation(db: Session, e: MeEvaluation, body: EvaluationUpdate) -> MeEvaluation:
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(e, k, v.strip() if isinstance(v, str) and k in ("title", "description") else v)
    if e.period_start and e.period_end and e.period_end < e.period_start:
        raise HTTPException(400, "The period ends before it starts")
    db.flush()
    return e


def delete_evaluation(db: Session, e: MeEvaluation) -> None:
    """Remove an evaluation that received no submissions (a duplicate or a test); one with responses is closed instead."""
    if _counts(db, e.id)["submitted"]:
        raise HTTPException(409, "This evaluation has responses; close it instead of deleting it")
    db.delete(e)
    db.flush()


def respondents(db: Session, evaluation_id: int) -> list[RespondentOut]:
    rows = db.execute(select(MeRespondent).where(MeRespondent.evaluation_id == evaluation_id).order_by(MeRespondent.created_at.desc())).scalars().all()
    out = []
    for r in rows:
        resp = r.response if r.response and not r.response.deleted else None
        answers = json.loads(resp.answers) if resp else {}
        out.append(RespondentOut(
            id=r.id, full_name=r.full_name, email=r.email, phone=r.phone, registered_at=r.created_at,
            role=resp.role if resp else None, submitted_at=resp.submitted_at if resp else None, response_id=resp.id if resp else None,
            district=answers.get("A04"),
        ))
    return out


def delete_response(db: Session, evaluation_id: int, response_id: int) -> MeResponse:
    r = db.get(MeResponse, response_id)
    if r is None or r.evaluation_id != evaluation_id:
        raise HTTPException(404, "Response not found")
    r.deleted = True
    db.flush()
    return r


# ---- public page -------------------------------------------------------------


def by_token(db: Session, token: str) -> MeEvaluation:
    e = db.execute(select(MeEvaluation).where(MeEvaluation.token == token)).scalars().first()
    if e is None:
        raise HTTPException(404, "This evaluation link is not valid")
    return e


def register(db: Session, e: MeEvaluation, body: RegisterIn) -> RegisterOut:
    if e.status != "OPEN":
        raise HTTPException(409, "This evaluation is closed")
    email = body.email.strip().lower()
    if not me_form.valid_email(email):
        raise HTTPException(400, "Enter a valid email address")
    phone = body.phone.strip()
    if not me_form.valid_phone(phone):
        raise HTTPException(400, "Enter a valid phone number (8 to 15 digits)")
    token = secrets.token_urlsafe(24)
    r = db.execute(select(MeRespondent).where(MeRespondent.evaluation_id == e.id, MeRespondent.email == email)).scalars().first()
    if r is None:
        r = MeRespondent(evaluation_id=e.id, full_name=body.full_name.strip(), email=email, phone=phone, resume_token_hash=_hash(token))
        db.add(r)
    else:
        # the same person coming back (new device, interrupted session): refresh their details and key
        r.full_name = body.full_name.strip()
        r.phone = phone
        r.resume_token_hash = _hash(token)
    db.flush()
    already = r.response is not None and not r.response.deleted
    return RegisterOut(respondent_id=r.id, resume_token=token, full_name=r.full_name, already_submitted=already)


def submit(db: Session, e: MeEvaluation, body: SubmitIn, user_agent: str | None) -> SubmitOut:
    if e.status != "OPEN":
        raise HTTPException(409, "This evaluation is closed")
    r = db.get(MeRespondent, body.respondent_id)
    if r is None or r.evaluation_id != e.id or r.resume_token_hash != _hash(body.resume_token):
        raise HTTPException(403, "Please register again before submitting")
    if r.response is not None and not r.response.deleted:
        raise HTTPException(409, "You have already submitted this evaluation. Thank you!")
    clean, errors = me_form.validate(body.answers, e.training_mode)
    if errors:
        raise HTTPException(422, {"errors": errors})
    role = me_form.role_of(clean) or "NEITHER"
    if r.response is not None:  # a deleted earlier response: replace it
        db.delete(r.response)
        db.flush()
    resp = MeResponse(evaluation_id=e.id, respondent_id=r.id, role=role, answers=json.dumps(clean), submitted_at=_now(), user_agent=(user_agent or "")[:300] or None)
    db.add(resp)
    db.flush()
    return SubmitOut(response_id=resp.id, role=role, submitted_at=resp.submitted_at)


# ---- results -----------------------------------------------------------------


def _label(code: str, value) -> str:
    item = me_form.ITEMS.get(code)
    if item and "options" in item:
        for o in item["options"]:
            if o["value"] == str(value):
                return o["label"]
    return str(value)


def _breakdown(values: list[str], code: str, order: list[str] | None = None) -> list[Breakdown]:
    c = Counter(values)
    total = sum(c.values())
    keys = order or [o["value"] for o in me_form.ITEMS[code]["options"]] if code in me_form.ITEMS and "options" in me_form.ITEMS[code] else sorted(c)
    out = [Breakdown(label=_label(code, k), count=c[k], pct=round(100 * c[k] / total, 1) if total else 0.0) for k in keys if c.get(k)]
    for k in c:
        if k not in keys:
            out.append(Breakdown(label=_label(code, k), count=c[k], pct=round(100 * c[k] / total, 1)))
    return out


def _item_stat(code: str, answers: list[dict]) -> ItemStat:
    ratings = [int(a[code]) for a in answers if str(a.get(code, "")) in ("1", "2", "3", "4", "5")]
    na = sum(1 for a in answers if a.get(code) == "NA")
    fav = sum(1 for r in ratings if r >= 4)
    return ItemStat(
        code=code, text=me_form.ITEMS[code]["text"], n=len(ratings), na=na,
        mean=round(mean(ratings), 2) if ratings else None, pct_favourable=round(100 * fav / len(ratings), 1) if ratings else None,
    )


def _domain(d: dict, answers: list[dict]) -> DomainStat:
    items = [_item_stat(c, answers) for c in d["items"]]
    for it in items:
        it.flag = it.pct_favourable is not None and it.pct_favourable < d["flag"]
    # a respondent's domain score counts only when at most 20% of its items are missing or N/A
    scores: list[float] = []
    favs: list[float] = []
    for a in answers:
        vals = [int(a[c]) for c in d["items"] if str(a.get(c, "")) in ("1", "2", "3", "4", "5")]
        asked = [c for c in d["items"] if c in a]
        if not vals or not asked or (len(asked) - len(vals)) / len(asked) > 0.2:
            continue
        scores.append(mean(vals))
        favs.append(100 * sum(1 for v in vals if v >= 4) / len(vals))
    m = round(mean(scores), 2) if scores else None
    f = round(mean(favs), 1) if favs else None
    return DomainStat(code=d["code"], label=d["label"], n_respondents=len(scores), mean=m, pct_favourable=f, flag=f is not None and f < d["flag"], threshold=d["flag"], items=items)


def _district_rows(rows: list[MeResponse], all_answers: list[dict]) -> list[DistrictRow]:
    """National table: every district that answered, with its own counts and scores."""
    by: dict[str, dict] = {}
    for r, a in zip(rows, all_answers):
        d = a.get("A04")
        if not d or r.role not in ("TRAINEE", "TRAINER"):
            continue
        g = by.setdefault(d, {"trainees": [], "trainers": []})
        g["trainees" if r.role == "TRAINEE" else "trainers"].append(a)
    out = []
    for d in sorted(by):
        tr, tn = by[d]["trainees"], by[d]["trainers"]
        a06 = [str(a["A06"]) for a in tr if a.get("A06")]
        gains = [int(a["H02"]) - int(a["H01"]) for a in tr if a.get("H01") and a.get("H02")]
        h07 = [str(a["H07"]) for a in tr if a.get("H07")]
        h03 = [int(a["H03"]) for a in tr if a.get("H03")]
        domains = {dom["code"]: _domain(dom, tn if dom["code"] == "J" else tr).pct_favourable for dom in me_form.DOMAINS}
        out.append(DistrictRow(
            district=d, trainees=len(tr), trainers=len(tn),
            completion_pct=round(100 * a06.count("1") / len(a06), 1) if a06 else None, domains=domains,
            gain=round(mean(gains), 2) if gains else None,
            ready_pct=round(100 * h07.count("3") / len(h07), 1) if h07 else None, not_ready=h07.count("1"),
            quality_mean=round(mean(h03), 2) if h03 else None,
        ))
    return out


def results(db: Session, e: MeEvaluation, district: str | None = None) -> Results:
    rows = db.execute(select(MeResponse).where(MeResponse.evaluation_id == e.id, MeResponse.deleted.is_(False))).scalars().all()
    all_answers = [json.loads(r.answers) for r in rows]
    by_district = _district_rows(rows, all_answers)
    if district:
        keep = [i for i, a in enumerate(all_answers) if a.get("A04") == district]
        rows = [rows[i] for i in keep]
        all_answers = [all_answers[i] for i in keep]
    trainees = [a for r, a in zip(rows, all_answers) if r.role == "TRAINEE"]
    trainers = [a for r, a in zip(rows, all_answers) if r.role == "TRAINER"]
    neither = sum(1 for r in rows if r.role == "NEITHER")
    counts = _counts(db, e.id)
    participants = trainees + trainers

    def vals(code: str, source: list[dict]) -> list[str]:
        return [str(a[code]) for a in source if a.get(code) not in (None, "")]

    profile = {
        "district": _breakdown(vals("A04", participants), "A04"),
        "role": _breakdown(vals("A01", trainees), "A01"),
        "institution": _breakdown(vals("A05", participants), "A05"),
        "sex": _breakdown(vals("A02", participants), "A02"),
        "age": _breakdown(vals("A03", participants), "A03"),
        "respondent_role": [Breakdown(label=k, count=v, pct=round(100 * v / len(rows), 1) if rows else 0.0) for k, v in (("Trainees", len(trainees)), ("Trainers", len(trainers)), ("Neither", neither)) if v],
    }
    completion = {code: _breakdown(vals(code, trainees), code) for code in ("A06", "A07", "A08", "B07", "A09")}
    domains = [_domain(d, trainers if d["code"] == "J" else trainees) for d in me_form.DOMAINS]

    before = [int(v) for v in vals("H01", trainees)]
    after = [int(v) for v in vals("H02", trainees)]
    gains = [int(a["H02"]) - int(a["H01"]) for a in trainees if a.get("H01") and a.get("H02")]
    knowledge = {
        "before": round(mean(before), 2) if before else None,
        "after": round(mean(after), 2) if after else None,
        "gain": round(mean(gains), 2) if gains else None,
        "pct_positive": round(100 * sum(1 for g in gains if g > 0) / len(gains), 1) if gains else None,
    }
    overall = {code: _breakdown(vals(code, trainees), code) for code in ("H03", "H04", "H05", "H06", "H07")}
    overall["H03_mean"] = [Breakdown(label="Mean quality (1–5)", count=len(vals("H03", trainees)), pct=round(mean(int(v) for v in vals("H03", trainees)), 2))] if vals("H03", trainees) else []
    overall["J10"] = _breakdown(vals("J10", trainers), "J10")
    overall["J11"] = _breakdown(vals("J11", trainers), "J11")

    def multi_freq(code: str, source: list[dict]) -> list[Breakdown]:
        c: Counter = Counter()
        for a in source:
            for v in a.get(code) or []:
                c[v] += 1
        total = len([a for a in source if a.get(code)])
        return sorted([Breakdown(label=_label(code, k), count=n, pct=round(100 * n / total, 1) if total else 0.0) for k, n in c.items()], key=lambda b: -b.count)

    reinforcement = {"trainees": multi_freq("H08", trainees), "trainers": multi_freq("J13", trainers)}

    rated = [it for d in domains if d.code != "J" for it in d.items if it.mean is not None]  # trainee-rated items only
    strengths = sorted(rated, key=lambda i: (-(i.pct_favourable or 0), -(i.mean or 0)))[:5]
    weaknesses = sorted(rated, key=lambda i: ((i.pct_favourable or 0), (i.mean or 0)))[:5]

    open_feedback: list[OpenAnswer] = []
    for r, a in zip(rows, all_answers):
        for code in ("I01", "I02", "I03", "I04", "J14", "J12_names"):
            if a.get(code):
                open_feedback.append(OpenAnswer(code=code, text=a[code], role=r.role, district=a.get("A04")))

    if district:
        counts = {**counts, "submitted": len(rows)}
    return Results(
        evaluation=to_out(db, e), district=district, by_district=by_district, registered=counts["registered"], submitted=counts["submitted"], trainees=len(trainees), trainers=len(trainers), neither=neither,
        response_rate=round(100 * counts["submitted"] / counts["registered"], 1) if counts["registered"] else None,
        profile=profile, completion=completion, domains=domains, knowledge=knowledge, overall=overall, reinforcement=reinforcement,
        strengths=strengths, weaknesses=weaknesses, open_feedback=open_feedback,
    )


# ---- export ------------------------------------------------------------------


def export(db: Session, e: MeEvaluation) -> report_service.Report:
    res = results(db, e)
    rows = db.execute(select(MeResponse).where(MeResponse.evaluation_id == e.id, MeResponse.deleted.is_(False)).order_by(MeResponse.submitted_at)).scalars().all()
    codes = list(me_form.ITEMS)
    extra = [f"{c}_other" for c in codes if me_form.ITEMS[c].get("other")]
    headers = ["Response", "Submitted", "Role", "Name", "Email", "Phone"] + codes + extra
    data = []
    for r in rows:
        a = json.loads(r.answers)
        data.append([r.id, r.submitted_at, r.role, r.respondent.full_name, r.respondent.email, r.respondent.phone]
                    + [", ".join(a[c]) if isinstance(a.get(c), list) else a.get(c, "") for c in codes] + [a.get(c, "") for c in extra])
    items_rows = [[d.label, it.code, it.text, it.n, it.na, it.mean if it.mean is not None else "", it.pct_favourable if it.pct_favourable is not None else "", "FLAG" if it.flag else ""] for d in res.domains for it in d.items]
    def cell(v):
        return v if v is not None else ""

    district_rows = [[x.district, x.trainees, x.trainers, cell(x.completion_pct)] + [cell(x.domains.get(c)) for c in ("B", "C", "D", "E", "F", "G", "J")] + [cell(x.gain), cell(x.ready_pct), x.not_ready, cell(x.quality_mean)] for x in res.by_district]
    domain_rows = [[d.label, d.n_respondents, d.mean if d.mean is not None else "", d.pct_favourable if d.pct_favourable is not None else "", d.threshold, "FLAG" if d.flag else ""] for d in res.domains]
    feedback_rows = [[f.code, me_form.ITEMS[f.code]["text"], f.role, f.district or "", f.text] for f in res.open_feedback]
    codebook = [[c, me_form.SECTION_OF[c], me_form.ITEMS[c]["text"], "; ".join(f"{o['value']}={o['label']}" for o in me_form.ITEMS[c].get("options", []))] for c in codes]
    period = f"{e.period_start or ''} to {e.period_end or ''}".strip(" to")
    return report_service.Report(
        kind="me_evaluation", title=f"Training evaluation · {e.title}", generated_at=_now(),
        filters=f"mode={e.training_mode}; period={period or 'n/a'}; responses={len(rows)}",
        sheets=[
            report_service.Sheet("By district", ["District", "Trainees", "Trainers", "% completed modules", "B digital %fav", "C organisation %fav", "D content %fav", "E CAPI/DQ %fav", "F trainers %fav", "G readiness %fav", "J trainer view %fav", "Knowledge gain", "% fully ready", "Not ready", "Quality mean"], district_rows, landscape=True),
            report_service.Sheet("Domains", ["Domain", "Respondents", "Mean", "% favourable", "Flag below %", "Flag"], domain_rows),
            report_service.Sheet("Items", ["Domain", "Code", "Statement", "n", "N/A", "Mean", "% favourable", "Flag"], items_rows, landscape=True),
            report_service.Sheet("Responses", headers, data, landscape=True),
            report_service.Sheet("Open feedback", ["Code", "Question", "Role", "District", "Answer"], feedback_rows, landscape=True),
            report_service.Sheet("Codebook", ["Code", "Section", "Question", "Options"], codebook, landscape=True),
        ],
    )
