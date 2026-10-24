-- Rate check: is the system paying anyone at a different hourly rate than the crew master file?
-- One row per crew member; the impact covers all of their pay lines.
CREATE OR REPLACE VIEW rate_exceptions AS
SELECT
    s.crew_id,
    NULL                                                   AS pairing_id,
    'WRONG_RATE'                                           AS cause,
    c.hourly_rate::DOUBLE                                  AS expected,
    MIN(s.hourly_rate)                                     AS system,
    SUM(s.credit_hrs * (s.hourly_rate - c.hourly_rate))    AS impact
FROM system_pay s
JOIN crew c ON c.crew_id = s.crew_id
WHERE ABS(s.hourly_rate - c.hourly_rate) >= 0.01
GROUP BY s.crew_id, c.hourly_rate;
