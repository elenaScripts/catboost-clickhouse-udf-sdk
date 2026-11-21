# Use cases

These examples describe places where SQL-based model scoring may be useful. They are not claims about model quality or production performance.

## Rank service logs for investigation

A team can score service log rows and sort them by a model's estimated risk. The included demo uses service name, HTTP status code, response time, and retry count. Its labels are synthetic, so the ranking only demonstrates the integration. The query in [incident-risk.sql](../examples/incident-risk.sql) calls the executable UDF from a `SELECT` query and returns the highest-scoring recent rows.

A score does not identify an incident by itself. For an alerting workflow, define how to group rows, choose a threshold, and measure missed incidents and investigation volume against representative data. The [synthetic incident tutorial](synthetic-scenario.md) shows one simulated evaluation.

## Score transactions for review

If transaction features already exist in a table, an analyst can use a binary classifier to prioritize rows for review. The model owner must supply the trained model and a manifest with the same feature order and positive class used during training. Validate the scores against direct CatBoost predictions and measure precision and recall with appropriately labeled data.

The included classifier is not trained for transactions. This repository does not include a transaction dataset or a fraud model.

## Add a regression estimate to a query

A team can package a supported scalar regression model and call its UDF from a `SELECT` statement. The result is the raw regression prediction, not a probability. Use the [manifest reference](reference.md) to select a supported objective and match the arguments to the model.

This repository does not include a production regression model. Before deployment, compare predictions and measure the cost of scoring with your own model and data.
