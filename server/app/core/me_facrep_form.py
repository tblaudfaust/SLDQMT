"""The Daily Facilitator's Report (2026 PHC Training of Trainers, in-person) as data.

One report per hall per day, submitted by the Lead Facilitator of the hall after the day's sessions, so the
Training Coordinator and the CTA have a consistent record of what went right, what went wrong and what should
change. Sections A to I follow the form "Daily_FACILITATOR_REPORT_FORM_ToT_IN-PERSON-V1"."""

from __future__ import annotations

TITLE = "Daily Facilitator's Report"
SUBTITLE = "2026 Population and Housing Census: Training of Trainers (ToT)"
PURPOSE = ("To give the Training Coordinator and CTA a consistent record of what went right, what went wrong, and what "
           "should change in each Hall, so they can make corrections before the next training day.")
HOW_TO = [
    "One report per Hall per day, submitted by the Lead Facilitator of that Hall. It is not an individual facilitator report.",
    "Submit the same day, after the day's sessions, by 6:00 p.m.",
    "Be candid and objective. Give evidence (what was observed), not general impressions.",
    "Use the rating scale: 1 = Poor, 2 = Fair, 3 = Good, 4 = Very good, 5 = Excellent.",
    "Complete every field. Where not applicable, write \"N/A\" and give the reason. Do not leave mandatory fields (marked *) blank.",
]
NOTE = "For the purposes of this report, all Master Trainers are named Facilitators."

VENUES = ["Bo", "Kenema", "Makeni", "Port Loko", "Freetown", "Waterloo"]
DAYS = list(range(1, 11))
SCALE = [(1, "Poor"), (2, "Fair"), (3, "Good"), (4, "Very good"), (5, "Excellent")]
SCALE_LABEL = {v: lb for v, lb in SCALE}
DELIVERY = [("FULL", "Yes, fully"), ("PARTLY", "Partly"), ("NO", "No")]
DELIVERY_LABEL = dict(DELIVERY)

# Section D: one rating per row (1 to 5)
RATINGS = [
    ("knowledge", "Participants' knowledge check and understanding of today's content"),
    ("engagement", "Participants' engagement and interaction (questions, discussion, etc.)"),
    ("illustrations", "Use of illustrations and practice exercises / scenarios"),
    ("connectivity", "Internet connectivity and power supply (facilitators and participants)"),
    ("coordination", "Co-facilitator and technical-support coordination"),
]
RATING_KEYS = [k for k, _ in RATINGS]
RATING_LABEL = dict(RATINGS)

# Section E: connectivity, power and logistics (rating or value, with details: who was affected, backup used)
LOGISTICS = [
    ("internet", "Internet connectivity", "rating"),
    ("power", "Power supply", "rating"),
    ("devices", "Device shortages", "text"),
    ("food", "Food & beverages", "text"),
]

# Section H, question 17: who should act
ACTORS = [
    ("LEAD", "Lead Facilitator"),
    ("COORD", "Training Coordinator"),
    ("CTA", "CTA"),
    ("CCIT", "CCIT-Lead"),
    ("ASSESS", "Assessment Administrator"),
    ("TECH", "Platform / technical support"),
    ("SG", "SG / Census Secretariat"),
    ("OTHER", "Other (specify)"),
]
ACTOR_KEYS = [k for k, _ in ACTORS]
ACTOR_LABEL = dict(ACTORS)

SECTIONS = [
    ("A", "Report identification"),
    ("B", "Attendance and participation", "Report the class as a whole."),
    ("C", "Delivery and time management", "Sessions are the chapters of the day on the agenda."),
    ("D", "Class rating at a glance", "One rating per row. Explain any rating of 1 or 2 in sections F and G."),
    ("E", "Connectivity, power and logistics"),
    ("F", "What went right", "Keep it short: up to three points."),
    ("G", "What went wrong", "Keep it short: up to three points."),
    ("H", "Recommendations", "Make each recommendation specific and actionable."),
    ("I", "Closing", "Submission confirms the report reflects the classroom's session."),
]


def public_spec() -> dict:
    return {
        "version": 1, "title": TITLE, "subtitle": SUBTITLE, "purpose": PURPOSE, "how_to": HOW_TO, "note": NOTE,
        "venues": VENUES, "days": DAYS, "scale": [{"value": v, "label": lb} for v, lb in SCALE],
        "delivery": [{"value": v, "label": lb} for v, lb in DELIVERY],
        "ratings": [{"key": k, "label": lb} for k, lb in RATINGS],
        "logistics": [{"key": k, "label": lb, "type": t} for k, lb, t in LOGISTICS],
        "actors": [{"value": v, "label": lb} for v, lb in ACTORS],
        "sections": [{"code": s[0], "title": s[1], "note": s[2] if len(s) > 2 else None} for s in SECTIONS],
    }


def mean_rating(values: dict[str, int]) -> float:
    return round(sum(values[k] for k in RATING_KEYS) / len(RATING_KEYS), 2)


def attention_reasons(x) -> list[str]:
    """Why a report needs the coordinator's eye."""
    reasons = []
    low = [RATING_LABEL[k] for k in RATING_KEYS if getattr(x, f"r_{k}") <= 2]
    if low:
        reasons.append("Rated 1 or 2: " + "; ".join(low))
    if x.delivered == "NO":
        reasons.append("Sessions not delivered as scheduled")
    elif x.delivered == "PARTLY" and (x.minutes_lost or 0) >= 60:
        reasons.append(f"{x.minutes_lost} minutes lost")
    if x.registered and x.present is not None and x.registered > 0 and 100.0 * x.present / x.registered < 75:
        reasons.append(f"Attendance {round(100.0 * x.present / x.registered)}%")
    if x.e_internet is not None and x.e_internet <= 2:
        reasons.append("Internet connectivity poor")
    if x.e_power is not None and x.e_power <= 2:
        reasons.append("Power supply poor")
    return reasons
