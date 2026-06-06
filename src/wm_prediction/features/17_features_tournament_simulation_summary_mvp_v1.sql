CREATE SCHEMA IF NOT EXISTS features;

DROP TABLE IF EXISTS features.tournament_simulation_summary_mvp_v1;

CREATE TABLE features.tournament_simulation_summary_mvp_v1 (
    simulation_run_id text NOT NULL,
    model_name text NOT NULL,
    n_simulations integer NOT NULL,
    seed_start integer NOT NULL,
    seed_end integer NOT NULL,
    team text NOT NULL,
    p_advance_group double precision NOT NULL,
    p_reach_round_of_16 double precision NOT NULL,
    p_reach_quarter_final double precision NOT NULL,
    p_reach_semi_final double precision NOT NULL,
    p_final double precision NOT NULL,
    p_title double precision NOT NULL,
    p_third_place double precision NOT NULL,
    created_at timestamp without time zone NOT NULL DEFAULT now(),

    PRIMARY KEY (simulation_run_id, team)
);

CREATE INDEX IF NOT EXISTS idx_tournament_sim_summary_mvp_v1_title
ON features.tournament_simulation_summary_mvp_v1 (p_title DESC);

CREATE INDEX IF NOT EXISTS idx_tournament_sim_summary_mvp_v1_model_run
ON features.tournament_simulation_summary_mvp_v1 (model_name, simulation_run_id);
