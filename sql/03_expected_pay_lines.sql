-- What every crew member should be paid:
--   one TRIP line per trip they flew
--   one GUARANTEE line topping them up to 70 hrs, if their trips credit less than that
CREATE OR REPLACE VIEW expected_pay_lines AS
WITH trip_lines AS (
    SELECT
        ro.crew_id,
        'TRIP'                AS line_type,
        ro.pairing_id,
        tc.trip_credit        AS credit_hrs,
        c.hourly_rate::DOUBLE AS hourly_rate
    FROM roster ro
    JOIN trip_credit tc ON tc.pairing_id = ro.pairing_id
    JOIN crew c         ON c.crew_id = ro.crew_id
),
crew_totals AS (
    -- total trip credit per crew member (0 if they flew nothing)
    SELECT
        c.crew_id,
        c.hourly_rate::DOUBLE           AS hourly_rate,
        COALESCE(SUM(tl.credit_hrs), 0) AS trip_hrs
    FROM crew c
    LEFT JOIN trip_lines tl ON tl.crew_id = c.crew_id
    GROUP BY c.crew_id, c.hourly_rate
),
guarantee_lines AS (
    SELECT
        ct.crew_id,
        'GUARANTEE'                                    AS line_type,
        NULL                                           AS pairing_id,
        ROUND(r.monthly_guarantee_hrs - ct.trip_hrs, 2) AS credit_hrs,
        ct.hourly_rate
    FROM crew_totals ct
    CROSS JOIN rules r
    WHERE ct.trip_hrs < r.monthly_guarantee_hrs
)
SELECT crew_id, line_type, pairing_id, credit_hrs, hourly_rate,
       ROUND(credit_hrs * hourly_rate, 2) AS amount
FROM trip_lines
UNION ALL
SELECT crew_id, line_type, pairing_id, credit_hrs, hourly_rate,
       ROUND(credit_hrs * hourly_rate, 2) AS amount
FROM guarantee_lines;
