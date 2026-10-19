"""Android app updates: the latest version of each app and the APK itself, without sign-in (an APK is not
sensitive, and the app checks before the user signs in)."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core import app_versions

router = APIRouter(tags=["app-updates"])


@router.get("/public/app-version")
def app_version():
    """Latest version code and name per app, with the download address."""
    return app_versions.latest()


@router.get("/public/app/{key}.apk")
def download_apk(key: str):
    apps = app_versions.latest()
    if key not in apps:
        raise HTTPException(404, "Unknown app")
    path = app_versions.resources_dir() / apps[key]["file"]
    if not path.is_file():
        raise HTTPException(404, "This app has not been uploaded to the server yet")
    return FileResponse(path, media_type="application/vnd.android.package-archive", filename=apps[key]["file"], content_disposition_type="attachment")
