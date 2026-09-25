import os
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "adminpass123"

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db import session as session_module  # noqa: E402
from app.db import init_db as init_module  # noqa: E402

# One in-memory database shared by every connection in the test process.
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
session_module.engine = engine
session_module.SessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=engine, future=True)
init_module.engine = engine

from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def login(client, username, password, device_id=None):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password, "device_id": device_id})
    assert r.status_code == 200, r.text
    return r.json()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin(client):
    data = login(client, "admin", "adminpass123")
    return auth(data["access_token"])


@pytest.fixture
def geo(client, admin):
    """Two districts in one region via the import endpoint, plus an admin-created second region."""
    csv = (
        "Region,District Code,District,SA Code,SA Name,Supervisor,Enumerator,EA Code\n"
        "Western,WAU,Western Area Urban,WAU-SA01,Central 1,Mohamed Kamara,Fatmata Sesay,WAU-SA01-EA01\n"
        "Western,WAU,Western Area Urban,WAU-SA01,Central 1,Mohamed Kamara,Ibrahim Conteh,WAU-SA01-EA02\n"
        "Western,WAR,Western Area Rural,WAR-SA01,Waterloo 1,Aminata Bangura,Sorie Koroma,WAR-SA01-EA01\n"
    )
    r = client.post("/api/v1/admin/reference/import", files={"file": ("sa.csv", csv, "text/csv")}, headers=admin)
    assert r.status_code == 200, r.text
    districts = client.get("/api/v1/admin/reference/districts", headers=admin).json()
    teams = client.get("/api/v1/admin/reference/teams", headers=admin).json()
    cats = client.get("/api/v1/admin/reference/categories", headers=admin).json()
    return {"districts": {d["code"]: d for d in districts}, "teams": {t["code"]: t for t in teams}, "categories": cats, "import": r.json()}


@pytest.fixture
def monitor(client, admin, geo):
    body = {
        "username": "fm.wau",
        "password": "Password123",
        "full_name": "Field Monitor WAU",
        "role": "FIELD_MONITOR",
        "district_ids": [geo["districts"]["WAU"]["id"]],
    }
    r = client.post("/api/v1/admin/users", json=body, headers=admin)
    assert r.status_code == 201, r.text
    device_id = str(uuid.uuid4())
    data = login(client, "fm.wau", "Password123", device_id)
    headers = auth(data["access_token"])
    r = client.post("/api/v1/devices/register", json={"device_id": device_id, "model": "Test tablet", "android_version": "13", "app_version": "0.1.0"}, headers=headers)
    assert r.status_code == 200, r.text
    return {"headers": headers, "device_id": device_id, "user": data["user"], "refresh": data["refresh_token"]}


def make_error(geo, district="WAU", team="WAU-SA01", status="UNRESOLVED", hours_ago=1, **over):
    now = datetime.now(timezone.utc)
    created = now - timedelta(hours=hours_ago)
    body = {
        "id": str(uuid.uuid4()),
        "display_id": f"FM-{district}-2609-{uuid.uuid4().int % 10000:04d}",
        "district_id": geo["districts"][district]["id"],
        "team_id": geo["teams"][team]["id"],
        "supervisor_name": "Mohamed Kamara",
        "enumerator_name": "Fatmata Sesay",
        "category_id": geo["categories"][0]["id"],
        "description": "Missing household 12",
        "date_received": date.today().isoformat(),
        "support_method": "REMOTE",
        "action_taken": "Called supervisor",
        "status": status,
        "resolved_at": now.isoformat() if status == "RESOLVED" else None,
        "last_action_at": created.isoformat(),
        "client_created_at": created.isoformat(),
        "client_updated_at": created.isoformat(),
    }
    body.update(over)
    return body
