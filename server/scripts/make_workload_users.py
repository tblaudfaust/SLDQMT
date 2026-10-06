"""Build the user-import CSV for every Field Monitor and DQM officer in the workload frame.

    python -m scripts.make_workload_users "C:\\...\\FIELD_MONITOR-NATIONAL_MASTER_FRAME.xlsx" out.csv

Reads the FIELD_MONITOR sheet (one row per SA with Field monitor ID and DQM ID) and
writes one account per officer: the staff code in the district-abbreviation style
(FM-Bo-001, DQM-Bo-001) as both username and staff code (sign-in ignores case), the
code again as the full name until an administrator enters the officer's real name,
role FIELD_MONITOR or DISTRICT_DQM, the officer's district and a generated initial
password.

The CSV is imported on the dashboard: User management > Import CSV. Keep the file
private: it holds the initial passwords to hand to each officer. Accounts that
already exist are skipped by the import, so it is safe to re-run."""

import csv
import secrets
import string
import sys
from collections import OrderedDict

from openpyxl import load_workbook

from app.core.districts import canonical_staff_code

ALPHABET = string.ascii_uppercase + string.ascii_lowercase + string.digits


def password() -> str:
    # 10 characters, letters and digits only, no look-alikes: easy to read out and type on a tablet
    chars = [c for c in ALPHABET if c not in "0O1lI"]
    return "".join(secrets.choice(chars) for _ in range(10))


def main(workbook: str, out: str) -> None:
    wb = load_workbook(workbook, read_only=True, data_only=True)
    ws = wb["FIELD_MONITOR"] if "FIELD_MONITOR" in wb.sheetnames else wb.active
    it = ws.iter_rows(values_only=True)
    headers = [str(h or "").strip() for h in next(it)]
    col = {h.lower(): i for i, h in enumerate(headers)}
    fm_i, dqm_i, dist_i = col["field monitor id"], col["dqm id"], col["district"]
    officers: "OrderedDict[str, dict]" = OrderedDict()
    for row in it:
        if not row or not row[fm_i]:
            continue
        district = str(row[dist_i]).strip().title()
        for raw, role in ((row[fm_i], "FIELD_MONITOR"), (row[dqm_i], "DISTRICT_DQM")):
            code = canonical_staff_code(str(raw))  # FM-41-001 -> FM-Bo-001
            if code not in officers:
                officers[code] = {
                    "username": code,  # the staff code is the username (sign-in ignores case)
                    "password": password(),
                    # the real name is not known yet: the code stands in until an administrator edits it
                    "full_name": code,
                    "phone": "",
                    "role": role,
                    "districts": district,
                    "region": "",
                    "staff_code": code,
                }
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["username", "password", "full_name", "phone", "role", "districts", "region", "staff_code"])
        w.writeheader()
        w.writerows(officers.values())
    fms = sum(1 for o in officers.values() if o["role"] == "FIELD_MONITOR")
    print(f"wrote {out}: {fms} Field Monitors, {len(officers) - fms} DQM officers")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
