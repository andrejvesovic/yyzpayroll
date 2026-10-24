-- Credit for each trip (pairing) = the higher of:
--   the sum of its duty-day credits
--   the trip rig (1 hr credit per 3.5 hrs away from base)
CREATE OR REPLACE VIEW trip_credit AS
WITH trips AS (
    -- one row per trip: total duty-day credit, and hours from first report to last release
    SELECT
        dc.pairing_id,
        SUM(dc.duty_credit) AS duty_credit_sum,
        DATEDIFF('minute', MIN(d.report_utc), MAX(d.release_utc)) / 60.0 AS tafb_hrs
    FROM duty_credit dc
    JOIN duty_periods d ON d.duty_id = dc.duty_id
    GROUP BY dc.pairing_id
)
SELECT
    t.pairing_id,
    t.duty_credit_sum,
    t.tafb_hrs,
    ROUND(GREATEST(t.duty_credit_sum, r.trip_rig_ratio * t.tafb_hrs), 2) AS trip_credit,
    -- which rule decided the pay
    CASE WHEN t.duty_credit_sum >= r.trip_rig_ratio * t.tafb_hrs
         THEN 'duty_days' ELSE 'trip_rig' END AS trip_basis
FROM trips t
CROSS JOIN rules r;
