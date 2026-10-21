"""The latest version of each Android app, so an installed app can tell the user an update is available.

Defaults below match the APKs shipped with this server version. To publish a newer APK without a server
release, copy it to the downloads folder (RESOURCES_DIR) and write app-versions.json next to it, e.g.
{"fieldtool": {"version_code": 3, "version_name": "1.2.0"}}; the file overrides the defaults."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings

APPS: dict[str, dict] = {
    "fieldtool": {"title": "SLPHC M&E Field Tool", "package": "sl.gov.statistics.mefieldtool", "version_code": 2, "version_name": "1.1.0", "file": "SLPHC-ME-FieldTool.apk", "notes": "EAs under the SA, GPS required, update check."},
    "fieldmonitor": {"title": "SLPHC Field Monitor", "package": "sl.gov.statistics.fieldmonitor", "version_code": 5, "version_name": "0.4.1", "file": "SLPHC-FieldMonitor.apk", "notes": "SA filter, enumerator linked to the EA, no future date received"},
}


def resources_dir() -> Path:
    return Path(settings.RESOURCES_DIR)


def latest() -> dict[str, dict]:
    out = {k: dict(v) for k, v in APPS.items()}
    override = resources_dir() / "app-versions.json"
    if override.is_file():
        try:
            for k, v in json.loads(override.read_text(encoding="utf-8")).items():
                if k in out and isinstance(v, dict):
                    out[k].update({kk: vv for kk, vv in v.items() if kk in ("version_code", "version_name", "notes", "file")})
        except (ValueError, OSError):
            pass
    for k, v in out.items():
        path = resources_dir() / v["file"]
        v["available"] = path.is_file()
        v["size_bytes"] = path.stat().st_size if path.is_file() else None
        v["download_url"] = f"{settings.API_V1_PREFIX}/public/app/{k}.apk"
    return out
