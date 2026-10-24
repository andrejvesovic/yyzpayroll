-- What each trip's credit would be if a pay system got one rule wrong.
-- If the system pays a trip at exactly one of these numbers, that's the likely cause.
-- (generate_system_pay.py also uses these to plant errors.)
CREATE OR REPLACE VIEW failure_modes AS
WITH wrong_duty_credit AS (
    SELECT
        dc.pairing_id,
        -- duty rig left out
        GREATEST(dc.block_hrs + r.deadhead_ratio * dc.deadhead_hrs,
                 r.min_day_hrs)                                     AS no_duty_rig,
        -- deadhead paid at 100% instead of 50%
        GREATEST(dc.block_hrs + dc.deadhead_hrs,
                 r.min_day_hrs,
                 r.duty_rig_ratio * dc.duty_hrs)                    AS deadhead_full
    FROM duty_credit dc
    CROSS JOIN rules r
),
wrong_trip_totals AS (
    SELECT pairing_id,
           SUM(no_duty_rig)   AS no_duty_rig_sum,
           SUM(deadhead_full) AS deadhead_full_sum
    FROM wrong_duty_credit
    GROUP BY pairing_id
)
SELECT
    tc.pairing_id,
    ROUND(GREATEST(w.no_duty_rig_sum,   r.trip_rig_ratio * tc.tafb_hrs), 2) AS no_duty_rig,
    ROUND(GREATEST(w.deadhead_full_sum, r.trip_rig_ratio * tc.tafb_hrs), 2) AS deadhead_full_credit,
    -- trip rig left out: just the duty-day credits added up
    ROUND(tc.duty_credit_sum, 2)                                           AS no_trip_rig
FROM trip_credit tc
JOIN wrong_trip_totals w ON w.pairing_id = tc.pairing_id
CROSS JOIN rules r;
