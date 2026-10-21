-- Crew pay validator schema (DuckDB).
-- All times are UTC. All rates and rules are illustrative, not Air Canada's actual terms.

CREATE TABLE crew (
    crew_id      INTEGER PRIMARY KEY,
    position     VARCHAR NOT NULL,       -- CA = captain, FO = first officer, FA = flight attendant
    base         VARCHAR NOT NULL,
    hourly_rate  DECIMAL(8,2) NOT NULL   -- CAD per credit hour
);

CREATE TABLE pairings (
    pairing_id   VARCHAR PRIMARY KEY,    -- e.g. P-LHR-3D-1014 (template + start date)
    template     VARCHAR NOT NULL,
    base         VARCHAR NOT NULL,
    start_date   DATE NOT NULL
);

CREATE TABLE duty_periods (
    duty_id      VARCHAR PRIMARY KEY,
    pairing_id   VARCHAR NOT NULL REFERENCES pairings(pairing_id),
    duty_seq     INTEGER NOT NULL,
    report_utc   TIMESTAMP NOT NULL,     -- 60 min before first departure
    release_utc  TIMESTAMP NOT NULL      -- 15 min after last arrival
);

CREATE TABLE flights (
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

CREATE TABLE roster (
    crew_id      INTEGER NOT NULL REFERENCES crew(crew_id),
    pairing_id   VARCHAR NOT NULL REFERENCES pairings(pairing_id),
    PRIMARY KEY (crew_id, pairing_id)
);

CREATE TABLE pay_rules (
    rule_name    VARCHAR PRIMARY KEY,
    value        DECIMAL(8,3) NOT NULL,
    description  VARCHAR NOT NULL
);

CREATE TABLE meal_rates (
    station        VARCHAR PRIMARY KEY,
    region         VARCHAR NOT NULL,       -- domestic, transborder, international
    rate_per_hour  DECIMAL(6,2) NOT NULL,  -- CAD per hour away from base
    effective_date DATE NOT NULL
);
