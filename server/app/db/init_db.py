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


# Columns that were NOT NULL when a database was created and are optional (or no longer used) now.
RELAXED_COLUMNS = [("me_respondent", "full_name"), ("me_respondent", "phone"), ("me_respondent", "email")]


def relax_not_null() -> None:
    """Drop NOT NULL from columns the models no longer require (the training evaluation became anonymous)."""
    with engine.begin() as conn:
        insp = inspect(conn)
        for table in dict.fromkeys(t for t, _ in RELAXED_COLUMNS):
            if not insp.has_table(table):
                continue
            columns = {c["name"]: c for c in insp.get_columns(table)}
            wanted = [c for t, c in RELAXED_COLUMNS if t == table and c in columns and not columns[c].get("nullable", True)]
            if not wanted:
                continue
            if engine.dialect.name == "postgresql":
                for column in wanted:
                    conn.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" DROP NOT NULL'))
            else:
                _rebuild_sqlite_table(conn, table)
                insp = inspect(conn)


def _rebuild_sqlite_table(conn, table: str) -> None:
    """SQLite cannot change a column's constraints: recreate the table from the model and copy the
    columns both versions share (the local development database; tests start from scratch)."""
    model_table = Base.metadata.tables[table]
    insp = inspect(conn)
    old_cols = [c["name"] for c in insp.get_columns(table)]
    keep = [c.name for c in model_table.columns if c.name in old_cols]
    cols = ", ".join(f'"{c}"' for c in keep)
    for ix in insp.get_indexes(table):
        if ix.get("name"):
            conn.execute(text(f'DROP INDEX IF EXISTS "{ix["name"]}"'))
    conn.execute(text(f'ALTER TABLE "{table}" RENAME TO "{table}__old"'))
    model_table.create(conn)
    conn.execute(text(f'INSERT INTO "{table}" ({cols}) SELECT {cols} FROM "{table}__old"'))
    conn.execute(text(f'DROP TABLE "{table}__old"'))


def recover_half_rebuilds() -> None:
    """A SQLite rebuild that stopped half way leaves `<table>__old` (with the data) next to an empty new
    table; put the old table back before create_all so the next rebuild starts clean."""
    if engine.dialect.name == "postgresql":
        return
    with engine.begin() as conn:
        insp = inspect(conn)
        for table in dict.fromkeys(t for t, _ in RELAXED_COLUMNS):
            if insp.has_table(f"{table}__old"):
                conn.execute(text(f'DROP TABLE IF EXISTS "{table}"'))
                conn.execute(text(f'ALTER TABLE "{table}__old" RENAME TO "{table}"'))


def add_missing_enum_values() -> None:
    """PostgreSQL stores Role as the enum type user_role; a value added to the Python enum
    (such as ME) must be added to the type too. SQLite stores plain strings."""
    if engine.dialect.name != "postgresql":
        return
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        for role in Role:
            conn.execute(text(f"ALTER TYPE user_role ADD VALUE IF NOT EXISTS '{role.value}'"))


def init_db(db: Session) -> None:
    # Several uvicorn workers start at once; on PostgreSQL an advisory lock makes them run this
    # one after the other, so the second finds the tables and columns already there.
    lock = None
    if engine.dialect.name == "postgresql":
        lock = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
        lock.execute(text("SELECT pg_advisory_lock(727272)"))
    try:
        _init_schema_and_seed(db)
    finally:
        if lock is not None:
            lock.execute(text("SELECT pg_advisory_unlock(727272)"))
            lock.close()


def _init_schema_and_seed(db: Session) -> None:
    recover_half_rebuilds()
    Base.metadata.create_all(bind=engine)
    add_missing_columns()
    relax_not_null()
    add_missing_enum_values()

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
