"""Import of reference data: regions, districts, teams (supervisory areas),
supervisors, enumerators and EAs.

Two inputs are accepted:

1. The census GIS district workbooks (`<DISTRICT>_EA_FRAME_<date>.xlsx`), which
   carry a SUPERVISORY_AREA sheet (one row per SA with SA_CODE, SA_NAME,
   CHFDM_NAME, LC_CC_NAME, NO_OF_EAS, SUPERVISOR id) and an ENUMERATION_AREA
   sheet (one row per EA-locality with SA_CODE, EA_CODE, EA_NAME, LOC_NAME,
   TOT_HH, LONGITUDE, LATITUDE, ENUMERATOR id). Supervisors and enumerators
   appear only as ID numbers there, so they are created as "Supervisor 1961"
   and "Enumerator 006011" until names are supplied.

2. A simple CSV or XLSX with a header row using any of the recognised column
   names below (Region, District, SA Code, Supervisor, Enumerator, EA Code...),
   which is also how names and phone numbers can be added later.

3. The workload frame (FIELD_MONITOR sheet, or the national master frame that
   carries it next to the two frame sheets): one row per SA with Field monitor ID
   and DQM ID, stored on the team as monitor_code and dqm_code in the
   district-abbreviation form (FM-11-001 -> FM-Kai-001, see app.core.districts).

3. The workload frame (FIELD_MONITOR sheet, or the national master frame that
   carries it next to the two frame sheets): one row per SA with Field monitor ID
   and DQM ID, stored on the team as monitor_code and dqm_code.

Re-running an import updates names in place and never changes ids, so error
records keep pointing at the right team."""

import csv
import io
import re
from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.districts import canonical_staff_code
from app.models import District, Enumerator, EnumerationArea, MefmChiefdom, MefmSection, Region, Supervisor, Team
from app.schemas.admin import ImportResult

# canonical field -> accepted header spellings (normalised: lower-case, alphanumerics only)
COLUMNS: dict[str, list[str]] = {
    "region": ["region", "regionname", "province", "regname"],
    "region_code": ["regioncode", "regcode"],
    "district": ["district", "districtname", "distname"],
    "district_code": ["districtcode", "distcode", "dcode"],
    "chiefdom": ["chiefdom", "chiefdomname", "chfdmname"],
    "local_council": ["localcouncil", "council", "lcccname"],
    "team_code": ["teamcode", "sacode", "supervisoryareacode", "sa", "sano", "sanumber", "team"],
    "team_name": ["teamname", "saname", "supervisoryarea", "supervisoryareaname"],
    "ea_count": ["noofeas", "eacount", "numberofeas"],
    "chiefdom_code": ["chiefdomcode", "chfdmcode"],
    "section": ["section", "sectname", "sectionname"],
    "section_code": ["sectioncode", "sectcode"],
    "pop_ea_code": ["popeacode", "eacode10", "popea"],
    "loc_status": ["locstatus", "urbanrural"],
    "monitor_code": ["fieldmonitorid", "fmid", "monitorid", "fieldmonitorcode", "fieldmonitor"],
    "dqm_code": ["dqmid", "dqmcode", "dqm"],
    "monitor_code": ["fieldmonitorid", "fmid", "monitorid", "fieldmonitorcode", "fieldmonitor"],
    "dqm_code": ["dqmid", "dqmcode", "dqm"],
    "supervisor_code": ["supervisorcode", "supcode", "supervisorno", "supervisornumber"],
    "supervisor_external_id": ["supid", "supervisorid"],
    "supervisor": ["supervisor", "supervisorname"],
    "supervisor_phone": ["supervisorphone", "supervisorcontact", "supervisortel", "supphone"],
    "enumerator_code": ["enumeratorcode", "enumcode", "enumeratorno", "enumeratornumber"],
    "enumerator_external_id": ["enumid", "enumeratorid"],
    "enumerator": ["enumerator", "enumeratorname"],
    "enumerator_phone": ["enumeratorphone", "enumeratorcontact", "enumeratortel"],
    "ea_code": ["eacode", "ea", "eanumber", "eano", "enumerationareacode", "enumerationarea"],
    "ea_name": ["eaname", "enumerationareaname", "eadescription"],
    "locality": ["locality", "locname", "localityname"],
    "households": ["households", "tothh", "hh", "nohouseholds"],
    "latitude": ["latitude", "lat", "y"],
    "longitude": ["longitude", "lng", "lon", "long", "x"],
}

# In the GIS frame workbooks SUPERVISOR and ENUMERATOR are ID numbers, not names.
FRAME_OVERRIDES = {"supervisor": "supervisor_code", "enumerator": "enumerator_code"}
# FIELD_MONITOR (the workload sheet) carries, per SA, the Field monitor ID and DQM ID.
FRAME_SHEETS = ("SUPERVISORY_AREA", "ENUMERATION_AREA", "FIELD_MONITOR")

# spelling -> (canonical, rank). Earlier spellings in COLUMNS win when a sheet
# carries several candidates, e.g. SA_CODE (rank 1) beats SA_NO (rank 4).
_LOOKUP: dict[str, tuple[str, int]] = {}
for _canonical, _spellings in COLUMNS.items():
    for _rank, _s in enumerate(_spellings):
        _LOOKUP.setdefault(_s, (_canonical, _rank))


def _norm(h) -> str:
    return re.sub(r"[^a-z0-9]", "", str(h or "").lower())


def clean_name(value: str | None) -> str | None:
    """'MADULFORAYA_COMMUNITY_MOSQUE_' -> 'Madulforaya Community Mosque'."""
    if value is None:
        return None
    text = re.sub(r"[_\s]+", " ", str(value)).strip()
    if not text:
        return None
    if text.isupper() or "_" in str(value):
        text = " ".join(w.capitalize() if not w.isdigit() else w for w in text.split(" "))
    return text


def _map_row(raw: dict, frame: bool) -> dict[str, str]:
    out: dict[str, str] = {}
    ranks: dict[str, int] = {}
    for k, v in raw.items():
        hit = _LOOKUP.get(_norm(k))
        if hit is None or v is None or str(v).strip() == "":
            continue
        canon, rank = hit
        if frame:
            canon = FRAME_OVERRIDES.get(canon, canon)
        if canon not in out or rank < ranks[canon]:
            out[canon] = str(v).strip()
            ranks[canon] = rank
    return out


def _sheet_rows(ws, frame: bool):
    it = ws.iter_rows(values_only=True)
    headers = next(it, None) or []
    for row in it:
        mapped = _map_row(dict(zip(headers, row)), frame)
        if mapped:
            yield mapped


def read_rows(filename: str, source: bytes | str | Path):
    """Yield canonical rows from a CSV, a plain XLSX, or a GIS frame workbook."""
    if filename.lower().endswith((".xlsx", ".xlsm")):
        handle = io.BytesIO(source) if isinstance(source, bytes) else str(source)
        wb = load_workbook(handle, read_only=True, data_only=True)
        if "SUPERVISORY_AREA" in wb.sheetnames:
            for sheet in FRAME_SHEETS:
                if sheet in wb.sheetnames:
                    yield from _sheet_rows(wb[sheet], frame=True)
        else:
            yield from _sheet_rows(wb.active, frame=False)
        wb.close()
    else:
        text = source.decode("utf-8-sig", errors="replace") if isinstance(source, bytes) else Path(source).read_text(encoding="utf-8-sig")
        for raw in csv.DictReader(io.StringIO(text)):
            mapped = _map_row(raw, frame=False)
            if mapped:
                yield mapped


class _Importer:
    def __init__(self, db: Session, default_region: str | None):
        self.db = db
        self.default_region = default_region
        self.counts = {"regions": 0, "districts": 0, "teams": 0, "supervisors": 0, "enumerators": 0, "eas": 0, "assigned": 0, "chiefdoms": 0, "sections": 0, "updated": 0}
        self.chiefdoms: dict[str, MefmChiefdom] = {c.code: c for c in db.execute(select(MefmChiefdom)).scalars()}
        self.sections: dict[str, MefmSection] = {x.code: x for x in db.execute(select(MefmSection)).scalars()}
        self.seen_teams: set[int] = set()
        self.seen_eas: set[int] = set()
        self.touched_districts: set[int] = set()
        self.warnings: list[str] = []
        self.rows = 0
        self.regions = {r.code: r for r in db.execute(select(Region)).scalars()}
        self.regions_by_name = {r.name.lower(): r for r in self.regions.values()}
        self.districts = {d.code: d for d in db.execute(select(District)).scalars()}
        self.districts_by_name = {d.name.lower(): d for d in self.districts.values()}
        self.teams: dict[tuple[int, str], Team] = {}
        self.supervisors: dict[tuple[int, str], Supervisor] = {}
        self.enumerators: dict[tuple[int, str], Enumerator] = {}
        self.eas: dict[tuple[int, str], EnumerationArea] = {}

    def warn(self, i: int, msg: str):
        if len(self.warnings) < 200:
            self.warnings.append(f"Row {i}: {msg}")

    def region(self, row: dict) -> Region | None:
        name = clean_name(row.get("region") or self.default_region)
        code = row.get("region_code")
        if code and code in self.regions:
            return self.regions[code]
        if name and name.lower() in self.regions_by_name:
            return self.regions_by_name[name.lower()]
        if not (name or code):
            return None
        code = code or name[:3].upper()
        region = Region(code=code, name=name or code)
        self.db.add(region)
        self.db.flush()
        self.regions[code] = region
        self.regions_by_name[region.name.lower()] = region
        self.counts["regions"] += 1
        return region

    def district(self, i: int, row: dict) -> District | None:
        name = clean_name(row.get("district"))
        code = row.get("district_code")
        if not (name or code):
            self.warn(i, "no district, skipped")
            return None
        if code and code in self.districts:
            d = self.districts[code]
        elif name and name.lower() in self.districts_by_name:
            d = self.districts_by_name[name.lower()]
        else:
            region = self.region(row)
            if region is None:
                self.warn(i, f"new district '{name or code}' has no region, skipped")
                return None
            code = code or name[:3].upper()
            d = District(region_id=region.id, code=code, name=name or code)
            self.db.add(d)
            self.db.flush()
            self.districts[code] = d
            self.districts_by_name[d.name.lower()] = d
            self.counts["districts"] += 1
        if name and d.name != name:
            d.name = name
        return d

    def team(self, i: int, row: dict, district: District) -> Team | None:
        code = row.get("team_code")
        if not code:
            if any(row.get(k) for k in ("supervisor", "supervisor_code", "enumerator", "enumerator_code", "ea_code")):
                self.warn(i, "supervisor/enumerator/EA without a team (SA) code, skipped")
            return None
        key = (district.id, code)
        team = self.teams.get(key)
        if team is None:
            team = self.db.execute(select(Team).where(Team.district_id == district.id, Team.code == code)).scalars().first()
        name = clean_name(row.get("team_name"))
        if team is None:
            team = Team(district_id=district.id, code=code, name=name or f"SA {code}", chiefdom=clean_name(row.get("chiefdom")), local_council=clean_name(row.get("local_council")))
            self.db.add(team)
            self.db.flush()
            self.counts["teams"] += 1
        else:
            if name and team.name != name:
                team.name = name
                self.counts["updated"] += 1
            if row.get("chiefdom"):
                team.chiefdom = clean_name(row["chiefdom"])
            if row.get("local_council"):
                team.local_council = clean_name(row["local_council"])
        if row.get("ea_count") and str(row["ea_count"]).isdigit():
            team.ea_count = int(row["ea_count"])
        if row.get("monitor_code") or row.get("dqm_code"):
            # Workload: who is responsible for this SA. The same SAs go to the Field Monitor and the DQM.
            for attr in ("monitor_code", "dqm_code"):
                if row.get(attr):
                    setattr(team, attr, canonical_staff_code(row[attr]))  # FM-11-001 -> FM-Kai-001
            self.counts["assigned"] += 1
        self.teams[key] = team
        self.seen_teams.add(team.id)
        self.touched_districts.add(district.id)
        return team

    def chiefdom(self, row: dict, district: District) -> MefmChiefdom | None:
        code = row.get("chiefdom_code")
        if not code:
            return None
        name = clean_name(row.get("chiefdom")) or f"Chiefdom {code}"
        c = self.chiefdoms.get(code)
        if c is None:
            c = MefmChiefdom(district_id=district.id, code=code, name=name)
            self.db.add(c)
            self.db.flush()
            self.chiefdoms[code] = c
            self.counts["chiefdoms"] += 1
        elif c.name != name or c.district_id != district.id:
            c.name, c.district_id = name, district.id
            self.counts["updated"] += 1
        return c

    def section(self, row: dict, chiefdom: MefmChiefdom | None) -> MefmSection | None:
        code = row.get("section_code")
        if not code or chiefdom is None:
            return None
        name = clean_name(row.get("section")) or f"Section {code}"
        x = self.sections.get(code)
        if x is None:
            x = MefmSection(district_id=chiefdom.district_id, chiefdom_id=chiefdom.id, code=code, name=name)
            self.db.add(x)
            self.db.flush()
            self.sections[code] = x
            self.counts["sections"] += 1
        elif x.name != name or x.chiefdom_id != chiefdom.id:
            x.name, x.chiefdom_id, x.district_id = name, chiefdom.id, chiefdom.district_id
            self.counts["updated"] += 1
        return x

    def person(self, model, cache: dict, counter: str, team: Team, name: str | None, code: str | None, external_id: str | None, phone: str | None):
        if not (name or code):
            return
        label = clean_name(name) or f"{'Supervisor' if model is Supervisor else 'Enumerator'} {code}"
        key = (team.id, code or label.lower())
        row = cache.get(key)
        if row is None:
            q = select(model).where(model.team_id == team.id)
            q = q.where(model.code == code) if code else q.where(model.name == label)
            row = self.db.execute(q).scalars().first()
        if row is None:
            row = model(team_id=team.id, code=code, external_id=external_id, name=label, phone=phone)
            self.db.add(row)
            self.db.flush()
            self.counts[counter] += 1
        else:
            if name:
                row.name = label
            if phone:
                row.phone = phone
            if external_id and not row.external_id:
                row.external_id = external_id
        cache[key] = row

    def ea(self, row: dict, team: Team):
        code = row.get("ea_code")
        if not code:
            return
        key = (team.id, code)
        ea = self.eas.get(key)
        if ea is None:
            ea = self.db.execute(select(EnumerationArea).where(EnumerationArea.team_id == team.id, EnumerationArea.code == code)).scalars().first()
        name = clean_name(row.get("ea_name"))
        locality = clean_name(row.get("locality"))
        households = int(row["households"]) if str(row.get("households", "")).isdigit() else None
        lat = _float(row.get("latitude"))
        lng = _float(row.get("longitude"))
        if ea is None:
            ea = EnumerationArea(team_id=team.id, code=code, name=name, locality=locality, households=households, lat=lat, lng=lng)
            self.db.add(ea)
            self.db.flush()
            self.counts["eas"] += 1
        else:
            if name and ea.name != name:
                ea.name = name
                self.counts["updated"] += 1
            # An EA spans several localities; keep the first as the reference locality.
            if locality and not ea.locality:
                ea.locality = locality
            if households is not None and ea.households is None:
                ea.households = households
            if lat is not None and ea.lat is None:
                ea.lat, ea.lng = lat, lng
        # the national frame: the 10-digit code officers type, geography below the district, expected households
        for attr, col in (("pop_ea_code", "pop_ea_code"), ("chiefdom_code", "chiefdom_code"), ("section_code", "section_code"), ("loc_status", "loc_status")):
            if row.get(col) and getattr(ea, attr) != str(row[col]):
                setattr(ea, attr, str(row[col]))
        if households is not None and ea.expected_households != households:
            ea.expected_households = households
        self.eas[key] = ea
        self.seen_eas.add(ea.id)

    def run(self, rows, dry_run: bool = False) -> ImportResult:
        for i, row in enumerate(rows, start=2):
            self.rows += 1
            district = self.district(i, row)
            if district is None:
                continue
            self.section(row, self.chiefdom(row, district))
            team = self.team(i, row, district)
            if team is None:
                continue
            self.person(Supervisor, self.supervisors, "supervisors", team, row.get("supervisor"), row.get("supervisor_code"), row.get("supervisor_external_id"), row.get("supervisor_phone"))
            self.person(Enumerator, self.enumerators, "enumerators", team, row.get("enumerator"), row.get("enumerator_code"), row.get("enumerator_external_id"), row.get("enumerator_phone"))
            self.ea(row, team)
            if self.rows % 2000 == 0:
                self.db.flush()
        removed = self.removed()
        if dry_run:
            self.db.rollback()
        else:
            self.db.commit()
        return ImportResult(rows=self.rows, warnings=self.warnings[:100], dry_run=dry_run, removed=removed, **self.counts)

    def removed(self) -> dict:
        """Active SAs and EAs of the districts in the file that the file no longer lists: reported, never deleted."""
        if not self.touched_districts:
            return {}
        teams = self.db.execute(select(Team).where(Team.district_id.in_(self.touched_districts), Team.active.is_(True))).scalars().all()
        gone_teams = [t for t in teams if t.id not in self.seen_teams]
        team_ids = [t.id for t in teams]
        eas = self.db.execute(select(EnumerationArea).where(EnumerationArea.team_id.in_(team_ids), EnumerationArea.active.is_(True))).scalars().all() if team_ids else []
        gone_eas = [e for e in eas if e.id not in self.seen_eas]
        return {"teams": len(gone_teams), "eas": len(gone_eas), "team_codes": [t.code for t in gone_teams[:20]], "ea_codes": [e.code for e in gone_eas[:20]]}


def _float(v) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def import_reference(db: Session, filename: str, source: bytes | str | Path, default_region: str | None = None, dry_run: bool = False) -> ImportResult:
    return _Importer(db, default_region).run(read_rows(filename, source), dry_run=dry_run)
