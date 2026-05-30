from news_client import fetch_team_news

articles = fetch_team_news(
    team="Germany national team",
    from_date="2026-05-01",
    page_size=5,
)

for article in articles:
    print(article["title"])
    print(article["description"])
    print(article["url"])
    print()