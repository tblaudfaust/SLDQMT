"""The Daily Trainer Facilitation Rating Tool (Facilitators Assessment Tool, days 2 and 3) as data.

An M&E monitor sits in a training hall and rates each trainer once a day: section A, five criteria
scored 1 to 4 (out of 20, with a rating band), and section B, the chapters or thematic sections the
trainer facilitated that day, each 1 to 4 or left unrated when not observed. The overall score is the
percentage of the points awarded over the maximum of the sections actually rated, as the tool asks."""

from __future__ import annotations

import re

from app.core.me_form import DISTRICTS

PHASES = [("MASTER", "Master Training"), ("TOT", "Training of Trainers"), ("FIELD", "Field Staff Training")]
SCALE = [(1, "Poor"), (2, "Fair"), (3, "Good"), (4, "Excellent")]
CRITERIA = [
    ("technical", "Technical accuracy", "Explains concepts correctly and consistently with the approved manual and presentation."),
    ("clarity", "Clarity", "Explains content clearly and responds effectively to questions."),
    ("practical", "Practical delivery", "Demonstrates the required procedures and effective use of tablets where applicable."),
    ("participation", "Participation", "Engages trainees, encourages questions and manages the class effectively."),
    ("time", "Time management", "Follows the agenda and adequately covers the session content."),
]
CRITERION_KEYS = [k for k, _, _ in CRITERIA]
SECTION_A_MAX = 4 * len(CRITERIA)  # 20
# Section A bands by total (the tool), and the same cut-offs as percentages for the overall score
BANDS = [("EXCELLENT", "Excellent", 17, 85.0), ("GOOD", "Good", 13, 65.0), ("FAIR", "Fair", 9, 45.0), ("NEEDS_IMPROVEMENT", "Needs improvement", 0, 0.0)]
BAND_LABEL = {k: lb for k, lb, _, _ in BANDS}
# Agenda rows that are not something a trainer is rated on (loaded from a template, the monitor can still add them)
NOT_RATED_RE = re.compile(r"recap|quiz|briefing|debrief|official opening|administrative|oath of secrecy|proceed to|introduction of participants|registration|attendance|lunch|break", re.IGNORECASE)


def band_for_total(total: int) -> str:
    for key, _, min_total, _ in BANDS:
        if total >= min_total:
            return key
    return "NEEDS_IMPROVEMENT"


def band_for_pct(pct: float | None) -> str | None:
    if pct is None:
        return None
    for key, _, _, min_pct in BANDS:
        if pct >= min_pct:
            return key
    return "NEEDS_IMPROVEMENT"


def score(section_a: dict[str, int], sections: list[dict]) -> tuple[int, int, int, float, str]:
    """(section A total, section B total, section B maximum, overall %, band)."""
    a_total = sum(int(section_a[k]) for k in CRITERION_KEYS)
    rated = [s for s in sections if s.get("rating") is not None]
    b_total = sum(int(s["rating"]) for s in rated)
    b_max = 4 * len(rated)
    pct = round(100.0 * (a_total + b_total) / (SECTION_A_MAX + b_max), 1)
    return a_total, b_total, b_max, pct, band_for_pct(pct)


def is_rateable(topic: str) -> bool:
    return not NOT_RATED_RE.search(topic or "")


def public_spec() -> dict:
    return {
        "title": "Daily Trainer Facilitation Rating Tool",
        "subtitle": "The M&E monitor rates each trainer once a day, in the hall, on what was facilitated",
        "intro": "Rate each trainer's strengths on the criteria below. Rating scale: 1 = Poor, 2 = Fair, 3 = Good, 4 = Excellent. Section B lists the chapters and thematic sections of the training day: rate the ones you observed this trainer facilitate and leave the others unrated.",
        "phases": [{"value": v, "label": lb} for v, lb in PHASES],
        "scale": [{"value": v, "label": lb} for v, lb in SCALE],
        "criteria": [{"key": k, "label": lb, "help": h} for k, lb, h in CRITERIA],
        "section_a_max": SECTION_A_MAX,
        "bands": [{"key": k, "label": lb, "min_total": mt, "min_pct": mp} for k, lb, mt, mp in BANDS],
        "districts": DISTRICTS,
    }
