from pathlib import Path

from app.core.config import settings
from tests.test_dqm_reports import users  # noqa: F401


def test_resources_need_sign_in_and_links_serve_files(client, admin, users, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "RESOURCES_DIR", str(tmp_path))
    Path(tmp_path, "SLPHC-2026-Field-Monitor-User-Manual.pdf").write_bytes(b"%PDF-1.4 test")

    assert client.get("/api/v1/resources").status_code == 401

    listing = client.get("/api/v1/resources", headers=users["wau"]).json()
    by_key = {r["key"]: r for r in listing}
    assert by_key["manual-pdf"]["available"] is True and by_key["manual-pdf"]["opens_in_tab"] is True
    assert by_key["app-apk"]["available"] is False

    assert client.post("/api/v1/resources/app-apk/link", headers=users["wau"]).status_code == 404
    link = client.post("/api/v1/resources/manual-pdf/link", headers=users["wau"]).json()
    assert link["url"].startswith("/api/v1/resources/manual-pdf/file?t=")

    r = client.get(link["url"])  # no bearer header: the link itself carries the authorisation
    assert r.status_code == 200 and r.content == b"%PDF-1.4 test"
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith("inline")

    # a link cannot be reused for another file, and a bad token is refused
    token = link["url"].split("t=")[1]
    assert client.get(f"/api/v1/resources/manual-docx/file?t={token}").status_code == 401
    assert client.get("/api/v1/resources/manual-pdf/file?t=not-a-token").status_code == 401

    log = client.get("/api/v1/admin/audit", params={"action": "resource.download"}, headers=admin).json()
    assert log and log[0]["entity_id"] == "SLPHC-2026-Field-Monitor-User-Manual.pdf"
