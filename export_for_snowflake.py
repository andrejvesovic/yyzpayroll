"""Export every table to CSV so it can be uploaded to Snowflake by hand.

Run the local pipeline first (generate_data.py through validate.py).
Writes one CSV per table to snowflake_upload/. See snowflake/README.md for the upload steps.
"""
import shutil

import duckdb

from db import DB_PATH, HERE

TABLES = ["crew", "pairings", "duty_periods", "flights", "roster", "pay_rules", "meal_rates"]
SYSTEM_FILE = HERE / "data" / "system_pay_2026_10.csv"
OUT_DIR = HERE / "snowflake_upload"


def main():
    OUT_DIR.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    for table in TABLES:
        path = OUT_DIR / f"{table}.csv"
        con.execute(f"COPY {table} TO '{path.as_posix()}' (HEADER)")
        n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{path.name:<20}{n:>6} rows")
    con.close()

    shutil.copy(SYSTEM_FILE, OUT_DIR / "system_pay.csv")
    print(f"{'system_pay.csv':<20}  (copied from {SYSTEM_FILE.name})")


if __name__ == "__main__":
    main()
