"""The Daily Facilitator Report (2026 PHC, REPORTING_REQUIREMENTS_and_Template_final) as data.

Completed by the lead facilitator for each class, each day, within 2 hours of class close, so
management / CCIT sees the same indicators from every class every day. Sections: A identification,
C schedule and content coverage (one row per agenda session, minutes over/under computed), D participant
performance and learning, E facilitation quality (1 to 5, evidence required for 1, 2 or 5), F materials
and assessment issues log, G connectivity, power and logistics, H escalations and decisions needed.
The public page renders from this; the server validates with the rules below."""

from __future__ import annotations

from datetime import datetime

from app.core.me_form import DISTRICTS

PHASES = [("MASTER", "Master Training"), ("TOT", "Training of Trainers"), ("FIELD", "Field Staff Training")]
SCALE = [(5, "5 · Excellent, no gaps and evidence cited"), (4, "4 · Good, minor gaps"), (3, "3 · Acceptable, some gaps"), (2, "2 · Below expectations, major gaps"), (1, "1 · Serious problems, session not effective")]
SCALE_SHORT = {5: "Excellent", 4: "Good", 3: "Acceptable", 2: "Below expectations", 1: "Serious problems"}
DELIVERED = [("Y", "Y · Fully delivered"), ("P", "P · Partly delivered"), ("N", "N · Not delivered")]
QUALITY = [
    ("content", "1. Content accuracy and clarity"),
    ("engagement", "2. Participant engagement and interaction"),
    ("time", "3. Time management"),
    ("illustrations", "4. Use of illustrations and practice exercises / scenarios"),
]
ISSUE_TYPES = [("ERROR", "Error"), ("MISMATCH", "Mismatch"), ("UNCLEAR", "Unclear"), ("MISSING", "Missing")]
SEVERITIES = [("H", "High"), ("M", "Medium"), ("L", "Low")]
ESCALATION_STATUS = [("OPEN", "Open"), ("IN_PROGRESS", "In progress"), ("RESOLVED", "Resolved")]
LOGISTICS = [("internet", "Internet connectivity (1–5)"), ("power", "Power supply (1–5)"), ("devices", "Device shortages (number of devices short)"), ("food", "Food & beverages (1–5)")]
EVIDENCE_SCORES = {1, 2, 5}

LABELS = {"phase": dict(PHASES), "delivered": dict(DELIVERED), "issue_type": dict(ISSUE_TYPES), "severity": dict(SEVERITIES), "status": dict(ESCALATION_STATUS), "quality": dict(QUALITY)}


def label(kind: str, value) -> str:
    return LABELS[kind].get(value, str(value) if value is not None else "")


def public_spec() -> dict:
    opts = lambda pairs: [{"value": v, "label": lb} for v, lb in pairs]  # noqa: E731
    return {
        "title": "Daily Facilitator Report",
        "subtitle": "To be completed by the Lead Facilitator for each class, each day · Submit within 2 hours of class close",
        "intro": "This form captures a standard set of facts that lead facilitators report after every training class, so management / CCIT sees the same indicators from every class, every day, and can decide before problems reach the field.",
        "instructions": "Complete every field. Where not applicable, write N/A and give the reason. Mandatory fields are marked *.",
        "scale_text": "Rating scale: 1 = serious problems, session not effective; 2 = below expectations, major gaps; 3 = acceptable, some gaps; 4 = good, minor gaps; 5 = excellent, no gaps and evidence cited. Delivered codes: Y = fully delivered; P = partly delivered; N = not delivered.",
        "phases": opts(PHASES), "scale": opts(SCALE), "delivered": opts(DELIVERED), "quality": opts(QUALITY), "issue_types": opts(ISSUE_TYPES),
        "severities": opts(SEVERITIES), "escalation_status": opts(ESCALATION_STATUS), "logistics": opts(LOGISTICS), "districts": DISTRICTS, "evidence_scores": sorted(EVIDENCE_SCORES),
    }


def minutes(t: str | None) -> int | None:
    try:
        d = datetime.strptime(t or "", "%H:%M")
    except ValueError:
        return None
    return d.hour * 60 + d.minute


def session_delta(s: dict) -> int | None:
    """Minutes over (+) or under (−) the planned duration, from the four times; None when any is missing."""
    ps, pe, as_, ae = (minutes(s.get(k)) for k in ("planned_start", "planned_end", "actual_start", "actual_end"))
    if None in (ps, pe, as_, ae):
        return None
    return (ae - as_) - (pe - ps)


def validate(d: dict) -> list[str]:
    """Cross-field rules the pydantic schema cannot express. Returns messages; empty when valid."""
    e: list[str] = []
    sessions = d.get("sessions") or []
    if not sessions:
        e.append("Section C: add the day's sessions (at least one)")
    for i, s in enumerate(sessions, start=1):
        if not (s.get("topic") or "").strip():
            e.append(f"Session {i}: give the topic")
        if s.get("delivered") not in LABELS["delivered"]:
            e.append(f"Session {i}: tick Delivered Y, P or N")
        for k in ("planned_start", "planned_end", "actual_start", "actual_end"):
            if s.get(k) and minutes(s[k]) is None:
                e.append(f"Session {i}: {k.replace('_', ' ')} must be HH:MM")
        if s.get("delivered") in ("P", "N") and not (s.get("reason") or "").strip():
            e.append(f"Session {i}: give the reason when a session is partly or not delivered")
        if s.get("delivered") == "N" and (s.get("actual_start") or s.get("actual_end")):
            pass  # a cancelled session may still carry the time it was attempted
        ps, pe = minutes(s.get("planned_start")), minutes(s.get("planned_end"))
        if ps is not None and pe is not None and pe <= ps:
            e.append(f"Session {i}: planned end must be after planned start")
        as_, ae = minutes(s.get("actual_start")), minutes(s.get("actual_end"))
        if as_ is not None and ae is not None and ae <= as_:
            e.append(f"Session {i}: actual end must be after actual start")
        if s.get("delivered") == "Y" and (as_ is None or ae is None):
            e.append(f"Session {i}: give the actual start and end of a delivered session")
    if d.get("quiz_administered") is None:
        e.append("D: say whether a quiz / assessment was administered")
    elif d.get("quiz_administered"):
        if not (d.get("quiz_title") or "").strip():
            e.append("D: give the quiz / assessment title")
        if d.get("mean_score") is None or d.get("pass_rate") is None:
            e.append("D: give the mean score and the pass rate (%)")
    if d.get("practice_minutes") is None and not (d.get("practice_comments") or "").strip():
        e.append("D: give the practical / CAPI hands-on minutes, or N/A with the reason in Comments")
    for key, lb in QUALITY:
        score = d.get(f"q_{key}")
        if score not in (1, 2, 3, 4, 5):
            e.append(f"E: rate {lb[3:].lower()} from 1 to 5")
        elif score in EVIDENCE_SCORES and not (d.get(f"q_{key}_evidence") or "").strip():
            e.append(f"E: evidence / justification is required for a score of {score} on {lb[3:].lower()}")
    for i, m in enumerate(d.get("material_issues") or [], start=1):
        if not (m.get("item") or "").strip():
            e.append(f"F issue {i}: give the item (manual chapter, quiz, questionnaire ref.)")
        if m.get("type") not in LABELS["issue_type"]:
            e.append(f"F issue {i}: choose the type")
        if m.get("severity") not in LABELS["severity"]:
            e.append(f"F issue {i}: choose the severity H, M or L")
    for key in ("internet", "power", "food"):
        if d.get(f"g_{key}") not in (1, 2, 3, 4, 5):
            e.append(f"G: rate {dict(LOGISTICS)[key].split(' (')[0].lower()} from 1 to 5")
    if d.get("g_devices") is None:
        e.append("G: give the number of devices short (0 if none)")
    for i, x in enumerate(d.get("escalations") or [], start=1):
        if not (x.get("issue") or "").strip():
            e.append(f"H escalation {i}: describe the issue requiring management / CCIT action")
        if not (x.get("raised_to") or "").strip():
            e.append(f"H escalation {i}: say who it was raised to")
        if x.get("status") not in LABELS["status"]:
            e.append(f"H escalation {i}: choose the status")
    return e
