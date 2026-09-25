"""One-off for SQLite development databases created before 25 Sep 2026:
rebuild dqm_daily_report without the (district, date) UNIQUE constraint so a
deleted report no longer blocks re-entry for that day. Data is preserved.

    python -m scripts.rebuild_dqm_table
"""

from sqlalchemy import inspect, text

from app.db.base import Base
from app.db.session import engine
from app.models import DqmDailyReport  # noqa: F401  (registers the table)


def main() -> None:
    if engine.dialect.name != "sqlite":
        print("Only needed for SQLite; on PostgreSQL drop the constraint uq_dqm_report_day instead")
        return
    insp = inspect(engine)
    if not any(c["name"] == "uq_dqm_report_day" or c["column_names"] == ["district_id", "report_date"] for c in insp.get_unique_constraints("dqm_daily_report")):
        print("Nothing to do")
        return
    table = Base.metadata.tables["dqm_daily_report"]
    cols = ", ".join(f'"{c.name}"' for c in table.columns)
    # SQLite DDL is not reliably transactional through pysqlite, so run each step in autocommit mode.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("ALTER TABLE dqm_daily_report RENAME TO dqm_daily_report_old"))
        for idx in table.indexes:  # the renamed table keeps its index names
            conn.execute(text(f'DROP INDEX IF EXISTS "{idx.name}"'))
        table.create(conn)
        conn.execute(text(f"INSERT INTO dqm_daily_report ({cols}) SELECT {cols} FROM dqm_daily_report_old"))
        conn.execute(text("DROP TABLE dqm_daily_report_old"))
    print("Rebuilt dqm_daily_report without the unique constraint")


if __name__ == "__main__":
    main()
