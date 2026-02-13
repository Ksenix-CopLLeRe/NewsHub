from typing import List, Dict

from ..rss_parser import fetch_rss_news


class LocalFeedClient:
    """
    Локальная реализация Feed Service.

    Сейчас использует встроенный rss_parser и БД Django.
    В будущем здесь можно реализовать HTTP‑клиент к FastAPI Feed Service.
    """

    TEST_ARTICLES = [
        {
            "title": "Тестовая новость 1",
            "description": "Описание тестовой новости 1.",
            "url": "#",
            "urlToImage": "https://via.placeholder.com/300x200.png?text=News+1",
        },
        {
            "title": "Тестовая новость 2",
            "description": "Описание тестовой новости 2.",
            "url": "#",
            "urlToImage": "https://via.placeholder.com/300x200.png?text=News+2",
        },
    ]

    def get_feed(self, category: str, query: str | None = None) -> List[Dict]:
        """
        Вернуть список новостей для главной страницы.

        Сохраняет текущее поведение: берём RSS/кеш и фильтруем по строке поиска.
        """
        articles = fetch_rss_news(category=category)
        if not articles:
            articles = self.TEST_ARTICLES

        if query:
            query_lower = query.lower().strip()
            if query_lower:
                filtered_articles: List[Dict] = []
                for article in articles:
                    title = article.get("title") or ""
                    description = article.get("description") or ""

                    title_lower = str(title).lower()
                    desc_lower = str(description).lower()

                    if query_lower in title_lower or query_lower in desc_lower:
                        filtered_articles.append(article)

                articles = filtered_articles

        return articles

