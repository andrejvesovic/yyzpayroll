"""Simulate the payroll system's month-end pay file, with known errors planted in it.

The "system" applies the same rules as calc_pay.py, except for a few crew where
it makes a realistic mistake. The mistakes are logged to planted_errors.csv as
an answer key, so validate.py's results can be scored.

Outputs:
  data/system_pay_2026_10.csv   what the pay system says it will pay
  data/planted_errors.csv       answer key (validate.py never reads this)
"""
import random
from pathlib import Path

import duckdb
import pandas as pd

from calc_pay import DB_PATH, duty_credits, load_rules, pay_lines, trip_credits

HERE = Path(__file__).parent
DATA_DIR = HERE / "data"
SEED = 7

# error code: number of crew to plant it on
PLAN = {
    "NO_DUTY_RIG": 2,           # system skips the duty rig
    "DEADHEAD_FULL_CREDIT": 2,  # deadhead paid at 100% instead of 50%
    "NO_TRIP_RIG": 2,           # system skips the trip rig
    "MISSING_TRIP": 2,          # a trip never reached the pay system
    "WRONG_RATE": 2,            # last year's hourly rate still loaded
    "NO_MONTHLY_GUARANTEE": 2,  # guarantee top-up not paid
    "MANUAL_ADJUSTMENT": 1,     # an unexplained keyed-in change to one trip's credit
}
MIN_CREDIT_FOR_TRIP_ERRORS = 85  # keeps the guarantee from absorbing trip-level errors


def main():
    rng = random.Random(SEED)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    rules = load_rules(con)

    duties = duty_credits(con, rules)
    correct = trip_credits(con, rules, duties).set_index("pairing_id")["trip_credit"]
    variants = {
        "NO_DUTY_RIG": trip_credits(con, rules, duty_credits(con, rules, duty_rig=False)),
        "DEADHEAD_FULL_CREDIT": trip_credits(con, rules, duty_credits(con, rules, deadhead_ratio=1.0)),
        "NO_TRIP_RIG": trip_credits(con, rules, duties, trip_rig=False),
    }

    expected = pay_lines(con, rules, trip_credits(con, rules, duties))
    trips = expected[expected["line_type"] == "TRIP"].copy()
    month_credit = trips.groupby("crew_id")["credit_hrs"].sum()
    high_credit = set(month_credit[month_credit >= MIN_CREDIT_FOR_TRIP_ERRORS].index)
    low_credit = set(month_credit[month_credit < rules["monthly_guarantee_hrs"]].index)

    used, planted = set(), []

    def pick(candidates, n):
        """Pick n rows from different crew, one error per crew member."""
        candidates = candidates[~candidates["crew_id"].isin(used)]
        chosen = []
        for idx in rng.sample(list(candidates.index), len(candidates)):
            if len(chosen) == n:
                break
            if candidates.at[idx, "crew_id"] not in {candidates.at[i, "crew_id"] for i in chosen}:
                chosen.append(idx)
        used.update(candidates.loc[chosen, "crew_id"])
        return chosen

    # Trip-credit errors: only trips where the mistake actually changes the credit
    for code, variant in variants.items():
        wrong = trips["pairing_id"].map(variant.set_index("pairing_id")["trip_credit"])
        cands = trips[((wrong - trips["credit_hrs"]).abs() > 0.01) & trips["crew_id"].isin(high_credit)]
        for idx in pick(cands, PLAN[code]):
            trips.at[idx, "credit_hrs"] = wrong[idx]
            planted.append((trips.at[idx, "crew_id"], trips.at[idx, "pairing_id"], code))

    for idx in pick(trips[trips["crew_id"].isin(high_credit)], PLAN["MANUAL_ADJUSTMENT"]):
        trips.at[idx, "credit_hrs"] = round(trips.at[idx, "credit_hrs"] + rng.choice([-1.5, 1.25]), 2)
        planted.append((trips.at[idx, "crew_id"], trips.at[idx, "pairing_id"], "MANUAL_ADJUSTMENT"))

    for idx in pick(trips[trips["crew_id"].isin(high_credit)], PLAN["MISSING_TRIP"]):
        planted.append((trips.at[idx, "crew_id"], trips.at[idx, "pairing_id"], "MISSING_TRIP"))
        trips = trips.drop(idx)

    crew_ids = pd.Series(sorted(month_credit.index), index=sorted(month_credit.index))
    for crew_id in pick(crew_ids.to_frame("crew_id"), PLAN["WRONG_RATE"]):
        trips.loc[trips["crew_id"] == crew_id, "hourly_rate"] = round(
            trips.loc[trips["crew_id"] == crew_id, "hourly_rate"].iloc[0] / 1.035, 2)
        planted.append((crew_id, None, "WRONG_RATE"))

    no_guarantee = pick(crew_ids[crew_ids.isin(low_credit)].to_frame("crew_id"), PLAN["NO_MONTHLY_GUARANTEE"])
    planted += [(crew_id, None, "NO_MONTHLY_GUARANTEE") for crew_id in no_guarantee]

    # The system works out guarantee top-ups from its own (possibly wrong) trip credits
    rates = trips.groupby("crew_id")["hourly_rate"].first()
    shortfall = (rules["monthly_guarantee_hrs"] - trips.groupby("crew_id")["credit_hrs"].sum()).clip(lower=0).round(2)
    shortfall = shortfall[(shortfall > 0) & ~shortfall.index.isin(no_guarantee)]
    topups = pd.DataFrame({"crew_id": shortfall.index, "line_type": "GUARANTEE", "pairing_id": None,
                           "credit_hrs": shortfall.values, "hourly_rate": rates[shortfall.index].values})

    system = pd.concat([trips, topups], ignore_index=True)
    system["amount"] = (system["credit_hrs"] * system["hourly_rate"]).round(2)
    system = system.sort_values(["crew_id", "line_type", "pairing_id"])

    DATA_DIR.mkdir(exist_ok=True)
    system.to_csv(DATA_DIR / "system_pay_2026_10.csv", index=False)
    key = pd.DataFrame(planted, columns=["crew_id", "pairing_id", "error_code"])
    key.to_csv(DATA_DIR / "planted_errors.csv", index=False)

    print(f"System pay file: {len(system)} lines, ${system['amount'].sum():,.2f}")
    print(f"Expected pay:    {len(expected)} lines, ${expected['amount'].sum():,.2f}")
    print(f"Planted {len(key)} errors:", key["error_code"].value_counts().to_dict())

    counts = key["error_code"].value_counts()
    for code, n in PLAN.items():
        if counts.get(code, 0) < n:
            print(f"WARNING: planted {counts.get(code, 0)}/{n} {code}: no trips in this data "
                  f"where that mistake changes pay. Check generate_data.py.")


if __name__ == "__main__":
    main()
