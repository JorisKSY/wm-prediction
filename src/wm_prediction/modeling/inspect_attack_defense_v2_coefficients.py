import pandas as pd

from wm_prediction.modeling.experiment_attack_defense_form_v2 import (
    ALPHA,
    FEATURE_SETS,
    load_attack_defense_model_input,
    make_model,
)
from wm_prediction.modeling.poisson_regressor_mvp import add_temporal_split


FEATURE_SET_NAME = "attack_defense_v2_candidate"


def main() -> None:
    df = add_temporal_split(load_attack_defense_model_input())
    feature_columns = FEATURE_SETS[FEATURE_SET_NAME]

    train = df[df["split"] == "train_pre_2018"].copy()

    home_model = make_model(feature_columns)
    away_model = make_model(feature_columns)

    home_model.named_steps["model"].set_params(alpha=ALPHA)
    away_model.named_steps["model"].set_params(alpha=ALPHA)

    home_model.fit(train[feature_columns], train["home_goals"])
    away_model.fit(train[feature_columns], train["away_goals"])

    summary = pd.DataFrame(
        {
            "feature": feature_columns,
            "home_coef_std": home_model.named_steps["model"].coef_,
            "away_coef_std": away_model.named_steps["model"].coef_,
        }
    )

    summary["max_abs_coef_std"] = summary[
        ["home_coef_std", "away_coef_std"]
    ].abs().max(axis=1)

    print("Attack/Defense v2 standardized coefficients")
    print(f"feature_set: {FEATURE_SET_NAME}")
    print(f"alpha: {ALPHA}")
    print("Interpretation: +1 std feature change effect on log(lambda_home/lambda_away)")
    print()

    print(
        summary.sort_values(
            ["max_abs_coef_std", "feature"],
            ascending=[False, True],
        )
        .round(4)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
