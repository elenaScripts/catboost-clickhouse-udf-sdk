-- Run once on the local demo server. The source path is relative to user_files.
CREATE TABLE filelog_events
(
    event_time DateTime('UTC'),
    event_id UUID,
    service String,
    error_code String,
    response_ms Float64,
    retry_count UInt8
)
ENGINE = MergeTree
ORDER BY (event_time, event_id);

CREATE TABLE filelog_source
(
    event_time DateTime('UTC'),
    event_id UUID,
    service String,
    error_code String,
    response_ms Float64,
    retry_count UInt8
)
ENGINE = FileLog('incident-filelog/*.log', 'JSONEachRow');

CREATE MATERIALIZED VIEW filelog_to_events TO filelog_events AS
SELECT event_time, event_id, service, error_code, response_ms, retry_count
FROM filelog_source;
