"""Staff codes for Field Monitors and DQM officers, named after their district.

The workload frame numbers officers by district code (FM-11-001, DQM-11-001 for
Kailahun, code 11). Accounts use the same codes with the district abbreviated:
FM-Kai-001 and DQM-Kai-001, and the code is also the username (sign-in ignores
case). Both spellings are accepted anywhere a code is typed or imported and are
stored in the canonical abbreviated form."""

import re

# census district code -> abbreviation used in staff codes
DISTRICT_ABBREVIATIONS: dict[str, str] = {
    "11": "Kai",  # Kailahun
    "12": "Ken",  # Kenema
    "13": "Kon",  # Kono
    "21": "Bom",  # Bombali
    "22": "Fal",  # Falaba
    "23": "Koi",  # Koinadugu
    "24": "Ton",  # Tonkolili
    "31": "Kam",  # Kambia
    "32": "Kar",  # Karene
    "33": "PLo",  # Port Loko
    "41": "Bo",   # Bo
    "42": "Bon",  # Bonthe
    "43": "Moy",  # Moyamba
    "44": "Puj",  # Pujehun
    "51": "WAR",  # Western Area Rural
    "52": "WAU",  # Western Area Urban
}
_ABBR_BY_LOWER = {a.lower(): a for a in DISTRICT_ABBREVIATIONS.values()}
_CODE_BY_ABBR = {a: c for c, a in DISTRICT_ABBREVIATIONS.items()}
_PATTERN = re.compile(r"^\s*(FM|DQM)\s*-\s*([A-Za-z0-9]+)\s*-\s*(\d{1,4})\s*$", re.IGNORECASE)


def district_abbreviation(district_code: str) -> str:
    """'41' -> 'Bo'; an unknown code is used as it is (test fixtures, future districts)."""
    return DISTRICT_ABBREVIATIONS.get(str(district_code), str(district_code))


def canonical_staff_code(value: str | None) -> str | None:
    """'fm-41-1', 'FM-BO-001' and 'FM-Bo-001' all become 'FM-Bo-001'. Blank -> None.
    A value that is not a staff code is kept as typed (stripped)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    m = _PATTERN.match(text)
    if not m:
        return text
    prefix, district, number = m.group(1).upper(), m.group(2), m.group(3)
    district = DISTRICT_ABBREVIATIONS.get(district) or _ABBR_BY_LOWER.get(district.lower()) or district
    return f"{prefix}-{district}-{int(number):03d}"


def staff_code_role(code: str) -> str | None:
    """'FM-Bo-001' -> 'FIELD_MONITOR', 'DQM-Bo-001' -> 'DISTRICT_DQM'."""
    m = _PATTERN.match(code or "")
    if not m:
        return None
    return "FIELD_MONITOR" if m.group(1).upper() == "FM" else "DISTRICT_DQM"


def staff_code_district(code: str) -> str | None:
    """The district token of a code, as the census district code when known: 'FM-Bo-001' -> '41'."""
    m = _PATTERN.match(code or "")
    if not m:
        return None
    token = m.group(2)
    if token in DISTRICT_ABBREVIATIONS:
        return token
    return _CODE_BY_ABBR.get(_ABBR_BY_LOWER.get(token.lower(), token), token)
