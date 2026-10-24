# Running the pipeline on Snowflake

The SQL in `schema.sql` and `sql/` runs on Snowflake unchanged. These steps load the data by hand through the Snowflake web interface (Snowsight). It takes about 20 minutes.

## Result

Verified on a Snowflake trial account: all 13 exceptions and the reconciliation matched the local DuckDB run exactly. Snowflake's exception output is in [`snowflake_exceptions.csv`](snowflake_exceptions.csv). Compare it with [`../reports/exceptions_2026_10.csv`](../reports/exceptions_2026_10.csv).

## 1. Export the data locally

```bash
python3 generate_data.py
python3 calc_pay.py
python3 generate_system_pay.py
python3 validate.py
python3 export_for_snowflake.py
```

That writes 8 CSVs to `snowflake_upload/`.

## 2. Create the warehouse, database and tables

In Snowsight, open a SQL editor: **Projects → Workspaces → + Add new → SQL File**.

1. Paste `snowflake/setup.sql` and **Run All** (the dropdown beside the run button). This creates an X-Small warehouse that suspends after 60 seconds, plus the `CREW_PAY.PAYROLL` schema.
2. Paste `schema.sql` and Run All. This creates the empty tables and fills in `exception_causes`.

The top bar should show `COMPUTE_WH` and `CREW_PAY` / `PAYROLL`. On a Mac, `pbcopy < schema.sql` copies a file to the clipboard.

## 3. Load the CSVs

Load the 8 files in this order: crew, pairings, duty_periods, flights, roster, pay_rules, meal_rates, system_pay. For each one:

1. Go to **Catalog → Database Explorer → CREW_PAY → PAYROLL → Tables** and click the table.
2. Click **Load Data** (top right), select warehouse `COMPUTE_WH`, and upload the matching CSV.
3. In the file format options, set the header to skip 1 line and fields optionally enclosed by double quotes.
4. Load it, and check the row count matches what `export_for_snowflake.py` printed.

## 4. Build the views

Back in the SQL editor, paste all of `sql/` at once (`cat sql/*.sql | pbcopy`) and Run All. This creates 10 views; `01` creates two.

## 5. Check the results

Paste `snowflake/checks.sql` and Run All. Click each query in Query History to see its result. The comments in the file say what to expect.

## If something fails

- **"Object does not exist" on the first line:** there's no warehouse. `setup.sql` creates one; make sure it ran.
- **No Load Data option:** it isn't in the Workspaces explorer. Use Catalog (step 3).
- **Load errors on a CSV:** usually the header or quote setting.
- **Date function errors:** change `DATEDIFF('minute', ...)` to `DATEDIFF(minute, ...)`.
