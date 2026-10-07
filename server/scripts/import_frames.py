"""Load every frame workbook from a folder into the reference tables.

    python -m scripts.import_frames "C:\\2026_GIS_PRODUCTION_MAPS\\Field Monitoring"

Every .xlsx in the folder is imported (Excel lock files are skipped): the district
EA frames (*_EA_FRAME_*.xlsx), the national master frame (SUPERVISORY_AREA,
ENUMERATION_AREA and FIELD_MONITOR sheets) and the workload frame
(FIELD_MONITOR sheet only, imported last so its assignments win). Safe to
re-run: names are updated in place and ids never change."""

import sys
import time
from pathlib import Path

import json

from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models import MefmFrameVersion
from app.services.import_service import import_reference


def main(folder: str) -> None:
    files = sorted(
        (p for p in Path(folder).glob("*.xlsx") if not p.name.startswith("~$")),
        key=lambda p: (p.name.upper().startswith("FIELD_MONITOR"), p.name),  # workload frame last
    )
    if not files:
        print(f"No .xlsx files in {folder}")
        sys.exit(1)
    db = SessionLocal()
    init_db(db)
    totals = {"rows": 0, "teams": 0, "supervisors": 0, "enumerators": 0, "eas": 0}
    for path in files:
        started = time.time()
        print(f"{path.name} ... ", end="", flush=True)
        result = import_reference(db, path.name, path)
        for k in totals:
            totals[k] += getattr(result, k)
        print(f"{result.rows} rows, +{result.teams} teams, +{result.chiefdoms} chiefdoms, +{result.sections} sections, +{result.supervisors} supervisors, +{result.enumerators} enumerators, +{result.eas} EAs, {result.assigned} SAs assigned, {result.updated} updated, {len(result.warnings)} warnings, {time.time() - started:.0f}s")
        for w in result.warnings[:5]:
            print("   ", w)
        # the same record a dashboard upload leaves, so the Frame versions table shows command-line imports too
        db.add(MefmFrameVersion(
            filename=path.name, applied_by=None, rows=result.rows,
            counts=json.dumps({"regions": result.regions, "districts": result.districts, "chiefdoms": result.chiefdoms, "sections": result.sections, "teams": result.teams, "supervisors": result.supervisors, "enumerators": result.enumerators, "eas": result.eas, "assigned": result.assigned}),
            changes=json.dumps({"updated": result.updated, "removed": result.removed, "warnings": len(result.warnings)}), note="command line (scripts.import_frames)",
        ))
        db.commit()
    print("Done:", totals)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
