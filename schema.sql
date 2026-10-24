-- Crew pay validator schema. Runs on DuckDB (local) and Snowflake.
-- All times are UTC. All rates and rules are illustrative, not Air Canada's actual terms.
-- Keys are declared for documentation; Snowflake does not enforce them, which is
-- one reason the validation checks in sql/ exist.

CREATE OR REPLACE TABLE crew (
    crew_id      INTEGER PRIMARY KEY,
    position     VARCHAR NOT NULL,       -- CA = captain, FO = first officer, FA = flight attendant
    base         VARCHAR NOT NULL,
    hourly_rate  DECIMAL(8,2) NOT NULL   -- CAD per credit hour
);

CREATE OR REPLACE TABLE pairings (
    pairing_id   VARCHAR PRIMARY KEY,    -- e.g. P-LHR-3D-1014 (template + start date)
    template     VARCHAR NOT NULL,
    base         VARCHAR NOT NULL,
    start_date   DATE NOT NULL
);

CREATE OR REPLACE TABLE duty_periods (
    duty_id      VARCHAR PRIMARY KEY,
    pairing_id   VARCHAR NOT NULL REFERENCES pairings(pairing_id),
    duty_seq     INTEGER NOT NULL,
    report_utc   TIMESTAMP NOT NULL,     -- 60 min before first departure
    release_utc  TIMESTAMP NOT NULL      -- 15 min after last arrival
);

CREATE OR REPLACE TABLE flights (
    flight_id    VARCHAR PRIMARY KEY,
    duty_id      VARCHAR NOT NULL REFERENCES duty_periods(duty_id),
    leg_seq      INTEGER NOT NULL,
    flight_no    VARCHAR NOT NULL,
    origin       VARCHAR NOT NULL,
    destination  VARCHAR NOT NULL,
    dep_utc      TIMESTAMP NOT NULL,
    arr_utc      TIMESTAMP NOT NULL,
    block_hrs    DECIMAL(5,2) NOT NULL,
    is_deadhead  BOOLEAN NOT NULL        -- crew rides as a passenger to reposition
);

CREATE OR REPLACE TABLE roster (
    crew_id      INTEGER NOT NULL REFERENCES crew(crew_id),
    pairing_id   VARCHAR NOT NULL REFERENCES pairings(pairing_id),
    PRIMARY KEY (crew_id, pairing_id)
);

CREATE OR REPLACE TABLE pay_rules (
    rule_name    VARCHAR PRIMARY KEY,
    value        DECIMAL(8,3) NOT NULL,
    description  VARCHAR NOT NULL
);

CREATE OR REPLACE TABLE meal_rates (
    station        VARCHAR PRIMARY KEY,
    region         VARCHAR NOT NULL,       -- domestic, transborder, international
    rate_per_hour  DECIMAL(6,2) NOT NULL,  -- CAD per hour away from base
    effective_date DATE NOT NULL
);

-- Landing table for the pay system's month-end file (loaded by validate.py).
CREATE OR REPLACE TABLE system_pay (
    crew_id      INTEGER NOT NULL,
    line_type    VARCHAR NOT NULL,       -- TRIP or GUARANTEE
    pairing_id   VARCHAR,                -- NULL for GUARANTEE lines
    credit_hrs   DOUBLE NOT NULL,
    hourly_rate  DOUBLE NOT NULL,
    amount       DOUBLE NOT NULL
);

-- Reference list of exception causes, so reports can show a plain-English description.
CREATE OR REPLACE TABLE exception_causes (
    cause        VARCHAR PRIMARY KEY,
    description  VARCHAR NOT NULL
);

INSERT INTO exception_causes VALUES
    ('MISSING_TRIP',                 'Trip on roster but not in system pay'),
    ('UNROSTERED_TRIP',              'Trip paid by system but not on roster'),
    ('NO_DUTY_RIG',                  'Credit matches pay without duty rig applied'),
    ('DEADHEAD_FULL_CREDIT',         'Credit matches deadhead paid at 100% instead of 50%'),
    ('NO_TRIP_RIG',                  'Credit matches pay without trip rig applied'),
    ('WRONG_RATE',                   'Hourly rate differs from crew master rate'),
    ('NO_MONTHLY_GUARANTEE',         'Below monthly guarantee but no top-up paid'),
    ('GUARANTEE_FOLLOWS_TRIP_ERROR', 'Top-up differs only because trip credits above are wrong'),
    ('UNEXPLAINED',                  'Difference matches no known failure mode: review manually');
