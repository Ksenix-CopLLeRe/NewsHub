import feedparser
from datetime import datetime
import logging
from typing import List, Dict, Optional
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CATEGORY_MAPPING = {
    "russia": "россия",
    "world": "мир",
    "economics": "экономика", 
    "science": "наука",
    "sport": "спорт",
    "culture": "культура"
}

# URL RSS лент Lenta.ru по категориям
RSS_FEEDS = {
    "россия": "https://lenta.ru/rss/news/russia",
    "мир": "https://lenta.ru/rss/news/world", 
    "экономика": "https://lenta.ru/rss/news/economics",
    "наука": "https://lenta.ru/rss/news/science",
    "спорт": "https://lenta.ru/rss/news/sport",
    "культура": "https://lenta.ru/rss/news/culture"
}

def parse_rss_feed(category: str) -> List[Dict]:
    """
    Парсит RSS ленту Lenta.ru для указанной категории
    """
    if category not in RSS_FEEDS:
        logger.error(f"Неизвестная категория: {category}")
        return []
    
    feed_url = RSS_FEEDS[category]
    logger.info(f"Парсинг RSS для категории '{category}': {feed_url}")
    
    try:
        # Парсим RSS ленту
        feed = feedparser.parse(feed_url)
        
        if feed.bozo:
            logger.warning(f"Ошибки при парсинге RSS: {feed.bozo_exception}")
        
        news_items = []
        for entry in feed.entries[:30]:  # Берем последние 30 новостей
            try:
                news_item = {
                    "url": entry.link,
                    "title": entry.title,
                    "description": entry.summary if hasattr(entry, 'summary') else '',
                    "image_url": extract_image_url(entry),
                    "source_name": "Lenta.ru",
                    "published_at": parse_pub_date(entry),
                    "category": category
                }
                news_items.append(news_item)
            except Exception as e:
                logger.error(f"Ошибка обработки записи: {e}")
                continue
        
        logger.info(f"Получено {len(news_items)} новостей для категории '{category}'")
        return news_items
        
    except Exception as e:
        logger.error(f"Ошибка при парсинге RSS: {e}")
        return []

def extract_image_url(entry) -> str:
    """
    Извлекает URL изображения из RSS записи
    """
    if hasattr(entry, 'media_content') and entry.media_content:
        return entry.media_content[0].get('url', '')
    
    if hasattr(entry, 'links'):
        for link in entry.links:
            if link.get('type', '').startswith('image/'):
                return link.get('href', '')
    
    if hasattr(entry, 'enclosures'):
        for enclosure in entry.enclosures:
            if enclosure.get('type', '').startswith('image/'):
                return enclosure.get('href', '')
    
    # Возвращаем пустую строку, если изображение не найдено
    return ""

def parse_pub_date(entry) -> datetime:
    """
    Преобразует дату публикации из RSS в datetime
    """
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        return datetime(*entry.published_parsed[:6])
    
    if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6])
    
    # Если даты нет, используем текущее время
    return datetime.now()

def update_all_categories() -> Dict[str, int]:
    """
    Обновляет новости для всех категорий
    """
    results = {}
    for category in RSS_FEEDS.keys():
        news_items = parse_rss_feed(category)
        results[category] = len(news_items)
        time.sleep(1) 
    
    return results

if __name__ == "__main__":
    test_items = parse_rss_feed("россия")
    for item in test_items[:3]:
        print(f"Заголовок: {item['title']}")
        print(f"URL: {item['url']}")
        print(f"Дата: {item['published_at']}")
        print("-" * 50)



# Как посмотреть новости
# # Получить все новости (первые 20)
# curl http://localhost:8000/feed

# # Получить новости конкретной категории
# curl "http://localhost:8000/feed?category=экономика&limit=5"

# # Поиск по тексту
# curl "http://localhost:8000/feed?q=путин&limit=3"

# # С пагинацией (пропустить 10, взять 5)
# curl "http://localhost:8000/feed?skip=10&limit=5"

# # Зайти в контейнер
# docker exec -it feed-service /bin/bash

# # Открыть базу данных
# sqlite3 feed.db

# # SQL запросы
# sqlite> .tables
# sqlite> SELECT COUNT(*) FROM news;
# sqlite> SELECT title, category, published_at FROM news LIMIT 5;
# sqlite> SELECT * FROM news WHERE category = 'экономика' LIMIT 3;
# sqlite> .exit