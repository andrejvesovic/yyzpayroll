-- Reconciliation control: for each crew member, every dollar of difference between
-- expected and system pay should be explained by an exception.
-- unexplained should be ~$0; anything else means a problem the checks missed.
CREATE OR REPLACE VIEW crew_reconciliation AS
WITH expected_totals AS (
    SELECT crew_id, SUM(amount) AS pay FROM expected_pay_lines GROUP BY crew_id
),
system_totals AS (
    SELECT crew_id, SUM(amount) AS pay FROM system_pay GROUP BY crew_id
),
explained_totals AS (
    SELECT crew_id, SUM(impact) AS explained FROM exceptions GROUP BY crew_id
),
per_crew AS (
    SELECT
        c.crew_id,
        COALESCE(e.pay, 0)                              AS expected_pay,
        COALESCE(s.pay, 0)                              AS system_pay,
        ROUND(COALESCE(s.pay, 0) - COALESCE(e.pay, 0), 2) AS difference,
        COALESCE(x.explained, 0)                        AS explained
    FROM crew c
    LEFT JOIN expected_totals e  ON e.crew_id = c.crew_id
    LEFT JOIN system_totals s    ON s.crew_id = c.crew_id
    LEFT JOIN explained_totals x ON x.crew_id = c.crew_id
)
SELECT
    crew_id,
    ROUND(expected_pay, 2)            AS expected_pay,
    ROUND(system_pay, 2)              AS system_pay,
    difference,
    ROUND(explained, 2)               AS explained,
    ROUND(difference - explained, 2)  AS unexplained
FROM per_crew;
