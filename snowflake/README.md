# Running the pipeline on Snowflake

The SQL in `schema.sql` and `sql/` runs on Snowflake unchanged. These steps load the data by hand through the Snowflake web interface (Snowsight). It takes about 20 minutes.

## 1. Export the data locally

Run the local pipeline, then the export:

```bash
python generate_data.py
python calc_pay.py
python generate_system_pay.py
python validate.py
python export_for_snowflake.py
```

That writes 8 CSVs to `snowflake_upload/`.

## 2. Create the tables

In Snowsight, open a new SQL worksheet (Projects → Worksheets → +).

1. Paste `snowflake/setup.sql` and run it. Run all statements with Ctrl/Cmd + Shift + Enter.
2. Paste `schema.sql` and run all. This creates the empty tables and fills in `exception_causes`.

Check that the worksheet's context (top of the worksheet) shows `CREW_PAY.PAYROLL`.

## 3. Load the CSVs

Load the 8 files in `snowflake_upload/` in this order: crew, pairings, duty_periods, flights, roster, pay_rules, meal_rates, system_pay. Snowflake doesn't strictly need the order, but it's good practice to load parent tables before the ones that reference them. For each file:

1. Go to Data → Databases → CREW_PAY → PAYROLL → Tables, and click the table with the same name.
2. Click **Load Data**, choose the CSV, and pick the warehouse `COMPUTE_WH`.
3. For the file format, choose CSV and set it so that:
   - the first line is treated as a **header** (skip 1 line)
   - fields are **optionally enclosed by double quotes**
4. Load it, and confirm the row count matches the count `export_for_snowflake.py` printed.

## 4. Build the views

Back in the worksheet, paste and run each file in `sql/` in order, `01` through `09`. Each one creates a view.

## 5. Check the results

Paste `snowflake/checks.sql` and run each query. The comments say what to expect. If everything matches, the Snowflake results are the same as the local run.

## If something fails

- **Date function errors:** these come from `DATEDIFF`, which DuckDB and Snowflake write slightly differently. Change `DATEDIFF('minute', ...)` to `DATEDIFF(minute, ...)` for Snowflake.
- **Load errors on a CSV:** usually a header or quote setting in step 3.3.
- **"Object does not exist":** the worksheet context isn't set to `CREW_PAY.PAYROLL`, so run `setup.sql` again.
