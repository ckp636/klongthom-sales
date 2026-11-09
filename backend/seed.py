"""Build the v2 schema and load sample data into an EMPTY database.

    cd backend && python seed.py

Uses the connection settings from backend/.env. Runs
database/sql/01_schema.sql → 02_sample_data.sql → 03_sample_expense.sql.
Each script refuses to run if the tables already exist / hold data, so this
never overwrites anything.
"""
import re
import sys
from pathlib import Path

from app.core.database import engine

SQL_DIR = Path(__file__).parent / "database" / "sql"
SCRIPTS = ["01_schema.sql", "02_sample_data.sql", "03_sample_expense.sql"]


def run_script(cursor, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    batches = [b.strip() for b in re.split(r"^\s*GO\s*$", sql, flags=re.M | re.I) if b.strip()]
    for batch in batches:
        cursor.execute(batch)
        while cursor.nextset():
            pass
    print(f"  {path.name}: {len(batches)} batch(es) OK")


def main() -> int:
    raw = engine.raw_connection()
    try:
        raw.autocommit(True)
        cur = raw.cursor()
        for name in SCRIPTS:
            run_script(cur, SQL_DIR / name)
    except Exception as e:  # noqa: BLE001
        print(f"FAILED: {e}")
        return 1
    finally:
        raw.close()
    print("Done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
