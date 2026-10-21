"""Score validate.py's exceptions against the planted-error answer key."""
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
# A manual adjustment follows no rule, so the correct result is to flag it for review
EXPECTED_CAUSE = {"MANUAL_ADJUSTMENT": "UNEXPLAINED"}
SECONDARY = {"GUARANTEE_FOLLOWS_TRIP_ERROR"}  # knock-on effects, not separate errors


def keyed(df, code_col):
    return set(zip(df["crew_id"], df["pairing_id"].fillna(""), df[code_col]))


def main():
    key = pd.read_csv(HERE / "data" / "planted_errors.csv")
    found = pd.read_csv(HERE / "reports" / "exceptions_2026_10.csv")
    key["cause"] = key["error_code"].replace(EXPECTED_CAUSE)
    found = found[~found["cause"].isin(SECONDARY)]

    planted, flagged = keyed(key, "cause"), keyed(found, "cause")
    caught, missed, false_alarms = planted & flagged, planted - flagged, flagged - planted

    print(f"Caught with correct cause: {len(caught)}/{len(planted)}")
    for label, rows in [("Missed", missed), ("False alarms", false_alarms)]:
        print(f"{label}: {len(rows)}")
        for crew_id, pairing_id, cause in sorted(rows):
            print(f"  {crew_id} {pairing_id or '-'} {cause}")


if __name__ == "__main__":
    main()
