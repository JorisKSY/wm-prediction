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


## Feature-Ablation v1.1 Diagnose

Datum: 2026-06-06

Scope:

- Nur Diagnose-Scripts.
- Keine Datenbank-Writes.
- Noch keine Änderung am produktiven MVP-Modell.
- Trainingssplit bleibt `train_pre_2018`.
- Validierungs- und Testsplit bleiben unverändert.

Getestete Feature-Varianten:

- Aktuelles MVP-Feature-Set mit 18 Features.
- FIFA-Varianten:
  - alle rohen Rank-Features
  - nur `fifa_rank_diff_home_minus_away`
  - nur `home_fifa_rank` + `away_fifa_rank`
  - Log-Rank-Transformationen
  - reziproke Rank-Strength-Transformation
- Form-Varianten:
  - Points-per-Match plus Goal-Diff-Form
  - nur Goal-Diff-Form
  - nur Points-per-Match-Form
- Kontext-Varianten:
  - alle Kontextflags
  - ohne `is_nations_league`
  - nur neutral/friendly
  - nur neutral
  - kein Kontext
- Extreme-Score-Sensitivität:
  - voller Trainingsdatensatz
  - Ausschluss von Trainingsspielen, in denen ein Team 8+ Tore erzielt hat
  - Ausschluss von Trainingsspielen mit insgesamt 10+ Toren

Wichtigste Befunde:

- `goal_diff_form_no_ppm` war auf Validierung und Test minimal besser als das aktuelle MVP-Feature-Set.
- Points-per-Match-Formfeatures haben im aktuellen PoissonRegressor-Setup keinen messbaren Nutzen gebracht.
- Rohe FIFA-Rank-Features waren besser als Log-Rank- oder reziproke Rank-Strength-Transformationen.
- Nur `fifa_rank_diff_home_minus_away` war schlechter als die Kombination aus rohen Home-/Away-Ranks plus Rank-Differenz.
- Das Entfernen extremer Scores aus dem Training hat Validierungs- und Testperformance verschlechtert. Extreme Scores sollten daher im MVP-Training vorerst enthalten bleiben.
- Das Entfernen von `is_nations_league` hatte keinen Effekt, weil es im Trainingssplit keine Nations-League-Spiele gibt.

Kontextflag-Abdeckung nach Split:

- `train_pre_2018`: 21.140 Zeilen, `is_nations_league = 0`
- `valid_2018_2021`: 3.334 Zeilen, `is_nations_league = 435`
- `test_2022_plus`: 4.166 Zeilen, `is_nations_league = 578`

Aktueller v1.1-Kandidat:

- Rohe FIFA-Rank-Features behalten:
  - `home_fifa_rank`
  - `away_fifa_rank`
  - `home_fifa_ranking_age_days`
  - `away_fifa_ranking_age_days`
  - `fifa_rank_diff_home_minus_away`
- Goal-Diff-Formfeatures behalten:
  - `prev5_goal_diff_per_match_diff`
  - `prev10_goal_diff_per_match_diff`
  - `prev5y_goal_diff_per_match_diff`
- Points-per-Match-Formfeatures im Kandidatenmodell entfernen.
- `is_nations_league` im Kandidatenmodell entfernen.
- Andere Kontextflags vorerst behalten; komplett ohne Kontext war klar schlechter.

Wichtige Einschränkung:

Die Unterschiede sind klein. Das Ergebnis sollte als v1.1-Diagnosekandidat verstanden werden, nicht als Beweis für ein allgemein überlegenes Feature-Set.


## Entscheidung zu v1.1 nach erster Ablation

Nach der ersten Feature-Ablation wurde ein bereinigter Kandidat `cleaned_14_candidate` in der Experiment-DB gespeichert und mit dem aktuellen MVP-Feature-Set `current_mvp_all_18` verglichen.

Ergebnis:

- `cleaned_14_candidate` ist bei WDL-Log-Loss und Brier auf Validierung und Test minimal besser.
- Die Verbesserung ist klein und sollte nicht als echter Modell-Sprung interpretiert werden.
- Die entfernten Features waren eher unnötig, redundant oder im aktuellen Trainingssplit nicht lernbar, aber nicht stark schädlich.

Entfernte Features im bereinigten Kandidaten:

- `prev5_points_per_match_diff`
- `prev10_points_per_match_diff`
- `prev5y_points_per_match_diff`
- `is_nations_league`

Begründung:

- Points-per-Match-Formfeatures brachten im aktuellen PoissonRegressor-Setup keinen messbaren Zusatznutzen gegenüber Goal-Diff-Formfeatures.
- `is_nations_league` hat im aktuellen Trainingssplit `train_pre_2018` keine positiven Trainingsbeispiele und kann deshalb vom Modell nicht sinnvoll gelernt werden.

Entscheidung:

- Der produktive MVP-v1-Stand wird vorerst nicht end-to-end durch `cleaned_14_candidate` ersetzt.
- `poisson_regressor_mvp_v1` bleibt die aktuelle Referenz für Predictions, Simulationen und Streamlit.
- `cleaned_14_candidate` bleibt als dokumentierter Vergleichs- und Hygiene-Kandidat in `experiments.model_evaluation_results`.
- Die nächste echte Modellverbesserung soll über v2-Features erfolgen, insbesondere Attack-/Defense-Formfeatures und später opponent-adjusted Form.

Interpretation:

`cleaned_14_candidate` ist methodisch etwas sauberer, aber nicht ausreichend besser, um allein daraus eine neue Modellgeneration abzuleiten.


## Phase B: Alpha-Tuning und v1.1-Kandidat

Nach der ersten Feature-Ablation wurde ein Alpha-Tuning für den `PoissonRegressor` durchgeführt.

Getestete Feature-Sets:

- `current_mvp_all_18`
- `cleaned_14_candidate`

Getestete Alpha-Werte:

- `0.01`
- `0.03`
- `0.1`
- `0.3`
- `1.0`
- `3.0`
- `10.0`

Wichtigster Befund:

Das bisherige MVP-Modell mit `alpha=1.0` war deutlich stärker regularisiert als für die aktuellen Features sinnvoll erscheint. Niedrigere Alpha-Werte verbessern Train-, Validierungs- und Testmetriken gleichzeitig.

Vergleich bisheriger MVP gegen stärksten v1.1-Kandidaten:

- `current_mvp_all_18`, `alpha=1.0`
  - Valid WDL Log-Loss: `0.8706`
  - Test WDL Log-Loss: `0.8818`

- `current_mvp_all_18`, `alpha=0.03`
  - Valid WDL Log-Loss: `0.8555`
  - Test WDL Log-Loss: `0.8666`

Interpretation:

- Die Verbesserung kommt primär durch Alpha-Tuning, nicht durch Feature-Removal.
- `cleaned_14_candidate` bleibt methodisch interessant, ist aber nach Alpha-Tuning nicht der stärkste Kandidat.
- `current_mvp_all_18` mit `alpha=0.03` ist der beste pragmatische v1.1-Kandidat, weil das Feature-Set kompatibel zum bestehenden MVP bleibt und die Metriken deutlich besser sind.

Entscheidung:

- v1.1-Kandidat: `current_mvp_all_18` mit `PoissonRegressor(alpha=0.03)`.
- MVP-v1 wird noch nicht automatisch end-to-end ersetzt.
- Der Kandidat bleibt zunächst in der Experiment-DB dokumentiert.
- Der nächste echte Verbesserungsblock ist v2 mit neuen zeitabhängigen Teamstärke-Features, insbesondere Attack-/Defense-Formfeatures.


## Phase C: v2 Feature Set 1 — Attack-/Defense-Form

Datum: 2026-06-06

Scope:

- Erster v2-Featureblock: getrennte Attack-/Defense-Formsignale für Home und Away.
- Reine Diagnose über `experiment_attack_defense_form_v2.py`.
- Trainingssplit bleibt `train_pre_2018`, Alpha fix `0.03` (v1.1-Referenz).
- Kein End-to-End-Umbau, keine neue WM-Pipeline.

Verwendete Attack-/Defense-Features (bereits in `features.model_input_mvp_v1` vorhanden, leakage-sicher über `prev.match_date < cur.match_date`):

- `home_prev5_goals_for_per_match`, `home_prev5_goals_against_per_match`
- `away_prev5_goals_for_per_match`, `away_prev5_goals_against_per_match`
- analog `prev10` und `prev5y`

Getestete Feature-Sets:

- `current_mvp_all_18`
- `attack_defense_plus_mvp_form`
- `attack_defense_only`
- `attack_defense_plus_goal_diff`
- `attack_defense_plus_points`

Wichtigste Befunde:

- Attack-/Defense-Features verbessern vor allem `home_deviance` und `away_deviance` spürbar. Das ist fachlich plausibel, weil Stage 1 genau erwartete Tore (`lambda_home`, `lambda_away`) schätzt.
- WDL Log-Loss und Brier verbessern sich nur leicht, aber stabil.
- Bester Kandidat nach Metrik: `attack_defense_plus_mvp_form` (Test Log-Loss `0.8650` vs. `0.8666` für `current_mvp_all_18`).
- Koeffizientenprüfung (`inspect_attack_defense_v2_coefficients.py`) zeigt Multikollinearität/redundante Signale zwischen den Formfeatures. `attack_defense_only` ist schlanker und fachlich sauberer, aber minimal schlechter.

Status Feature Set 1:

- Für die **lineare** Stufe (PoissonRegressor) inhaltlich abgeschlossen: Der Roh-Attack-/Defense-Block ist getestet.
- Die ursprünglich geplanten Cross-Differenzen `home_attack_minus_away_defense` und `away_attack_minus_home_defense` wurden **bewusst nicht** ergänzt. Begründung: In einem linearen GLM sind sie nur Linearkombinationen bereits vorhandener Features (z. B. `home_prev5_goals_for - away_prev5_goals_against`) und damit redundant. Das deckt sich mit dem Befund, dass `attack_defense_plus_goal_diff` und `attack_defense_plus_points` kaum Mehrwert brachten — `goal_diff` ist dieselbe Art linear-redundanter Differenz.
- Offene Notiz für Phase H: Cross-Differenz- und Interaktionsfeatures bei Baum-/Boosting-Modellen erneut prüfen. Bäume splitten achsenweise und können schräge Differenzbeziehungen nicht in einem Schritt abbilden; dort kann eine fertige Differenzspalte echten Mehrwert bringen. Produkte/Interaktionen finden Bäume dagegen meist selbst.

Einordnung zur Modellklassenfrage:

- Fußballergebnisse sind stark rauschbehaftet; ein großer Ergebnisanteil ist nicht lernbar. Das zeigt sich an den kleinen Metrikbewegungen (Alpha-Tuning war der weit größere Hebel als die Attack-/Defense-Features).
- Der Two-Stage-Poisson-Ansatz ist der fachliche Standard (Maher / Dixon-Coles-Linie), kein Behelf.
- Ein Wechsel zu `HistGradientBoostingRegressor(loss="poisson")` bzw. XGBoost bleibt ein legitimer Phase-H-Kandidat, aber mit realistisch kleinen erwartbaren Gewinnen und Kalibrierungsrisiko.
- Wahrscheinlich größere Hebel als die Modellklasse: bessere Features (opponent-adjusted Form, Rank-Buckets) und Stage-2-Kalibrierung, insbesondere eine Dixon-Coles-artige Draw-Korrektur, da unabhängige Poisson-Modelle Unentschieden und niedrige Ergebnisse systematisch unterschätzen.

Wichtig:

- `attack_defense_plus_mvp_form` ist ein **guter erster v2-Kandidat**, **kein fertiges v2**.
- Nächster Schritt vor weiteren Featureblöcken: Rolling Validation, um zu prüfen, ob der Vorteil über mehrere Zeiträume robust ist.


## Phase D: Rolling Validation (anchored expanding windows)

Datum: 2026-06-06

Experiment Run: `rolling_validation_v2_phase_d_2026_06_06`
Script: `src/wm_prediction/modeling/rolling_validation_poisson_v2.py`
Modell: `sklearn_poisson_regressor_alpha_0p03` (alpha fix 0.03, Features isoliert)

Ziel:

Prüfen, ob der Attack-/Defense-Vorteil aus Phase C robust über mehrere Zeiträume ist oder nur ein Artefakt des einzelnen `valid_2018_2021`-Fensters war.

Splits (anchored / expanding; Training strikt vor Validierung):

- `rolling_train_le_2010_valid_2011_2014`
- `rolling_train_le_2014_valid_2015_2018`
- `rolling_train_le_2018_valid_2019_2021`

Wichtig:

- Das finale `test_2022_plus`-Fenster wurde **bewusst nicht** angefasst und bleibt unberührter Holdout.
- Verglichene Sets: `current_mvp_all_18`, `attack_defense_only`, `attack_defense_plus_mvp_form`, `attack_defense_plus_points`.
- Ergebnisse in `experiments.model_evaluation_results` (3 Splits x 4 Sets x 6 Metriken = 72 rows).

Mittelwerte über die drei Rolling-Splits:

| feature_set | home_deviance | away_deviance | wdl_log_loss | wdl_brier |
|---|---|---|---|---|
| attack_defense_plus_points | 1.1727 | 1.1248 | 0.8473 | 0.4969 |
| attack_defense_plus_mvp_form | 1.1726 | 1.1247 | 0.8473 | 0.4969 |
| current_mvp_all_18 | 1.1906 | 1.1388 | 0.8488 | 0.4978 |
| attack_defense_only | 1.1734 | 1.1262 | 0.8502 | 0.4990 |

Wichtigste Befunde:

1. Der Attack-/Defense-Vorteil ist auf `home_deviance`/`away_deviance` **robust**: `current_mvp_all_18` ist in allen drei Fenstern das schlechteste Set auf der Deviance. Das ist kein Artefakt des einzelnen 2018-2021-Fensters mehr. Da die Tournament-Simulation direkt aus den Lambdas zieht, ist genau diese Metrik relevant. Der Effekt ist klein (~1-1.5 % relativ), aber gleichgerichtet.

2. Auf WDL Log-Loss ist der Gewinn dagegen nur marginal (Mittel 0.8473 vs. 0.8488). Allein auf WDL wäre der Block nicht überzeugend; der Wert liegt in der Deviance.

3. `attack_defense_only` ist auf WDL Log-Loss **das schwächste Set** (Mittel 0.8502, schlechter als die Baseline) und in zwei von drei Fenstern schlechter als `current_mvp_all_18`. Die in Phase C als "fachlich sauberste" eingeschätzte Variante ist empirisch die schwächste. Interpretation: Die Form-Diff-Features (points/goal-diff) tragen zur Kalibrierung der W/D/L-Wahrscheinlichkeiten bei, auch wenn sie die reine Tor-Deviance kaum bewegen. Sie können also nicht einfach gestrichen werden.

4. `attack_defense_plus_points` und `attack_defense_plus_mvp_form` sind praktisch identisch (Unterschiede in der 4. Nachkommastelle). Da `plus_mvp_form` nur zusätzlich die drei `goal_diff_per_match_diff`-Formfeatures enthält und diese keinen Mehrwert bringen (goal-diff ist aus for/against ableitbar, dieselbe Redundanz wie bei Cross-Differenzen), ist `attack_defense_plus_points` der **schlankere Kandidat bei gleicher Performance** (27 statt 30 Features).

Status:

- Phase D bestätigt Phase C robust, ersetzt v2 aber nicht.
- Aktueller stärkster, schlanker v2-Featureblock-Kandidat: `attack_defense_plus_points`.
- Weiterhin **kein** v2-End-to-End-Umbau.
- Vor einer v2-Entscheidung noch offen: opponent-adjusted Form, bessere historische FIFA-Stärkefeatures, Modellklassenvergleich.

## Phase E: opponent-adjusted Form / Strength-of-Schedule (getestet, für lineares Modell abgeschlossen)

Idee: Bestehende prevN-Formfeatures sind unadjusted. SOS gewichtet vergangene Spiele nach Gegnerstärke = FIFA-Rank-Perzentil INNERHALB des damaligen Semester-Snapshots (skalen-robust über den 2018er Methodikwechsel und wechselnde Teamzahl). 1.0 = stärkstes Team im Snapshot, 0.0 = schwächstes.

Wichtige Erkenntnisse aus der Bauphase:
- staging.fifa_rankings.team_id ist NICHT kompatibel mit team_match_rows.team_id (andere Domäne). Join MUSS über canonical_name / normalisierten Namen laufen. Ein team_id-Join trifft lautlos das falsche Team (Beispiel-Bug: opponent_team_id 78 = "Germany" in team_match_rows, aber 78 = "Syria" in fifa_rankings).
- Namens-Mapping war NICHT verloren, sondern lag bereits in 07_features_fifa_ranking.sql (CASE-Block: Cabo Verde/Cape Verde Islands -> Cape Verde, Chinese Taipei -> Taiwan, Curacao -> Curaçao, FYR Macedonia -> North Macedonia, Sao Tome e Principe -> São Tomé and Príncipe).
- Diese Normalisierung wurde aus dem inline-CTE in 07 in eine eigene, geteilte Tabelle features.fifa_rankings_normalized ausgelagert (eine Quelle der Wahrheit; 07 verhaltensneutral, exakt gleiche Output-Zahlen 98512/58609/39903). Phase-E-Perzentiltabelle liest daraus.
- Es gab nie ein echtes Fallback-Problem für fehlende Gegnerränge: nach dem Mapping-Fix hat im Trainings-Scope (1992+) praktisch jeder Gegner einen as-of-Rank. Eine erwogene Fallback-Konstante (0.5) wäre falsch gewesen.

Leakage-Schutz (doppelt): nur vergangene Spiele (prev.match_date < cur.match_date) UND Gegner-Rank as-of (snap.ranking_date < prev.match_date). Komparator '<' identisch zu 07.

Neue SQL: src/wm_prediction/features/20_features_opponent_strength.sql
Tabellen: features.fifa_rank_percentile_snapshot, features.team_opponent_strength_before_match (team-level, Key historical_match_id+team_id).
Spalten je Fenster prev5/prev10/prev365d: *_opp_strength_mean und *_opp_strength_coverage. Kein prev5y (über 5 Jahre mittelt Gegnerstärke sich weg, wenig Varianz). NULL-Policy: mean bleibt NULL wenn kein Fenster-Spiel einen Gegnerrank hat (konsistent mit 06). Coverage = Spiele-mit-Rank / Spiele-im-Fenster (nicht /N).
Coverage global ~0.96-0.97 im Scope; NULL-mean nur 169 (prev5) bis 820 (prev365d) von 57280 team-rows.

Experiment fester Split: experiment_opponent_strength_v2_phase_e_2026_06_07.py, run_id poisson_opponent_strength_v2_phase_e_2026_06_07, alpha=0.03. Option B: alle Sets auf SOS-vollständige Zeilen gefiltert (719 gedroppt, 27921 verbleibend), daher NICHT zeilengleich mit Phase B/C/D-Runs. Sets: current_mvp_all_18 (+/- sos, +/- sos_mean_only), attack_defense_plus_points (+/- sos, +/- sos_mean_only).

Coverage-als-Zeit-Proxy-Verdacht GEPRÜFT und WIDERLEGT: sos_mean_only liegt praktisch deckungsgleich mit sos (mean+coverage), Unterschiede 4. Nachkommastelle. -> Gewinn kommt vom mean-Stärkesignal, nicht von coverage. ENTSCHEIDUNG: coverage-Spalten bleiben in der Tabelle (Qualitätsmaß/NULL-Logik), gehen aber NICHT ins Modell. SOS-Block fürs Modell = 6 mean-Spalten (home/away x prev5/prev10/prev365d).

Rolling Validation (Hürde 2): rolling_validation_opponent_strength_phase_e_2026_06_07.py, run_id rolling_validation_sos_phase_e_2026_06_07. Drei Sets (current_mvp_all_18, attack_defense_plus_points, attack_defense_plus_points_plus_sos_mean_only) über die drei Phase-D-Fenster. Option-B-Drop gleichmäßig (511/572/630, je ~3.5%). test_2022_plus unberührt.
Mittel über Fenster: sos_mean_only home_dev 1.1571 / away_dev 1.1154 / log_loss 0.8483 / brier 0.4981; attack_defense_plus_points 1.1706/1.1206/0.8498/0.4988; baseline 1.1890/1.1350/0.8513/0.4996.

Befund: SOS-Gewinn lebt fast vollständig in der DEVIANCE (gewinnt in allen 3 Fenstern, gleichgerichtet), nicht im WDL. WDL nur in 2/3 Fenstern besser, in Fenster 1 praktisch gleich; fester Split hatte den WDL-Effekt leicht überzeichnet. Für dieses Projekt trotzdem relevant, weil die Monte-Carlo-Simulation direkt aus den Lambdas zieht (Deviance misst Lambda-Güte).

STATUS Phase E: SOS (mean-only, 6 Spalten) qualifiziert sich als v2-Featureblock-Bestandteil wegen robustem, coverage-unabhängigem, zu Attack/Defense inkrementellem Deviance-Gewinn. WDL-Gewinn klein und nicht in jedem Fenster (ehrlich dokumentiert). Phase E ist KEIN fertiges v2 und KEIN End-to-End-Umbau.

## Phase F (FIFA-Stärke): rank_pct als Rang-Level VERWORFEN (2026-06-07)

Befund: rank_pct ist innerhalb eines Snapshots affin im rohen Rang
(pct = 1 - (rank-1)/(max_rank-1)). Einziger Signalkanal gegenüber rohem
Rang = Variation von max_rank ueber Snapshots.

Messung (features.fifa_rank_percentile_snapshot, R2 rank_pct ~ rank_int):
  pre2000     R2 = 0.9669  (max_rank 149->200, hier lebt die Drift)
  2000_2010   R2 = 0.99953
  2011_plus   R2 = 0.99943  <- alle Eval-Fenster liegen hier

max_rank stabilisiert sich ab ~2000 in [196,211]; die snapshot-relative
Decoupling ist post-2000 praktisch tot. In allen Eval-Fenstern (fester
Split valid2018+/test2022+; Rolling 2011-2014/2015-2018/2019-2021) ist
rank_pct damit eine ~affine Transformation von rank_int -> fuer lineares
Modell nach StandardScaler informationsgleich, fuer Baeume invariant.

ENTSCHEIDUNG: rank_pct NICHT als eigenstaendiges Rang-Level-Feature
einbauen. Ein gemessener Gewinn waere Zeit-Confound-verdaechtig
(rank + rank_pct gemeinsam = Backdoor-Aera-Indikator), kein Staerkesignal.
rank_pct bleibt im SOS-Block (Phase E, ueber Gegner gemittelt = echter
zweiter Kanal, von diesem Befund unberuehrt).

Naechste Phase-F-Idee: Rang-Momentum (delta rank ueber letzte N Semester,
as-of-datiert) -- nicht aus aktuellem Rang ableitbar, daher potenziell
inkrementell. Noch nicht gebaut/getestet.

## Phase F neu: Rang-Momentum (2-Semester) -- Diagnose + verschaerfte Huerde (2026-06-07)

Idee: delta rank ueber 1 Jahr (improve = rank_1yr_ago - rank_now, positiv =
besser geworden). Differenz, kein Level -> keine Monotonie-Falle wie rank_pct.

Coverage-Diagnose (Snapshot-Raster, LEFT JOIN auf ranking_date - 1 Jahr):
  pre2000          85.0%   sd_improve 15.74  avg_abs 11.98
  2000_2018        99.6%   sd_improve 17.28  avg_abs 12.53
  2018_19_straddle 99.0%   sd_improve  7.58  avg_abs  5.49
  post2019         99.7%   sd_improve  6.32  avg_abs  4.45

Coverage post-2000 unkritisch (~99.6%).

2018-Methodikwechsel: KEIN kuenstlicher Delta-Spike im Straddle-Fenster
(Verdacht widerlegt). Im Gegenteil -- das neue Elo-basierte System erzeugt
deutlich STABILERE Semester-zu-Semester-Raenge (sd ~17 alt -> ~6 neu).

Folge: Momentum-Signal ist regime-abhaengig. Altes Regime (bis 2018, sd~17)
hat lernbare Trajektorie; neues Regime (post-2019, sd~6) ist traege, 1-Jahres-
Delta groesstenteils Rauschen um Null. Eval-Fenster sind gemischt: Rolling 1-2
(valid 2011-2014/2015-2018) = altes Regime; Rolling 3 (valid 2019-2021) +
fester Holdout (test 2022+) = neues Regime = das fuer WM 2026 relevante.

VERSCHAERFTE HUERDE (zusaetzlich zu Standard-2-Huerden): Momentum qualifiziert
sich nur, wenn der Deviance-Gewinn IM POST-2019-REGIME (Rolling-Fenster 3,
valid 2019-2021) sichtbar ist -- nicht nur im Mittel ueber alle Fenster. Gewinn
nur in alten Regime-Fenstern = fuer WM 2026 wertlos -> verwerfen.

## Phase F: FIFA-Rang-Momentum qualifiziert (2026-06-07)

Nach Verwerfen von `rank_pct` als eigenständigem Rang-Level-Feature wurde ein
echtes Differenzsignal getestet:

- `rank_now`: letzter FIFA-Ranking-Snapshot strikt vor `match_date`
- `rank_1yr_ago`: letzter FIFA-Ranking-Snapshot strikt vor `match_date - 1 year`
- `rank_improve_1yr = rank_1yr_ago - rank_now`
- positiv = Team ist im FIFA-Ranking gestiegen / besser geworden

Wichtige Korrektur vor dem Modelltest: Der naive As-of-Join konnte für Teams mit
Ranking-Lücken auf sehr alte Snapshots zurückfallen, z. B. 2019 auf 2006. Deshalb
wurde `21_features_rank_momentum.sql` mit einem Freshness-Gate repariert:

- beide Snapshots müssen höchstens 240 Tage alt sein
- sonst bleibt der jeweilige Rang bzw. das Momentum `NULL`
- Snapshot-Datum und Snapshot-Alter bleiben als Audit-Spalten erhalten

Coverage nach Gating im Match-Level-Modellscope:

- train_pre_2018: 94.7% beide Momentumwerte vorhanden
- valid_2018_2021: 99.2%
- test_2022_plus: 73.1%, wegen Rankingquelle aktuell nur bis 2024-07-01; daher
  2022+-Momentum-Test nur diagnostisch interpretieren

Fixed-Split-Test:
`poisson_rank_momentum_phase_f_2026_06_07`

Vergleich auf identischen SOS+Momentum-vollständigen Zeilen:

- `attack_defense_plus_sos_mean_only`
- `attack_defense_plus_sos_plus_rank_momentum`

Valid 2018-2021:

- home_deviance: 1.1896 -> 1.1790
- away_deviance: 1.1162 -> 1.1078
- wdl_log_loss: 0.8517 -> 0.8429
- wdl_brier: 0.5002 -> 0.4946

Rolling Validation:
`rolling_validation_rank_momentum_phase_f_2026_06_07`

Verschärfte Phase-F-Hürde erfüllt: Gewinn ist auch im post-2019-Fenster sichtbar.

Rolling 3, valid 2019-2021, Delta plus Momentum minus Baseline:

- home_deviance: -0.0101
- away_deviance: -0.0084
- wdl_log_loss: -0.0081
- wdl_brier: -0.0053

Auch über alle drei Rolling-Fenster verbessert Momentum WDL-Log-Loss und Brier
stabil. Home-Deviance ist in den alten Fenstern minimal schlechter bzw. neutral,
aber im post-2019-Fenster klar besser; Away-Deviance gewinnt in allen Fenstern.

Koeffizienten-Plausibilisierung:
Die Vorzeichen sind über Fixed- und Rolling-Trainingsfenster stabil plausibel:

- Home-Goal-Modell: `home_rank_improve_1yr` positiv
- Home-Goal-Modell: `away_rank_improve_1yr` negativ
- Away-Goal-Modell: `home_rank_improve_1yr` negativ
- Away-Goal-Modell: `away_rank_improve_1yr` positiv

Entscheidung:
FIFA-Rang-Momentum qualifiziert sich als weiterer v2-Kandidat-Block.

Modellfeatures:

- `home_rank_improve_1yr`
- `away_rank_improve_1yr`

Nicht aufnehmen:

- `rank_improve_1yr_diff`, weil es im linearen PoissonRegressor exakt redundant
  zu `home_rank_improve_1yr` und `away_rank_improve_1yr` ist

Wichtig:
Das ist noch kein fertiges v2-End-to-End-Modell. Der Block ist auf Match-Level
qualifiziert und wird später gemeinsam mit Attack/Defense und SOS in den
v2-Kandidaten aufgenommen.

## Phase H: Modellklassenvergleich - XGBoost als v2-Modellkandidat (2026-06-07)

Nach Abschluss der Featureblöcke Attack/Defense, SOS mean-only und FIFA-Rang-Momentum
wurde das v2-Kandidaten-Feature-Set zentral eingefroren:

- Datei: src/wm_prediction/modeling/v2_candidate_features.py
- Feature-Set: v2_candidate_35_features
- Feature Count: 35
- vollständige Modellzeilen nach SOS+Momentum-Drop: 25.799
- train_pre_2018: 19.554
- valid_2018_2021: 3.229
- test_2022_plus: 3.016

Wichtig:
Der 2022+-Holdout ist für Momentum aktuell nur eingeschränkt interpretierbar,
weil staging.fifa_rankings derzeit nur bis 2024-07-01 reicht. Für WM-2026-End-to-End
muss die Rankingquelle aktualisiert werden.

Verglichene Modellklassen:

- PoissonRegressor alpha=0.03, StandardScaler
- HistGradientBoostingRegressor loss=poisson
- XGBoost XGBRegressor objective=count:poisson

Initialer Fixed-Split-Run:
model_class_comparison_phase_h_2026_06_07

Rolling Validation:
rolling_validation_model_class_phase_h_2026_06_07

Kleines Rolling-Hyperparameter-Tuning:
tune_boosting_phase_h_2026_06_07

Bestes XGBoost-Setup nach Rolling-Tuning:

- objective=count:poisson
- eval_metric=poisson-nloglik
- n_estimators=800
- learning_rate=0.02
- max_depth=3
- min_child_weight=5
- subsample=0.90
- colsample_bytree=0.90
- reg_lambda=2.0
- reg_alpha=0.0
- tree_method=hist
- random_state=42
- n_jobs=4

Rolling-Tuning, Mittel über drei Rolling-Fenster:

- XGBoost best mean_goal_deviance: 1.11551
- HistGB best mean_goal_deviance: 1.11726
- Poisson reference mean_goal_deviance: 1.12730

WDL-Guardrails:

- XGBoost wdl_log_loss: 0.83103
- Poisson wdl_log_loss: 0.83471
- XGBoost wdl_brier: 0.48714
- Poisson wdl_brier: 0.48958

Finaler Fixed-Split-Kandidatenvergleich:
final_model_candidates_phase_h_2026_06_07

Valid 2018-2021, XGBoost best minus Poisson reference:

- mean_goal_deviance: -0.0088
- home_deviance: -0.0043
- away_deviance: -0.0134
- wdl_log_loss: -0.0002
- wdl_brier: +0.0006

Lambda-Sanity-Check:
XGBoost erzeugt keine problematischen extremen erwarteten Tore. Auf valid_2018_2021
liegt max home_lambda bei 8.39 und max away_lambda bei 7.01; nur eine home_lambda
liegt über 8. Auf test_2022_plus liegt max home_lambda bei 8.25 und max away_lambda
bei 5.28; ebenfalls nur eine home_lambda über 8.

Entscheidung:
Phase H qualifiziert XGBoost als aktuellen v2-Modellkandidaten.

Aktueller v2-Kandidat:

- Feature-Set: v2_candidate_35_features
- Modell: XGBoost count:poisson
- Parametrisierung: xgb_pois_lr002_n800_d3_child5_sub90_col90_l2_2

Wichtig:
Das ist noch nicht die produktive WM-2026-End-to-End-v2-Pipeline. Als nächstes
muss Phase J die v2-Prediction-/Simulation-Pipeline bauen und dabei die FIFA-Ranking-
Quelle für 2026 aktualisieren oder das Momentum für 2026 sauber behandeln.

## Phase J Readiness: FIFA-Ranking-Blocker für produktives v2 End-to-End (2026-06-07)

Beim Start von Phase J wurde die bestehende MVP-2026-Prediction-Pipeline auditiert.

Befund MVP-v1:
`features.match_prediction_mvp_v1` und `features.team_prediction_snapshot_mvp_v1`
verwenden für WM-2026-Fixtures den letzten historischen FIFA-Ranking-Snapshot aus
`staging.fifa_rankings`.

Aktueller Stand der Rankingquellen:

- `staging.fifa_rankings`: 1992-07-01 bis 2024-07-01
- `staging.current_fifa_rankings`: aktueller Snapshot vom 2026-06-04
- fehlend: echter historischer Snapshot um 2025-06 für 1-Jahres-Momentum

Damit waren die MVP-v1-2026-FIFA-Ranks ursprünglich 710 Tage alt
(2024-07-01 -> 2026-06-11). Das ist kein Leakage, aber stale data und für
eine ernsthafte WM-2026-Prognose nicht akzeptabel.

Current-FIFA-Coverage:
`staging.current_fifa_rankings` deckt nach zentralem Alias-Fix alle 48 WM-Teams ab.
Dafür wurden in `staging.team_name_aliases` ergänzt:

- `Cabo Verde` -> `Cape Verde`
- der fehlerhaft ingestierte JSON-Text mit `Côte d'Ivoire` -> `Ivory Coast`

Damit kann `rank_now` für 2026 sauber aus `staging.current_fifa_rankings`
verwendet werden.

Offener Blocker:
Das v2-Kandidatenmodell nutzt `home_rank_improve_1yr` und `away_rank_improve_1yr`.
Für WM-2026 braucht dieses Feature einen echten Rang ungefähr ein Jahr vor dem
Turnierstart, also um 2025-06. Dieser Snapshot ist aktuell nicht vorhanden.
`previous_fifa_rank` aus `staging.current_fifa_rankings` wird NICHT verwendet,
weil es vermutlich nur den vorherigen FIFA-Release beschreibt und nicht semantisch
dem trainierten 1-Jahres-Momentum entspricht.

Entscheidung:
Produktives v2 End-to-End mit allen 35 Features ist blockiert, bis ein echter
2025er FIFA-Ranking-Snapshot verfügbar ist.

Erlaubter nächster Schritt:
Ein technischer v2-Dry-Run ohne Momentum ist möglich:

- 33 Features
- XGBoost count:poisson aus Phase H
- aktuelle 2026-FIFA-Ranks aus `staging.current_fifa_rankings`
- klar als `v2_technical_33_no_momentum` kennzeichnen
- nicht als finale WM-2026-Prognose interpretieren

## Phase J.1: v2 Technical Dry Run mit 33 Features ohne Momentum (2026-06-07)

Nach Phase H war der fachliche v2-Kandidat:

- Feature-Set: `v2_candidate_35_features`
- Modell: XGBoost `count:poisson`
- Momentum-Features:
  - `home_rank_improve_1yr`
  - `away_rank_improve_1yr`

Beim Start von Phase J wurde aber festgestellt:

- `staging.fifa_rankings` endet bei `2024-07-01`
- `staging.current_fifa_rankings` enthält einen aktuellen Snapshot vom `2026-06-04`
- ein echter historischer FIFA-Ranking-Snapshot rund um `2025-06` fehlt
- damit kann `rank_improve_1yr` für WM 2026 aktuell nicht korrekt berechnet werden

Entscheidung:
Produktives v2 End-to-End mit allen 35 Features bleibt blockiert, bis der echte 2025er Snapshot vorhanden ist.

Technischer Übergang:
Es wurde ein klar gelabelter Dry Run gebaut:

- Name: `v2_technical_33_no_momentum`
- Modell: `xgboost_v2_technical_33_no_momentum`
- Feature-Set: 33 Features = v2-Kandidat ohne Momentum
- Nicht als finale WM-2026-Prognose interpretieren

Zentrale Feature-Ergänzung:

- Datei: `src/wm_prediction/modeling/v2_candidate_features.py`
- neue Konstanten:
  - `V2_TECHNICAL_33_NO_MOMENTUM_FEATURES`
  - `V2_TECHNICAL_33_REQUIRED_JOINED_FEATURES`

Current-FIFA-Fix:
`staging.current_fifa_rankings` deckte zunächst nur 46/48 WM-Teams ab. Die fehlenden Teams waren Alias-/Ingestion-Probleme:

- `Cabo Verde` -> `Cape Verde`
- fehlerhaft ingestierter JSON-Text mit `Côte d'Ivoire` -> `Ivory Coast`

Diese Aliases wurden zentral in `src/wm_prediction/db/staging.sql` ergänzt und in der laufenden DB upserted. Danach matcht `staging.current_fifa_rankings` 48/48 WM-Teams.

Neue Phase-J.1-Input-Tabellen:

- `features.match_prediction_v2_technical_33`
- `features.team_prediction_snapshot_v2_technical_33`

Audit `features.match_prediction_v2_technical_33`:

- 72 Fixture-Zeilen
- Match-Dates: `2026-06-11` bis `2026-06-27`
- FIFA-Ranking-Datum: `2026-06-04`
- FIFA-Ranking-Age: 7 bis 23 Tage
- keine NULLs in den 33 Modellfeatures
- SOS-Coverage vollständig

Audit `features.team_prediction_snapshot_v2_technical_33`:

- 48 Teams
- Prediction-Date: `2026-06-11`
- FIFA-Ranking-Datum: `2026-06-04`
- FIFA-Ranking-Age: 7 Tage
- keine FIFA-Rank-NULLs
- keine SOS-NULLs

Historischer Vergleich 33 vs. 35 Features auf identischen 35er Complete Rows:
Der Momentum-Verzicht kostet spürbar Performance.

Valid 2018-2021, 33 minus 35:

- mean_goal_deviance: +0.0090
- home_deviance: +0.0088
- away_deviance: +0.0091
- wdl_log_loss: +0.0109
- wdl_brier: +0.0071

Test 2022+, 33 minus 35:

- mean_goal_deviance: +0.0127
- home_deviance: +0.0108
- away_deviance: +0.0146
- wdl_log_loss: +0.0132
- wdl_brier: +0.0087

Folge:
Der 33er Lauf ist fachlich nur ein technischer Dry Run. Momentum ist wichtig und soll wieder aktiviert werden, sobald der 2025er Ranking-Snapshot verfügbar ist.

Neue Prediction-/Simulation-Skripte:

- `src/wm_prediction/modeling/predict_world_cup_fixtures_v2_technical_33.py`
- `src/wm_prediction/modeling/predict_knockout_matchup_v2_technical_33.py`
- `src/wm_prediction/modeling/simulate_group_stage_v2_technical_33.py`
- `src/wm_prediction/modeling/simulate_tournament_v2_technical_33.py`

Neue Output-Tabellen:

- `features.match_predictions_v2_technical_33`
- `features.group_stage_simulation_summary_v2_technical_33`
- `features.tournament_simulation_summary_v2_technical_33`

Audit `features.match_predictions_v2_technical_33`:

- 72 Predictions
- alle mit `is_technical_dry_run = true`
- Model: `xgboost_v2_technical_33_no_momentum`
- Feature-Set: `v2_technical_33_no_momentum`
- Probability sums exakt 1.0
- Lambda-Range plausibel:
  - home: 0.6840 bis 2.7417
  - away: 0.4779 bis 2.5328

Gruppenphasen-Simulation:

- Tabelle: `features.group_stage_simulation_summary_v2_technical_33`
- 1000 Simulationen, Seed 42
- 48 Teams
- `sum_p_advance = 32`
- `sum_p_rank_1 = 12`
- `sum_p_rank_2 = 12`
- alle Zeilen als Technical Dry Run markiert

Full-Tournament-Simulation:

- Skript: `simulate_tournament_v2_technical_33.py`
- nutzt:
  - `load_match_predictions` aus `simulate_group_stage_v2_technical_33`
  - `KnockoutMatchupPredictorV2Technical33`
- Output-Tabelle: `features.tournament_simulation_summary_v2_technical_33`
- erster DB-Write musste gepatcht werden, weil die Tabelle beim ersten Lauf noch nicht existierte
- 100 Simulationen mit Seed 42 liefen anschließend erfolgreich durch

Wichtig für Fortsetzung:
Als nächstes sollte die Full-Tournament-Tabelle auditiert und danach das Tournament-Script performanter gemacht werden, bevor 1000 oder 10000 Full-Tournament-Simulationen laufen. Der 33er Dry Run bleibt bewusst nicht-final.

## BUG-FUND: Knockout-Bracket nutzte bedeutungslose Gruppenlabels (2026-06-07)

### Symptom
Beim Audit der v2-technical-33-Turniersimulation fiel auf: Die Gruppen
enthalten die richtigen 48 Teams in den korrekten Vierergruppen, aber unsere
Gruppenbuchstaben stimmen NICHT mit der offiziellen FIFA-Auslosung ueberein
(unser "A" ist nicht das offizielle "A").

### Ursache (in 14_features_world_cup_groups_mvp_v1.sql)
Die Tabelle world_cup_groups_mvp_v1 rekonstruiert die Gruppen korrekt aus den
Fixtures (wer-gegen-wen -> Vierergruppe). ABER die Buchstabenvergabe erfolgte
ueber ROW_NUMBER() OVER (ORDER BY group_teams::text), also ALPHABETISCH nach der
konkatenierten Teamnamensliste. "Internes A" = alphabetisch erste Gruppe
(beginnt mit Algeria), voellig ohne Bezug zur offiziellen Auslosung.
official_group_label wurde in der Quelle nie befuellt (NULL::text); die in der
laufenden DB sichtbaren A/B/C-Werte stammten aus spaeteren manuellen UPDATEs und
waren ebenfalls nur diese alphabetische Reihenfolge, nicht die offizielle.

### Warum es lange unsichtbar blieb (leise Fehlerklasse)
Die Gruppenphase rechnet rein ueber Team-Mengen (build_group_table nutzt
isin(teams)); das Label geht in keine Berechnung ein. Daher:
- Gruppenphasen-Ergebnisse (p_advance_group, p_rank_1/2) sind KORREKT.
- Alle Wahrscheinlichkeits-Summen blieben exakt (32/16/8/4/2/1/1), weil nur die
  Slot-ANZAHL geprueft wurde, nicht die konkreten Paarungen.
Der Fehler lebt ausschliesslich in der K.o.-Phase: world_cup_round32_slots_mvp_v1
ist nach dem OFFIZIELLEN FIFA-Schema verdrahtet (1A vs 3CEFHI etc.,
source=fifa_schedule_text_manual). simulate_tournament_*.py loest diese
offiziellen Buchstaben gegen group_letter() auf, das aus dem INTERNEN
(alphabetischen) Label kommt -> offizieller Buchstabe trifft falsches Quartett
-> ALLE Paarungen ab Round of 32 falsch verdrahtet.

### Tragweite
Betrifft BEIDE Pipelines, da beide das Turniergeruest von MVP-v1 erben
(load_groups + simulate_group_stage_mvp aus simulate_tournament_*.py):
- MVP-v1 Full-Tournament-Simulation
- v2_technical_33 Full-Tournament-Simulation
Konkret falsch (neu zu rechnen nach Fix): p_reach_round_of_16, p_reach_quarter_final,
p_reach_semi_final, p_final, p_title, p_third_place und das gesamte
knockout_bracket. KORREKT und unberuehrt: alle Gruppenphasen-Outputs und die
zugrundeliegenden Match-Level-Lambdas/Predictions (das Modell selbst ist nicht
betroffen).

### Rueckwirkende Bedeutung fuer MVP-v1
Der MVP-v1 1000er-Run (mvp_v1_seed_42_n_1000) hat korrekte Gruppenphasen-, aber
falsch verdrahtete K.o.-Statistiken. Die berichteten Titel-/Weiterkommens-
wahrscheinlichkeiten ab R32 sind nicht interpretierbar und muessen nach dem Fix
neu simuliert werden. Das Modelltraining, die Feature-Pipeline, die Metriken
(Deviance/LogLoss/Brier auf Match-Level) und alle Phase-A-bis-J.1-Modellbefunde
sind NICHT betroffen -- der Bug sitzt rein in der Turnier-Bracket-Aufloesung,
nicht im Modell.

### Fix (Variante a)
14_features_world_cup_groups_mvp_v1.sql wird umgebaut:
- Fixture-Rekonstruktion der Quartette BLEIBT (unabhaengige Quelle der
  Zusammensetzung).
- Offizielle Auslosung als explizite 48-Zeilen-VALUES-Liste
  (team_name -> official_group_label, Namen in DB-Schreibweise).
- official_group_label wird per Join aus dieser Liste gesetzt.
- HARTE Konsistenz-Assertion: fuer jedes Team muessen seine drei
  Fixture-Gegner denselben offiziellen Buchstaben tragen wie es selbst, sonst
  Abbruch (faengt Tippfehler in VALUES UND Alias-Bugs in den Fixtures).
- simulate_tournament_*.py: group_letter muss aus official_group_label gespeist
  werden statt aus dem internen alphabetischen Label.

Offizielle Auslosung (Quelle: FIFA / Wikipedia 2026 FIFA World Cup, Stand
2026-06-07), Namen in DB-Schreibweise:
A: Mexico, South Africa, South Korea, Czech Republic
B: Canada, Bosnia and Herzegovina, Qatar, Switzerland
C: Brazil, Morocco, Haiti, Scotland
D: United States, Paraguay, Australia, Turkey
E: Germany, Curacao, Ivory Coast, Ecuador
F: Netherlands, Japan, Sweden, Tunisia
G: Belgium, Egypt, Iran, New Zealand
H: Spain, Cape Verde, Saudi Arabia, Uruguay
I: France, Senegal, Iraq, Norway
J: Argentina, Algeria, Austria, Jordan
K: Portugal, DR Congo, Uzbekistan, Colombia
L: England, Croatia, Ghana, Panama

### Fix verifiziert (2026-06-07)
load_groups() in simulate_group_stage_mvp.py liest jetzt official_group_label
und keyt das Gruppen-Dict danach (A..L). group_letter() ist damit Pass-through.
Wirkt auf BEIDE Pipelines (geteilte Funktion). Smoke-Test bestaetigt: Key "A" =
{Mexico, South Africa, South Korea, Czech Republic}, Key "E" = {Germany,
Curacao, Ivory Coast, Ecuador} -- entspricht offizieller Auslosung.

100er-Re-Run (xgboost_v2_technical_33_no_momentum_seed_42_to_141_n_100) vs.
gesicherte buggy-Werte zeigt grosse, gerichtete, plausible K.o.-Verschiebungen
(struktureller Fix-Effekt, ueber Monte-Carlo-Rauschen bei n=100):
  Colombia  p_reach_round_of_16  0.57 -> 0.34  (-0.23; Phantom-Vorteil weg)
  Argentina p_title              0.10 -> 0.16  (+0.06)
  England   p_title              0.07 -> 0.13  (+0.06)
  Portugal  p_title              0.02 -> 0.07  (+0.05)
  Brazil    p_title              0.11 -> 0.06  (-0.05)
  Spain     p_title              0.13 -> 0.08  (-0.05)
Struktur-Summen weiter exakt (32/16/8/4/2/1/1). Gruppenphasen-Outputs
unveraendert (label-agnostisch, waren schon korrekt).

OFFENE TODOs aus diesem Fix:
- MVP-v1 Full-Tournament (mvp_v1_seed_42_n_1000) muss ebenfalls neu simuliert
  werden (gleicher Bug, gleiche geteilte load_groups; Fix greift, aber Run ist
  noch alt/buggy in der DB).
- Technische Schuld: group_letter + resolve_*_slot sind in simulate_tournament_mvp.py
  und simulate_tournament_v2_technical_33.py dupliziert. Bei Phase J (v2 end-to-end)
  in ein geteiltes Modul ziehen (eine Quelle der Wahrheit).

### MVP-v1 1000er ebenfalls neu simuliert + verifiziert (2026-06-07)
mvp_v1_seed_42_n_1000 mit --simulation-run-id neu geschrieben (ersetzt buggy
Run via DELETE-by-run_id). Buggy Test-Runs mvp_v1_seed_42_n_50 und
smoke_seed_42_n_5 geloescht. Struktur-Summen exakt (32/16/8/4/2/1/1).

Vorher/Nachher (n=1000, Rauschen klein): Fix-Effekt sitzt erwartungsgemaess in
der ERSTEN K.o.-Runde (p_reach_round_of_16), wo die falschen R32-Paarungen
direkt wirkten -- nicht primaer in p_title (ueber Runden verduennt):
  Morocco  r16  0.570 -> 0.512  (-0.058)
  Spain    r16  0.619 -> 0.561  (-0.058)
  Brazil   r16  0.490 -> 0.437  (-0.053)
  Iran     r16  0.417 -> 0.484  (+0.067)
  USA      r16  0.440 -> 0.473  (+0.033)
d_title bleibt klein (<=0.012), weil n=1000 das Rauschen rausnimmt und das
Titelsignal von den Topteams dominiert wird, deren Pfade sich weniger
verschoben. (Der v2-100er-Diff sah groessere d_title-Spruenge, war aber
rauschueberlagert; der MVP-1000er-Diff ist die ehrlichere Messung.)
Bugfix damit in BEIDEN Pipelines end-to-end bestaetigt.

## Phase J.1: Performance-Optimierung Full-Tournament-Simulation (2026-06-07)

Problem: simulate_tournament_v2_technical_33 war fuer n=1000 zu langsam
(~3.3 Min extrapoliert). Timing-Analyse (n=100): 19.6s, fast komplett user-CPU
(18.8s) -> CPU-gebunden, NICHT DB-I/O.

Zwei verhaltensneutrale Optimierungen (jeweils per Seed-42-100er bitgenau gegen
den Vor-Stand verifiziert, identische Wahrscheinlichkeiten):
1. Invariante DB-Reads aus der Monte-Carlo-Schleife gezogen: matches, groups,
   bracket werden in main einmal geladen und durch simulate_tournament /
   simulate_group_stage als optionale Parameter durchgereicht (Defaults =
   selbst laden, Rueckwaertskompatibilitaet). Vorher 3 Reads pro Simulation.
2. KnockoutMatchupPredictorV2Technical33: O(1) Team-Lookup-Dict statt
   DataFrame-Scan; Lambda-Cache pro GEORDNETEM (home, away)-Matchup (nicht
   symmetrisch). Cache lebt ueber den ganzen Run (Predictor wird in main einmal
   gebaut) -> wiederholte Matchups ueber Sims werden nur einmal gerechnet
   (spart make_matchup_features + 2 XGBoost-Inferenzen pro Hit).

Ergebnis: n=100 19.6s -> 11.4s; n=1000 ~196s(extrapoliert) -> 46.5s (~4x).
Restlicher 100er-Sockel ist v.a. das einmalige XGBoost-Training im
Predictor-__init__ (Fixkost, skaliert nicht mit n). n=10000 waere ~7-8 Min;
bewusst NICHT weiter optimiert (Dry-Run-Status, Aufwand/Nutzen).

Finaler Dry-Run-Lauf in DB: xgboost_v2_technical_33_no_momentum_seed_42_to_1041_n_1000
(1000 Sims, Summen exakt 32/16/8/4/2/1/1). Alter 100er-Run entfernt.
WICHTIG: weiterhin technischer Dry Run (33 Features, Momentum fehlt) -- NICHT
als finale WM-2026-Prognose verwenden. v2_full_35 erst mit 2025er Rankings.

## Frontend: Modellauswahl MVP-v1 vs. v2-technical-33 (2026-06-07)
app/Home.py erweitert: MODELS-Registry (Dict) haelt pro Modell die drei Tabellen
(match_predictions, group_stage_summary, tournament_summary) + is_dry_run-Flag.
Selectbox oben schaltet alle drei Bloecke um (Match Predictions, Gruppenphase,
Full-Tournament). v2 = "v2 Technical 33 (Dry Run, XGBoost)" mit prominenter
Dry-Run-Warnung (33 Features, Momentum fehlt, keine finale Prognose). Default MVP v1.
Tabellennamen aus Whitelist (Dict), nicht aus User-Input -> kein Injection-Risiko.
Schema-Unterschied beachtet: v2-tournament-Summary hat KEIN created_at ->
load_tournament_runs sortiert nach simulation_run_id DESC statt created_at.

## Phase J.2: Echte 2025/2026-FIFA-Rankings und v2_full_35 End-to-End-Basis (2026-06-09)

Blocker aus Phase J.1 ist geloest: echte FIFA-Ranking-Snapshots von 2024-07-18
bis 2026-06-10 wurden in Raw/Staging ergaenzt. Damit ist `rank_improve_1yr`
fuer WM-2026-Fixtures nicht mehr kuenstlich/technisch blockiert.

Neue Raw-Quelle:
- `data/raw/atheels_datasets/fifa_mens_rankings_2024_07_to_2026_06.csv`
- geladen nach `raw.atheels_datasets_fifa_mens_rankings`
- 2322 Raw-Zeilen, originalgetreu inkl. 11 gescrapter Werbe-/JS-Muellzeilen
- Staging filtert diese Muellzeilen ueber `country_code !~ '^[A-Z]{3}$'`

Staging-Integration:
- `src/wm_prediction/db/fifa_ranking.sql`
- neuer idempotenter Append-Block: DELETE/INSERT fuer `ranking_date >= '2024-07-18'`
- 2311 gueltige Ranking-Zeilen
- echtes `ranking_date` ist der fachliche Snapshot-Schluessel
- `ranking_year` und `ranking_semester` bleiben nur grobe Etiketten
- as-of-Joins duerfen NICHT ueber `team_id` laufen, sondern ueber normalisierte/canonical Namen

Drei stille Normalisierungsbugs wurden in `fifa_rankings_normalized` behoben:
- `Cabo Verde` und `Cape Verde Islands` werden auf `Cape Verde` vereinheitlicht
- `The Gambia` wird auf `Gambia` vereinheitlicht
- `Brunei Darussalam` wird auf `Brunei` vereinheitlicht

Wichtiger Fix in SOS:
- `20_features_opponent_strength.sql`
- `fifa_rank_percentile_snapshot` partitioniert jetzt nach `ranking_date`
  statt nach `(ranking_year, ranking_semester)`
- fuer Altdaten verhaltensneutral verifiziert, aber fuer mehrere Releases pro
  Halbjahr fachlich korrekt

Neu gebaute Feature-Kette:
- `features.fifa_rankings_normalized`
- `features.team_fifa_ranking_before_match`
- `features.team_rank_momentum_before_match`
- `features.model_input_mvp_v1`
- `features.match_prediction_v2_full_35`
- `features.team_prediction_snapshot_v2_full_35`

Plausibilitaetsanker nach Rebuild:
- Spanien-Rang in WM-2026-Fixtures kommt aus dem echten 2026-06-10-Snapshot
- Spanien: Rang 2, Momentum +1
- Argentinien: Rang 1, Momentum 0
- Cape Verde: Rang 67 vorhanden
- `features.match_prediction_v2_full_35`: 72 Fixtures, 0 NULLs in Rang/Momentum/SOS
- `features.team_prediction_snapshot_v2_full_35`: 48 Teams, 0 NULLs
- `features.match_predictions_v2_full_35`: 72 Predictions, Wahrscheinlichkeiten summieren auf 1.0

Modellentscheidung:
`v2_full_35` ist jetzt der echte v2-End-to-End-Kandidat, nicht mehr ein Dry Run.
Feature-Set:
- 35 Features aus `V2_CANDIDATE_FEATURES`
- Modell: XGBoost via `make_xgb_best()`
- `MODEL_NAME = xgboost_v2_full_35`
- `FEATURE_SET_NAME = v2_full_35`

Fester Split:
Run `final_model_candidates_v2_full_35_fresh_fifa_2026_06_09` reproduziert den
Phase-H-Befund. Gegen Poisson gewinnt XGBoost auf Validierung vor allem bei
Goal-Deviance:
- mean_goal_deviance: -0.0088
- home_deviance: -0.0050
- away_deviance: -0.0126
- wdl_log_loss: 0.0000
- wdl_brier: +0.0006

Ehrliche Einschraenkung:
Auf `test_2022_plus` gewinnt v2_full_35 knapp NICHT gegen Poisson
(1.1330 vs. 1.1318 mean_goal_deviance). Dieser Holdout wurde nicht fuer die
Entscheidung optimiert; die Entscheidung stuetzt sich auf Validierung plus
Rolling Robustheit.

Rolling Validation:
Run `rolling_validation_v2_full_35_fresh_fifa_2026_06_09` bestaetigt den
XGBoost-Vorteil ueber Zeit. Die Goal-Deviance-Gewinne sind in allen drei
Fenstern gleichgerichtet negativ; WDL-Metriken sind diesmal ebenfalls in allen
drei Fenstern negativ. Die verschaerfte post-2019-Huerde wurde erfuellt.

Fazit:
`v2_full_35` ist durch beide Huerden. Der Vorteil ist robust, primaer in der
Goal-Deviance sichtbar und damit fuer die Poisson-basierte Turniersimulation
projektrelevant. `v2_technical_33` bleibt als technischer Dry Run dokumentiert,
ist aber nicht die finale WM-2026-Prognose.

Aktueller End-to-End-Stand:
- `predict_world_cup_fixtures_v2_full_35.py` existiert
- `features.match_predictions_v2_full_35` ist geschrieben und plausibilisiert
- noch offen: drei Simulation-Pendants fuer `v2_full_35`,
  10k Full-Tournament-Simulation und Streamlit-Dropdown als dritter Kandidat
  ohne Dry-Run-Warnung

## Phase J.3: v2_full_35 Simulation + Frontend-Anbindung abgeschlossen (2026-06-09)

Die v2_full_35-End-to-End-Simulation ist jetzt gebaut und verifiziert. Das betrifft
gezielt den echten v2_full_35-Kandidaten, nicht eine generelle Aussage zu allen
Modellen oder zukuenftigen Modellversionen.

Neu angelegte Modeling-Skripte:

- src/wm_prediction/modeling/simulate_group_stage_v2_full_35.py
- src/wm_prediction/modeling/predict_knockout_matchup_v2_full_35.py
- src/wm_prediction/modeling/simulate_tournament_v2_full_35.py

Ableitung:

- group_stage wurde strukturgleich aus v2_technical_33 abgeleitet, aber mit
  features.match_predictions_v2_full_35 als Quelle und ohne Dry-Run-Flag.
- knockout wurde auf V2_CANDIDATE_FEATURES mit allen 35 Features umgestellt,
  inklusive rank_improve_1yr fuer home/away.
- tournament wurde aus dem bereits optimierten v2_technical_33-Skript abgeleitet.

Wichtige uebernommene Eigenschaften:

- offizielle Gruppenlabels bleiben ueber load_groups() erhalten
- Round-of-32-Bracket nutzt den vorherigen Bracket-Label-Fix
- Drittplatzierten-Slots werden per Backtracking aufloesbar zugewiesen
- invariante DB-Reads fuer matches/groups/bracket liegen ausserhalb der
  Monte-Carlo-Schleife
- Knockout-Predictor wird einmal pro Run gebaut
- O(1)-Team-Lookup und Lambda-Cache pro geordnetem (home, away)-Matchup sind im
  v2_full_35-Knockout-Predictor enthalten

Verifikation:

- Group-Stage-Smoke ohne DB-Write: sum_p_advance = 32
- Group-Stage-DB-Write mit 1000 Simulationen: 48 Rows, sum_p_advance = 32,
  sum_p_rank_1 = 12, sum_p_rank_2 = 12, kein Dry Run
- Knockout-Smokes:
  - Spain vs Cape Verde: Spain klarer Favorit, advance_prob_sum = 1.0
  - Argentina vs Jordan: Argentina klarer Favorit, advance_prob_sum = 1.0
- Full-Tournament Single-Smoke: 32 qualifizierte Teams, 32 Knockout-Matches,
  Champion und Third Place erzeugt
- Full-Tournament Multi-Smoke: Summen exakt 32/16/8/4/2/1/1
- 100er DB-Smoke: Run xgboost_v2_full_35_seed_42_to_141_n_100_smoke, Summen exakt
- finaler 10k-Run:
  xgboost_v2_full_35_seed_42_to_10041_n_10000

Finaler 10k-Run in DB:

- Tabelle: features.tournament_simulation_summary_v2_full_35
- Rows fuer finalen Run: 48
- Modell: xgboost_v2_full_35
- Feature-Set: v2_full_35
- is_technical_dry_run = false
- n_simulations = 10000
- seed_start = 42
- seed_end = 10041
- Summen exakt:
  - p_advance_group = 32
  - p_reach_round_of_16 = 16
  - p_reach_quarter_final = 8
  - p_reach_semi_final = 4
  - p_final = 2
  - p_title = 1
  - p_third_place = 1

Top-Titelwahrscheinlichkeiten im 10k-Run:

- Argentina: 0.1427
- Spain: 0.1109
- France: 0.0885
- England: 0.0818
- Portugal: 0.0710
- Brazil: 0.0644
- Morocco: 0.0594

Frontend:

app/Home.py wurde fuer v2_full_35 erweitert. Der neue Dropdown-Kandidat heisst
"v2 Full 35 (XGBoost)" und nutzt:

- features.match_predictions_v2_full_35
- features.group_stage_simulation_summary_v2_full_35
- features.tournament_simulation_summary_v2_full_35

Wichtig: v2_full_35 hat is_dry_run = False und bekommt deshalb keine Dry-Run-
Warnung im Frontend. Die Dry-Run-Warnung bleibt nur fuer den v2 Technical 33-
Kandidaten aktiv.

Frontend-Readiness:

- match_predictions_v2_full_35: 72 Rows
- group_stage_simulation_summary_v2_full_35: 48 Rows
- tournament_simulation_summary_v2_full_35: 96 Rows insgesamt
  - 100er-Smoke
  - 10k-Final-Run

## Phase J.4: Praesentations-Frontend + Scenario Mode (2026-06-09)

Das Streamlit-Frontend wurde von einem eher technischen Status-Dashboard zu einem
praesentationsfaehigen Forecast-Dashboard umgebaut. Ziel war bewusst kein
ueberladenes Spezialdashboard, sondern eine saubere, serioese und gut lesbare App
fuer Uni-Praesentation und Projekt-Demo.

Wichtig: Die bestehende Modellvergleichslogik bleibt erhalten. Das Frontend
unterstuetzt weiterhin alle drei Kandidaten:

- MVP v1 (Poisson)
- v2 Technical 33 (Dry Run, XGBoost)
- v2 Full 35 (XGBoost)

Die Sidebar steuert weiterhin Modell und Simulation Run. v2 Technical 33 behaelt
die Dry-Run-Warnung. v2 Full 35 ist die echte Prognose und wird ohne Dry-Run-
Warnung angezeigt.

Neue Frontend-Struktur in `app/Home.py`:

- Overview
- Match Explorer
- Groups
- Scenario Mode
- Team Path
- Full Results
- Method / Data

Overview:

- Landingpage-artiger Einstieg mit ruhigem Card-Design
- vier KPI-Cards:
  - Titel-Favorit
  - hoechste Finalwahrscheinlichkeit
  - Dark Horse
  - offenste Gruppe
- Top-10-Balkencharts fuer Titel- und Finalchancen
- kompakter Modellvergleich zwischen den verfuegbaren Kandidaten

Match Explorer:

- Bugfix: Teamauswahl ist jetzt richtungsunabhaengig.
- Vorher wurden nur Spiele angezeigt, in denen das gewaehlte Team `home_team_name`
  war.
- Jetzt zeigt z.B. Germany alle drei Gruppengegner, auch wenn ein Fixture als
  `Ecuador vs Germany` gespeichert ist.
- Anzeige:
  - Expected Goals fuer beide Teams
  - W/D/L-Wahrscheinlichkeiten
  - Balkenchart
  - kurzer Interpretationstext

Groups:

- zeigt immer nur eine ausgewaehlte Gruppe
- Summary-Cards fuer:
  - wahrscheinlichster Gruppensieger
  - engster Kampf um Top 2
  - hoechste Weiterkommenswahrscheinlichkeit
  - niedrigste Weiterkommenswahrscheinlichkeit
- formatierte Gruppentabelle und Weiterkommens-Balkenchart

Team Path:

- einfache Pfadansicht pro Team statt komplexem Bracket
- zeigt Wahrscheinlichkeiten fuer:
  - Gruppenphase ueberstehen
  - Viertelfinale erreichen
  - Halbfinale erreichen
  - Finale erreichen
  - Weltmeister werden
  - Spiel um Platz 3 gewinnen

Full Results:

- vollstaendige Ergebnistabelle
- nach Titelchance vorsortiert
- Suchfeld fuer Teams
- Top 3 mit Medaillen markiert
- nur relevante Spalten, alle Prozentwerte einheitlich formatiert

Method / Data:

- technische Details sind nicht mehr dominant auf der Startseite
- kurze Pipeline-Erklaerung:
  Historische Spiele -> Feature Engineering -> Match-Wahrscheinlichkeiten ->
  Turniersimulation -> Ergebniswahrscheinlichkeiten
- technische Checks liegen im Expander

Neu: Scenario Mode

Es wurde ein interaktiver Scenario Mode fuer v2 Full 35 ergaenzt. Neue Datei:

- `src/wm_prediction/modeling/scenario_tournament_v2_full_35.py`

Funktion:

- User setzt manuell die Platzierungen 1-4 pro Gruppe.
- Daraus wird eine manuelle Gruppentabelle gebaut.
- Gruppensieger, Zweite und acht beste Drittplatzierte werden bestimmt.
- Die bestehende offizielle Round-of-32-/Drittplatzierten-Slot-Logik wird
  wiederverwendet.
- Die K.o.-Phase wird mit dem bestehenden v2_full_35-Knockout-Predictor simuliert.
- Ergebnisse werden nur im Frontend berechnet und NICHT in die DB geschrieben.

Wichtige methodische Einschraenkung:

Scenario Mode veraendert nur den Turnierpfad, nicht die Teamstaerke. Die
manuellen Gruppenplatzierungen aktualisieren keine Features wie Form der letzten
Spiele, Rang-Momentum, SOS oder Attack/Defense-Form. Das ist bewusst so, um
keine ungepruefte Heuristik in das validierte Modell einzubauen.

Da im Scenario Mode keine exakten Gruppenspiel-Scores eingegeben werden, werden
die besten Gruppendritten pragmatisch anhand der Baseline-Staerke aus der
Gruppensimulation des gewaehlten Modells sortiert. Der Modus ist damit ein
"Path Scenario", kein neues trainiertes Modell und keine dynamische
Post-Gruppenphasen-Feature-Aktualisierung.

Scenario Mode ist aktuell bewusst nur fuer `v2 Full 35 (XGBoost)` aktiviert,
weil der neue Szenario-Simulator den v2_full_35-Knockout-Predictor verwendet.
Die anderen Modelle bleiben im restlichen Dashboard voll vergleichbar.

Scenario-Simulationen:

- einstellbar: 100, 200, 300, 500, 1000, 10000
- 100-500: gut fuer schnelle Live-Demo
- 1000+: stabilere Szenario-Ergebnisse
- 10000: moeglich, aber mit Warnung wegen laengerer Laufzeit
- Seed Start default = 42 fuer reproduzierbare Monte-Carlo-Laeufe

Plausibilitaetscheck fuer Scenario Mode:

- isolierter 20er-Testlauf kompiliert und laeuft
- 32 qualifizierte Teams
- 32 K.o.-Matches
- Rundensummen exakt:
  - p_advance_group = 32
  - p_reach_round_of_16 = 16
  - p_reach_quarter_final = 8
  - p_reach_semi_final = 4
  - p_final = 2
  - p_title = 1
  - p_third_place = 1

Wichtig fuer Interpretation in Praesentation:

- Dashboard-Werte sind Modell- und Simulationswahrscheinlichkeiten, keine Wahrheit.
- Scenario Mode beantwortet: "Was passiert, wenn der Turnierpfad anders aussieht?"
- Scenario Mode beantwortet NICHT: "Wie wuerde sich die Teamform nach diesen
  hypothetischen Gruppenspielen neu berechnen?"
