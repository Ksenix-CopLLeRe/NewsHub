"""
Клиенты для взаимодействия с микросервисами.
Поддерживает как синхронные, так и асинхронные вызовы.
"""

import os
import requests
from typing import Optional, List, Dict, Set, Tuple
from urllib.parse import quote
from django.conf import settings

# ============ Настройки ============
FEED_SERVICE_URL = getattr(settings, 'FEED_SERVICE_URL', 'http://feed-service:8003')
REACTIONS_SERVICE_URL = getattr(settings, 'REACTIONS_SERVICE_URL', 'http://reactions-service:8004')
USER_CONTENT_SERVICE_URL = getattr(settings, 'USER_CONTENT_SERVICE_URL', 'http://user-content-service:8002')

REQUEST_TIMEOUT = 3.0

# Типы реакций (стандартизированы)
REACTION_TYPES = ['important', 'interesting', 'shocking', 'useful', 'liked']

# ============ Feed Service (новости) ============

class FeedServiceClient:
    """Клиент для Feed Service (управление новостями)"""
    
    def __init__(self, base_url: str = FEED_SERVICE_URL):
        self.base_url = base_url.rstrip('/')
    
    def get_feed(
        self,
        category: Optional[str] = None,
        query: Optional[str] = None,
        page: int = 1,
        size: int = 20
    ) -> Dict:
        """
        Получить ленту новостей
        
        Returns:
            {
                'items': [...],
                'total': int,
                'page': int,
                'size': int
            }
        """
        params = {'page': page, 'size': size}
        if category:
            params['category'] = category
        if query:
            params['q'] = query
        
        try:
            response = requests.get(
                f"{self.base_url}/feed",
                params=params,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            return data
        except requests.exceptions.RequestException as e:
            print(f"Feed Service error: {e}")
            return {
                'items': [],
                'total': 0,
                'page': page,
                'size': size,
                'error': str(e)
            }
    
    def get_news_by_url(self, url: str) -> Optional[Dict]:
        """Получить новость по URL"""
        try:
            encoded_url = quote(url, safe='')
            response = requests.get(
                f"{self.base_url}/news/{encoded_url}",
                timeout=REQUEST_TIMEOUT
            )
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException:
            pass
        return None
    
    def get_categories(self) -> List[Dict]:
        """Получить список категорий с количеством"""
        try:
            response = requests.get(
                f"{self.base_url}/categories",
                timeout=REQUEST_TIMEOUT
            )
            if response.status_code == 200:
                return response.json().get('categories', [])
        except requests.exceptions.RequestException:
            pass
        return []
    
    def get_stats(self) -> Dict:
        """Получить статистику по новостям"""
        try:
            response = requests.get(
                f"{self.base_url}/stats",
                timeout=REQUEST_TIMEOUT
            )
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException:
            pass
        return {}


# ============ Reactions Service (реакции) ============

class ReactionsServiceClient:
    """Клиент для Reactions Service (управление реакциями)"""
    
    def __init__(self, base_url: str = REACTIONS_SERVICE_URL):
        self.base_url = base_url.rstrip('/')
    
    def toggle_reaction(
        self,
        user_id: int,
        news_url: str,
        reaction_type: str
    ) -> Dict:
        """
        Добавить/удалить/обновить реакцию (toggle-логика)
        
        Returns:
            {
                'success': bool,
                'action': 'created' | 'updated' | 'deleted',
                'reaction': {...}
            }
        """
        if reaction_type not in REACTION_TYPES:
            return {'success': False, 'error': 'Invalid reaction type'}
        
        payload = {
            'user_id': user_id,
            'news_id': news_url,
            'reaction_type': reaction_type
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/reactions",
                json=payload,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            data['status'] = response.status_code
            return data
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': str(e),
                'status': 500
            }
    
    def get_reaction_counts(self, news_url: str) -> Dict[str, int]:
        """
        Получить счётчики реакций для новости
        
        Returns:
            {'important': 5, 'interesting': 2, ...}
        """
        try:
            encoded_url = quote(news_url, safe='')
            response = requests.get(
                f"{self.base_url}/reactions/counts/{encoded_url}",
                timeout=REQUEST_TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('counts', {})
        except requests.exceptions.RequestException:
            pass
        
        # Возвращаем нулевые счётчики при ошибке
        return {rt: 0 for rt in REACTION_TYPES}
    
    def get_batch_reaction_counts(self, urls: List[str]) -> Dict[str, Dict[str, int]]:
        """
        Получить счётчики реакций для нескольких новостей
        (использует массовый запрос)
        """
        result = {}
        # Пока делаем последовательные запросы, можно оптимизировать
        # если добавить массовый эндпоинт в reactions-service
        for url in urls:
            result[url] = self.get_reaction_counts(url)
        return result
    
    def get_user_reaction(self, user_id: int, news_url: str) -> Optional[str]:
        """
        Получить реакцию пользователя на конкретную новость
        """
        try:
            encoded_url = quote(news_url, safe='')
            # Ищем реакцию пользователя через фильтрацию
            response = requests.get(
                f"{self.base_url}/reactions/news/{encoded_url}",
                params={'page': 1, 'size': 100},
                timeout=REQUEST_TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                for reaction in data.get('items', []):
                    if reaction.get('user_id') == user_id:
                        return reaction.get('reaction_type')
        except requests.exceptions.RequestException:
            pass
        return None
    
    def get_user_reactions_for_urls(
        self,
        user_id: int,
        urls: List[str]
    ) -> Tuple[Dict[str, str], Dict[str, Dict[str, int]]]:
        """
        Получить реакции пользователя и счётчики для списка URL
        
        Returns:
            (user_reactions, reactions_count)
            user_reactions: {url: reaction_type}
            reactions_count: {url: {type: count}}
        """
        user_reactions = {}
        reactions_count = {}
        
        for url in urls:
            if not url:
                continue
            reactions_count[url] = self.get_reaction_counts(url)
            user_reaction = self.get_user_reaction(user_id, url)
            if user_reaction:
                user_reactions[url] = user_reaction
        
        return user_reactions, reactions_count


# ============ User Content Service (избранное и комментарии) ============

class UserContentServiceClient:
    """Клиент для User Content Service (избранное и комментарии)"""
    
    def __init__(self, base_url: str = USER_CONTENT_SERVICE_URL):
        self.base_url = base_url.rstrip('/')
    
    def toggle_favorite(self, user_id: int, article_data: Dict) -> Dict:
        """
        Добавить/удалить статью из избранного
        
        Returns:
            {
                'success': bool,
                'is_favorite': bool,
                'action': 'added' | 'removed'
            }
        """
        # source_name: если пусто или None, используем Lenta.ru
        source_name = article_data.get('source_name')
        if not source_name:
            source_name = 'Lenta.ru'

        payload = {
            'user_id': user_id,
            'url': article_data.get('url'),
            'title': article_data.get('title', ''),
            'description': article_data.get('description', ''),
            'url_to_image': article_data.get('url_to_image') or article_data.get('image_url'),
            'source_name': article_data.get('source_name') or 
                           article_data.get('source', {}).get('name', 'Lenta.ru'),
            'published_at': article_data.get('publishedAt') or article_data.get('published_at')
        }

        payload = {k: v for k, v in payload.items() if v is not None}
        
        try:
            response = requests.post(
                f"{self.base_url}/favorites/toggle",
                json=payload,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            data['status'] = response.status_code
            return data
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': str(e),
                'status': 500
            }
    
    def get_favorites(self, user_id: int, include_comments: bool = False) -> List[Dict]:
        """
        Получить список избранных статей пользователя
        """
        try:
            params = {'user_id': user_id}
            if include_comments:
                params['include_comments'] = 'true'
            
            response = requests.get(
                f"{self.base_url}/favorites",
                params=params,
                timeout=REQUEST_TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('items', [])
        except requests.exceptions.RequestException:
            pass
        return []
    
    def get_favorites_with_comments(self, user_id: int) -> List[Dict]:
        """
        Получить избранные статьи с комментариями
        """
        return self.get_favorites(user_id, include_comments=True)
    
    def get_favorite_urls(self, user_id: int) -> Set[str]:
        """
        Получить множество URL избранных статей
        """
        try:
            response = requests.get(
                f"{self.base_url}/favorites/urls",
                params={'user_id': user_id},
                timeout=REQUEST_TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                return set(data.get('urls', []))
        except requests.exceptions.RequestException:
            pass
        return set()
    
    def check_favorite(self, user_id: int, url: str) -> bool:
        """
        Проверить, находится ли статья в избранном
        """
        try:
            encoded_url = quote(url, safe='')
            response = requests.get(
                f"{self.base_url}/favorites/check/{encoded_url}",
                params={'user_id': user_id},
                timeout=REQUEST_TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('is_favorite', False)
        except requests.exceptions.RequestException:
            pass
        return False
    
    def add_comment(self, user_id: int, article_id: int, text: str) -> Dict:
        """
        Добавить комментарий к избранной статье
        """
        payload = {'user_id': user_id, 'text': text}
        
        try:
            response = requests.post(
                f"{self.base_url}/favorites/{article_id}/comments",
                json=payload,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            data['status'] = response.status_code
            return data
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': str(e),
                'status': 500
            }
    
    def edit_comment(self, user_id: int, comment_id: int, text: str) -> Dict:
        """
        Редактировать комментарий
        """
        payload = {'user_id': user_id, 'text': text}
        
        try:
            response = requests.put(
                f"{self.base_url}/comments/{comment_id}",
                json=payload,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            data['status'] = response.status_code
            return data
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': str(e),
                'status': 500
            }
    
    def delete_comment(self, user_id: int, comment_id: int) -> Dict:
        """
        Удалить комментарий
        """
        try:
            response = requests.delete(
                f"{self.base_url}/comments/{comment_id}",
                params={'user_id': user_id},
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return {
                'success': True,
                'status': response.status_code
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': str(e),
                'status': 500
            }
    
    def get_comments(self, user_id: int, article_id: int, page: int = 1, size: int = 10) -> Dict:
        """
        Получить комментарии к статье
        """
        try:
            response = requests.get(
                f"{self.base_url}/favorites/{article_id}/comments",
                params={'user_id': user_id, 'page': page, 'size': size},
                timeout=REQUEST_TIMEOUT
            )
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException:
            pass
        return {'items': [], 'total': 0, 'page': page, 'size': size}


# ============ Фабрики для создания клиентов ============

def get_feed_client() -> FeedServiceClient:
    """Получить экземпляр клиента Feed Service"""
    return FeedServiceClient()

def get_reactions_client() -> ReactionsServiceClient:
    """Получить экземпляр клиента Reactions Service"""
    return ReactionsServiceClient()

def get_user_content_client() -> UserContentServiceClient:
    """Получить экземпляр клиента User Content Service"""
    return UserContentServiceClient()


# ============ Утилиты для шаблонов ============

def format_reaction_counts(reactions_count: Dict[str, int]) -> Dict[str, str]:
    """
    Форматирует счётчики реакций для отображения
    Возвращает словарь с эмодзи и текстом
    """
    emojis = {
        'important': '🔥',
        'interesting': '🤔',
        'shocking': '😱',
        'useful': '💡',
        'liked': '❤️'
    }
    
    result = {}
    for rt, count in reactions_count.items():
        if count > 0:
            result[rt] = f"{emojis.get(rt, '')} {count}"
    return result