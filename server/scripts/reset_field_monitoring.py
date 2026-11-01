"""Reset the Field Monitor error follow-up system by hand (see app/services/fm_reset.py for what is removed):

    python -m scripts.reset_field_monitoring --yes
"""

import sys

from app.db.session import SessionLocal
from app.services.fm_reset import reset_field_monitoring


def main(argv: list[str]) -> None:
    if "--yes" not in argv:
        print(__doc__)
        print("Nothing deleted: add --yes to confirm.")
        sys.exit(1)
    db = SessionLocal()
    try:
        counts = reset_field_monitoring(db)
        db.commit()
        for k, v in counts.items():
            print(f"{k:34s} {v}")
    finally:
        db.close()


if __name__ == "__main__":
    main(sys.argv[1:])
