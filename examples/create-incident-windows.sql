CREATE TABLE incident_scenario_windows
(
    service LowCardinality(String),
    start_utc DateTime('UTC'),
    end_utc DateTime('UTC'),
    simulated_type LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY (service, start_utc);
