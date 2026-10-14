"""The Daily Trainer Class Evaluation (2026 PHC) as data: the lead trainer completes one form per class
each day (3 to 5 minutes, within 2 hours of class close). Sections: context, 1 attendance and delivery,
2 learning evidence, 3 delivery and support, 4 priority actions. The public page renders from this and
the server validates with the rules below; the labels are reused by the reports and exports."""

from __future__ import annotations

from app.core.me_form import DISTRICTS

PHASES = [("MASTER", "Master training"), ("TOT", "Training of trainers"), ("FIELD", "Field staff training")]
COVERAGE = [("ALL", "All topics completed"), ("SOME", "Some incomplete"), ("NONE", "None completed")]
CHECKS = [("QUIZ", "Quiz"), ("PRACTICAL", "Practical task"), ("ORAL", "Oral check"), ("NOT_ASSESSED", "Not assessed")]
RATINGS = [("GOOD", "Good"), ("SOME", "Some gaps"), ("MAJOR", "Major gaps")]
RATING_HELP = "Good = minor or no gaps; Some gaps = needs improvement; Major gaps = disrupted learning."
DELIVERY_AREAS = [("content", "Content accuracy and clarity"), ("participation", "Participation and use of practice"), ("time", "Time management")]
SUPPORT = [
    ("NONE", "None"), ("DEVICES", "Devices / CAPI"), ("INTERNET_POWER", "Internet / power"),
    ("MATERIALS", "Materials / quiz errors"), ("VENUE_MEALS", "Venue / meals"), ("OTHER", "Other"),
]
MAX_ACTIONS = 2

LABELS = {k: dict(v) for k, v in {"phase": PHASES, "coverage": COVERAGE, "check": CHECKS, "rating": RATINGS, "support": SUPPORT}.items()}


def label(kind: str, value: str | None) -> str:
    return LABELS[kind].get(value or "", value or "")


def public_spec() -> dict:
    """What the public page needs to render the form."""
    opts = lambda pairs: [{"value": v, "label": lb} for v, lb in pairs]  # noqa: E731
    return {
        "title": "Daily Trainer Class Evaluation",
        "intro": "Lead trainer completes one form per class each day. Aim for 3–5 minutes; submit within 2 hours of class close. "
                 "Tick options and use counts from registers or checks. Write None if no issue; use Not assessed if learning was not checked.",
        "phases": opts(PHASES), "coverage": opts(COVERAGE), "checks": opts(CHECKS), "ratings": opts(RATINGS), "rating_help": RATING_HELP,
        "delivery_areas": opts(DELIVERY_AREAS), "support": opts(SUPPORT), "districts": DISTRICTS, "max_actions": MAX_ACTIONS,
        "urgent_note": "Urgent issues: notify the coordinator immediately; do not wait for this report.",
    }


def validate(d: dict) -> list[str]:
    """Cross-field rules the pydantic schema cannot express. Returns messages, empty when valid."""
    errors: list[str] = []
    if d.get("present") is not None and d.get("expected") is not None and d["present"] > d["expected"]:
        errors.append("Present cannot exceed the expected trainees")
    if d.get("late") is not None and d.get("present") is not None and d["late"] > d["present"]:
        errors.append("Arrived late cannot exceed the trainees present")
    if d.get("coverage") != "ALL" and not (d.get("incomplete_topic") or "").strip():
        errors.append("Give the topic and reason when the agenda was not fully covered")
    if not d.get("practice_not_scheduled") and d.get("practice_minutes") is None:
        errors.append("Enter the practical / CAPI practice minutes, or tick Not scheduled")
    checks = list(d.get("checks") or [])
    if not checks:
        errors.append("Tick the check used, or Not assessed")
    if "NOT_ASSESSED" in checks and len(checks) > 1:
        errors.append("Not assessed cannot be combined with a check")
    assessed = bool(checks) and "NOT_ASSESSED" not in checks
    if assessed:
        if d.get("number_checked") is None or d.get("number_met") is None:
            errors.append("Enter the number checked and the number meeting the criterion")
        elif d["number_met"] > d["number_checked"]:
            errors.append("The number meeting the criterion cannot exceed the number checked")
        if not (d.get("task_checked") or "").strip():
            errors.append("Say which task or topic was checked")
        if not (d.get("criterion") or "").strip():
            errors.append("Give the pass / success criterion used")
    if not d.get("followup_not_assessed") and d.get("followup_count") is None:
        errors.append("Enter the trainees needing follow-up, or tick Not assessed")
    for key, _ in DELIVERY_AREAS:
        if d.get(f"delivery_{key}") not in LABELS["rating"]:
            errors.append(f"Rate {dict(DELIVERY_AREAS)[key].lower()}")
    support = list(d.get("support") or [])
    if not support:
        errors.append("Tick the support problems, or None")
    if "NONE" in support and len(support) > 1:
        errors.append("None cannot be combined with a support problem")
    if "OTHER" in support and not (d.get("support_other") or "").strip():
        errors.append("Describe the other support problem")
    actions = [a for a in (d.get("actions") or []) if any((a.get(k) or "").strip() for k in ("issue", "action", "owner_due"))]
    if len(actions) > MAX_ACTIONS:
        errors.append(f"Record at most {MAX_ACTIONS} priority actions")
    for i, a in enumerate(actions, start=1):
        if not (a.get("issue") or "").strip():
            errors.append(f"Action {i}: describe the issue and its impact")
        if not (a.get("action") or "").strip():
            errors.append(f"Action {i}: give the next action")
    if d.get("mgmt_help") and not (d.get("raised_to") or "").strip():
        errors.append("Say who the management / CCIT request was raised to")
    return errors
