"""Load every district EA-frame workbook from a folder into the reference tables.

    python -m scripts.import_frames "C:\\2026_GIS_PRODUCTION_MAPS\\National"

Files named *_EA_FRAME_*.xlsx are imported one by one (the national workbook
and Excel lock files are skipped). Safe to re-run: names are updated in place
and ids never change."""

import sys
import time
from pathlib import Path

from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.services.import_service import import_reference


def main(folder: str) -> None:
    files = sorted(
        p for p in Path(folder).glob("*_EA_FRAME_*.xlsx")
        if not p.name.startswith("~$") and not p.name.upper().startswith("NATIONAL")
    )
    if not files:
        print(f"No *_EA_FRAME_*.xlsx files in {folder}")
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
        print(f"{result.rows} rows, +{result.teams} teams, +{result.supervisors} supervisors, +{result.enumerators} enumerators, +{result.eas} EAs, {len(result.warnings)} warnings, {time.time() - started:.0f}s")
        for w in result.warnings[:5]:
            print("   ", w)
    print("Done:", totals)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
