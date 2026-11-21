SELECT
    event_time,
    event_id,
    service,
    error_code,
    response_ms,
    retry_count,
    incident_risk(
        CAST(service, 'Nullable(String)'),
        CAST(error_code, 'Nullable(String)'),
        CAST(response_ms, 'Nullable(Float64)'),
        CAST(retry_count, 'Nullable(Float64)')
    ) AS risk
FROM filelog_events
ORDER BY event_time DESC, event_id
LIMIT 20;
