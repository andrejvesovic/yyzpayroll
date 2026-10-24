-- The pay rules, turned from rows into one row with a column per rule,
-- so other queries can use them by name (r.min_day_hrs, r.duty_rig_ratio, ...).
CREATE OR REPLACE VIEW rules AS
SELECT
    MAX(CASE WHEN rule_name = 'min_day_guarantee_hrs' THEN value END)::DOUBLE AS min_day_hrs,
    MAX(CASE WHEN rule_name = 'duty_rig_ratio'        THEN value END)::DOUBLE AS duty_rig_ratio,
    MAX(CASE WHEN rule_name = 'trip_rig_ratio'        THEN value END)::DOUBLE AS trip_rig_ratio,
    MAX(CASE WHEN rule_name = 'deadhead_credit_ratio' THEN value END)::DOUBLE AS deadhead_ratio,
    MAX(CASE WHEN rule_name = 'monthly_guarantee_hrs' THEN value END)::DOUBLE AS monthly_guarantee_hrs
FROM pay_rules;

-- Credit for each duty day = the highest of:
--   block credit (flying hours, deadhead counted at 50%)
--   the minimum day guarantee (4 hrs)
--   the duty rig (1 hr credit per 2 hrs on duty)
CREATE OR REPLACE VIEW duty_credit AS
WITH duty AS (
    -- one row per duty day: hours flown, hours deadheaded, hours on duty
    SELECT
        d.pairing_id,
        d.duty_id,
        SUM(CASE WHEN f.is_deadhead THEN 0 ELSE f.block_hrs END)::DOUBLE AS block_hrs,
        SUM(CASE WHEN f.is_deadhead THEN f.block_hrs ELSE 0 END)::DOUBLE AS deadhead_hrs,
        DATEDIFF('minute', d.report_utc, d.release_utc) / 60.0           AS duty_hrs
    FROM duty_periods d
    JOIN flights f ON f.duty_id = d.duty_id
    GROUP BY d.pairing_id, d.duty_id, d.report_utc, d.release_utc
)
SELECT
    duty.pairing_id,
    duty.duty_id,
    duty.block_hrs,
    duty.deadhead_hrs,
    duty.duty_hrs,
    GREATEST(
        duty.block_hrs + r.deadhead_ratio * duty.deadhead_hrs,
        r.min_day_hrs,
        r.duty_rig_ratio * duty.duty_hrs
    ) AS duty_credit
FROM duty
CROSS JOIN rules r;
