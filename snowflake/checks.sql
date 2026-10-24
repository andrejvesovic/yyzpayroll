-- Run after loading the data and running sql/01-09.
-- The comments show what the local DuckDB run produced; Snowflake should match.

-- 1. Row counts. Expect: crew 50, pairings 266, duty_periods 438, flights 608,
--    roster 487, pay_rules 5, meal_rates 10, system_pay 493
SELECT 'crew' AS table_name, COUNT(*) AS row_count FROM crew
UNION ALL SELECT 'pairings',     COUNT(*) FROM pairings
UNION ALL SELECT 'duty_periods', COUNT(*) FROM duty_periods
UNION ALL SELECT 'flights',      COUNT(*) FROM flights
UNION ALL SELECT 'roster',       COUNT(*) FROM roster
UNION ALL SELECT 'pay_rules',    COUNT(*) FROM pay_rules
UNION ALL SELECT 'meal_rates',   COUNT(*) FROM meal_rates
UNION ALL SELECT 'system_pay',   COUNT(*) FROM system_pay;

-- 2. Pay totals. Expect: expected 468930.30, system 461642.09
SELECT
    (SELECT ROUND(SUM(amount), 2) FROM expected_pay_lines) AS expected_total,
    (SELECT ROUND(SUM(amount), 2) FROM system_pay)         AS system_total;

-- 3. Exceptions by cause. Expect 13 rows in total: 2 each of MISSING_TRIP, WRONG_RATE,
--    NO_MONTHLY_GUARANTEE, NO_DUTY_RIG, DEADHEAD_FULL_CREDIT, NO_TRIP_RIG, and 1 UNEXPLAINED
SELECT cause, COUNT(*) AS n
FROM exceptions
GROUP BY cause
ORDER BY n DESC, cause;

-- 4. Reconciliation control. Expect 13 crew with a difference, and a largest unexplained of 0.02
SELECT
    SUM(CASE WHEN difference <> 0 THEN 1 ELSE 0 END) AS crew_with_difference,
    MAX(ABS(unexplained))                            AS largest_unexplained
FROM crew_reconciliation;

-- 5. The full exception list, biggest first. Compare with reports/exceptions_2026_10.csv
SELECT *
FROM exceptions
ORDER BY ABS(impact) DESC;
