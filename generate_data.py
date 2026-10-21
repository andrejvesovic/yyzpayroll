"""Generate one synthetic month of crew schedule data and load it into DuckDB.

Everything here is made up for illustration: routes, block times, pay rates
and rules are plausible but are not Air Canada's actual terms.
"""
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import pandas as pd

HERE = Path(__file__).parent
DB_PATH = HERE / "crew_pay.duckdb"
SCHEMA_PATH = HERE / "schema.sql"

SEED = 42
MONTH_START = date(2026, 10, 1)
N_CREW = 50
BASE = "YYZ"

REPORT_BEFORE = timedelta(minutes=60)
RELEASE_AFTER = timedelta(minutes=15)
MIN_REST = timedelta(hours=12)
WORK_PROB = 0.45  # chance a free crew member starts a trip on a given day

# position: (share of crew, CAD per credit hour)
POSITIONS = {"CA": (0.2, 230.00), "FO": (0.2, 145.00), "FA": (0.6, 58.00)}

# Each template is a list of duty days; each duty is a list of legs:
# (flight_no, origin, destination, day_offset, dep_time_utc, block_hrs, is_deadhead)
TEMPLATES = {
    "YUL-TURN": [[("AC401", "YYZ", "YUL", 0, "12:00", 1.3, False),
                  ("AC412", "YUL", "YYZ", 0, "14:15", 1.4, False)]],
    "YHZ-TURN": [[("AC604", "YYZ", "YHZ", 0, "13:30", 2.0, False),   # long sit in YHZ,
                  ("AC611", "YHZ", "YYZ", 0, "19:30", 2.3, False)]],  # so duty rig decides
    "ORD-TURN": [[("AC511", "YYZ", "ORD", 0, "15:00", 1.9, False),
                  ("AC516", "ORD", "YYZ", 0, "18:00", 1.7, False)]],
    "YOW-YUL-DAY": [[("AC450", "YYZ", "YOW", 0, "11:00", 1.0, False),
                     ("AC455", "YOW", "YYZ", 0, "12:45", 1.0, False),
                     ("AC417", "YYZ", "YUL", 0, "15:00", 1.3, False),
                     ("AC428", "YUL", "YYZ", 0, "19:15", 1.4, False)]],
    "YVR-2D": [[("AC103", "YYZ", "YVR", 0, "14:00", 4.8, False)],
               [("AC104", "YVR", "YYZ", 1, "16:30", 4.3, False)]],
    "YYC-2D": [[("AC137", "YYZ", "YYC", 0, "13:00", 4.0, False)],
               [("AC140", "YYC", "YYZ", 1, "15:00", 3.6, False)]],
    "LAX-2D": [[("AC791", "YYZ", "LAX", 0, "14:30", 5.2, False)],
               [("AC796", "LAX", "YYZ", 1, "16:00", 4.6, False)]],
    "FLL-2D": [[("AC1630", "YYZ", "FLL", 0, "12:30", 3.1, False)],
               [("AC1631", "FLL", "YYZ", 1, "13:30", 3.3, False)]],
    "LHR-3D": [[("AC856", "YYZ", "LHR", 0, "23:00", 6.7, False)],
               [("AC857", "LHR", "YYZ", 2, "12:00", 8.0, False)]],
    "FRA-3D": [[("AC872", "YYZ", "FRA", 0, "22:00", 7.8, False)],
               [("AC873", "FRA", "YYZ", 2, "11:00", 8.6, False)]],
    # deadhead to YVR, then operate YVR-YYC the same day, then YYC-YYZ next day
    "YVR-DH-2D": [[("AC105", "YYZ", "YVR", 0, "15:00", 4.8, True),
                   ("AC218", "YVR", "YYC", 0, "21:00", 1.5, False)],
                  [("AC146", "YYC", "YYZ", 1, "15:00", 3.6, False)]],
}

PAY_RULES = [
    ("min_day_guarantee_hrs", 4.0, "Minimum credit hours for any duty day"),
    ("duty_rig_ratio", 0.5, "Credit 1 hr per 2 hrs on duty (duty rig)"),
    ("trip_rig_ratio", 0.286, "Credit 1 hr per 3.5 hrs away from base (trip rig)"),
    ("deadhead_credit_ratio", 0.5, "Deadhead block hours credited at 50%"),
    ("monthly_guarantee_hrs", 70.0, "Minimum credit hours paid per month"),
]

# station, region, CAD per hour away from base
MEAL_RATES = [
    ("YUL", "domestic", 2.60), ("YOW", "domestic", 2.60), ("YHZ", "domestic", 2.60),
    ("YVR", "domestic", 2.60), ("YYC", "domestic", 2.60),
    ("ORD", "transborder", 2.95), ("LAX", "transborder", 2.95), ("FLL", "transborder", 2.95),
    ("LHR", "international", 3.40), ("FRA", "international", 3.40),
]


def build_crew():
    rows, crew_id = [], 10001
    for position, (share, rate) in POSITIONS.items():
        for _ in range(round(N_CREW * share)):
            rows.append({"crew_id": crew_id, "position": position,
                         "base": BASE, "hourly_rate": rate})
            crew_id += 1
    return pd.DataFrame(rows)


def build_pairing(template, start):
    """Turn a template into one dated pairing with its duty periods and flights."""
    pairing_id = f"P-{template}-{start:%m%d}"
    duties, flights = [], []
    for duty_seq, legs in enumerate(TEMPLATES[template], start=1):
        duty_id = f"{pairing_id}-D{duty_seq}"
        legs_out = []
        for leg_seq, (flight_no, origin, dest, offset, dep_time, block, deadhead) in enumerate(legs, start=1):
            dep = datetime.combine(start + timedelta(days=offset),
                                   datetime.strptime(dep_time, "%H:%M").time())
            legs_out.append({
                "flight_id": f"{duty_id}-L{leg_seq}", "duty_id": duty_id, "leg_seq": leg_seq,
                "flight_no": flight_no, "origin": origin, "destination": dest,
                "dep_utc": dep, "arr_utc": dep + timedelta(hours=block),
                "block_hrs": block, "is_deadhead": deadhead,
            })
        flights.extend(legs_out)
        duties.append({
            "duty_id": duty_id, "pairing_id": pairing_id, "duty_seq": duty_seq,
            "report_utc": legs_out[0]["dep_utc"] - REPORT_BEFORE,
            "release_utc": legs_out[-1]["arr_utc"] + RELEASE_AFTER,
        })
    pairing = {"pairing_id": pairing_id, "template": template,
               "base": BASE, "start_date": start}
    return pairing, duties, flights


def build_schedule(crew, rng):
    """Greedily give each crew member non-overlapping trips with minimum rest between them."""
    month_end = (MONTH_START.replace(day=28) + timedelta(days=4)).replace(day=1)
    built, roster = {}, []

    for crew_id in crew["crew_id"]:
        free_from = datetime.combine(MONTH_START, datetime.min.time())
        day = MONTH_START
        while day < month_end:
            if rng.random() >= WORK_PROB:
                day += timedelta(days=1)
                continue
            template = rng.choice(list(TEMPLATES))
            key = (template, day)
            if key not in built:
                built[key] = build_pairing(template, day)
            pairing, duties, _ = built[key]
            report, release = duties[0]["report_utc"], duties[-1]["release_utc"]
            # keep trips inside the month so there's no month-end proration to deal with
            if report >= free_from and release.date() < month_end:
                roster.append({"crew_id": crew_id, "pairing_id": pairing["pairing_id"]})
                free_from = release + MIN_REST
                day = release.date() + timedelta(days=1)  # at least one day off after a trip
            else:
                day += timedelta(days=1)

    used = {r["pairing_id"] for r in roster}
    kept = [v for v in built.values() if v[0]["pairing_id"] in used]
    return {
        "pairings": pd.DataFrame([p for p, _, _ in kept]),
        "duty_periods": pd.DataFrame([d for _, ds, _ in kept for d in ds]),
        "flights": pd.DataFrame([f for _, _, fs in kept for f in fs]),
        "roster": pd.DataFrame(roster),
    }


def load(tables):
    DB_PATH.unlink(missing_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute(SCHEMA_PATH.read_text())
    # parents before children so foreign keys are satisfied
    for name in ["crew", "pairings", "duty_periods", "flights", "roster", "pay_rules", "meal_rates"]:
        df = tables[name]
        con.register("staging", df)
        con.execute(f"INSERT INTO {name} BY NAME SELECT * FROM staging")
        con.unregister("staging")
    return con


def main():
    rng = random.Random(SEED)
    crew = build_crew()
    tables = {"crew": crew, **build_schedule(crew, rng)}
    tables["pay_rules"] = pd.DataFrame(PAY_RULES, columns=["rule_name", "value", "description"])
    tables["meal_rates"] = pd.DataFrame(MEAL_RATES, columns=["station", "region", "rate_per_hour"])
    tables["meal_rates"]["effective_date"] = MONTH_START

    con = load(tables)
    for name in tables:
        n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        print(f"{name:<14}{n:>6} rows")

    summary = con.execute("""
        SELECT ROUND(MIN(hrs), 1), ROUND(AVG(hrs), 1), ROUND(MAX(hrs), 1)
        FROM (
            SELECT r.crew_id, SUM(f.block_hrs) AS hrs
            FROM roster r
            JOIN duty_periods d USING (pairing_id)
            JOIN flights f USING (duty_id)
            GROUP BY r.crew_id
        )
    """).fetchone()
    print(f"\nBlock hours per crew member: min {summary[0]}, avg {summary[1]}, max {summary[2]}")
    con.close()


if __name__ == "__main__":
    main()
