-- These metrics count log rows, not incident windows.
SELECT
    threshold,
    countIf(risk >= threshold AND incident = 1) AS detected,
    countIf(risk < threshold AND incident = 1) AS missed,
    countIf(risk >= threshold AND incident = 0) AS false_alarms,
    round(100.0 * detected / nullIf(detected + missed, 0), 1) AS recall_pct,
    round(100.0 * detected / nullIf(detected + false_alarms, 0), 1) AS precision_pct
FROM
(
    SELECT
        incident,
        incident_risk_scenario(
            CAST(service, 'Nullable(String)'),
            CAST(error_code, 'Nullable(String)'),
            CAST(response_ms, 'Nullable(Float64)'),
            CAST(retry_count, 'Nullable(Float64)')
        ) AS risk
    FROM incident_logs_scenario_utc
) AS scored
CROSS JOIN
(
    SELECT arrayJoin([0.01, 0.02, 0.05, 0.10, 0.20]) AS threshold
) AS thresholds
GROUP BY threshold
ORDER BY threshold;
