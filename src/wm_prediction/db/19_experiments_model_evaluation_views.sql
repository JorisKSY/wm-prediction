CREATE OR REPLACE VIEW experiments.model_evaluation_metric_pivot AS
SELECT
    experiment_run_id,
    model_name,
    feature_set_name,
    target_name,
    split,

    MAX(metric_value) FILTER (WHERE metric_name = 'home_deviance') AS home_deviance,
    MAX(metric_value) FILTER (WHERE metric_name = 'away_deviance') AS away_deviance,
    MAX(metric_value) FILTER (WHERE metric_name = 'home_mae') AS home_mae,
    MAX(metric_value) FILTER (WHERE metric_name = 'away_mae') AS away_mae,
    MAX(metric_value) FILTER (WHERE metric_name = 'wdl_log_loss') AS wdl_log_loss,
    MAX(metric_value) FILTER (WHERE metric_name = 'wdl_brier') AS wdl_brier,

    MAX(n_train_rows) AS n_train_rows,
    MAX(n_eval_rows) AS n_eval_rows,
    MIN(train_start_date) AS train_start_date,
    MAX(train_end_date) AS train_end_date,
    MIN(eval_start_date) AS eval_start_date,
    MAX(eval_end_date) AS eval_end_date,
    MIN(created_at) AS created_at
FROM experiments.model_evaluation_results
GROUP BY
    experiment_run_id,
    model_name,
    feature_set_name,
    target_name,
    split;
