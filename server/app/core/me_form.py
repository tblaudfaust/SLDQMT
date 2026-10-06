"""The 2026 PHC training evaluation questionnaire (M&E module), as a data structure.

Transcribed from "SLPHC 2026 Online / Self-paced Training Evaluation Form (concise)":
sections A to J, the response options with their codes, and the routing, skip and
validation rules of the digital form. The public evaluation page renders from this
spec and the server validates submissions against it, so the two cannot drift apart.

Answer values: single-choice items store the option value ("1", "2", "96"...); rating
items store "1".."5" or "NA" (not applicable, kept distinct from a skipped item, which is
simply absent); multi-select items store a list of option values; text items a string;
number items an integer. Items with an "Other (specify)" option take the free text in
"<code>_other".
"""

from __future__ import annotations

import re
from typing import Any

TRAINING_MODES = ("ONLINE", "IN_PERSON")

AGREE_SCALE = [("1", "Strongly disagree"), ("2", "Disagree"), ("3", "Neutral / unsure"), ("4", "Agree"), ("5", "Strongly agree")]
CONFIDENCE_SCALE = [("1", "Not confident"), ("2", "Slightly confident"), ("3", "Moderately confident"), ("4", "Confident"), ("5", "Very confident")]

DISTRICTS = [
    "Bo", "Bombali", "Bonthe", "Falaba", "Kailahun", "Kambia", "Karene", "Kenema", "Koinadugu", "Kono",
    "Moyamba", "Port Loko", "Pujehun", "Tonkolili", "Western Area Rural", "Western Area Urban",
]
INSTITUTIONS = [
    "Stats SL", "Stats SL Ad-Hoc", "University/FBC", "University/NU", "University/EBK", "MDA/NCRA", "MDA/Agriculture",
    "MDA/MTHE", "MDA/Local Government", "MDA/MoPED", "MDA/Labour", "MDA/Education", "Other",
]
REINFORCEMENT_TOPICS = [
    "Census concepts", "Listing/coverage", "Maps/GIS/GPS", "Questionnaire administration", "Special populations",
    "CAPI/tablet", "Synchronisation", "Data quality/DQM", "Supervisor responsibilities", "Practical scenarios",
]


def opts(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"value": v, "label": label} for v, label in pairs]


def named(values: list[str], other: str | None = None) -> list[dict[str, str]]:
    out = [{"value": v, "label": v} for v in values]
    if other:
        out.append({"value": "96", "label": other})
    return out


def single(code: str, text: str, options: list[dict[str, str]], *, audience: str = "trainee", required: bool = True, other: bool = False, help: str | None = None, text_in_person: str | None = None) -> dict:
    return {"code": code, "text": text, "type": "single", "options": options, "audience": audience, "required": required, "other": other, "help": help, "text_in_person": text_in_person}


def likert(code: str, text: str, *, audience: str = "trainee", scale: str = "agree") -> dict:
    return {"code": code, "text": text, "type": "likert", "scale": scale, "audience": audience, "required": True}


def multi(code: str, text: str, options: list[dict[str, str]], *, audience: str = "trainee", max_select: int = 3, exclusive: str | None = None, other: bool = True) -> dict:
    return {"code": code, "text": text, "type": "multi", "options": options, "audience": audience, "required": True, "max_select": max_select, "exclusive": exclusive, "other": other}


def text(code: str, text_: str, *, audience: str = "trainee", required: bool = False) -> dict:
    return {"code": code, "text": text_, "type": "text", "audience": audience, "required": required}


def number(code: str, text_: str, *, audience: str = "trainer", minimum: int = 0, required: bool = True) -> dict:
    return {"code": code, "text": text_, "type": "number", "audience": audience, "required": required, "min": minimum}


SECTIONS: list[dict[str, Any]] = [
    {
        "code": "A", "title": "Participant profile and participation", "audience": "both",
        "intro": "A few questions about you and your part in the training.",
        "items": [
            single("A00", "What was your role in this training?", opts(("1", "Trainer / facilitator"), ("2", "Trainee / participant"), ("3", "Neither (observer, admin, support)")), audience="both"),
            single("A01", "Position / role", opts(("1", "Master Trainer"), ("2", "DQM"), ("96", "Other (specify)")), other=True),
            single("A02", "Sex", opts(("1", "Male"), ("2", "Female"), ("3", "Prefer not to say")), audience="both"),
            single("A03", "Age group", opts(("1", "20–29"), ("2", "30–39"), ("3", "40–49"), ("4", "50+")), audience="both"),
            single("A04", "District", named(DISTRICTS), audience="both"),
            single("A05", "Institution", named(INSTITUTIONS), audience="both"),
            single("A06", "Did you complete all scheduled online/self-paced modules?", opts(("1", "Yes"), ("0", "No")), text_in_person="Did you attend all scheduled training sessions?"),
            single("A07", "How many live/interactive sessions did you attend?", opts(("4", "All"), ("3", "Most"), ("2", "Some"), ("1", "None"), ("9", "None scheduled")), text_in_person="How many practical / interactive sessions did you attend?"),
            single("A08", "Did you take all scheduled assessments/tests?", opts(("1", "Yes"), ("0", "No"), ("9", "None scheduled"))),
            single("A09", "Main device used for the training", opts(("1", "Laptop"), ("2", "Desktop"), ("3", "Tablet"), ("4", "Smartphone"), ("96", "Other")), other=True),
        ],
    },
    {
        "code": "B", "title": "Access and digital learning", "audience": "trainee", "scale": "agree",
        "intro": "Helps separate technology and connectivity problems from content problems.",
        "items": [
            likert("B01", "I could access the training platform and resources whenever I needed them."),
            likert("B02", "Materials (manuals, slides, scenarios) were well organised, and navigation instructions were clear."),
            likert("B03", "Training videos and assessment links worked reliably. (N/A if not used)"),
            likert("B04", "The resources worked well with the internet connection available to me."),
            likert("B05", "I had enough time to complete the required learning activities."),
            likert("B06", "Technical support was available when I needed it."),
            single("B07", "Main reason you could not complete all modules/assessments", opts(("1", "Connectivity"), ("2", "Power/electricity"), ("3", "Device problem"), ("4", "Platform/login/link problem"), ("5", "Workload/time"), ("6", "Unclear instructions / not informed"), ("96", "Other (specify)")), other=True),
        ],
    },
    {
        "code": "C", "title": "Training organisation and methods", "audience": "trainee", "scale": "agree",
        "items": [
            likert("C01", "Training objectives and participant roles were clearly explained."),
            likert("C02", "Modules were well organised and logically sequenced."),
            likert("C03", "Registration/onboarding was efficient."),
            likert("C04", "Training materials were relevant and adequate for my role."),
            likert("C05", "Role plays, mock interviews, scenarios and group discussions reflected real field situations and clarified difficult concepts."),
            likert("C06", "Practical and CAPI/tablet exercises gave me enough practice, including in my weak areas."),
            likert("C07", "Assessments and their feedback reinforced my learning and helped me correct my mistakes."),
        ],
    },
    {
        "code": "D", "title": "Understanding of census content", "audience": "trainee", "scale": "agree",
        "intro": "The training helped me understand the following well enough for my role:",
        "items": [
            likert("D01", "Census objectives and the purpose of Census Night"),
            likert("D02", "Enumerator conduct, confidentiality and professional responsibilities"),
            likert("D03", "Geographic concepts: locality, SA, EA, building, structure and dwelling unit"),
            likert("D04", "Household membership and place of usual residence"),
            likert("D05", "Institutional and special populations: definitions, Census Night treatment and their questionnaires"),
            likert("D06", "Community entry and systematic movement through the EA"),
            likert("D07", "Reading EA maps, boundaries and symbols; navigation, GPS and locality types"),
            likert("D08", "Building/structure identification and numbering"),
            likert("D09", "Handling boundary problems, missing settlements/buildings and duplicate coverage"),
            likert("D10", "Household listing, callbacks, coverage verification and EA completion"),
            likert("D11", "Questionnaire flow, geographic identification and household roster"),
            likert("D12", "The difference between primary and support Enumerator roles"),
        ],
    },
    {
        "code": "E", "title": "Tablet, CAPI and data quality", "audience": "trainee", "scale": "agree",
        "intro": "The training helped me understand the following well enough for my role:",
        "items": [
            likert("E01", "Device setup, login, assignments, GPS and Bluetooth"),
            likert("E02", "CAPI navigation, data entry, skip patterns, coding and validation"),
            likert("E03", "Enumerator and Supervisor menus/modes"),
            likert("E04", "Data synchronisation and re-synchronisation"),
            likert("E05", "Device readiness, security and basic troubleshooting"),
            likert("E06", "Supervisor data-quality responsibilities and the main field quality risks"),
            likert("E07", "Household selection and re-interview procedures"),
            likert("E08", "Data-quality indicators, dashboards, common errors, discrepancy and completeness checks"),
            likert("E09", "The feedback → CAPI correction → re-synchronisation → clearance workflow"),
        ],
    },
    {
        "code": "F", "title": "Trainers / facilitators", "audience": "trainee", "scale": "agree",
        "items": [
            likert("F01", "Trainers demonstrated mastery of the subject matter."),
            likert("F02", "Trainers explained concepts clearly, using examples relevant to census fieldwork."),
            likert("F03", "Trainers encouraged questions, answered them adequately and gave useful feedback on mistakes."),
            likert("F04", "Trainers managed time and pace well and facilitated effectively."),
        ],
    },
    {
        "code": "G", "title": "Readiness (self-assessment)", "audience": "trainee", "scale": "confidence",
        "intro": "Rate your confidence to perform your assigned role (not your satisfaction with the training). I am confident that I can:",
        "items": [
            likert("G01", "Explain census objectives, concepts, Census Night, household membership and special-population rules", scale="confidence"),
            likert("G02", "Guide listing, EA navigation, building identification and complete coverage", scale="confidence"),
            likert("G03", "Guide questionnaire administration and household roster procedures", scale="confidence"),
            likert("G04", "Use or support the CAPI/tablet functions required for my role", scale="confidence"),
            likert("G05", "Identify common data-quality problems and explain the correction/re-sync workflow", scale="confidence"),
            likert("G06", "Handle practical field scenarios and participants' questions", scale="confidence"),
            likert("G07", "Facilitate all sessions assigned to me (Master Trainers)", scale="confidence"),
            likert("G08", "Interpret DQM indicators/flags and support correction, verification and closure (DQM)", scale="confidence"),
        ],
    },
    {
        "code": "H", "title": "Overall assessment and needs", "audience": "trainee",
        "items": [
            single("H01", "Your overall knowledge of the 2026 PHC training content BEFORE this training", opts(("1", "Very low"), ("2", "Low"), ("3", "Moderate"), ("4", "High"), ("5", "Very high"))),
            single("H02", "Your overall knowledge NOW, after the training", opts(("1", "Very low"), ("2", "Low"), ("3", "Moderate"), ("4", "High"), ("5", "Very high"))),
            single("H03", "Overall quality of the training", opts(("5", "Excellent"), ("4", "Very good"), ("3", "Good"), ("2", "Fair"), ("1", "Poor"))),
            single("H04", "Overall training duration", opts(("1", "Too short"), ("2", "About right"), ("3", "Too long"))),
            single("H05", "Which approach do you recommend for future census training?", opts(("1", "This approach (online/self-paced)"), ("2", "Blended (online + in-person)"), ("3", "Fully in-person"), ("4", "Live online"), ("96", "Other (specify)")), other=True, text_in_person="Which approach do you recommend for future census training?"),
            single("H06", "Should the training materials stay accessible during fieldwork for reference?", opts(("1", "Yes"), ("0", "No"))),
            single("H07", "Are you ready to perform your assigned role?", opts(("3", "Yes, fully ready"), ("2", "Ready with minor support"), ("1", "Not yet ready"))),
            multi("H08", "Which areas need more explanation or practice before the next stage? (Tick up to three, or None)", [{"value": "0", "label": "None"}] + named(REINFORCEMENT_TOPICS, "Other (specify)"), exclusive="0"),
        ],
    },
    {
        "code": "I", "title": "Open feedback", "audience": "trainee",
        "intro": "Short, practical answers please. Responses will be grouped into themes for reporting.",
        "items": [
            text("I01", "What was the most useful aspect of the training?"),
            text("I02", "What was your biggest challenge during the training?"),
            text("I03", "What is the one thing Stats SL should improve or do before the next stage of training?"),
            text("I04", "Any other comments or recommendations?"),
        ],
    },
    {
        "code": "J", "title": "Trainers' evaluation of trainees", "audience": "trainer", "scale": "agree",
        "intro": "Answer about the group of trainees you facilitated as a whole, not individuals. Most trainees in my group…",
        "items": [
            text("J01", "Training group / cohort you facilitated", audience="trainer", required=True),
            number("J02", "Number of trainees in your group", minimum=1),
            likert("J03", "participated actively in sessions and discussions.", audience="trainer"),
            likert("J04", "completed assigned modules, exercises and assessments on time.", audience="trainer"),
            likert("J05", "understood core census concepts (Census Night, household membership, special populations).", audience="trainer"),
            likert("J06", "understood listing, EA maps and complete-coverage procedures.", audience="trainer"),
            likert("J07", "can administer the questionnaire and household roster correctly.", audience="trainer"),
            likert("J08", "can use the CAPI/tablet functions required, including synchronisation.", audience="trainer"),
            likert("J09", "understand data-quality checks and the correction workflow.", audience="trainer"),
            single("J10", "How many of your trainees are ready for the next stage?", opts(("4", "All / almost all"), ("3", "Most"), ("2", "About half"), ("1", "Fewer than half")), audience="trainer"),
            single("J11", "Do any trainees need individual follow-up before deployment?", opts(("1", "Yes"), ("0", "No")), audience="trainer"),
            number("J12_n", "How many trainees need individual follow-up?", minimum=1),
            text("J12_names", "Their names / IDs", audience="trainer"),
            multi("J13", "Where do trainees most need reinforcement? (Tick up to three)", named(REINFORCEMENT_TOPICS, "Other (specify)"), audience="trainer"),
            text("J14", "Your main recommendation to improve trainee performance before the next stage", audience="trainer"),
        ],
    },
]

ITEMS: dict[str, dict] = {item["code"]: item for section in SECTIONS for item in section["items"]}
SECTION_OF: dict[str, str] = {item["code"]: section["code"] for section in SECTIONS for item in section["items"]}
RATING_VALUES = {"1", "2", "3", "4", "5", "NA"}

# Reporting domains (annex): items, favourable = 4 or 5, provisional flag thresholds on % favourable
DOMAINS = [
    {"code": "B", "label": "Digital access", "items": [f"B0{i}" for i in range(1, 7)], "flag": 70},
    {"code": "C", "label": "Organisation and methods", "items": [f"C0{i}" for i in range(1, 8)], "flag": 70},
    {"code": "D", "label": "Census content", "items": [f"D{i:02d}" for i in range(1, 13)], "flag": 70},
    {"code": "E", "label": "CAPI and data quality", "items": [f"E0{i}" for i in range(1, 10)], "flag": 70},
    {"code": "F", "label": "Trainer performance", "items": [f"F0{i}" for i in range(1, 5)], "flag": 75},
    {"code": "G", "label": "Readiness (self-assessment)", "items": [f"G0{i}" for i in range(1, 9)], "flag": 70},
    {"code": "J", "label": "Trainee performance (trainer view)", "items": [f"J0{i}" for i in range(3, 10)], "flag": 70},
]


def role_of(answers: dict[str, Any]) -> str | None:
    """"TRAINER", "TRAINEE", "NEITHER" from A00, or None when A00 is not answered."""
    return {"1": "TRAINER", "2": "TRAINEE", "3": "NEITHER"}.get(str(answers.get("A00", "")))


def is_asked(code: str, answers: dict[str, Any], mode: str) -> bool:
    """The routing and skip rules of the digital form."""
    if code == "A00":
        return True
    role = role_of(answers)
    if role is None or role == "NEITHER":
        return False
    item = ITEMS[code]
    if role == "TRAINER":
        if code in ("A02", "A03", "A04", "A05"):
            return True
        if item["audience"] != "trainer":
            return False
        if code in ("J12_n", "J12_names"):
            return str(answers.get("J11")) == "1"
        return True
    # trainee
    if item["audience"] == "trainer":
        return False
    if mode == "IN_PERSON" and code in ("A09", "B01", "B02", "B03", "B04", "B05", "B06", "B07"):
        return False
    if code == "B07":
        return str(answers.get("A06")) == "0" or str(answers.get("A08")) == "0"
    if SECTION_OF[code] == "F":
        return str(answers.get("A07")) not in ("1", "9")
    if code == "G07":
        return str(answers.get("A01")) == "1"
    if code == "G08":
        return str(answers.get("A01")) == "2"
    return True


_PHONE = re.compile(r"^\+?\d{8,15}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def valid_phone(value: str) -> bool:
    return bool(_PHONE.match(re.sub(r"[\s\-()]", "", value or "")))


def valid_email(value: str) -> bool:
    return bool(_EMAIL.match((value or "").strip()))


def validate(answers: dict[str, Any], mode: str) -> tuple[dict[str, Any], list[str]]:
    """Keep only the items that were asked, check each against its definition, and report
    every problem as "<code>: message". Returns (clean answers, errors)."""
    clean: dict[str, Any] = {}
    errors: list[str] = []
    if role_of(answers) is None:
        return clean, ["A00: choose your role in this training"]
    for code, item in ITEMS.items():
        if not is_asked(code, answers, mode):
            continue
        value = answers.get(code)
        kind = item["type"]
        missing = value is None or value == "" or value == []
        if missing:
            if item.get("required"):
                errors.append(f"{code}: an answer is required")
            continue
        if kind == "likert":
            if str(value) not in RATING_VALUES:
                errors.append(f"{code}: rating must be 1 to 5 or N/A")
                continue
            clean[code] = str(value)
        elif kind == "single":
            allowed = {o["value"] for o in item["options"]}
            if str(value) not in allowed:
                errors.append(f"{code}: not one of the options")
                continue
            clean[code] = str(value)
            if item.get("other") and str(value) == "96":
                other = str(answers.get(f"{code}_other") or "").strip()
                if not other:
                    errors.append(f"{code}: please specify")
                else:
                    clean[f"{code}_other"] = other[:200]
        elif kind == "multi":
            values = [str(v) for v in (value if isinstance(value, list) else [value])]
            allowed = {o["value"] for o in item["options"]}
            if any(v not in allowed for v in values):
                errors.append(f"{code}: not one of the options")
                continue
            values = list(dict.fromkeys(values))
            if len(values) > item.get("max_select", 3):
                errors.append(f"{code}: choose at most {item.get('max_select', 3)}")
                continue
            if item.get("exclusive") in values and len(values) > 1:
                errors.append(f"{code}: 'None' cannot be combined with other options")
                continue
            clean[code] = values
            if item.get("other") and "96" in values:
                other = str(answers.get(f"{code}_other") or "").strip()
                if not other:
                    errors.append(f"{code}: please specify 'Other'")
                else:
                    clean[f"{code}_other"] = other[:200]
        elif kind == "text":
            clean[code] = str(value).strip()[:2000]
        elif kind == "number":
            try:
                n = int(value)
            except (TypeError, ValueError):
                errors.append(f"{code}: enter a whole number")
                continue
            if n < item.get("min", 0):
                errors.append(f"{code}: must be at least {item.get('min', 0)}")
                continue
            clean[code] = n
    if "J12_n" in clean and "J02" in clean and clean["J12_n"] > clean["J02"]:
        errors.append("J12_n: cannot exceed the number of trainees in the group")
    return clean, errors


def public_spec() -> dict[str, Any]:
    """What the evaluation page needs to render the form."""
    return {
        "scales": {"agree": opts(*AGREE_SCALE), "confidence": opts(*CONFIDENCE_SCALE)},
        "sections": SECTIONS,
        "rules": {
            "role_item": "A00",
            "in_person_hidden": ["A09", "B01", "B02", "B03", "B04", "B05", "B06", "B07"],
        },
    }
