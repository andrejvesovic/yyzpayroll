-- All exceptions in one list, with a plain-English description of each cause.
CREATE OR REPLACE VIEW exceptions AS
WITH all_exceptions AS (
    SELECT * FROM trip_exceptions
    UNION ALL
    SELECT * FROM rate_exceptions
    UNION ALL
    SELECT * FROM guarantee_exceptions
)
SELECT
    a.crew_id,
    a.pairing_id,
    a.cause,
    a.expected,
    a.system,
    ROUND(a.impact, 2) AS impact,
    ec.description
FROM all_exceptions a
JOIN exception_causes ec ON ec.cause = a.cause;
