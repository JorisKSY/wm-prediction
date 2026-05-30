from newsapi import NewsApiClient
from config import NEWS_API_KEY


def get_news_client():
    return NewsApiClient(api_key=NEWS_API_KEY)


def fetch_team_news(
    team: str,
    from_date: str | None = None,
    to_date: str | None = None,
    page_size: int = 10,
):
    newsapi = get_news_client()

    query = f'"{team}" football OR soccer OR injury OR squad OR coach OR pressure OR form'

    articles = newsapi.get_everything(
        q=query,
        language="en",
        sort_by="publishedAt",
        from_param=from_date,
        to=to_date,
        page_size=page_size,
    )

    return articles["articles"]