# news_analysis.py

import json
from openai import OpenAIError
from llm_client import ask_llm


import time
from openai import OpenAIError


def ask_llm_with_retry(messages, max_retries=3):
    for attempt in range(max_retries):
        try:
            return ask_llm(
                messages=messages,
                max_tokens=700,
                temperature=0.0,
                stream_output=False,
            )

        except OpenAIError as e:
            print(f"LLM Fehler, Versuch {attempt + 1}/{max_retries}: {e}")

            if attempt == max_retries - 1:
                raise

            time.sleep(5)

def analyze_article(article: dict, team: str) -> dict:
    title = article.get("title") or ""
    description = article.get("description") or ""
    content = article.get("content") or ""
    source = article.get("source", {}).get("name", "")
    published_at = article.get("publishedAt", "")
    url = article.get("url", "")

    article_text = f"""
Quelle: {source}
Datum: {published_at}
Titel: {title}
Beschreibung: {description}
Inhalt: {content}
URL: {url}
"""

    messages = [
        {
            "role": "system",
            "content": """
Du bist ein NLP-System für ein Data-Science-Projekt zur Vorhersage von Fußballspielen.

Deine Aufgabe:
Analysiere Nachrichtenartikel über Nationalteams und extrahiere strukturierte Features.

Wichtig:
- Gib ausschließlich gültiges JSON zurück.
- Kein Markdown.
- Keine Erklärung außerhalb von JSON.
- Bewerte nur Informationen, die im Artikel wirklich stehen.
- Wenn etwas nicht erwähnt wird, setze false, 0 oder eine leere Liste [].
- Erfinde keine Spielernamen.
- Entscheide NICHT, ob ein Spieler ein Key Player ist.
- Entscheide NICHT, wie wichtig ein Spieler für das Team ist.
- Antworte auf Deutsch bei Begründungen.
"""
        },
        {
            "role": "user",
            "content": f"""
Team: {team}

Artikel:
{article_text}

Extrahiere folgende Features:

{{
  "team": "{team}",

  "sentiment_score": Zahl von -1 bis 1,
  "sentiment_label": "negative" | "neutral" | "positive",

  "injury_news": true/false,
  "injured_players": ["Name Spieler 1", "Name Spieler 2"],
  "injury_status": "none" | "injured" | "doubtful" | "returned" | "mixed" | "unknown",

  "suspension_news": true/false,
  "suspended_players": ["Name Spieler 1", "Name Spieler 2"],

  "morale_pressure_news": true/false,
  "morale_pressure_score": Zahl von -1 bis 1,

  "coach_news": true/false,
  "coach_pressure": true/false,
  "coach_sentiment_score": Zahl von -1 bis 1,

  "short_reason": "kurze Begründung auf Deutsch"
}}

Definitionen:

injury_news:
true, wenn der Artikel Verletzungen, Ausfälle wegen Verletzung, Fitnessprobleme oder Rückkehr nach Verletzung erwähnt.

injured_players:
Liste der Spielernamen, die laut Artikel verletzt, angeschlagen, fraglich oder gerade von einer Verletzung zurückgekehrt sind.
Wenn keine Namen erwähnt werden, gib [] zurück.

injury_status:
- "none" = keine Verletzungsinformation
- "injured" = Spieler fällt verletzt aus oder ist klar verletzt
- "doubtful" = Spieler ist fraglich/angeschlagen/unsicher
- "returned" = Spieler ist nach Verletzung zurück
- "mixed" = mehrere verschiedene Fälle, z.B. ein Spieler verletzt und ein anderer zurück
- "unknown" = Verletzung wird erwähnt, aber Status ist unklar

suspension_news:
true, wenn Sperren, rote Karten, Gelbsperren oder Disziplinarsperren erwähnt werden.

suspended_players:
Liste der gesperrten Spielernamen.
Wenn keine Namen erwähnt werden, gib [] zurück.

Wichtig:
Bewerte bei Verletzungen und Sperren NICHT die Wichtigkeit des Spielers.
Das wird später mit separaten Spielerdaten berechnet.
"""
        }
    ]

    try:
        raw_answer = ask_llm_with_retry(
            messages=messages,
            max_retries=2,
        )

        result = json.loads(raw_answer)

    except json.JSONDecodeError:
        result = {
            "team": team,
            "error": "LLM hat kein gültiges JSON geliefert",
            "raw_answer": raw_answer,
        }

    except OpenAIError as e:
        result = {
            "team": team,
            "error": "LLM API Fehler",
            "error_message": str(e),
        }

    except Exception as e:
        result = {
            "team": team,
            "error": "Unbekannter Fehler",
            "error_message": str(e),
        }

    result["article_title"] = title
    result["article_url"] = url
    result["published_at"] = published_at
    result["source"] = source

    return result