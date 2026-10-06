"""Build the user-import CSV for every Field Monitor and DQM officer in the workload frame.

    python -m scripts.make_workload_users "C:\\...\\FIELD_MONITOR-NATIONAL_MASTER_FRAME.xlsx" out.csv

Reads the FIELD_MONITOR sheet (one row per SA with Field monitor ID and DQM ID) and
writes one account per officer: username = the staff code in lower case (fm-11-001,
dqm-11-001), role FIELD_MONITOR or DISTRICT_DQM, the officer's district, the staff
code (which links the account to its SAs) and a generated initial password.

The CSV is imported on the dashboard: User management > Import CSV. Keep the file
private: it holds the initial passwords to hand to each officer. Accounts that
already exist are skipped by the import, so it is safe to re-run."""

import csv
import secrets
import string
import sys
from collections import OrderedDict

from openpyxl import load_workbook

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
        district = str(row[dist_i]).strip().title().replace("Western Urban", "Western Urban")
        for code, role in ((str(row[fm_i]).strip().upper(), "FIELD_MONITOR"), (str(row[dqm_i]).strip().upper(), "DISTRICT_DQM")):
            if code not in officers:
                officers[code] = {
                    "username": code.lower(),
                    "password": password(),
                    "full_name": f"{'Field Monitor' if role == 'FIELD_MONITOR' else 'DQM'} {code} ({district})",
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
