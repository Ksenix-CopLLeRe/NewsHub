from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .rss_parser import fetch_rss_news
from .models import FavoriteArticle, Comment, Reaction
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

    articles = fetch_rss_news(category=category)
    if not articles:
        articles = TEST_ARTICLES
    
    categories = [
        {'code': 'general', 'name': 'Все новости'},
        {'code': 'russia', 'name': 'Россия'},
        {'code': 'world', 'name': 'Мир'},
        {'code': 'economics', 'name': 'Экономика'},
        {'code': 'science', 'name': 'Наука'},
        {'code': 'sport', 'name': 'Спорт'},
        {'code': 'culture', 'name': 'Культура'},
    ]

    if query:
        query_lower = query.lower().strip()
        if query_lower:  # Проверяем, что запрос не пустой после обработки
            filtered_articles = []
            for article in articles:
                # Безопасная обработка None значений
                title = article.get('title') or ''
                description = article.get('description') or ''
                
                # Преобразуем в строку и приводим к нижнему регистру
                title_lower = str(title).lower()
                desc_lower = str(description).lower()
                
                # Поиск по заголовку и описанию
                title_match = query_lower in title_lower
                desc_match = query_lower in desc_lower
                
                if title_match or desc_match:
                    filtered_articles.append(article)
            
            articles = filtered_articles

    # Получаем информацию об избранном и реакциях для авторизованных пользователей
    favorite_urls = set()
    user_reactions = {}
    reactions_count = {}
    
    if request.user.is_authenticated:
        # Избранное
        favorite_urls = set(
            FavoriteArticle.objects.filter(user=request.user)
            .values_list('url', flat=True)
        )
        
        # Реакции пользователя
        user_reactions_dict = {
            r.article_url: r.reaction_type 
            for r in Reaction.objects.filter(user=request.user)
        }
        user_reactions = user_reactions_dict
        
        # Количество реакций для каждой новости
        for article in articles:
            url = article.get('url')
            if url:
                reactions = Reaction.objects.filter(article_url=url)
                count_dict = {}
                for reaction_type, _ in Reaction.REACTION_TYPES:
                    count = reactions.filter(reaction_type=reaction_type).count()
                    if count > 0:
                        count_dict[reaction_type] = count
                # Всегда добавляем словарь, даже если он пустой
                reactions_count[url] = count_dict

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
    favorite_articles = FavoriteArticle.objects.filter(user=request.user)
    
    # Добавляем комментарии к каждой статье
    articles_with_comments = []
    for article in favorite_articles:
        comments = Comment.objects.filter(article=article, user=request.user)
        articles_with_comments.append({
            'article': article,
            'comments': comments,
        })
    
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
        article_url = data.get('url')
        title = data.get('title', '')
        description = data.get('description', '')
        image_url = data.get('urlToImage', '')
        source_name = data.get('source', {}).get('name', 'Lenta.ru')
        published_at_str = data.get('publishedAt', '')
        
        if not article_url:
            return JsonResponse({'success': False, 'error': 'URL статьи не указан'}, status=400)
        
        # Парсим дату публикации
        try:
            from datetime import datetime
            if published_at_str:
                if 'T' in published_at_str:
                    published_at = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
                else:
                    published_at = timezone.now()
            else:
                published_at = timezone.now()
            if timezone.is_naive(published_at):
                published_at = timezone.make_aware(published_at)
        except:
            published_at = timezone.now()
        
        favorite, created = FavoriteArticle.objects.get_or_create(
            user=request.user,
            url=article_url,
            defaults={
                'title': title,
                'description': description,
                'image_url': image_url,
                'source_name': source_name,
                'published_at': published_at,
            }
        )
        
        if not created:
            # Удаляем из избранного
            favorite.delete()
            return JsonResponse({'success': True, 'is_favorite': False})
        
        return JsonResponse({'success': True, 'is_favorite': True})
    
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
        
        if not article_url or not reaction_type:
            return JsonResponse({'success': False, 'error': 'Не указаны обязательные параметры'}, status=400)
        
        # Проверяем, что тип реакции валидный
        valid_types = [rt[0] for rt in Reaction.REACTION_TYPES]
        if reaction_type not in valid_types:
            return JsonResponse({'success': False, 'error': 'Неверный тип реакции'}, status=400)
        
        # Получаем или создаем реакцию
        reaction, created = Reaction.objects.get_or_create(
            user=request.user,
            article_url=article_url,
            defaults={'reaction_type': reaction_type}
        )
        
        if not created:
            # Если реакция уже существует, обновляем её
            if reaction.reaction_type == reaction_type:
                # Та же реакция - удаляем (отмена реакции)
                reaction.delete()
                return JsonResponse({
                    'success': True, 
                    'reaction_type': None,
                    'reactions_count': _get_reactions_count(article_url)
                })
            else:
                # Меняем тип реакции
                reaction.reaction_type = reaction_type
                reaction.save()
        
        return JsonResponse({
            'success': True,
            'reaction_type': reaction_type,
            'reactions_count': _get_reactions_count(article_url)
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def _get_reactions_count(article_url):
    """
    Вспомогательная функция для получения количества реакций по типам.
    
    Args:
        article_url: URL новости
        
    Returns:
        dict: Словарь {reaction_type: count} для всех типов реакций,
              где count > 0
    """
    reactions = Reaction.objects.filter(article_url=article_url)
    count_dict = {}
    for reaction_type, _ in Reaction.REACTION_TYPES:
        count = reactions.filter(reaction_type=reaction_type).count()
        if count > 0:
            count_dict[reaction_type] = count
    return count_dict


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
        
        if not article_id or not text:
            return JsonResponse({'success': False, 'error': 'Не указаны обязательные параметры'}, status=400)
        
        article = get_object_or_404(FavoriteArticle, id=article_id, user=request.user)
        
        comment = Comment.objects.create(
            article=article,
            user=request.user,
            text=text
        )
        
        return JsonResponse({
            'success': True,
            'comment': {
                'id': comment.id,
                'text': comment.text,
                'created_at': comment.created_at.strftime('%d.%m.%Y %H:%M'),
            }
        })
    
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
        comment = get_object_or_404(Comment, id=comment_id, user=request.user)
        data = json.loads(request.body)
        text = data.get('text', '').strip()
        
        if not text:
            return JsonResponse({'success': False, 'error': 'Текст комментария не может быть пустым'}, status=400)
        
        comment.text = text
        comment.save()
        
        return JsonResponse({
            'success': True,
            'comment': {
                'id': comment.id,
                'text': comment.text,
                'created_at': comment.created_at.strftime('%d.%m.%Y %H:%M'),
            }
        })
    
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
        comment = get_object_or_404(Comment, id=comment_id, user=request.user)
        comment.delete()
        
        return JsonResponse({'success': True})
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)