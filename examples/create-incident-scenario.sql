-- Each label marks a row inside a simulated service incident window.
CREATE TABLE incident_logs_scenario_utc
(
    event_time DateTime('UTC'),
    event_id UInt64,
    service LowCardinality(String),
    error_code LowCardinality(String),
    response_ms Float64,
    retry_count UInt8,
    incident UInt8
)
ENGINE = MergeTree
ORDER BY (event_time, service, event_id);
