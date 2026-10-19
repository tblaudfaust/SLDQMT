"""The 2026 SLPHC M&E Field Tool (KPIs for Monitoring and Evaluation, version 3) as data.

Completed by the M&E team in the field with the Field Supervisor (or the trainer during field practice):
one form per SA or practice team, each practice day and weekly during listing and enumeration. The web
app renders the form from this spec (cached for offline use) and the server validates every report
against it, so the two cannot drift apart.

Phases: MT master trainers' field practice · TOT ToT field practice · L listing · E enumeration.
Item types: yesno (1 Yes, 2 No) · yesno_na (+ 8 N/A) · choice · multi · number · numbers (several labelled
numbers) · text. ``detail`` adds a short text asked when the answer equals ``detail_when`` (or always when
``detail_when`` is absent). ``phases`` limits an item to some phases; otherwise it is asked in all."""

from __future__ import annotations

from typing import Any

PHASES = [("MT", "Master trainers' field practice"), ("TOT", "ToT field practice"), ("TOE", "ToE field practice (enumerators' field test)"), ("L", "Census listing"), ("E", "Census enumeration")]
PHASE_LABEL = dict(PHASES)
ROLES = [("SUPERVISOR", "Field Supervisor"), ("ENUMERATOR", "Enumerator"), ("FM", "Field Monitor"), ("DQM", "DQM (Data Quality Monitor)"), ("FC", "Field Coordinator"), ("DCO", "District Census Officer"), ("TRAINER", "Trainer"), ("TRAINEE", "Trainee"), ("OTHER", "Other")]
ROLE_LABEL = dict(ROLES)
YES_NO = [("1", "Yes"), ("2", "No")]
YES_NO_NA = [("1", "Yes"), ("2", "No"), ("8", "N/A")]
RATING = [("4", "Very good"), ("3", "Good"), ("2", "Weak"), ("1", "Poor")]


def opts(pairs) -> list[dict[str, str]]:
    return [{"value": v, "label": lb} for v, lb in pairs]


def item(code: str, text: str, kind: str, options=None, *, phases: list[str] | None = None, detail: str | None = None, detail_when: str | None = None, fields=None, help: str | None = None, required: bool | list[str] = False) -> dict:
    """`required` is True, or the list of phases in which the item is mandatory."""
    d: dict[str, Any] = {"code": code, "text": text, "type": kind, "required": required}
    if kind in ("yesno", "yesno_na"):
        d["options"] = opts(YES_NO if kind == "yesno" else YES_NO_NA)
    elif options is not None:
        d["options"] = opts(options)
    if fields:
        d["fields"] = [{"key": k, "label": lb} for k, lb in fields]
    if phases:
        d["phases"] = phases
    if detail:
        d["detail"] = detail
        if detail_when:
            d["detail_when"] = detail_when
    if help:
        d["help"] = help
    return d


LE = ["L", "E"]

SECTIONS: list[dict[str, Any]] = [
    {"code": "K1", "title": "KPI 1 · Community engagement", "subtitle": "Stakeholders: was the community prepared?", "items": [
        item("k1_1", "Has the community been informed about the census purpose, dates and process?", "yesno"),
        item("k1_2", "Which communication channels reached the community?", "multi", [("radio", "Radio"), ("meetings", "Community meetings"), ("religious", "Religious leaders"), ("leaders", "Local leaders / chiefs"), ("social", "Social media"), ("posters", "Posters / banners"), ("sms", "SMS"), ("other", "Other")], detail="Other channel", detail_when="other"),
        item("k1_3", "Have marginalised groups been specifically reached (women, persons with disabilities, migrants, nomadic groups, older persons, language minorities)?", "yesno", detail="Which groups were not reached", detail_when="2"),
        item("k1_4", "Concerns, misconceptions or rumours raised by community members", "text"),
        item("k1_5", "Is there a clear channel for the community to ask questions, complain or report on enumeration activities?", "yesno", detail="Which channel", detail_when="1"),
    ]},
    {"code": "K2", "title": "KPI 2 · Community entry", "subtitle": "Acceptance once the team is on the ground", "items": [
        item("k2_1", "Households visited: are they aware of the census?", "choice", [("1", "All"), ("2", "Most"), ("3", "Some"), ("4", "None")]),
        item("k2_2", "Do respondents trust the enumerators and feel safe giving information?", "yesno", detail="If No, why", detail_when="2"),
        item("k2_3", "Was the community helpful in identifying hard-to-reach locations or groups needing special arrangements?", "yesno_na"),
        item("k2_4", "Are there local events, security issues, weather or cultural / occupational practices (farming, hunting, fishing) that may affect enumeration?", "yesno", detail="Specify, with dates", detail_when="1"),
        item("k2_5", "Are community leaders supporting household participation and access for enumerators?", "yesno"),
    ]},
    {"code": "K3", "title": "KPI 3 · EA coverage", "subtitle": "From the tablet or supervisor application · in field practice, the practice assignment", "items": [
        item("k3_1", "Households expected and completed in the SA / practice assignment", "numbers", fields=[("expected", "Households to be enumerated"), ("done", "Listed / enumerated so far")], required=LE),
        item("k3_3", "EAs completed and assigned", "numbers", fields=[("done", "EAs completed"), ("assigned", "EAs assigned")]),
        item("k3_7", "Are the enumerators working within the EA boundary on the map (nothing enumerated outside the EA)?", "yesno", detail="EA(s) and what was outside", detail_when="2"),
        item("k3_8", "Have all parts of the EA been reached (every locality, street or compound; no part left out)?", "yesno", detail="Parts not yet covered and why", detail_when="2"),
        item("k3_9", "Structures or households found that are missing from the listing or the EA map?", "yesno", detail="Number and action taken", detail_when="1"),
        item("k3_4", "Refusals?", "yesno", detail="Number and action taken", detail_when="1"),
        item("k3_5", "Callbacks pending?", "yesno", detail="Number and action taken", detail_when="1"),
        item("k3_6", "Any enumerator who will not complete the assignment on time?", "yesno", detail="EA number(s) and reason", detail_when="1", phases=LE),
    ]},
    {"code": "K4", "title": "KPI 4 · CAPI readiness", "subtitle": "Tablets, GPS and GIS resources", "items": [
        item("k4_1", "Tablets working and issued", "numbers", fields=[("working", "Working"), ("issued", "Issued to the team")]),
        item("k4_2", "GPS performance issues (accuracy worse than 5 m)?", "yesno", detail="EA(s) affected", detail_when="1"),
        item("k4_3", "Technical support received when needed?", "yesno_na", detail="Comment"),
        item("k4_4", "GIS resources (EA maps) loaded and working properly?", "yesno", detail="Comment"),
    ]},
    {"code": "K5", "title": "KPI 5 · Daily productivity per team", "subtitle": "Urban and rural", "items": [
        item("k5_1", "Households completed today (or this week) by the team", "numbers", fields=[("urban", "Urban"), ("rural", "Rural")]),
        item("k5_2", "Is the team on schedule?", "choice", [("1", "On schedule"), ("2", "Behind by 1–2 days"), ("3", "Behind by 3 days or more")], phases=LE),
        item("k5_3", "Observations or issues affecting enumeration", "text"),
        item("k5_4", "Hard-to-reach areas identified", "text"),
    ]},
    {"code": "K6", "title": "KPI 6 · Data submission timeliness", "subtitle": "Cases completed and synced to HQ", "items": [
        item("k6_1", "Cases completed on the tablets and synced to HQ", "numbers", fields=[("completed", "Completed"), ("synced", "Synced to HQ")]),
        item("k6_2", "Delays or blockers experienced", "multi", [("connectivity", "Connectivity"), ("validation", "Validation errors"), ("missing", "Missing forms"), ("bundle", "No data bundle"), ("other", "Other"), ("none", "None")], detail="Other blocker", detail_when="other"),
        item("k6_3", "Was data (bundle) provided for syncing to HQ, and was it enough?", "choice", [("1", "Yes, enough"), ("2", "Yes, but not enough"), ("3", "No")]),
    ]},
    {"code": "K7", "title": "KPI 7 · Data quality assurance", "subtitle": "Reviews by the Field Monitor and the DQM", "items": [
        item("k7_1", "Households reviewed and households with errors", "numbers", fields=[("reviewed", "Reviewed by the Field Monitor so far"), ("errors", "With errors detected (DQM / FM review)")]),
        item("k7_3", "Types of error most observed", "multi", [("missing", "Missing data"), ("coordinates", "Incorrect coordinates"), ("mislabel", "Mislabelling"), ("duplicate", "Duplication"), ("skips", "Skip patterns"), ("age", "Age mismatch"), ("other", "Other")], detail="Other error type", detail_when="other"),
        item("k7_4", "Technical support received from functionaries (FC, DCO)?", "yesno", detail="From whom", detail_when="1"),
    ]},
    {"code": "K8", "title": "KPI 8 · Re-interview", "subtitle": "Re-interviews (spot checks) done by the Field Supervisor", "items": [
        item("k8_0", "Has the supervisor re-interviewed completed households (spot checks on the supervisor application)?", "yesno", detail="If No, why", detail_when="2"),
        item("k8_1", "Households selected by the supervisor for re-interview and completed", "numbers", fields=[("selected", "Selected"), ("done", "Completed")]),
        item("k8_2", "Time taken to complete the re-interviews (days)", "number"),
        item("k8_3", "Any disparities between the re-interviews and the enumerators' data?", "yesno", detail="Number of households and what differed", detail_when="1"),
        item("k8_4", "Were the re-interview findings discussed with the enumerator(s) and corrections made?", "yesno_na"),
    ]},
    {"code": "K9", "title": "KPI 9 · Field supervision", "subtitle": "Presence in the field this period", "items": [
        item("k9_1", "Stats SL monitors present in the field this week?", "yesno"),
        item("k9_2", "External monitors present in the field this week?", "yesno"),
        item("k9_3", "Field Coordinator present during enumeration?", "yesno", detail="Number of visits", detail_when="1"),
        item("k9_4", "DCO present during enumeration?", "yesno", detail="Number of visits", detail_when="1"),
        item("k9_5", "Field visit time spent per visit (hours)", "number"),
        item("k9_6", "Any supervision gaps observed?", "yesno", detail="Describe", detail_when="1"),
    ]},
    {"code": "K10", "title": "KPI 10 · Data quality and consistency checks", "subtitle": "Answered by Field Supervisors", "items": [
        item("k10_1", "Do you review the enumerators' work before syncing to the server?", "choice", [("1", "Always"), ("2", "Sometimes"), ("3", "Never")]),
        item("k10_2", "Are you able to detect issues with the data during the review?", "yesno"),
        item("k10_3", "How often do the enumerators sync with you?", "choice", [("1", "Daily"), ("2", "Every 2–3 days"), ("3", "Weekly"), ("4", "Irregular")]),
        item("k10_4", "How often do you sync with HQ?", "choice", [("1", "Daily"), ("2", "Every 2–3 days"), ("3", "Weekly"), ("4", "Irregular")]),
        item("k10_5", "Challenges with syncing data to HQ", "text"),
    ]},
    {"code": "K11", "title": "KPI 11 · SWOT and risks", "subtitle": "Strengths, weaknesses, concerns and risks", "items": [
        item("k11_1", "Key strengths observed", "text"),
        item("k11_2", "Key weaknesses or bottlenecks", "text"),
        item("k11_3", "Communication concerns: escalation and feedback protocols", "text"),
        item("k11_4", "Safety / security concerns", "text", help="Also report it in the Census Incident Log the same day."),
        item("k11_5", "Community entry concerns", "text"),
        item("k11_6", "Risks that could interrupt enumeration", "multi", [("connectivity", "Connectivity"), ("electricity", "Electricity"), ("device", "Device failure"), ("weather", "Bad weather"), ("turnover", "Staff turnover"), ("security", "Security"), ("transport", "Transport"), ("other", "Other")], detail="Other risk", detail_when="other"),
    ]},
    {"code": "B", "title": "Section B · M&E officer's remarks", "subtitle": "Completed by the officer after the visit", "items": [
        item("b1", "Overall state of the SA / team", "choice", RATING, required=True),
        item("b2", "Issues to escalate today (issue · to whom · by when)", "text"),
        item("b3", "Follow-up visit needed?", "yesno", detail="Date", detail_when="1"),
    ]},
]

ITEMS: dict[str, dict] = {i["code"]: i for s in SECTIONS for i in s["items"]}
SECTION_OF: dict[str, dict] = {i["code"]: s for s in SECTIONS for i in s["items"]}


def applies(entry: dict, phase: str) -> bool:
    return not entry.get("phases") or phase in entry["phases"]


def public_spec() -> dict:
    return {
        "title": "M&E Field Tool · KPIs for Monitoring and Evaluation", "version": 3,
        "intro": "Completed by the M&E team member in the field with the Field Supervisor, or the trainer during field practice. One form per SA or practice team: each practice day, and weekly during listing and enumeration. Numbers come from the tablet or the supervisor application.",
        "phases": opts(PHASES), "roles": opts(ROLES), "rating": opts(RATING), "sections": SECTIONS,
    }


def _int(v) -> int | None:
    if v is None or v == "":
        return None
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise ValueError("must be a whole number")
    if n < 0 or n > 10_000_000:
        raise ValueError("out of range")
    return n


def validate(phase: str, answers: dict) -> tuple[dict, list[str]]:
    """Clean the answers against the spec: unknown codes dropped, values typed, option codes checked.
    Returns (clean answers, error messages)."""
    errors: list[str] = []
    clean: dict[str, Any] = {}
    for code, it in ITEMS.items():
        if not applies(it, phase) or not applies(SECTION_OF[code], phase):
            continue
        raw = answers.get(code)
        kind = it["type"]
        try:
            if kind in ("yesno", "yesno_na", "choice"):
                if raw not in (None, ""):
                    allowed = {o["value"] for o in it["options"]}
                    if str(raw) not in allowed:
                        raise ValueError(f"'{raw}' is not one of the options")
                    clean[code] = str(raw)
            elif kind == "multi":
                vals = raw or []
                if not isinstance(vals, list):
                    raise ValueError("must be a list")
                allowed = {o["value"] for o in it["options"]}
                bad = [v for v in vals if str(v) not in allowed]
                if bad:
                    raise ValueError(f"{bad} are not options")
                if vals:
                    clean[code] = [str(v) for v in vals]
            elif kind == "number":
                n = _int(raw)
                if n is not None:
                    clean[code] = n
            elif kind == "numbers":
                sub = raw or {}
                if not isinstance(sub, dict):
                    raise ValueError("must be a set of numbers")
                out = {}
                for f in it["fields"]:
                    n = _int(sub.get(f["key"]))
                    if n is not None:
                        out[f["key"]] = n
                if out:
                    clean[code] = out
            elif kind == "text":
                s = str(raw or "").strip()
                if len(s) > 2000:
                    raise ValueError("too long (2000 characters)")
                if s:
                    clean[code] = s
            if it.get("detail"):
                d = str(answers.get(code + "_detail") or "").strip()
                if d:
                    clean[code + "_detail"] = d[:500]
            req = it.get("required")
            if req and (req is True or phase in req) and code not in clean:
                errors.append(f"{it['text']}: required")
        except ValueError as e:
            errors.append(f"{it['text']}: {e}")
    return clean, errors


def _pct(n, d) -> float | None:
    return round(100.0 * n / d, 1) if (n is not None and d) else None


def metrics(answers: dict) -> dict:
    """The figures the dashboard aggregates, computed from the answers."""
    g = lambda code, key: (answers.get(code) or {}).get(key)  # noqa: E731
    return {
        "coverage_pct": _pct(g("k3_1", "done"), g("k3_1", "expected")),
        "ea_pct": _pct(g("k3_3", "done"), g("k3_3", "assigned")),
        "tablets_pct": _pct(g("k4_1", "working"), g("k4_1", "issued")),
        "synced_pct": _pct(g("k6_1", "synced"), g("k6_1", "completed")),
        "error_pct": _pct(g("k7_1", "errors"), g("k7_1", "reviewed")),
        "reinterview_pct": _pct(g("k8_1", "done"), g("k8_1", "selected")),
        "hh_expected": g("k3_1", "expected"), "hh_done": g("k3_1", "done"),
        "hh_today": (g("k5_1", "urban") or 0) + (g("k5_1", "rural") or 0) if answers.get("k5_1") else None,
        "on_schedule": answers.get("k5_2") == "1" if answers.get("k5_2") else None,
        "safety_concern": bool(answers.get("k11_4")),
        "escalation": bool(answers.get("b2")),
        "follow_up": answers.get("b3") == "1",
        "overall": int(answers["b1"]) if answers.get("b1") else None,
    }


def label(code: str, value) -> str:
    it = ITEMS.get(code)
    if not it or value is None:
        return "" if value is None else str(value)
    if it["type"] == "multi":
        m = {o["value"]: o["label"] for o in it["options"]}
        return "; ".join(m.get(str(v), str(v)) for v in (value or []))
    if "options" in it:
        return {o["value"]: o["label"] for o in it["options"]}.get(str(value), str(value))
    if it["type"] == "numbers":
        return " · ".join(f"{f['label']}: {value.get(f['key'], '')}" for f in it["fields"] if f["key"] in value)
    return str(value)
