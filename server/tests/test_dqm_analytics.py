from datetime import date, timedelta

from tests.conftest import auth, login
from tests.test_dqm_reports import report_body, users  # noqa: F401  (fixture re-use)


def test_district_region_and_national_analytics(client, users):  # noqa: F811
    today = date.today()
    y = today - timedelta(days=1)
    r1 = client.post("/api/v1/dqm-reports", json=report_body(day=y, teams_reviewed=8, teams_certified=5), headers=users["wau"]).json()
    client.post(f"/api/v1/dqm-reports/{r1['id']}/submit", headers=users["wau"])
    r2 = client.post("/api/v1/dqm-reports", json=report_body(), headers=users["wau"]).json()
    client.post(f"/api/v1/dqm-reports/{r2['id']}/submit", headers=users["wau"])
    client.post(f"/api/v1/dqm-reports/{r2['id']}/receive", json={}, headers=users["national"])
    client.post("/api/v1/dqm-reports", json=report_body(day=y), headers=users["war"])  # draft only

    # District level: the district officer needs no district_id
    a = client.get("/api/v1/dqm-reports/analytics", params={"level": "district", "date_from": y.isoformat(), "date_to": today.isoformat()}, headers=users["wau"]).json()
    assert a["level"] == "district" and a["title"] == "Western Area Urban" and len(a["days"]) == 2
    assert [t["reports"] for t in a["trend"]] == [1, 1]
    assert [t["teams_certified"] for t in a["trend"]] == [5, 9]
    assert a["trend"][1]["high"] == 1 and a["trend"][1]["gps"] == 1 and a["trend"][1]["issues_open"] == 1 and a["trend"][1]["issues_resolved"] == 1
    assert a["units"][0]["teams_certified"] == 9  # latest cumulative
    assert a["units"][0]["reint_received"] == 60
    assert a["compliance"][0]["cells"] == ["SUBMITTED", "RECEIVED"]
    assert a["expected_reports"] == 2 and a["submitted_reports"] == 2

    # Cannot peek at another district
    assert client.get("/api/v1/dqm-reports/analytics", params={"level": "district", "district_id": users["war_id"]}, headers=users["wau"]).status_code == 403

    # Region level for the regional user: region inferred
    g = client.get("/api/v1/dqm-reports/analytics", params={"level": "region", "date_from": y.isoformat(), "date_to": today.isoformat()}, headers=users["regional"]).json()
    assert g["unit_label"] == "District" and {u["label"] for u in g["units"]} == {"Western Area Urban", "Western Area Rural"}
    war = next(u for u in g["units"] if u["label"] == "Western Area Rural")
    assert war["reports"] == 1 and war["submitted"] == 0 and war["teams_certified"] == 9
    assert g["totals"]["teams_certified"] == 18 and g["totals"]["high"] == 3
    rows = {c["label"]: c["cells"] for c in g["compliance"]}
    assert rows["Western Area Rural"] == ["DRAFT", "NONE"]
    assert g["expected_reports"] == 4 and g["submitted_reports"] == 2

    # National level: regional user refused, national sees regions
    assert client.get("/api/v1/dqm-reports/analytics", params={"level": "national"}, headers=users["regional"]).status_code == 403
    n = client.get("/api/v1/dqm-reports/analytics", params={"level": "national", "date_from": y.isoformat(), "date_to": today.isoformat()}, headers=users["national"]).json()
    assert n["unit_label"] == "Region" and n["units"][0]["label"] == "Western" and n["units"][0]["reports"] == 3
    assert len(n["compliance"]) == 2  # compliance is always by district
    by_name = {x["label"]: x for x in n["districts"]}
    assert by_name["Western Area Urban"]["teams_certified"] == 9 and by_name["Western Area Urban"]["submitted"] == 2 and by_name["Western Area Urban"]["expected"] == 2
    assert by_name["Western Area Rural"]["region"] == "Western" and by_name["Western Area Rural"]["latest_date"] == y.isoformat()
    assert [t["reports"] for t in n["trend"]] == [2, 1]

    # Defaults to the last 14 days; over 120 days refused
    d = client.get("/api/v1/dqm-reports/analytics", params={"level": "national"}, headers=users["national"]).json()
    assert len(d["days"]) == 14
    assert client.get("/api/v1/dqm-reports/analytics", params={"level": "national", "date_from": "2026-01-01", "date_to": "2026-09-01"}, headers=users["national"]).status_code == 400
