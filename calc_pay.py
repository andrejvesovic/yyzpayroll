"""Build expected crew pay from the roster and pay rules (logic lives in sql/01-04).

Credit is built bottom-up, and each level pays the highest of several measures:
  duty day:  max(block credit, minimum day guarantee, duty rig)
  trip:      max(sum of duty credits, trip rig)
  month:     max(sum of trip credits, monthly guarantee)

Also builds failure_modes: trip credit under each known way a pay system
applies the rules wrongly. generate_system_pay.py and validate.py both use it.
"""
import duckdb

from db import DB_PATH, run_sql

SQL_FILES = ["01_duty_credit.sql", "02_trip_credit.sql",
             "03_expected_pay_lines.sql", "04_failure_modes.sql"]


def main():
    con = duckdb.connect(str(DB_PATH))
    run_sql(con, *SQL_FILES)

    trip = dict(con.execute("SELECT trip_basis, COUNT(*) FROM trip_credit GROUP BY 1 ORDER BY 2 DESC").fetchall())
    n_topup, total, n_crew = con.execute("""
        SELECT SUM(CASE WHEN line_type = 'GUARANTEE' THEN 1 ELSE 0 END), SUM(amount), COUNT(DISTINCT crew_id)
        FROM expected_pay_lines
    """).fetchone()

    print("Trips by deciding rule:", trip)
    print(f"Crew topped up to monthly guarantee: {n_topup}")
    print(f"Total expected pay: ${total:,.2f} across {n_crew} crew")
    con.close()


if __name__ == "__main__":
    main()
