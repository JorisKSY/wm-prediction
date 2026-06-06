# MVP v1 Notes

Projekt: WM Prediction via Two-Stage Modeling  
Stand: nach 1000 Full-Tournament-Simulationen (`mvp_v1_seed_42_n_1000`)

## Full-Tournament-Simulation

Der Run `mvp_v1_seed_42_n_1000` wurde erfolgreich in `features.tournament_simulation_summary_mvp_v1` geschrieben.

Audit-Summen:

- `p_advance_group`: 32
- `p_reach_round_of_16`: 16
- `p_reach_quarter_final`: 8
- `p_reach_semi_final`: 4
- `p_final`: 2
- `p_title`: 1
- `p_third_place`: 1

Zusätzlich geprüft:

- keine Wahrscheinlichkeiten außerhalb `[0, 1]`
- keine nicht-monotonen Rundenwahrscheinlichkeiten
- `p_third_place` nie größer als `p_reach_semi_final`

## Brazil / Morocco Auffälligkeit

Brazil hat im MVP-v1-Run eine relativ niedrige Titelwahrscheinlichkeit, obwohl der FIFA-Rank stark ist.

Der Befund ist aktuell kein offensichtlicher Join- oder Bracket-Fehler:

- Brazil ist in Group E nicht kaputt einsortiert.
- Morocco und Brazil liegen in Group E fast gleichauf.
- Brazil vs Morocco ist im Modell ein nahezu ausgeglichenes Matchup mit leichtem Morocco-Vorteil.
- Brazil hat im Pre-Tournament-Snapshot deutlich schwächere Formwerte als Morocco.
- Wenn Brazil in Group E Zweiter wird, trifft es in der Round of 32 auf `2I`; Group I enthält mit Germany, Ivory Coast und Ecuador mehrere unangenehme mögliche Gegner.

Interpretation:

- Die niedrige Brazil-Titelchance ist plausibel durch MVP-Featuregewichtung und Bracket-Pfad erklärbar.
- Das sollte später mit Feature-v2 oder Modell-v2 erneut geprüft werden.
- Kein akuter Grund für eine manuelle Korrektur.

## PoissonRegressor MVP Koeffizienten

Die standardisierten Koeffizienten zeigen grob, welche Features das MVP-v1-Modell aktuell treiben.

Wichtigste Beobachtungen:

- stärkster Treiber ist `fifa_rank_diff_home_minus_away`
- danach folgen die einzelnen FIFA-Rank-Spalten `home_fifa_rank` und `away_fifa_rank`
- danach kommen vor allem Goal-Diff-Formfeatures:
  - `prev5y_goal_diff_per_match_diff`
  - `prev10_goal_diff_per_match_diff`
  - `prev5_goal_diff_per_match_diff`
- Points-per-Match-Formfeatures sind im aktuellen regularisierten PoissonRegressor überraschend schwach
- `is_nations_league` hat praktisch keinen Effekt

Einschränkung:

`home_fifa_rank`, `away_fifa_rank` und `fifa_rank_diff_home_minus_away` sind redundant/kollinear. Die Koeffizienten sind daher nützlich zur Modell-Diagnose, aber nicht als saubere kausale Feature-Wichtigkeit zu interpretieren.

Folgerung:

Für v2 sollte geprüft werden, ob die FIFA-Rank-Features weniger redundant modelliert werden sollten, z. B. nur über Differenz plus optional stärkere/schwächere Team-Rank-Skala. Außerdem sollte geprüft werden, ob Points-per-Match-Formfeatures wirklich zusätzlichen Nutzen bringen oder durch Goal-Diff-Features verdrängt werden.
