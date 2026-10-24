# Crew Pay Exceptions Dashboard (Power BI)

Power BI report on top of the Snowflake views. It gives payroll reviewers the month's pay variance, the exceptions behind it, and the reconciliation control, filtered by row-level security so each payroll team sees only its own crew.

## Source

Get Data → Snowflake. Server `<account_identifier>.snowflakecomputing.com`, warehouse `COMPUTE_WH`, then `CREW_PAY.PAYROLL`. Use Import mode and load three objects:

| Table in Power BI | Snowflake object | What it is |
|---|---|---|
| `Crew` | `CREW` | one row per crew member |
| `Reconciliation` | `CREW_RECONCILIATION` | one row per crew member: expected, system, difference |
| `Exceptions` | `EXCEPTIONS` | one row per problem found |

## Power Query steps

- **All tables:** rename the columns to lowercase (Snowflake returns them uppercase) and check the data types.
- **Crew:** add a conditional column `Pay Group`: if `position` is CA or FO then "Pilot", else "Cabin".
- **Exceptions:** add a conditional column `Exception Type`: if `cause` is `GUARANTEE_FOLLOWS_TRIP_ERROR` then "Knock-on", else "Root cause".

## Relationships

`Crew[crew_id]` → `Reconciliation[crew_id]` and `Crew[crew_id]` → `Exceptions[crew_id]`. Both are one-to-many with single-direction filtering.

## Measures

```dax
Expected Pay = SUM ( Reconciliation[expected_pay] )

System Pay = SUM ( Reconciliation[system_pay] )

Pay Variance = SUM ( Reconciliation[difference] )

Underpaid $ = - CALCULATE ( SUM ( Reconciliation[difference] ), Reconciliation[difference] < 0 )

Overpaid $ = CALCULATE ( SUM ( Reconciliation[difference] ), Reconciliation[difference] > 0 )

Crew Affected = CALCULATE ( COUNTROWS ( Reconciliation ), Reconciliation[difference] <> 0 )

% Crew Affected = DIVIDE ( [Crew Affected], COUNTROWS ( Crew ) )

Root-Cause Exceptions = CALCULATE ( COUNTROWS ( Exceptions ), Exceptions[Exception Type] = "Root cause" )

Manual Review Queue = CALCULATE ( COUNTROWS ( Exceptions ), Exceptions[cause] = "UNEXPLAINED" )

Unreconciled $ = SUM ( Reconciliation[unexplained] )
```

## Row-level security

Modeling → Manage roles, with the filter on `Crew`:

| Role | DAX filter |
|---|---|
| Pilot Payroll | `[Pay Group] = "Pilot"` |
| Cabin Payroll | `[Pay Group] = "Cabin"` |

Test each role with Modeling → View as.

## Pages

1. **Overview.** KPI cards for the measures, a bar chart of exception `impact` by `cause`, the exceptions table, and a `position` slicer.
2. **Crew reconciliation.** The reconciliation table with conditional formatting on `difference`, and an `Unreconciled $` card (target $0).

## Expected values (use these to check the measures)

| Measure | All | Pilot Payroll | Cabin Payroll |
|---|---|---|---|
| Crew | 50 | 20 | 30 |
| Expected Pay | $468,930.30 | $320,316.90 | $148,613.40 |
| System Pay | $461,642.09 | $313,689.25 | $147,952.84 |
| Pay Variance | −$7,288.21 | −$6,627.65 | −$660.56 |
| Underpaid $ | $7,510.93 | $6,627.65 | $883.28 |
| Overpaid $ | $222.72 | $0.00 | $222.72 |
| Crew Affected | 13 | 5 | 8 |
| Root-Cause Exceptions | 13 | 5 | 8 |
| Manual Review Queue | 1 | 0 | 1 |
