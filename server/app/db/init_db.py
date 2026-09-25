"""Create tables, add columns introduced after a database was created, and
seed the minimum the system needs to start: the admin user, default settings,
the role permissions, and the error category and source pick lists."""

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import engine
from app.models import DEFAULT_SETTINGS, ErrorCategory, ErrorSource, Role, Setting, User
from app.services.permission_service import seed_defaults

DEFAULT_CATEGORIES = [
    ("MISSING_HH", "Missing household"),
    ("DUP_HH", "Duplicate household"),
    ("AGE_SEX", "Age/sex inconsistency"),
    ("INCOMPLETE", "Incomplete questionnaire"),
    ("GPS_OUT", "GPS outside EA"),
    ("HH_SIZE", "Household size mismatch"),
    ("SKIP", "Skip pattern violated"),
    ("OUTLIER", "Outlier value"),
    ("NOT_SYNCED", "Data not synced"),
    ("OTHER", "Other"),
]

DEFAULT_SOURCES = [
    ("EXCEL", "Excel sheet"),
    ("WHATSAPP", "WhatsApp"),
    ("SCREENSHOT", "Screenshot"),
    ("PHONE", "Phone call"),
    ("EMAIL", "Email"),
    ("OTHER", "Other"),
]


def add_missing_columns() -> None:
    """Lightweight forward migration: add nullable columns that models gained
    after the table was created. Types come from the model. (Alembic can
    replace this once the schema settles.)"""
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing or not col.nullable or col.primary_key:
                    continue
                ddl_type = col.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl_type}'))


def init_db(db: Session) -> None:
    Base.metadata.create_all(bind=engine)
    add_missing_columns()

    for key, value in DEFAULT_SETTINGS.items():
        if db.get(Setting, key) is None:
            db.add(Setting(key=key, value=value))

    for i, (code, name) in enumerate(DEFAULT_CATEGORIES):
        if not db.execute(select(ErrorCategory).where(ErrorCategory.code == code)).scalars().first():
            db.add(ErrorCategory(code=code, name=name, sort_order=i))
    for i, (code, name) in enumerate(DEFAULT_SOURCES):
        if not db.execute(select(ErrorSource).where(ErrorSource.code == code)).scalars().first():
            db.add(ErrorSource(code=code, name=name, sort_order=i))

    admin_username = settings.BOOTSTRAP_ADMIN_USERNAME.lower()
    if not db.execute(select(User).where(User.username == admin_username)).scalars().first():
        db.add(
            User(
                username=admin_username,
                password_hash=hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
                full_name="System Administrator",
                role=Role.ADMIN,
            )
        )
    seed_defaults(db)
    db.commit()
