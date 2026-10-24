"""Compare the pay system's month-end file to expected pay and explain every difference.

Loads the system pay file into the database, then runs the checks in sql/:
  05-07  trip, rate and guarantee checks; each credit difference is tested against
         the known failure modes, and anything that matches none is flagged
         UNEXPLAINED for manual review
  08     all exceptions in one list
  09     reconciliation: expected vs. system total per crew member; every dollar
         of difference should be covered by an exception

Run calc_pay.py and generate_system_pay.py first.

Outputs:
  reports/exceptions_2026_10.csv          one row per problem, with cause and $ impact
  reports/crew_reconciliation_2026_10.csv expected vs. system total per crew member
"""
from pathlib import Path

import duckdb

from db import DB_PATH, run_sql

HERE = Path(__file__).parent
SYSTEM_FILE = HERE / "data" / "system_pay_2026_10.csv"
REPORT_DIR = HERE / "reports"


def main():
    con = duckdb.connect(str(DB_PATH))
    con.execute("DELETE FROM system_pay")
    con.execute(f"COPY system_pay FROM '{SYSTEM_FILE.as_posix()}' (HEADER)")
    run_sql(con, "05_trip_exceptions.sql", "06_rate_exceptions.sql", "07_guarantee_exceptions.sql",
            "08_exceptions.sql", "09_crew_reconciliation.sql")

    exceptions = con.execute("SELECT * FROM exceptions ORDER BY ABS(impact) DESC, crew_id").df()
    recon = con.execute("SELECT * FROM crew_reconciliation ORDER BY crew_id").df()
    con.close()

    REPORT_DIR.mkdir(exist_ok=True)
    exceptions.to_csv(REPORT_DIR / "exceptions_2026_10.csv", index=False)
    recon.to_csv(REPORT_DIR / "crew_reconciliation_2026_10.csv", index=False)

    flagged = recon[recon["difference"].abs() >= 0.01]
    print(f"Crew checked: {len(recon)}  |  crew with pay differences: {len(flagged)}")
    print(f"Underpaid: ${-flagged['difference'].clip(upper=0).sum():,.2f}  |  "
          f"Overpaid: ${flagged['difference'].clip(lower=0).sum():,.2f}")
    print(f"Exceptions: {len(exceptions)}", exceptions["cause"].value_counts().to_dict())
    print(f"Largest unreconciled amount for any crew member: ${recon['unexplained'].abs().max():.2f}")
    print()
    print(exceptions.drop(columns="description").to_string(index=False))


if __name__ == "__main__":
    main()
