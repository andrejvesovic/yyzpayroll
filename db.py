"""Shared database location and a helper to run the SQL files in sql/."""
from pathlib import Path

HERE = Path(__file__).parent
DB_PATH = HERE / "crew_pay.duckdb"
SQL_DIR = HERE / "sql"


def run_sql(con, *filenames):
    """Execute each SQL file in sql/, in the order given."""
    for name in filenames:
        con.execute((SQL_DIR / name).read_text())
