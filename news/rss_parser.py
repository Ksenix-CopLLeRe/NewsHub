import feedparser
from datetime import datetime
from django.utils import timezone
from .models import RSSNews

RSS_FEEDS = {
    'russia': 'https://lenta.ru/rss/news/russia',
    'world': 'https://lenta.ru/rss/news/world',
    'economics': 'https://lenta.ru/rss/news/economics',
    'science': 'https://lenta.ru/rss/news/science',
    'sport': 'https://lenta.ru/rss/news/sport',
    'culture': 'https://lenta.ru/rss/news/culture',
    'general': 'https://lenta.ru/rss/news',
}

def fetch_rss_news(category='general'):
    """
    Получает новости из RSS-ленты Lenta.ru по указанной категории.
    
    Парсит RSS-ленту, извлекает данные о новостях и сохраняет их в БД
    для кеширования. Если RSS недоступен, возвращает новости из кеша.
    
    Args:
        category: Категория новостей. Доступные значения:
                 - 'russia' - Новости России
                 - 'world' - Мировые новости
                 - 'economics' - Экономика
                 - 'science' - Наука
                 - 'sport' - Спорт
                 - 'culture' - Культура
                 - 'general' - Все новости (по умолчанию)
    
    Returns:
        list: Список словарей с данными о новостях. Каждый словарь содержит:
            - title: Заголовок новости
            - description: Описание новости
            - url: URL новости
            - urlToImage: URL изображения (может быть пустым)
            - source: Словарь {'name': 'Lenta.ru'}
            - publishedAt: Дата публикации в ISO формате
            - published_at: Объект datetime для совместимости с моделями
    
    Note:
        Возвращает максимум 20 последних новостей из категории.
        При ошибке парсинга RSS возвращает новости из кеша БД.
    """
    rss_url = RSS_FEEDS.get(category, RSS_FEEDS['general'])
    
    try:
        feed = feedparser.parse(rss_url)
        news_list = []
        
        for entry in feed.entries[:20]:  # Берем последние 20 новостей
            # Преобразуем время публикации
            pub_date = datetime(*entry.published_parsed[:6])
            pub_date = timezone.make_aware(pub_date)
            
            news_item = {
                'title': entry.title,
                'description': entry.get('summary', ''),
                'url': entry.link,
                'urlToImage': (
                    entry.enclosures[0].url
                    if hasattr(entry, 'enclosures') and entry.enclosures and 'image' in entry.enclosures[0].type
                    else ''
                ),
                'source': {'name': 'Lenta.ru'},
                'publishedAt': pub_date.isoformat(),
                'published_at': pub_date,  # для совместимости с моделью
            }
            news_list.append(news_item)
            
            # Сохраняем в БД для кеширования
            RSSNews.objects.update_or_create(
                url=entry.link,
                defaults={
                    'title': entry.title,
                    'description': entry.get('summary', ''),
                    'published_at': pub_date,
                    'source': 'Lenta.ru',
                    'category': category,
                }
            )
        
        return news_list
    
    except Exception as e:
        print(f"Ошибка при парсинге RSS: {e}")
        
        # Если RSS недоступен, берем из БД
        cached_news = RSSNews.objects.filter(category=category)[:20]
        news_list = []
        
        for news in cached_news:
            news_list.append({
                'title': news.title,
                'description': news.description or '',
                'url': news.url,
                'urlToImage': '',  # В БД нет изображений, но добавляем поле для совместимости
                'source': {'name': news.source},
                'publishedAt': news.published_at.isoformat(),
                'published_at': news.published_at,  # для совместимости с моделью
            })
        
        return news_list

def update_all_categories():
    """
    Обновляет новости для всех доступных категорий.
    
    Вызывает fetch_rss_news() для каждой категории из RSS_FEEDS.
    Полезно для периодического обновления кеша новостей.
    
    Note:
        Может использоваться в cron-задачах или management командах
        для автоматического обновления новостей.
    """
    for category in RSS_FEEDS.keys():
        fetch_rss_news(category)