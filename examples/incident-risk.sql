-- Rank recent events by predicted risk.
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
FROM incident_logs
WHERE event_time >= now() - INTERVAL 1 DAY
ORDER BY risk DESC
LIMIT 100;

-- Evaluate a candidate threshold against the synthetic labels.
-- 0.10 is only illustrative; tune it using the real costs of false positives and misses.
SELECT
    count() AS scored_events,
    countIf(incident = 1) AS actual_incidents,
    countIf(risk >= 0.10 AND incident = 1) AS true_positives,
    countIf(risk >= 0.10 AND incident = 0) AS false_positives,
    countIf(risk < 0.10 AND incident = 1) AS missed_incidents
FROM
(
    SELECT
        incident,
        incident_risk(
            CAST(service, 'Nullable(String)'),
            CAST(error_code, 'Nullable(String)'),
            CAST(response_ms, 'Nullable(Float64)'),
            CAST(retry_count, 'Nullable(Float64)')
        ) AS risk
    FROM incident_logs
);
