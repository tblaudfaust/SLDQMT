"""The 2026 SLPHC Census Incident Log as data: categories, severities, statuses, phases, and the rules.
See docs/census-incident-log-design.md. No automatic escalation: the dashboard lists what needs action."""

from __future__ import annotations

import re

SEVERITIES = [("CRITICAL", "Critical"), ("MAJOR", "Major"), ("MINOR", "Minor")]
SEVERITY_HELP = {"CRITICAL": "Stops enumeration or endangers people", "MAJOR": "Disrupts a team or a supervisory area", "MINOR": "Local, a workaround is in place"}
STATUSES = [("NEW", "New"), ("ACKNOWLEDGED", "Acknowledged"), ("IN_PROGRESS", "In progress"), ("RESOLVED", "Resolved"), ("CLOSED", "Closed"), ("REJECTED", "Rejected")]
OPEN_STATUSES = {"NEW", "ACKNOWLEDGED", "IN_PROGRESS"}
PHASES = [("PRE_FIELD", "Pre-field"), ("TRAINING", "Training"), ("LISTING", "Listing"), ("ENUMERATION", "Enumeration"), ("MOP_UP", "Mop-up"), ("POST", "Post-enumeration")]
LEVELS = [("DISTRICT", "District"), ("REGION", "Region"), ("NATIONAL", "National")]
REPORTER_ROLES = [("SUPERVISOR", "Field Supervisor"), ("ENUMERATOR", "Enumerator"), ("FIELD_MONITOR", "Field Monitor"), ("DQM", "District DQM"), ("ME", "M&E Officer"), ("DS", "District Statistician"), ("COORDINATOR", "District Coordinator"), ("OTHER", "Other")]
UPDATE_TYPES = [("COMMENT", "Comment"), ("STATUS", "Status change"), ("ASSIGN", "Owner assigned"), ("ESCALATE", "Escalated"), ("SEVERITY", "Severity changed"), ("REOPEN", "Reopened"), ("LINK", "Record linked"), ("CREATED", "Reported")]

# Categories and sub-categories (the national level can extend them later through settings).
CATEGORIES: list[tuple[str, str, list[tuple[str, str]], str]] = [
    ("SECURITY", "Security and safety", [("THREAT", "Threat or assault on staff"), ("THEFT", "Theft or robbery"), ("ACCIDENT", "Road accident"), ("UNREST", "Civil unrest"), ("ANIMAL", "Animal attack"), ("HEALTH", "Health emergency"), ("HARASSMENT", "Harassment (incl. PSEAH)"), ("OTHER", "Other")], "CRITICAL"),
    ("STAFF", "Staff", [("ABSENT", "Absent or abandoned post"), ("RESIGNED", "Resignation"), ("MISCONDUCT", "Misconduct"), ("IMPERSONATION", "Impersonation"), ("ILLNESS", "Death or serious illness"), ("PAYMENT", "Payment or allowance dispute"), ("DISMISSAL", "Dismissal")], "MAJOR"),
    ("EQUIPMENT", "Equipment and systems", [("TABLET_LOST", "Tablet lost or stolen"), ("TABLET_DAMAGED", "Tablet damaged or dead"), ("POWER", "Power bank or charger"), ("SIM", "SIM or data bundle"), ("CAPI", "CAPI application fault"), ("SYNC", "Sync failure"), ("VERSION", "Wrong application version"), ("GPS", "GPS not working")], "MAJOR"),
    ("MAPS", "Maps and geography", [("MAP_MISSING", "Wrong or missing map"), ("BOUNDARY", "Boundary dispute between EAs"), ("EA_SIZE", "EA too large or split"), ("SETTLEMENT", "Settlement missing from map"), ("ACCESS", "Locality inaccessible")], "MAJOR"),
    ("COMMUNITY", "Community and respondents", [("REFUSAL_HH", "Refusal (household)"), ("REFUSAL_COMMUNITY", "Refusal (community)"), ("RUMOUR", "Misinformation or rumour"), ("POLITICAL", "Political interference"), ("LEADER", "Chief or leader not informed"), ("PAYMENT_DEMAND", "Demand for payment")], "MAJOR"),
    ("DATA", "Data quality", [("FABRICATION", "Fabrication suspected"), ("OUTSIDE_EA", "Interviews outside EA"), ("DUPLICATES", "Duplicated households"), ("SYSTEMATIC", "Systematic error found by DQM"), ("DATA_LOSS", "Data loss on device")], "MAJOR"),
    ("LOGISTICS", "Logistics", [("TRANSPORT", "Transport"), ("FUEL", "Fuel"), ("ACCOMMODATION", "Accommodation"), ("MATERIALS", "Materials and stationery"), ("FOOD", "Food"), ("VENUE", "Venue"), ("DEPLOYMENT", "Late deployment")], "MINOR"),
    ("ENVIRONMENT", "Environment", [("FLOOD", "Flooding"), ("ROAD", "Impassable road"), ("RIVER", "River crossing"), ("WEATHER", "Weather"), ("FIRE", "Fire")], "MAJOR"),
    ("TRAINING", "Training", [("TRAINEE", "Trainee issue"), ("TRAINER", "Trainer issue"), ("MATERIALS", "Training materials"), ("OTHER", "Other")], "MINOR"),
    ("OTHER", "Other", [("OTHER", "Other")], "MINOR"),
]
CATEGORY_LABEL = {c: lb for c, lb, _, _ in CATEGORIES}
SUBCATEGORY_LABEL = {(c, s): lb for c, _, subs, _ in CATEGORIES for s, lb in subs}
DEFAULT_SEVERITY = {c: sev for c, _, _, sev in CATEGORIES}

# Default time to resolve by severity, in hours (settings mefm-style: incident_due_hours_*); overdue is shown, never escalated automatically.
DEFAULT_DUE_HOURS = {"CRITICAL": 24, "MAJOR": 72, "MINOR": 168}

SA_CODE_RE = re.compile(r"^\d{12}$")


def label(kind: str, value: str | None) -> str:
    table = {"severity": dict(SEVERITIES), "status": dict(STATUSES), "phase": dict(PHASES), "level": dict(LEVELS), "reporter_role": dict(REPORTER_ROLES), "update": dict(UPDATE_TYPES), "category": CATEGORY_LABEL}[kind]
    return table.get(value or "", value or "")


def public_spec() -> dict:
    opts = lambda pairs: [{"value": v, "label": lb} for v, lb in pairs]  # noqa: E731
    return {
        "severities": [{"value": v, "label": lb, "help": SEVERITY_HELP[v]} for v, lb in SEVERITIES],
        "statuses": opts(STATUSES), "phases": opts(PHASES), "levels": opts(LEVELS), "reporter_roles": opts(REPORTER_ROLES),
        "categories": [{"value": c, "label": lb, "default_severity": sev, "subcategories": opts(subs)} for c, lb, subs, sev in CATEGORIES],
        "sa_code_format": "12 digits, e.g. 000000000100",
    }


def validate(d: dict) -> list[str]:
    e: list[str] = []
    if d.get("category") not in CATEGORY_LABEL:
        e.append("Choose the category")
    elif d.get("subcategory") and (d["category"], d["subcategory"]) not in SUBCATEGORY_LABEL:
        e.append("Choose the sub-category from the list")
    if d.get("severity") not in dict(SEVERITIES):
        e.append("Choose the severity")
    if d.get("phase") not in dict(PHASES):
        e.append("Choose the census phase")
    if len((d.get("description") or "").strip()) < 10:
        e.append("Describe what happened (at least 10 characters)")
    for k in ("teams_affected", "staff_affected", "households_affected", "days_lost"):
        v = d.get(k)
        if v is not None and (not isinstance(v, int) or v < 0):
            e.append(f"{k.replace('_', ' ')} must be a whole number")
    return e
