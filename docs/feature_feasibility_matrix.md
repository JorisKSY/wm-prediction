# Feature Feasibility Matrix

Projekt: WM Prediction via Two-Stage Modeling  
Stand: nach Team- und Spieler-Staging

## Ziel

Diese Matrix bewertet, welche geplanten Features mit der aktuellen Datenbasis möglich sind, welche nur als Proxy möglich sind und welche aktuell nicht sauber ableitbar sind.

Status-Kategorien:

- **möglich**: direkt aus vorhandenen Staging-Tabellen ableitbar
- **teilweise / Proxy**: ableitbar, aber mit fachlichen Einschränkungen
- **nicht möglich**: aktuelle Datenbasis enthält die nötigen Informationen nicht
- **später / externe Pipeline**: grundsätzlich möglich, aber noch nicht im aktuellen Staging

---

## Team Features

| Feature | Status | Hauptquellen | Leakage-Risiko | Bemerkung |
|---|---|---|---|---|
| Nationalteam-Form letzte 5 Spiele | möglich | `staging.historical_matches` | niedrig, wenn strikt vor Matchdatum berechnet | Sehr sinnvoller früher Feature-Kandidat |
| Nationalteam-Form letztes Jahr | möglich | `staging.historical_matches` | niedrig | Zeitfenster über `match_date` |
| Nationalteam-Form letzte 5 Jahre | möglich | `staging.historical_matches` | niedrig | Kann gewichtet werden |
| Gewichtete Teamform | möglich | `staging.historical_matches` | niedrig | Gewichtung nach Recency möglich |
| Tore für / gegen vor Match | möglich | `staging.historical_matches` | niedrig | Basis für offensive/defensive Teamstärke |
| Heimvorteil / neutraler Platz | möglich | `staging.historical_matches.neutral`, `staging.games` | niedrig | Für historische Matches direkt vorhanden |
| Historisches FIFA-Ranking vor Match | möglich | `staging.fifa_rankings` | niedrig, wenn Ranking vor Matchdatum gewählt wird | Gute zeitabhängige Ranking-Quelle |
| Aktuelles FIFA-Ranking | teilweise / Demo | `staging.current_fifa_rankings` | hoch für historisches Training | Nur für Status/Demo, nicht für finales Training |
| Aktueller Elo-Wert | teilweise / Demo | `staging.elo_ratings` | hoch für historisches Training | Snapshot, kein historischer Verlauf |
| Historisches Elo vor Match | nicht möglich | — | — | Aktuell kein Elo-Zeitverlauf vorhanden |
| Nationalteam-Profil Marktwert | teilweise / Demo | `staging.national_team_profiles` | hoch für historisches Training | Snapshot, nicht historisch |
| Kadergröße / Durchschnittsalter Teamprofil | teilweise / Demo | `staging.national_team_profiles` | hoch | Snapshot |
| Coach Name | teilweise / Proxy | `staging.national_team_profiles`, `staging.club_games`, `staging.games` | mittel bis hoch | Keine saubere historische Coach-Zeitreihe |
| Trainererfahrung | teilweise / Proxy | `staging.club_games`, `staging.games`, `staging.national_team_profiles` | mittel | Nur über Manager-/Coach-Namen approximierbar |
| Formation | teilweise | `staging.games`, `staging.player_lineups` | niedrig bis mittel | Club-Games breit, Nationalteam-Lineups nur teilweise |
| Bevorzugte Formation | teilweise / Proxy | `staging.games.home_club_formation`, `staging.games.away_club_formation`, `staging.player_lineups` | mittel | Für Clubs gut, für Nationalteams nur teilweise und abhängig von Lineup-Abdeckung |
| Bedeutung des Spiels | teilweise / Proxy | `tournament`, `competition_sub_type`, WM/K.o.-Runde später | mittel | Kann über Wettbewerb/Runde approximiert werden |
| Druck / Moral | teilweise / Proxy | Form, Turnierphase, Elo/FIFA-Differenz | mittel | Nicht direkt beobachtet |
| Erholungszeit seit letztem Spiel | möglich | `staging.historical_matches`, `staging.games` | niedrig | Für Teams über vorheriges Matchdatum berechenbar |
| Reisedistanz | später / externe Pipeline | `city`, `country`, Stadium/Venue + Geo-Daten | mittel | Koordinaten fehlen aktuell |
| Wetter | später / externe Pipeline | Open-Meteo / Venue-Date-Time | mittel | Noch keine saubere DB-Staging-Schicht |
| Verletzungen / Ausfälle | nicht möglich | — | — | Keine Verletzungsdaten vorhanden |
| Trainer-Begegnungshistorie | teilweise / Proxy | `staging.club_games`, `staging.games` | mittel | Nur wenn Manager-Namen ausreichend konsistent sind |

---

## Spieler Features

| Feature | Status | Hauptquellen | Leakage-Risiko | Bemerkung |
|---|---|---|---|---|
| Spieler-Alter am Matchdatum | möglich | `staging.players.date_of_birth`, Matchdatum | niedrig | Direkt berechenbar |
| Alter zu Marktwert | möglich | `staging.players`, `staging.player_valuations` | niedrig, wenn Valuation vor Matchdatum gewählt wird | Sehr guter früher Feature-Kandidat |
| Zeitabhängiger Marktwert vor Match | möglich | `staging.player_valuations` | niedrig | Valuation-Datum erlaubt As-of-Join |
| Aktueller Spieler-Marktwert | teilweise / Demo | `staging.players.current_market_value_eur` | hoch für historisches Training | Snapshot |
| Höchster Marktwert | teilweise / Demo | `staging.players.highest_market_value_eur` | hoch | Kann Zukunftsinformation enthalten |
| Form letzte Saison | möglich / teilweise | `staging.player_appearances`, `staging.games` | niedrig, wenn Saison vor Match | Hauptsächlich Club-Kontext |
| Form letzte 5 Spiele | möglich / teilweise | `staging.player_appearances`, `staging.games` | niedrig, wenn vor Match | Hauptsächlich Club-Kontext |
| Tore | möglich | `staging.player_appearances`, `staging.player_game_events` | niedrig | Club breit, Nationalteam über Events besser |
| Assists | möglich | `staging.player_appearances`, `staging.player_game_events.player_assist_id` | niedrig | Assist-Feld in Appearances und Events |
| Karten | möglich | `staging.player_appearances`, `staging.player_game_events` | niedrig | Events enthalten Cards |
| Minuten | möglich | `staging.player_appearances` | niedrig | Hauptsächlich Club-Kontext |
| Tackles / Zweikämpfe | nicht möglich | — | — | Nicht in vorhandenen Tabellen |
| Spieler gegen Spieler Matchups | teilweise / später | `staging.player_lineups`, Positionen | mittel | Lineups vorhanden, aber echte Duelle müssen konstruiert werden |
| Spieler-Chemistry | teilweise / Proxy | gemeinsame Club-/Lineup-/Appearance-Historie | mittel | Nur approximierbar |
| Erfahrung in Länderspielen | teilweise | `staging.players.international_caps`, `staging.player_game_events`, `staging.player_lineups` | hoch bei Snapshot-Caps | `international_caps` ist Snapshot; Events/Lineups historisch nur teilweise |
| Erfahrung in kontinentalen Club-Wettbewerben | möglich | `staging.games`, `staging.competitions`, `staging.player_appearances` | niedrig | Champions League, Europa League, Conference League vorhanden |
| Dynamische Turnierform | teilweise / später | `staging.player_game_events`, `staging.player_lineups`, spätere Turniersimulation | niedrig in Simulation | Für echte historische Turniere teilweise vorhanden |
| Startelfstatus | möglich / teilweise | `staging.player_lineups` | niedrig | Club breit, Nationalteam teilweise |
| Position im Spiel | möglich / teilweise | `staging.player_lineups` | niedrig | Positionen vorhanden |
| Captain | möglich / teilweise | `staging.player_lineups.is_team_captain` | niedrig | Vorhanden |
| Einwechslungen / Auswechslungen | möglich | `staging.player_game_events` | niedrig | Event-Typ Substitutions |
| Elfmeterschießen | möglich | `staging.player_game_events` | niedrig | Event-Typ Shootout |

---

## Aggregierte Spieler-zu-Team Features

| Feature | Status | Hauptquellen | Leakage-Risiko | Bemerkung |
|---|---|---|---|---|
| Team-Marktwertsumme vor Match | möglich / teilweise | `staging.player_valuations`, Spieler-Team-Zuordnung | mittel | Spieler-Team-Zuordnung historisch schwierig |
| Top-5-Spieler-Marktwertsumme | möglich / teilweise | `staging.player_valuations` | mittel | Gute Proxy-Idee, Teamzuordnung kritisch |
| Top-heavy Teams Bonus | möglich / teilweise | `staging.player_valuations` | mittel | Anteil Top-5 an Teamwert |
| Durchschnittsalter erwarteter Kader | teilweise | `staging.players`, `staging.player_lineups` | mittel | Lineups nicht vollständig für alle Nationalteam-Wettbewerbe |
| Offensive Aggregation | möglich / teilweise | Goals/Assists/Minutes aus `staging.player_appearances` | mittel | Hauptsächlich Clubform |
| Defensive Aggregation | teilweise | Karten, Positionen, Gegentore auf Team-/Clubebene | mittel | Keine Tackles/Zweikämpfe |
| Kaderbreite | teilweise | Marktwerte, Lineups, Appearances | mittel | Squad-Daten historisch nicht vollständig |
| Spieler-Kompatibilität | teilweise / Proxy | gemeinsame Lineups/Clubhistorie | mittel | Nicht direkt vorhanden |
| Kompatibilität einzelner Spieler | teilweise / Proxy | gemeinsame `staging.player_lineups`, gemeinsame Clubs/Games, Positionsnähe | mittel | Kann später als Co-Lineup-/Co-Minutes-Proxy modelliert werden |

---

## Wichtige Daten-Einschränkungen

1. `staging.player_appearances` ist sehr stark für Clubform, aber Nationalteam-Appearances sind stark eingeschränkt.
2. `staging.player_lineups` enthält Nationalteam-Lineups für AFC Asian Cup, Africa Cup of Nations und Copa América, aber nicht für World Cup / UEFA Euro.
3. `staging.player_game_events` enthält Nationalteam-Events auch für World Cup und UEFA Euro.
4. `staging.players.current_national_team_id` ist ein aktueller Snapshot und darf nicht blind historisch verwendet werden.
5. `staging.players.current_market_value_eur` und `highest_market_value_eur` sind Snapshot-/Zukunftsrisiko-Felder.
6. Für zeitabhängige Marktwertfeatures sollte `staging.player_valuations` verwendet werden.
7. Für finale Trainingsdaten dürfen nur Informationen verwendet werden, die vor dem jeweiligen Matchdatum bekannt waren.

---

## Empfohlene erste Feature-Reihenfolge

1. `features.team_form_before_match`
2. `features.fifa_ranking_before_match`
3. `features.player_market_value_before_match`
4. `features.team_player_value_aggregates_before_match`
5. `features.player_form_before_match`
6. `features.training_match_base`
7. Erst danach: `lambda_home` / `lambda_away` Modellierung
