"""Compare the pay system's month-end file to expected pay and explain every difference.

For each difference, the validator tests known failure modes (a rule skipped,
deadhead credited wrong, an old rate loaded, etc.) by recomputing pay the
"wrong" way and checking whether it reproduces the system's number. Anything
that matches no known failure mode is flagged UNEXPLAINED for manual review.

Outputs:
  reports/exceptions_2026_10.csv          one row per problem, with cause and $ impact
  reports/crew_reconciliation_2026_10.csv expected vs. system total per crew member
"""
from pathlib import Path

import duckdb
import pandas as pd

from calc_pay import DB_PATH, duty_credits, load_rules, trip_credits

HERE = Path(__file__).parent
SYSTEM_FILE = HERE / "data" / "system_pay_2026_10.csv"
REPORT_DIR = HERE / "reports"
TOL = 0.01

CAUSES = {
    "MISSING_TRIP": "Trip on roster but not in system pay",
    "UNROSTERED_TRIP": "Trip paid by system but not on roster",
    "NO_DUTY_RIG": "Credit matches pay without duty rig applied",
    "DEADHEAD_FULL_CREDIT": "Credit matches deadhead paid at 100% instead of 50%",
    "NO_TRIP_RIG": "Credit matches pay without trip rig applied",
    "WRONG_RATE": "Hourly rate differs from crew master rate",
    "NO_MONTHLY_GUARANTEE": "Below monthly guarantee but no top-up paid",
    "GUARANTEE_FOLLOWS_TRIP_ERROR": "Top-up differs only because trip credits above are wrong",
    "UNEXPLAINED": "Difference matches no known failure mode: review manually",
}


def known_failure_modes(con, rules):
    """Trip credit for every pairing under each known way the system gets it wrong."""
    duties = duty_credits(con, rules)
    modes = {
        "NO_DUTY_RIG": trip_credits(con, rules, duty_credits(con, rules, duty_rig=False)),
        "DEADHEAD_FULL_CREDIT": trip_credits(con, rules, duty_credits(con, rules, deadhead_ratio=1.0)),
        "NO_TRIP_RIG": trip_credits(con, rules, duties, trip_rig=False),
    }
    return {code: df.set_index("pairing_id")["trip_credit"] for code, df in modes.items()}


def diagnose_credit(row, modes):
    for code, credits in modes.items():
        if abs(credits[row["pairing_id"]] - row["credit_hrs_sys"]) < TOL:
            return code
    return "UNEXPLAINED"


def check_trips(expected, system, rates, modes):
    trips = expected[expected["line_type"] == "TRIP"].merge(
        system[system["line_type"] == "TRIP"], on=["crew_id", "pairing_id"],
        how="outer", suffixes=("_exp", "_sys"), indicator=True)
    trips["rate"] = trips["crew_id"].map(rates)
    out = []
    for _, r in trips.iterrows():
        if r["_merge"] == "left_only":
            out.append((r["crew_id"], r["pairing_id"], "MISSING_TRIP", r["credit_hrs_exp"], 0.0,
                        -r["credit_hrs_exp"] * r["rate"]))
        elif r["_merge"] == "right_only":
            out.append((r["crew_id"], r["pairing_id"], "UNROSTERED_TRIP", 0.0, r["credit_hrs_sys"],
                        r["credit_hrs_sys"] * r["rate"]))
        elif abs(r["credit_hrs_sys"] - r["credit_hrs_exp"]) >= TOL:
            out.append((r["crew_id"], r["pairing_id"], diagnose_credit(r, modes), r["credit_hrs_exp"],
                        r["credit_hrs_sys"], (r["credit_hrs_sys"] - r["credit_hrs_exp"]) * r["rate"]))
    return out


def check_rates(system, rates):
    """One exception per crew member paid at the wrong rate; impact covers all their lines."""
    wrong = system[(system["hourly_rate"] - system["crew_id"].map(rates)).abs() >= TOL]
    out = []
    for crew_id, lines in wrong.groupby("crew_id"):
        impact = (lines["credit_hrs"] * (lines["hourly_rate"] - rates[crew_id])).sum()
        out.append((crew_id, None, "WRONG_RATE", rates[crew_id], lines["hourly_rate"].iloc[0], impact))
    return out


def check_guarantee(expected, system, rates, guarantee_hrs):
    def topup(df):
        return df[df["line_type"] == "GUARANTEE"].groupby("crew_id")["credit_hrs"].sum()

    crew = pd.DataFrame(index=rates.index)
    crew["exp"] = topup(expected)
    crew["sys"] = topup(system)
    crew["sys_trips"] = system[system["line_type"] == "TRIP"].groupby("crew_id")["credit_hrs"].sum()
    crew = crew.fillna(0.0)
    # what the system *should* have topped up, given its own trip credits
    crew["implied"] = (guarantee_hrs - crew["sys_trips"]).clip(lower=0).round(2)

    out = []
    for crew_id, r in crew[(crew["sys"] - crew["exp"]).abs() >= TOL].iterrows():
        if r["sys"] < TOL and r["implied"] > TOL:
            cause = "NO_MONTHLY_GUARANTEE"
        elif abs(r["sys"] - r["implied"]) < TOL:
            cause = "GUARANTEE_FOLLOWS_TRIP_ERROR"
        else:
            cause = "UNEXPLAINED"
        out.append((crew_id, None, cause, r["exp"], r["sys"], (r["sys"] - r["exp"]) * rates[crew_id]))
    return out


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    rules = load_rules(con)
    expected = con.execute("SELECT * FROM expected_pay_lines").df()
    rates = con.execute("SELECT crew_id, hourly_rate::DOUBLE AS r FROM crew").df().set_index("crew_id")["r"]
    system = pd.read_csv(SYSTEM_FILE)
    modes = known_failure_modes(con, rules)
    con.close()

    rows = (check_trips(expected, system, rates, modes)
            + check_rates(system, rates)
            + check_guarantee(expected, system, rates, rules["monthly_guarantee_hrs"]))
    exceptions = pd.DataFrame(rows, columns=["crew_id", "pairing_id", "cause", "expected",
                                             "system", "impact"])
    exceptions["description"] = exceptions["cause"].map(CAUSES)
    exceptions["impact"] = exceptions["impact"].round(2)
    exceptions = exceptions.sort_values("impact", key=abs, ascending=False)

    # Reconciliation control: every dollar of difference should be explained by an exception
    recon = pd.DataFrame({
        "expected_pay": expected.groupby("crew_id")["amount"].sum(),
        "system_pay": system.groupby("crew_id")["amount"].sum(),
    }).fillna(0.0)
    recon["difference"] = (recon["system_pay"] - recon["expected_pay"]).round(2)
    recon["explained"] = exceptions.groupby("crew_id")["impact"].sum().reindex(recon.index, fill_value=0.0)
    recon["unexplained"] = (recon["difference"] - recon["explained"]).round(2)

    REPORT_DIR.mkdir(exist_ok=True)
    exceptions.to_csv(REPORT_DIR / "exceptions_2026_10.csv", index=False)
    recon.round(2).reset_index().to_csv(REPORT_DIR / "crew_reconciliation_2026_10.csv", index=False)

    flagged = recon[recon["difference"].abs() >= TOL]
    print(f"Crew checked: {len(recon)}  |  crew with pay differences: {len(flagged)}")
    print(f"Underpaid: ${-flagged['difference'].clip(upper=0).sum():,.2f}  |  "
          f"Overpaid: ${flagged['difference'].clip(lower=0).sum():,.2f}")
    print(f"Exceptions: {len(exceptions)}", exceptions["cause"].value_counts().to_dict())
    residual = recon["unexplained"].abs().max()
    print(f"Largest unreconciled amount for any crew member: ${residual:.2f}")
    print()
    print(exceptions.drop(columns="description").to_string(index=False))


if __name__ == "__main__":
    main()
