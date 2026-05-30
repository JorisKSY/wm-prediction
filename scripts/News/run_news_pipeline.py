# run_news_pipeline.py

import pandas as pd

from news_client import fetch_team_news
from news_analysis import analyze_article


def run_pipeline_for_team(team: str):
    articles = fetch_team_news(
        team=team,
        from_date="2026-05-01",
        page_size=5,
    )

    print(f"{len(articles)} Artikel gefunden für {team}.")

    results = []

    for article in articles:
        print("\nAnalysiere Artikel:")
        print(article.get("title"))

        result = analyze_article(article, team)
        results.append(result)

    df = pd.DataFrame(results)

    output_file = f"news_features_{team.lower().replace(' ', '_')}.csv"
    df.to_csv(output_file, index=False, encoding="utf-8")

    print(f"\nCSV gespeichert: {output_file}")

    return df


if __name__ == "__main__":
    run_pipeline_for_team("Germany national team")