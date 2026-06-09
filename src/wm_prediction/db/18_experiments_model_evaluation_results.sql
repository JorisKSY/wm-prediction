CREATE SCHEMA IF NOT EXISTS experiments;

DROP TABLE IF EXISTS experiments.model_evaluation_results;

CREATE TABLE experiments.model_evaluation_results (
    experiment_run_id text NOT NULL,
    model_name text NOT NULL,
    feature_set_name text NOT NULL,
    target_name text NOT NULL,
    split text NOT NULL,
    metric_name text NOT NULL,
    metric_value double precision NOT NULL,

    train_start_date date,
    train_end_date date,
    eval_start_date date,
    eval_end_date date,

    n_train_rows integer NOT NULL,
    n_eval_rows integer NOT NULL,

    params_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    notes text,

    created_at timestamp without time zone NOT NULL DEFAULT now(),

    PRIMARY KEY (
        experiment_run_id,
        model_name,
        feature_set_name,
        target_name,
        split,
        metric_name
    )
);

CREATE INDEX idx_model_eval_results_model_feature
    ON experiments.model_evaluation_results (
        model_name,
        feature_set_name,
        split
    );

CREATE INDEX idx_model_eval_results_metric
    ON experiments.model_evaluation_results (
        metric_name,
        metric_value
    );

CREATE INDEX idx_model_eval_results_created_at
    ON experiments.model_evaluation_results (
        created_at DESC
    );
