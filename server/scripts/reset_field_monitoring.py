"""Reset the Field Monitor error follow-up system by hand (see app/services/fm_reset.py for what is removed):

    python -m scripts.reset_field_monitoring --yes          # Field Monitor data, workload and accounts
    python -m scripts.reset_field_monitoring --yes --dqm    # ...and the DQM reports, exit check-outs and District DQM accounts
"""

import sys

from app.db.session import SessionLocal
from app.services.fm_reset import reset_data_quality, reset_field_monitoring


def main(argv: list[str]) -> None:
    if "--yes" not in argv:
        print(__doc__)
        print("Nothing deleted: add --yes to confirm.")
        sys.exit(1)
    db = SessionLocal()
    try:
        counts = reset_field_monitoring(db)
        if "--dqm" in argv:
            counts.update(reset_data_quality(db))
        db.commit()
        for k, v in counts.items():
            print(f"{k:34s} {v}")
    finally:
        db.close()


if __name__ == "__main__":
    main(sys.argv[1:])
