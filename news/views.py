from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .models import FavoriteArticle, Comment, Reaction
from .services import (
    get_feed_client,
    get_user_content_client,
    get_reactions_client,
)
import json


# Заглушка для теста, если API вернул пустой список
TEST_ARTICLES = [
    {
        'title': 'Тестовая новость 1',
        'description': 'Описание тестовой новости 1.',
        'url': '#',
        'urlToImage': 'https://via.placeholder.com/300x200.png?text=News+1'
    },
    {
        'title': 'Тестовая новость 2',
        'description': 'Описание тестовой новости 2.',
        'url': '#',
        'urlToImage': 'https://via.placeholder.com/300x200.png?text=News+2'
    },
]

def home(request):
    """
    Главная страница с лентой новостей.
    
    Отображает новости из выбранной категории с возможностью поиска.
    Для авторизованных пользователей показывает информацию об избранном
    и реакциях на новости.
    
    Args:
        request: HTTP-запрос
        
    Query Parameters:
        category: Категория новостей (по умолчанию 'russia')
        q: Поисковый запрос (опционально)
        
    Returns:
        HTTP-ответ с отрендеренным шаблоном home.html
        
    Context:
        articles: Список новостей
        current_category: Текущая выбранная категория
        categories: Список доступных категорий
        query: Поисковый запрос
        favorite_urls: Множество URL избранных статей (для авторизованных)
        user_reactions: Словарь реакций пользователя {url: reaction_type}
        reactions_count: Словарь количества реакций {url: {type: count}}
    """
    category = request.GET.get('category', 'russia')
    query = request.GET.get('q', '').strip()

    # BFF: получаем ленту новостей через клиент (позже здесь будет FastAPI Feed Service)
    feed_client = get_feed_client()
    articles = feed_client.get_feed(category=category, query=query)
    
    categories = [
        {'code': 'general', 'name': 'Все новости'},
        {'code': 'russia', 'name': 'Россия'},
        {'code': 'world', 'name': 'Мир'},
        {'code': 'economics', 'name': 'Экономика'},
        {'code': 'science', 'name': 'Наука'},
        {'code': 'sport', 'name': 'Спорт'},
        {'code': 'culture', 'name': 'Культура'},
    ]

    # Получаем информацию об избранном и реакциях для авторизованных пользователей
    favorite_urls = set()
    user_reactions = {}
    reactions_count = {}
    
    if request.user.is_authenticated:
        user_content_client = get_user_content_client()
        reactions_client = get_reactions_client()

        # Избранное через клиент User Content Service
        favorite_urls = user_content_client.get_favorite_urls(request.user)

        # Реакции и счетчики через клиент Reactions Service
        urls = [a.get('url') for a in articles if a.get('url')]
        reactions_data = reactions_client.get_user_reactions_for_urls(
            request.user, urls
        )
        user_reactions = reactions_data["user_reactions"]
        reactions_count = reactions_data["reactions_count"]

    context = {
        'articles': articles,
        'current_category': category,
        'categories': categories,
        'query': query,
        'favorite_urls': favorite_urls,
        'user_reactions': user_reactions,
        'reactions_count': reactions_count,
    }

    return render(request, 'news/home.html', context)

@login_required
def favorites(request):
    """
    Страница избранных статей пользователя.
    
    Отображает все статьи, сохраненные пользователем в избранное,
    вместе с комментариями к ним. Требует авторизации.
    
    Args:
        request: HTTP-запрос (должен содержать авторизованного пользователя)
        
    Returns:
        HTTP-ответ с отрендеренным шаблоном favorites.html
        
    Context:
        articles_with_comments: Список словарей, каждый содержит:
            - article: Объект FavoriteArticle
            - comments: QuerySet комментариев к статье
    """
    user_content_client = get_user_content_client()
    articles_with_comments = user_content_client.get_favorites_with_comments(
        request.user
    )
    
    context = {
        'title': 'Избранное',
        'articles_with_comments': articles_with_comments,
    }
    return render(request, 'news/favorites.html', context)


def user_login(request):
    """Страница входа"""
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = authenticate(
                username=form.cleaned_data.get('username'),
                password=form.cleaned_data.get('password')
            )
            if user:
                login(request, user)
                messages.success(request, f'Добро пожаловать, {user.username}!')
                return redirect('news:home')
        messages.error(request, 'Неверное имя пользователя или пароль')
    else:
        form = AuthenticationForm()
    return render(request, 'news/login.html', {'form': form})


def user_logout(request):
    """Выход из системы"""
    logout(request)
    messages.info(request, 'Вы вышли из системы')
    return redirect('news:home')


def register(request):
    """Страница регистрации"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно!')
            return redirect('news:home')
        messages.error(request, 'Ошибка при регистрации')
    else:
        form = UserCreationForm()
    return render(request, 'news/register.html', {'form': form})


@login_required
@require_http_methods(["POST"])
def toggle_favorite(request):
    """
    API endpoint для добавления/удаления статьи из избранного.
    
    Если статья уже в избранном - удаляет её, если нет - добавляет.
    Работает через AJAX-запросы.
    
    Args:
        request: HTTP POST-запрос с JSON-данными
        
    Request Body (JSON):
        url: URL статьи (обязательно)
        title: Заголовок статьи
        description: Описание статьи
        urlToImage: URL изображения
        source: Словарь с информацией об источнике {'name': '...'}
        publishedAt: Дата публикации в ISO формате
        
    Returns:
        JsonResponse с результатом операции:
        {
            'success': bool,
            'is_favorite': bool  # True если добавлено, False если удалено
        }
        
    Raises:
        JsonResponse с ошибкой при некорректных данных (status 400/500)
    """
    try:
        data = json.loads(request.body)
        user_content_client = get_user_content_client()
        result = user_content_client.toggle_favorite(request.user, data)
        status = result.pop("status", 200)
        return JsonResponse(result, status=status)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def add_reaction(request):
    """
    API endpoint для добавления/изменения/удаления реакции на новость.
    
    Если реакция уже существует и того же типа - удаляет её (отмена).
    Если реакция другого типа - обновляет тип реакции.
    Если реакции нет - создает новую.
    
    Args:
        request: HTTP POST-запрос с JSON-данными
        
    Request Body (JSON):
        url: URL новости (обязательно)
        reaction_type: Тип реакции - 'important', 'interesting', 'shocking',
                      'useful', 'liked' (обязательно)
        
    Returns:
        JsonResponse с результатом операции:
        {
            'success': bool,
            'reaction_type': str или None,  # None если реакция отменена
            'reactions_count': dict  # {reaction_type: count} для всех типов
        }
        
    Raises:
        JsonResponse с ошибкой при некорректных данных (status 400/500)
    """
    try:
        data = json.loads(request.body)
        article_url = data.get('url')
        reaction_type = data.get('reaction_type')

        reactions_client = get_reactions_client()
        result = reactions_client.toggle_reaction(
            request.user, article_url, reaction_type
        )
        status = result.pop("status", 200)
        return JsonResponse(result, status=status)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def add_comment(request):
    """
    API endpoint для добавления комментария к избранной статье.
    
    Позволяет пользователю добавить комментарий к своей избранной статье.
    Комментарии видны только автору.
    
    Args:
        request: HTTP POST-запрос с JSON-данными
        
    Request Body (JSON):
        article_id: ID избранной статьи (обязательно)
        text: Текст комментария (обязательно, не может быть пустым)
        
    Returns:
        JsonResponse с результатом операции:
        {
            'success': bool,
            'comment': {
                'id': int,
                'text': str,
                'created_at': str  # Формат: 'DD.MM.YYYY HH:MM'
            }
        }
        
    Raises:
        JsonResponse с ошибкой при некорректных данных (status 400/500)
        404 если статья не найдена или не принадлежит пользователю
    """
    try:
        data = json.loads(request.body)
        article_id = data.get('article_id')
        text = data.get('text', '').strip()

        user_content_client = get_user_content_client()
        result = user_content_client.add_comment(request.user, article_id, text)
        status = result.pop("status", 200)
        return JsonResponse(result, status=status)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def edit_comment(request, comment_id):
    """
    API endpoint для редактирования комментария.
    
    Позволяет пользователю изменить текст своего комментария.
    Редактировать можно только свои комментарии.
    
    Args:
        request: HTTP POST-запрос с JSON-данными
        comment_id: ID комментария для редактирования
        
    Request Body (JSON):
        text: Новый текст комментария (обязательно, не может быть пустым)
        
    Returns:
        JsonResponse с результатом операции:
        {
            'success': bool,
            'comment': {
                'id': int,
                'text': str,
                'created_at': str  # Формат: 'DD.MM.YYYY HH:MM'
            }
        }
        
    Raises:
        JsonResponse с ошибкой при некорректных данных (status 400/500)
        404 если комментарий не найден или не принадлежит пользователю
    """
    try:
        data = json.loads(request.body)
        text = data.get('text', '').strip()

        user_content_client = get_user_content_client()
        result = user_content_client.edit_comment(request.user, comment_id, text)
        status = result.pop("status", 200)
        return JsonResponse(result, status=status)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def delete_comment(request, comment_id):
    """
    API endpoint для удаления комментария.
    
    Позволяет пользователю удалить свой комментарий.
    Удалять можно только свои комментарии.
    
    Args:
        request: HTTP POST-запрос
        comment_id: ID комментария для удаления
        
    Returns:
        JsonResponse с результатом операции:
        {
            'success': bool
        }
        
    Raises:
        JsonResponse с ошибкой при некорректных данных (status 500)
        404 если комментарий не найден или не принадлежит пользователю
    """
    try:
        user_content_client = get_user_content_client()
        result = user_content_client.delete_comment(request.user, comment_id)
        status = result.pop("status", 200)
        return JsonResponse(result, status=status)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
