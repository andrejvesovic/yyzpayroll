-- Trip check: compare every trip in the system pay file to expected pay.
-- Three kinds of problem, stacked together with UNION ALL.
CREATE OR REPLACE VIEW trip_exceptions AS

-- 1. On the roster, but the system didn't pay it
SELECT
    e.crew_id,
    e.pairing_id,
    'MISSING_TRIP'                AS cause,
    e.credit_hrs                  AS expected,
    0.0                           AS system,
    -e.credit_hrs * e.hourly_rate AS impact
FROM expected_pay_lines e
LEFT JOIN system_pay s ON s.crew_id = e.crew_id AND s.pairing_id = e.pairing_id
WHERE e.line_type = 'TRIP'
  AND s.crew_id IS NULL

UNION ALL

-- 2. Paid by the system, but not on the roster
SELECT
    s.crew_id,
    s.pairing_id,
    'UNROSTERED_TRIP',
    0.0,
    s.credit_hrs,
    s.credit_hrs * c.hourly_rate
FROM system_pay s
JOIN crew c ON c.crew_id = s.crew_id
LEFT JOIN roster ro ON ro.crew_id = s.crew_id AND ro.pairing_id = s.pairing_id
WHERE s.line_type = 'TRIP'
  AND ro.crew_id IS NULL

UNION ALL

-- 3. Paid, but with the wrong credit: test it against each known failure mode
SELECT
    e.crew_id,
    e.pairing_id,
    CASE
        WHEN ABS(s.credit_hrs - fm.no_duty_rig)          < 0.01 THEN 'NO_DUTY_RIG'
        WHEN ABS(s.credit_hrs - fm.deadhead_full_credit) < 0.01 THEN 'DEADHEAD_FULL_CREDIT'
        WHEN ABS(s.credit_hrs - fm.no_trip_rig)          < 0.01 THEN 'NO_TRIP_RIG'
        ELSE 'UNEXPLAINED'
    END,
    e.credit_hrs,
    s.credit_hrs,
    (s.credit_hrs - e.credit_hrs) * e.hourly_rate
FROM expected_pay_lines e
JOIN system_pay s     ON s.crew_id = e.crew_id AND s.pairing_id = e.pairing_id
JOIN failure_modes fm ON fm.pairing_id = e.pairing_id
WHERE e.line_type = 'TRIP'
  AND ABS(s.credit_hrs - e.credit_hrs) >= 0.01;
