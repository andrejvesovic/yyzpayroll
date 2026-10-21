"""Calculate expected crew pay from the roster and the pay rules.

Credit is built bottom-up, and each level pays the highest of several measures:
  duty day:  max(block credit, minimum day guarantee, duty rig)
  trip:      max(sum of duty credits, trip rig)
  month:     max(sum of trip credits, monthly guarantee)

The rule functions take switches (duty_rig=False, etc.) so the same logic can
model a pay system that applies a rule wrongly. generate_system_pay.py and
validate.py both use those switches.
"""
from pathlib import Path

import duckdb
import pandas as pd

HERE = Path(__file__).parent
DB_PATH = HERE / "crew_pay.duckdb"


def load_rules(con):
    return {name: float(value) for name, value in
            con.execute("SELECT rule_name, value FROM pay_rules").fetchall()}


def duty_credits(con, rules, duty_rig=True, deadhead_ratio=None):
    """Credit hours for every duty day, plus which rule set the credit."""
    dh_ratio = rules["deadhead_credit_ratio"] if deadhead_ratio is None else deadhead_ratio
    df = con.execute("""
        SELECT d.pairing_id, d.duty_id,
               SUM(CASE WHEN f.is_deadhead THEN 0 ELSE f.block_hrs END)::DOUBLE AS block_hrs,
               SUM(CASE WHEN f.is_deadhead THEN f.block_hrs ELSE 0 END)::DOUBLE AS deadhead_hrs,
               date_diff('minute', d.report_utc, d.release_utc) / 60.0 AS duty_hrs
        FROM duty_periods d
        JOIN flights f USING (duty_id)
        GROUP BY d.pairing_id, d.duty_id, d.report_utc, d.release_utc
    """).df()

    measures = pd.DataFrame({
        "block": df["block_hrs"] + dh_ratio * df["deadhead_hrs"],
        "min_day": rules["min_day_guarantee_hrs"],
        "duty_rig": rules["duty_rig_ratio"] * df["duty_hrs"] if duty_rig else 0.0,
    })
    df["duty_credit"] = measures.max(axis=1)
    df["duty_basis"] = measures.idxmax(axis=1)
    return df


def trip_credits(con, rules, duties, trip_rig=True):
    """Credit hours for every pairing: duty credits vs. time away from base."""
    tafb = con.execute("""
        SELECT pairing_id,
               date_diff('minute', MIN(report_utc), MAX(release_utc)) / 60.0 AS tafb_hrs
        FROM duty_periods
        GROUP BY pairing_id
    """).df()
    trips = (duties.groupby("pairing_id", as_index=False)["duty_credit"].sum()
             .rename(columns={"duty_credit": "duty_credit_sum"})
             .merge(tafb, on="pairing_id"))

    measures = pd.DataFrame({
        "duty_days": trips["duty_credit_sum"],
        "trip_rig": rules["trip_rig_ratio"] * trips["tafb_hrs"] if trip_rig else 0.0,
    })
    trips["trip_credit"] = measures.max(axis=1).round(2)
    trips["trip_basis"] = measures.idxmax(axis=1)
    return trips


def pay_lines(con, rules, trips):
    """One pay line per trip flown, plus a guarantee top-up line where needed."""
    crew = con.execute("SELECT crew_id, hourly_rate::DOUBLE AS hourly_rate FROM crew").df()
    roster = con.execute("SELECT crew_id, pairing_id FROM roster").df()

    trip_lines = (roster.merge(trips[["pairing_id", "trip_credit"]], on="pairing_id")
                  .rename(columns={"trip_credit": "credit_hrs"})
                  .merge(crew, on="crew_id"))
    trip_lines["line_type"] = "TRIP"

    month = crew.merge(trip_lines.groupby("crew_id", as_index=False)["credit_hrs"].sum(),
                       on="crew_id", how="left").fillna({"credit_hrs": 0.0})
    month["credit_hrs"] = (rules["monthly_guarantee_hrs"] - month["credit_hrs"]).clip(lower=0).round(2)
    topups = month[month["credit_hrs"] > 0].assign(line_type="GUARANTEE", pairing_id=None)

    lines = pd.concat([trip_lines, topups], ignore_index=True)
    lines["amount"] = (lines["credit_hrs"] * lines["hourly_rate"]).round(2)
    cols = ["crew_id", "line_type", "pairing_id", "credit_hrs", "hourly_rate", "amount"]
    return lines[cols].sort_values(["crew_id", "line_type", "pairing_id"]).reset_index(drop=True)


def main():
    con = duckdb.connect(str(DB_PATH))
    rules = load_rules(con)
    duties = duty_credits(con, rules)
    trips = trip_credits(con, rules, duties)
    lines = pay_lines(con, rules, trips)

    for name, df in [("duty_credit", duties), ("trip_credit", trips), ("expected_pay_lines", lines)]:
        con.register("staging", df)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM staging")
        con.unregister("staging")

    print("Duty days by deciding rule:", duties["duty_basis"].value_counts().to_dict())
    print("Trips by deciding rule:    ", trips["trip_basis"].value_counts().to_dict())
    n_topup = (lines["line_type"] == "GUARANTEE").sum()
    print(f"Crew topped up to monthly guarantee: {n_topup}")
    print(f"Total expected pay: ${lines['amount'].sum():,.2f} across {lines['crew_id'].nunique()} crew")
    con.close()


if __name__ == "__main__":
    main()
