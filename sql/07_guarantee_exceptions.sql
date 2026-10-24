-- Guarantee check: did the system pay the right monthly guarantee top-up?
-- If the top-up is wrong only because the trip credits above it are wrong,
-- that's a knock-on effect (GUARANTEE_FOLLOWS_TRIP_ERROR), not a separate error.
CREATE OR REPLACE VIEW guarantee_exceptions AS
WITH expected_topup AS (
    SELECT crew_id, credit_hrs FROM expected_pay_lines WHERE line_type = 'GUARANTEE'
),
system_topup AS (
    SELECT crew_id, credit_hrs FROM system_pay WHERE line_type = 'GUARANTEE'
),
system_trip_hrs AS (
    SELECT crew_id, SUM(credit_hrs) AS trip_hrs FROM system_pay WHERE line_type = 'TRIP' GROUP BY crew_id
),
per_crew AS (
    SELECT
        c.crew_id,
        c.hourly_rate::DOUBLE        AS hourly_rate,
        COALESCE(e.credit_hrs, 0)    AS expected_topup,
        COALESCE(s.credit_hrs, 0)    AS system_topup,
        -- the top-up the system should have paid, based on its own trip credits
        ROUND(GREATEST(r.monthly_guarantee_hrs - COALESCE(t.trip_hrs, 0), 0), 2) AS implied_topup
    FROM crew c
    LEFT JOIN expected_topup e  ON e.crew_id = c.crew_id
    LEFT JOIN system_topup s    ON s.crew_id = c.crew_id
    LEFT JOIN system_trip_hrs t ON t.crew_id = c.crew_id
    CROSS JOIN rules r
)
SELECT
    crew_id,
    NULL AS pairing_id,
    CASE
        WHEN system_topup < 0.01 AND implied_topup > 0.01  THEN 'NO_MONTHLY_GUARANTEE'
        WHEN ABS(system_topup - implied_topup) < 0.01      THEN 'GUARANTEE_FOLLOWS_TRIP_ERROR'
        ELSE 'UNEXPLAINED'
    END                                          AS cause,
    expected_topup                               AS expected,
    system_topup                                 AS system,
    (system_topup - expected_topup) * hourly_rate AS impact
FROM per_crew
WHERE ABS(system_topup - expected_topup) >= 0.01;
