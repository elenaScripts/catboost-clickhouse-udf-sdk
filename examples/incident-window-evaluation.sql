-- Evaluate observed incident windows at a score threshold of 0.10.
SELECT
    windows.service AS service,
    windows.simulated_type AS simulated_type,
    windows.start_utc AS start_utc,
    windows.end_utc AS end_utc,
    count() AS sampled_events,
    countIf(scored.risk >= 0.10) AS flagged_events,
    minIf(toNullable(scored.event_time), scored.risk >= 0.10) AS first_flagged_utc,
    dateDiff('second', start_utc, first_flagged_utc) AS detection_delay_seconds
FROM incident_scenario_windows AS windows
INNER JOIN
(
    SELECT
        service,
        event_time,
        incident_risk_scenario(
            CAST(service, 'Nullable(String)'),
            CAST(error_code, 'Nullable(String)'),
            CAST(response_ms, 'Nullable(Float64)'),
            CAST(retry_count, 'Nullable(Float64)')
        ) AS risk
    FROM incident_logs_scenario_utc
) AS scored
ON windows.service = scored.service
    AND scored.event_time >= windows.start_utc
    AND scored.event_time < windows.end_utc
GROUP BY service, simulated_type, start_utc, end_utc
ORDER BY start_utc;
