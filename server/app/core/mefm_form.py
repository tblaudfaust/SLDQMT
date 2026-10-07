"""The 2026 SLPHC M&E Field Monitoring Questionnaire (7 October 2026) as data.

Sections A to J, their items, response codes, ⚑ critical items and skip patterns, transcribed
from the Word form. The Android app renders the form from this spec (sent at sync) and the
server validates every submission against it, so the two cannot drift apart.

Codes: 1 Yes · 2 No · 3 Partly · 8 Not observed / not applicable. Ratings: 4 Very good · 3 Good ·
2 Weak · 1 Poor. Phases (A12): P pre-field · L listing · E enumeration · M mop-up.

Rules are declarative so the app can apply them without knowing the questionnaire:
  - a section or item carries ``phases``: asked only when A12 is one of them;
  - ``when``: a list of [code, op, value] conditions that must all hold (ops eq, ne, in, nin);
  - ``flag``: the ⚑ mark; ``flag_value`` is the answer that makes it a critical issue
    (2 = No for most items; 1 = Yes for C15, D5, G10 and I5, where Yes is the problem);
  - repeated groups: G is answered once per household (``repeat``: "household", at least 2 in
    phases E and M); I is answered for three respondents (``repeat``: "respondent").
Answer keys: one key per item code; repeated groups store a list of answer dicts under the
group key ("G" and "I"); the J-1 issues log is a list under "J_issues"; H red-flag ticks are
a list under "H_flags"; D11 is a list.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time
from typing import Any

PHASES = {"P": "Pre-field", "L": "Listing", "E": "Enumeration", "M": "Mop-up / close-out"}
YES_NO = [("1", "Yes"), ("2", "No")]
YES_NO_PARTLY = [("1", "Yes"), ("2", "No"), ("3", "Partly")]
YES_NO_NA = [("1", "Yes"), ("2", "No"), ("8", "Not observed / N/A")]
YES_NO_PARTLY_NA = [("1", "Yes"), ("2", "No"), ("3", "Partly"), ("8", "Not observed / N/A")]
RATING = [("4", "Very good"), ("3", "Good"), ("2", "Weak"), ("1", "Poor")]
REINFORCEMENT = ["Supervisor", "DQM", "District Coordinator", "District Statistician", "HQ"]
SEVERITIES = ["Critical", "Major", "Minor"]


def opts(pairs) -> list[dict[str, str]]:
    return [{"value": v, "label": label} for v, label in pairs]


def item(code: str, text: str, kind: str, options=None, *, flag: bool = False, flag_value: str = "2", phases: str | None = None, when=None, required: bool = True, **extra) -> dict:
    d: dict[str, Any] = {"code": code, "text": text, "type": kind, "required": required}
    if options is not None:
        d["options"] = opts(options)
    if flag:
        d["flag"] = True
        d["flag_value"] = flag_value
    if phases:
        d["phases"] = list(phases)
    if when:
        d["when"] = when
    d.update(extra)
    return d


SECTIONS: list[dict[str, Any]] = [
    {
        "code": "A", "title": "Identification and visit details", "phases": "PLEM",
        "items": [
            item("A2", "Date of visit", "date"),
            item("A3_arrived", "Time arrived (24h)", "time"),
            item("A3_left", "Time left (24h)", "time", required=False, help="Enter when leaving the EA; it must be after the time arrived."),
            item("A8", "EA code (10 digits)", "ea", help="Type the 10-digit EA code or pick it from the list. Region, district, chiefdom, section, EA type and SA number follow from the frame."),
            item("A9", "EA type", "code", [("1", "Urban"), ("2", "Rural")], help="Pre-filled from the frame; correct it if the ground differs."),
            item("A11", "Supervisor name / Enumerator name and ID", "text"),
            item("A12", "Census phase at visit", "code", [("P", "Pre-field"), ("L", "Listing"), ("E", "Enumeration"), ("M", "Mop-up / close-out")]),
            item("A13", "Day number of fieldwork in this EA", "int", minimum=0),
            item("A14", "Visit type", "code", [("1", "Scheduled"), ("2", "Unannounced"), ("3", "Follow-up on earlier issue"), ("4", "Complaint-driven")]),
            item("A15", "GPS of monitoring point (auto-captured)", "gps"),
            item("A16", "Was the enumeration team found in the EA? ⚑", "code", YES_NO, flag=True),
            item("A17", "If No: reason", "code", [("1", "Not yet deployed"), ("2", "Team absent"), ("3", "Working in wrong EA"), ("4", "Moved to next EA early"), ("5", "Other (specify)")], when=[["A16", "eq", "2"]], other="5"),
        ],
    },
    {
        "code": "B", "title": "Field staff, training and deployment", "phases": "PLE", "when": [["A16", "eq", "1"]],
        "items": [
            item("B1", "Is the enumerator the person officially assigned to this EA (ID card matches list)? ⚑", "code", YES_NO, flag=True),
            item("B2", "Did the enumerator complete the full 10-day training and pass the final test?", "code", YES_NO_NA),
            item("B3", "Is the enumerator wearing the census ID card and branded kit?", "code", YES_NO_PARTLY),
            item("B4", "Does the enumerator speak the main local language of the EA?", "code", YES_NO_PARTLY),
            item("B5", "Does the enumerator have the Enumerator's Manual on the tablet or in print?", "code", YES_NO),
            item("B6", "Can the enumerator correctly explain the census reference night (census night) when asked? ⚑", "code", YES_NO_PARTLY, flag=True),
            item("B7", "Can the enumerator correctly explain who counts as a usual household member?", "code", YES_NO_PARTLY),
            item("B8", "Days since the supervisor last visited this enumerator in the field", "int", minimum=0),
            item("B9", "Has the enumerator received their allowance / payment as scheduled?", "code", YES_NO_NA),
            item("B10", "Has the team had any dropout or replacement since deployment?", "code", YES_NO),
            item("B11", "If replaced: was the replacement trained (reserve list)?", "code", YES_NO_NA, when=[["B10", "eq", "1"]]),
            item("B12", "Rate the enumerator's overall preparedness", "rating", RATING),
        ],
    },
    {
        "code": "C", "title": "Logistics, equipment and CAPI readiness", "phases": "PLEM", "when": [["A16", "eq", "1"]],
        "items": [
            item("C1", "Is the tablet working (switches on, touchscreen responsive)? ⚑", "code", YES_NO, flag=True),
            item("C2", "Battery level at visit (%)", "int", minimum=0, maximum=100, when=[["C1", "eq", "1"]]),
            item("C3", "Does the enumerator have a working power bank or charging arrangement?", "code", YES_NO, when=[["C1", "eq", "1"]]),
            item("C4", "Is CSEntry installed with the current approved application version? ⚑", "code", YES_NO, flag=True, when=[["C1", "eq", "1"]]),
            item("C4_version", "Application version recorded", "text", required=False, when=[["C1", "eq", "1"]]),
            item("C5", "Is the EA map (MBTiles) for this EA loaded and opening on the tablet? ⚑", "code", YES_NO, flag=True, when=[["C1", "eq", "1"]]),
            item("C6", "Is the tablet GPS on and capturing a fix within 2 minutes?", "code", YES_NO, when=[["C1", "eq", "1"]]),
            item("C7", "Is the tablet date and time correct?", "code", YES_NO, when=[["C1", "eq", "1"]]),
            item("C8", "Date of last successful sync to the CSWeb server", "date", required=False),
            item("C9", "Number of completed cases on tablet not yet synced", "int", minimum=0),
            item("C10", "Reason for any unsynced cases", "code", [("1", "No network"), ("2", "No data bundle"), ("3", "Sync error"), ("4", "Not attempted"), ("8", "N/A")], when=[["C9", "ne", "0"]]),
            item("C11", "Is the tablet used only for census work (no personal apps/use observed)?", "code", YES_NO),
            item("C12", "Has the tablet been lost, damaged or replaced?", "code", YES_NO),
            item("C13", "Paper back-up forms and stationery available?", "code", YES_NO),
            item("C14", "Transport adequate to reach all parts of the EA?", "code", YES_NO_PARTLY),
            item("C15", "Any security or safety concern for the team? ⚑ (if Yes, describe in J)", "code", YES_NO, flag=True, flag_value="1"),
        ],
    },
    {
        "code": "D", "title": "EA maps, boundaries and coverage", "phases": "LEM", "when": [["A16", "eq", "1"]],
        "intro": "Check the boundary on the ground against the map, not only on the tablet.",
        "items": [
            item("D1", "Can the enumerator correctly describe the EA boundary on the map? ⚑", "code", YES_NO_PARTLY, flag=True),
            item("D2", "Did the enumerator walk the full boundary before starting listing?", "code", YES_NO_NA),
            item("D3", "Does the ground match the map (landmarks, roads, settlements)?", "code", YES_NO_PARTLY),
            item("D4", "Are there settlements or structures inside the EA that are missing from the map? (if Yes, describe in J-1)", "code", YES_NO),
            item("D5", "Is the team working in any area outside the EA boundary? ⚑ (if Yes, Critical in J-1)", "code", YES_NO, flag=True, flag_value="1"),
            item("D6", "Is there an unclear or disputed boundary with a neighbouring EA?", "code", YES_NO),
            item("D7", "Is the EA visibly too large for one enumerator to complete on time?", "code", YES_NO),
            item("D8", "Are structures being numbered/chalked in the approved format?", "code", YES_NO_PARTLY),
            item("D9", "Is the enumerator following a systematic route (e.g. serpentine, clockwise)?", "code", YES_NO_PARTLY),
            item("D10", "Monitor's spot-check: walk to 3 structures at random near the boundary. How many are listed? (of 3)", "int", minimum=0, maximum=3),
            item("D11", "Are hard-to-count areas present? (tick all)", "multi", [("islands", "Islands / riverine"), ("mining", "Mining camps"), ("informal", "Informal / slum settlements"), ("farm_huts", "Farm huts"), ("border", "Border crossings"), ("none", "None")], exclusive="none"),
            item("D12", "Rate coverage of the EA so far", "rating", RATING),
        ],
    },
    {
        "code": "E", "title": "Household listing observation", "phases": "L", "when": [["A16", "eq", "1"]],
        "intro": "Observe the listing of at least 3 consecutive structures.",
        "items": [
            item("E1", "Structures listed so far (from tablet)", "int", minimum=0),
            item("E2", "Households listed so far (from tablet)", "int", minimum=0),
            item("E3", "Expected households in EA (from frame / SA plan)", "int", minimum=0, help="Pre-filled from the frame."),
            item("E4", "Is a GPS point captured at the structure (not from a distance)? ⚑", "code", YES_NO_PARTLY, flag=True),
            item("E5", "Are vacant, non-residential and under-construction structures recorded with the right status code?", "code", YES_NO_PARTLY),
            item("E6", "Does the enumerator ask about every household within a multi-household structure (compound)? ⚑", "code", YES_NO_PARTLY, flag=True),
            item("E7", "Does the enumerator correctly separate households (eat from the same pot / share living arrangements)?", "code", YES_NO_PARTLY),
            item("E8", "Are institutions and collective living quarters (schools, barracks, prisons, hospitals, religious houses) identified and flagged?", "code", YES_NO_NA),
            item("E9", "Is the head of household name and household size recorded?", "code", YES_NO_PARTLY),
            item("E10", "Are mobile/outdoor sleepers (homeless, market sleepers, fishermen at sea) being identified for special enumeration?", "code", YES_NO_NA),
            item("E11", "Average listing time per structure observed (minutes)", "int", minimum=0),
            item("E12", "Rate quality of listing observed", "rating", RATING),
        ],
    },
    {
        "code": "F", "title": "Enumeration interview observation", "phases": "EM", "when": [["A16", "eq", "1"]],
        "intro": "Sit in on one full interview per visit, with the household's consent. Code what you see, not what the enumerator says they do.",
        "items": [
            item("F0", "Did the household consent to the observation?", "code", [("1", "Yes, interview observed"), ("2", "Household refused")]),
            item("F1", "Did the enumerator introduce themselves, show ID and explain the census purpose and confidentiality?", "code", YES_NO_PARTLY, when=[["F0", "eq", "1"]]),
            item("F2", "Was the interview held with an eligible respondent (head, spouse or adult member 15+)? ⚑", "code", YES_NO, flag=True, when=[["F0", "eq", "1"]]),
            item("F3", "Language of interview", "code", [("krio", "Krio"), ("mende", "Mende"), ("temne", "Temne"), ("limba", "Limba"), ("english", "English"), ("other", "Other (specify)")], when=[["F0", "eq", "1"]], other="other"),
            item("F4", "Were questions asked as worded (no leading or skipped questions)? ⚑", "code", YES_NO_PARTLY, flag=True, when=[["F0", "eq", "1"]]),
            item("F5", "Did the enumerator probe correctly when answers were unclear?", "code", YES_NO_PARTLY, when=[["F0", "eq", "1"]]),
            item("F6", "Did the enumerator read answers into the tablet instead of guessing or filling later? ⚑", "code", YES_NO, flag=True, when=[["F0", "eq", "1"]]),
            item("F7", "Was the respondent treated with courtesy and patience?", "code", YES_NO_PARTLY, when=[["F0", "eq", "1"]]),
            item("F8_start", "Interview start time", "time", when=[["F0", "eq", "1"]]),
            item("F8_end", "Interview end time", "time", when=[["F0", "eq", "1"]]),
            item("F9", "Did the enumerator correctly apply the census reference night when listing household members? ⚑", "code", YES_NO_PARTLY, flag=True, when=[["F0", "eq", "1"]]),
            item("F10", "Include babies, young children, elderly and visitors present on census night?", "code", YES_NO_PARTLY, when=[["F0", "eq", "1"]]),
            item("F11", "Exclude members who were absent on census night where the rule requires it?", "code", YES_NO_PARTLY, when=[["F0", "eq", "1"]]),
            item("F12", "Establish age using date of birth, documents or the historical events calendar (no heaping on 0 or 5)?", "code", YES_NO_PARTLY, when=[["F0", "eq", "1"]]),
            item("F13", "Ask the disability (functioning) questions to every member as required?", "code", YES_NO_PARTLY, when=[["F0", "eq", "1"]]),
            item("F14", "Ask education, economic activity and migration questions with correct skips?", "code", YES_NO_PARTLY, when=[["F0", "eq", "1"]]),
            item("F15", "Ask fertility questions only to eligible women, and probe for all children ever born? (8 if no eligible woman)", "code", YES_NO_PARTLY_NA, when=[["F0", "eq", "1"]]),
            item("F16", "Ask the household deaths in the past 12 months questions, including maternal deaths?", "code", YES_NO_PARTLY, when=[["F0", "eq", "1"]]),
            item("F17", "Record housing characteristics and amenities by observation where required?", "code", YES_NO_PARTLY, when=[["F0", "eq", "1"]]),
            item("F18", "Capture the household GPS point at the dwelling?", "code", YES_NO, when=[["F0", "eq", "1"]]),
            item("F19", "Mark the structure as enumerated and leave a callback notice where members were absent? (8 if no member absent)", "code", YES_NO_NA, when=[["F0", "eq", "1"]]),
            item("F20", "Interviews completed today by this enumerator (from tablet)", "int", minimum=0),
            item("F21", "Overall quality of the interview observed", "rating", RATING, when=[["F0", "eq", "1"]]),
        ],
    },
    {
        "code": "G", "title": "Household verification / mini re-interview", "phases": "EM", "when": [["A16", "eq", "1"]], "repeat": "household", "min_repeat": 2,
        "intro": "Select at least 2 households the enumerator reports as completed: one at random from the tablet list, one of your choice. Ask the household directly, without the enumerator present, and compare with the tablet record.",
        "items": [
            item("G1", "Household / structure number", "text"),
            item("G2", "Did a census enumerator visit this household? ⚑", "code", YES_NO, flag=True, help="No: skip G3–G11; logged as Critical."),
            item("G3_match", "Name of household head: does it match the tablet?", "code", YES_NO, when=[["G2", "eq", "1"]]),
            item("G4_household", "Number of persons who spent census night here (household says) ⚑", "int", minimum=0, when=[["G2", "eq", "1"]]),
            item("G4_tablet", "Number of persons (tablet shows)", "int", minimum=0, when=[["G2", "eq", "1"]]),
            item("G5_household", "Males / females (household says), e.g. 3/4", "text", when=[["G2", "eq", "1"]]),
            item("G5_match", "Males / females match?", "code", YES_NO, when=[["G2", "eq", "1"]]),
            item("G6", "Any child under 1 year in the household?", "code", YES_NO, when=[["G2", "eq", "1"]]),
            item("G6_match", "Child under 1: matches the tablet?", "code", YES_NO, when=[["G2", "eq", "1"]]),
            item("G7_household", "Age of the household head (household says)", "int", minimum=0, maximum=120, when=[["G2", "eq", "1"]]),
            item("G7_tablet", "Age of the household head (tablet shows)", "int", minimum=0, maximum=120, when=[["G2", "eq", "1"]]),
            item("G8", "Any death in the household in the past 12 months?", "code", YES_NO, when=[["G2", "eq", "1"]]),
            item("G8_match", "Death in the past 12 months: matches the tablet?", "code", YES_NO, when=[["G2", "eq", "1"]]),
            item("G9", "Were you asked all questions in person (not answered by a neighbour)?", "code", YES_NO, when=[["G2", "eq", "1"]]),
            item("G10", "Were you asked for money or gifts by the enumerator? ⚑", "code", YES_NO, flag=True, flag_value="1", when=[["G2", "eq", "1"]]),
            item("G11", "Satisfaction with the enumerator's conduct", "rating", RATING, when=[["G2", "eq", "1"]]),
        ],
    },
    {
        "code": "H", "title": "Supervision, data quality and data transmission", "phases": "LEM", "when": [["A16", "eq", "1"]],
        "intro": "Interview the Supervisor and check the DQM reports for the SA.",
        "items": [
            item("H1", "Does the supervisor hold a daily work plan and EA allocation for all enumerators?", "code", YES_NO_PARTLY),
            item("H2_enumerators", "Enumerators in the SA", "int", minimum=0),
            item("H2_visited", "Enumerators visited by the supervisor in the past 2 days", "int", minimum=0),
            item("H3", "Is the supervisor receiving and reviewing enumerator data daily on the supervisor app? ⚑", "code", YES_NO_PARTLY, flag=True),
            item("H4", "Is the supervisor reviewing the error/consistency reports and returning cases for correction?", "code", YES_NO_PARTLY),
            item("H5", "Number of cases returned to enumerators for correction in the last 3 days", "int", minimum=0),
            item("H6", "Has the supervisor done any re-interviews / spot-checks in this EA?", "code", YES_NO),
            item("H7", "Has the DQM visited this SA in the past 3 days?", "code", YES_NO),
            item("H8", "Did the DQM report raise issues that remain unresolved? (specify in J)", "code", YES_NO_NA, when=[["H7", "eq", "1"]]),
            item("H9_done", "Households enumerated in the EA to date", "int", minimum=0),
            item("H9_expected", "Households expected", "int", minimum=0, help="Pre-filled from the frame."),
            item("H10", "Is the EA on track to finish within the enumeration period? ⚑", "code", YES_NO, flag=True),
            item("H11", "Households with no-contact / refusal / callback pending", "int", minimum=0),
            item("H12", "Does the tablet listing count match the dashboard count for this EA?", "code", YES_NO_NA),
            item("H13", "Is the supervisor sending daily progress to the District Coordinator on time?", "code", YES_NO_PARTLY),
            item("H14", "Rate supervision quality in this SA", "rating", RATING),
            item("H_flags", "Red-flag data checks found (from the dashboard or the supervisor's tablet; tick any)", "multi",
                 [("hh_size", "Average household size far above or below the district norm"), ("short_interviews", "Very short interviews (well below the observed average)"),
                  ("night_or_same_gps", "Many interviews recorded at night or at the same GPS point"), ("sex_ratio", "Sex ratio or child-woman ratio out of the expected range"),
                  ("age_heaping", "Age heaping on ages ending in 0 or 5"), ("listing_gap", "Listed households with no enumeration record")], required=False),
        ],
    },
    {
        "code": "I", "title": "Community, publicity and special populations", "phases": "PLEM", "repeat": "respondent", "respondents": ["Community leader", "Resident 1", "Resident 2"],
        "intro": "Ask the community leader (chief, councillor or headman) and 2 residents chosen at random.",
        "items": [
            item("I1", "Have you heard about the 2026 census?", "code", YES_NO),
            item("I2", "Main source of information", "code", [("radio", "Radio"), ("tv", "TV"), ("crier", "Town crier"), ("religious", "Religious leader"), ("social", "Social media"), ("chief", "Chief"), ("other", "Other")], when=[["I1", "eq", "1"]]),
            item("I3", "Do you know the census night date?", "code", YES_NO, when=[["I1", "eq", "1"]]),
            item("I4", "Was the community leader informed before the team arrived?", "code", YES_NO, respondents=[0]),
            item("I5", "Any fear, rumour or resistance about the census in this community? ⚑", "code", YES_NO, flag=True, flag_value="1"),
            item("I6", "If yes, what? (e.g. tax, land, politics, religion)", "text", when=[["I5", "eq", "1"]]),
            item("I7", "Do you know anyone in this area not yet counted?", "code", YES_NO),
        ],
    },
    {
        "code": "I_special", "title": "Special populations in this EA", "phases": "PLEM",
        "intro": "If a group is not present, leave the arrangement blank and go to the next group.",
        "items": [
            item("I8_present", "Institutions (boarding schools, hospitals, prisons, barracks): present?", "code", YES_NO),
            item("I8_arrangement", "Institutions: arrangement in place to count them?", "code", YES_NO_PARTLY, when=[["I8_present", "eq", "1"]]),
            item("I9_present", "Homeless and street children: present?", "code", YES_NO),
            item("I9_arrangement", "Homeless and street children: arrangement in place?", "code", YES_NO_PARTLY, when=[["I9_present", "eq", "1"]]),
            item("I10_present", "Mining camps, fishing and nomadic / seasonal populations: present?", "code", YES_NO),
            item("I10_arrangement", "Mining camps, fishing and nomadic populations: arrangement in place?", "code", YES_NO_PARTLY, when=[["I10_present", "eq", "1"]]),
            item("I11_present", "Travellers in hotels, lorry parks, ports and border points: present?", "code", YES_NO),
            item("I11_arrangement", "Travellers: arrangement in place?", "code", YES_NO_PARTLY, when=[["I11_present", "eq", "1"]]),
            item("I12_present", "Persons with disabilities needing special access or interpreter: present?", "code", YES_NO),
            item("I12_arrangement", "Persons with disabilities: arrangement in place?", "code", YES_NO_PARTLY, when=[["I12_present", "eq", "1"]]),
        ],
    },
    {
        "code": "J", "title": "Issues, actions and overall rating", "phases": "PLEM",
        "intro": "J-1 issues log: one row per issue; every ⚑ item coded as a problem is added automatically. Rate only the dimensions observed on this visit.",
        "items": [
            item("J_issues", "Issues log", "issues", required=False),
            item("J1", "Coverage (all structures, households and persons counted)", "rating", RATING, required=False),
            item("J2", "Content accuracy (questions asked and recorded correctly)", "rating", RATING, required=False),
            item("J3", "Timeliness (EA on schedule)", "rating", RATING, required=False),
            item("J4", "Supervision and data quality control", "rating", RATING, required=False),
            item("J5", "Logistics and CAPI", "rating", RATING, required=False),
            item("J6", "Community acceptance", "rating", RATING, required=False),
            item("J8", "Feedback given to the enumerator and supervisor", "code", YES_NO),
            item("J9", "Follow-up visit needed", "code", YES_NO),
            item("J9_date", "Follow-up visit date", "date", when=[["J9", "eq", "1"]]),
            item("J10", "Monitor's comments", "text", required=False),
        ],
    },
]

ITEMS: dict[str, dict] = {it["code"]: it for s in SECTIONS for it in s["items"]}
SECTION_OF: dict[str, str] = {it["code"]: s["code"] for s in SECTIONS for it in s["items"]}
ISSUE_FIELDS = {"question": str, "severity": str, "description": str, "action": str, "referred_to": str, "deadline": str}

# Annex: key indicators (computed per visit, aggregated on the dashboards) with proposed targets (%)
INDICATORS = [
    {"code": "team_in_ea", "label": "Teams found working in their assigned EA", "items": "A16, B1, D5", "target": 100},
    {"code": "tablet_ready", "label": "Tablets ready (working, current app, map loaded)", "items": "C1, C4, C5", "target": 98},
    {"code": "spot_check", "label": "Boundary spot-check coverage (3 of 3 listed)", "items": "D10", "target": 100},
    {"code": "hh_visited", "label": "Households confirmed visited", "items": "G2", "target": 98},
    {"code": "hh_size_match", "label": "Household size match (re-interview vs tablet)", "items": "G4", "target": 95},
    {"code": "census_night", "label": "Interviews with correct census-night rule", "items": "F9", "target": 95},
    {"code": "synced_24h", "label": "Cases synced within 24 hours", "items": "C8, C9", "target": 95},
    {"code": "on_schedule", "label": "EAs on schedule", "items": "H10", "target": 90},
    {"code": "issues_closed", "label": "Critical issues closed by deadline", "items": "J-1", "target": 100},
    {"code": "ea_good", "label": "EAs rated Good or Very good overall", "items": "J7", "target": 85},
]

_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _holds(cond: list, answers: dict) -> bool:
    code, op, value = cond
    actual = answers.get(code)
    actual_s = None if actual is None else str(actual)
    if op == "eq":
        return actual_s == str(value)
    if op == "ne":
        return actual_s is not None and actual_s != str(value)
    if op == "in":
        return actual_s in [str(v) for v in value]
    if op == "nin":
        return actual_s is not None and actual_s not in [str(v) for v in value]
    return False


def section_asked(section: dict, answers: dict) -> bool:
    phase = str(answers.get("A12") or "")
    if section.get("phases") and phase and phase not in section["phases"]:
        return False
    if section.get("phases") and not phase and section["code"] != "A":
        return False
    return all(_holds(c, answers) for c in section.get("when", []))


def item_asked(it: dict, answers: dict, group_answers: dict | None = None, respondent_index: int | None = None) -> bool:
    scope = group_answers if group_answers is not None else answers
    if "respondents" in it and respondent_index is not None and respondent_index not in it["respondents"]:
        return False
    return all(_holds(c, scope) for c in it.get("when", []))


def _check_value(it: dict, value, errors: list[str], prefix: str) -> Any:
    kind = it["type"]
    code = f"{prefix}{it['code']}"
    if kind in ("code", "rating"):
        allowed = {o["value"] for o in it["options"]}
        if str(value) not in allowed:
            errors.append(f"{code}: not one of the options")
            return None
        return str(value)
    if kind == "multi":
        values = [str(v) for v in (value if isinstance(value, list) else [value])]
        allowed = {o["value"] for o in it["options"]}
        if any(v not in allowed for v in values):
            errors.append(f"{code}: not one of the options")
            return None
        if it.get("exclusive") in values and len(values) > 1:
            errors.append(f"{code}: 'None' cannot be combined with other options")
            return None
        return list(dict.fromkeys(values))
    if kind == "int":
        try:
            n = int(value)
        except (TypeError, ValueError):
            errors.append(f"{code}: enter a whole number")
            return None
        if n < it.get("minimum", 0):
            errors.append(f"{code}: cannot be negative")
            return None
        if "maximum" in it and n > it["maximum"]:
            errors.append(f"{code}: at most {it['maximum']}")
            return None
        return n
    if kind == "time":
        if not _TIME.match(str(value)):
            errors.append(f"{code}: time must be HH:MM")
            return None
        return str(value)
    if kind == "date":
        try:
            return date.fromisoformat(str(value)).isoformat()
        except ValueError:
            errors.append(f"{code}: date must be YYYY-MM-DD")
            return None
    if kind == "text":
        return str(value).strip()[:2000]
    if kind == "ea":
        s = re.sub(r"\D", "", str(value))
        if len(s) != 10:
            errors.append(f"{code}: the EA code has 10 digits")
            return None
        return s
    if kind == "gps":
        if not isinstance(value, dict) or value.get("lat") is None or value.get("lng") is None:
            errors.append(f"{code}: a GPS fix is required; wait for the device to capture one")
            return None
        return {"lat": float(value["lat"]), "lng": float(value["lng"]), "accuracy_m": float(value.get("accuracy_m") or 0), "at": str(value.get("at") or "")}
    if kind == "issues":
        rows = value if isinstance(value, list) else []
        out = []
        for i, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                errors.append(f"J_issues row {i}: invalid")
                continue
            sev = str(row.get("severity") or "")
            if sev not in SEVERITIES:
                errors.append(f"J_issues row {i}: severity must be Critical, Major or Minor")
                continue
            dl = row.get("deadline")
            if dl:
                try:
                    dl = date.fromisoformat(str(dl)).isoformat()
                except ValueError:
                    errors.append(f"J_issues row {i}: deadline must be YYYY-MM-DD")
                    continue
            out.append({"question": str(row.get("question") or "")[:20], "severity": sev, "description": str(row.get("description") or "")[:1000],
                        "action": str(row.get("action") or "")[:1000], "referred_to": str(row.get("referred_to") or "")[:60], "deadline": dl or None})
        return out
    return value


def _validate_items(items: list[dict], answers: dict, errors: list[str], prefix: str = "", respondent_index: int | None = None) -> dict:
    clean: dict = {}
    for it in items:
        if not item_asked(it, answers, respondent_index=respondent_index):
            continue
        value = answers.get(it["code"])
        empty = value is None or value == "" or value == []
        if empty:
            if it.get("required"):
                errors.append(f"{prefix}{it['code']}: an answer is required")
            continue
        v = _check_value(it, value, errors, prefix)
        if v is not None:
            clean[it["code"]] = v
            if it.get("other") and str(v) == it["other"]:
                other = str(answers.get(f"{it['code']}_other") or "").strip()
                if not other:
                    errors.append(f"{prefix}{it['code']}: please specify")
                else:
                    clean[f"{it['code']}_other"] = other[:200]
    return clean


def validate(answers: dict) -> tuple[dict, list[str]]:
    """Keep the asked items only, check each one, and apply the cross-item rules.
    Returns (clean answers, errors as "<code>: message")."""
    errors: list[str] = []
    clean: dict = {}
    phase = str(answers.get("A12") or "")
    if phase not in PHASES:
        return clean, ["A12: choose the census phase at visit"]
    for section in SECTIONS:
        if not section_asked(section, answers):
            continue
        if section.get("repeat") == "household":
            rows = answers.get("G") if isinstance(answers.get("G"), list) else []
            households = []
            for i, row in enumerate(rows, start=1):
                households.append(_validate_items(section["items"], row if isinstance(row, dict) else {}, errors, prefix=f"G[{i}]."))
            if len(households) < section.get("min_repeat", 1):
                errors.append(f"G: at least {section.get('min_repeat', 1)} households must be verified in this phase")
            clean["G"] = households
        elif section.get("repeat") == "respondent":
            rows = answers.get("I") if isinstance(answers.get("I"), list) else []
            respondents = []
            for idx, label in enumerate(section["respondents"]):
                row = rows[idx] if idx < len(rows) and isinstance(rows[idx], dict) else {}
                respondents.append(_validate_items(section["items"], row, errors, prefix=f"I[{label}].", respondent_index=idx))
            clean["I"] = respondents
        else:
            clean.update(_validate_items(section["items"], answers, errors))
    # cross-item rules
    if clean.get("A3_arrived") and clean.get("A3_left") and clean["A3_left"] <= clean["A3_arrived"]:
        errors.append("A3_left: time left must be after time arrived")
    if clean.get("F8_start") and clean.get("F8_end") and clean["F8_end"] <= clean["F8_start"]:
        errors.append("F8_end: interview end must be after its start")
    if "H2_visited" in clean and "H2_enumerators" in clean and clean["H2_visited"] > clean["H2_enumerators"]:
        errors.append("H2_visited: cannot exceed the enumerators in the SA")
    if "C8" in clean and clean.get("A2") and clean["C8"] > clean["A2"]:
        errors.append("C8: the last sync cannot be after the visit date")
    ratings = [clean[c] for c in ("J1", "J2", "J3", "J4", "J5", "J6") if c in clean]
    if ratings:
        clean["J7"] = round(sum(int(r) for r in ratings) / len(ratings))
    return clean, errors


def critical_issues(clean: dict) -> list[dict]:
    """The J-1 rows that ⚑ answers add automatically (every ⚑ coded as a problem)."""
    out = []

    def check(it: dict, scope: dict, label: str):
        if it.get("flag") and str(scope.get(it["code"], "")) == it["flag_value"]:
            out.append({"question": it["code"], "severity": "Critical", "description": f"{label}{it['text'].replace(' ⚑', '')}", "action": "", "referred_to": "", "deadline": None, "auto": True})

    for section in SECTIONS:
        if section.get("repeat") == "household":
            for i, row in enumerate(clean.get("G") or [], start=1):
                for it in section["items"]:
                    check(it, row, f"Household {i}: ")
        elif section.get("repeat") == "respondent":
            for idx, row in enumerate(clean.get("I") or []):
                for it in section["items"]:
                    check(it, row, f"{section['respondents'][idx]}: ")
        else:
            for it in section["items"]:
                check(it, clean, "")
    return out


def indicators(clean: dict) -> dict[str, Any]:
    """Per-visit values of the annex indicators: True / False, or None when not observed."""
    g = clean.get("G") or []
    yes = lambda code, scope=clean: str(scope.get(code, "")) == "1"  # noqa: E731
    asked = lambda code, scope=clean: code in scope  # noqa: E731
    team = None
    if asked("A16"):
        team = yes("A16") and (not asked("B1") or yes("B1")) and (not asked("D5") or str(clean.get("D5")) == "2")
    tablet = None
    if asked("C1"):
        tablet = yes("C1") and yes("C4") and yes("C5")
    spot = clean.get("D10") == 3 if asked("D10") else None
    visited = [yes("G2", row) for row in g if asked("G2", row)]
    sizes = [row for row in g if asked("G4_household", row) and asked("G4_tablet", row)]
    synced = None
    if asked("C9"):
        last = clean.get("C8")
        within = bool(last) and (date.fromisoformat(clean["A2"]) - date.fromisoformat(last)).days <= 1 if clean.get("A2") else bool(last)
        synced = clean["C9"] == 0 and within
    return {
        "team_in_ea": team,
        "tablet_ready": tablet,
        "spot_check": spot,
        "hh_visited": (sum(visited) / len(visited)) if visited else None,
        "hh_size_match": (sum(1 for r in sizes if r["G4_household"] == r["G4_tablet"]) / len(sizes)) if sizes else None,
        "census_night": yes("F9") if asked("F9") else None,
        "synced_24h": synced,
        "on_schedule": yes("H10") if asked("H10") else None,
        "ea_good": (clean["J7"] >= 3) if "J7" in clean else None,
        "overall_rating": clean.get("J7"),
    }


def public_spec() -> dict[str, Any]:
    """The questionnaire for clients; section phases become lists like the item phases."""
    sections = []
    for s in SECTIONS:
        d = dict(s)
        d["phases"] = list(s["phases"]) if s.get("phases") else []
        sections.append(d)
    return {"phases": [{"value": k, "label": v} for k, v in PHASES.items()], "sections": sections, "severities": SEVERITIES, "referred_to": REINFORCEMENT, "indicators": INDICATORS}


def night(t: time, start: time, end: time) -> bool:
    """True when t falls in the night window, which may cross midnight (20:00 to 05:00)."""
    return (start <= t or t < end) if start > end else (start <= t < end)


def parse_time(value: str, default: time) -> time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError):
        return default
