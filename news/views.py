# news/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from config.settings import USER_CONTENT_SERVICE_URL, REACTIONS_SERVICE_URL
import json

from .services import (
    get_feed_client,
    get_reactions_client,
    get_user_content_client,
    REACTION_TYPES
)

CATEGORY_MAP = {
    'general': None,      # все новости
    'russia': 'россия',
    'world': 'мир',
    'economics': 'экономика',
    'science': 'наука',
    'sport': 'спорт',
    'culture': 'культура',
}

def home(request):
    """
    Главная страница с лентой новостей из Feed Service.
    """
    category = request.GET.get('category', 'general')
    query = request.GET.get('q', '').strip()
    page = int(request.GET.get('page', 1))
    size = int(request.GET.get('size', 20))

    feed_category = CATEGORY_MAP.get(category)

    # Получаем ленту новостей из Feed Service
    feed_client = get_feed_client()
    feed_data = feed_client.get_feed(
        category=feed_category,
        query=query if query else None,
        page=page,
        size=size
    )
    
    articles = feed_data.get('items', [])
    # Добавляем дефолтный source, если его нет
    for article in articles:
        if 'source' not in article or not article.get('source'):
            article['source'] = {'name': 'Lenta.ru'}
        elif not article['source'].get('name'):
            article['source']['name'] = 'Lenta.ru'
    total_news = feed_data.get('total', 0)
    
    # Категории для отображения
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
        
        # Получаем URL избранных статей
        favorite_urls = user_content_client.get_favorite_urls(request.user.id)
        
        # Получаем реакции для всех статей на странице
        urls = [a.get('url') for a in articles if a.get('url')]
        if urls:
            user_reactions, reactions_count = reactions_client.get_user_reactions_for_urls(
                request.user.id, urls
            )

    context = {
        'articles': articles,
        'current_category': category,
        'categories': categories,
        'query': query,
        'favorite_urls': favorite_urls,
        'user_reactions': user_reactions,
        'reactions_count': reactions_count,
        'total_news': total_news,
        'page': page,
        'size': size,
    }

    return render(request, 'news/home.html', context)


@login_required
def favorites(request):
    """
    Страница избранных статей пользователя из User Content Service.
    """
    user_content_client = get_user_content_client()
    
    # Получаем избранные статьи с комментариями
    favorites_data = user_content_client.get_favorites_with_comments(request.user.id)
    
    # Преобразуем данные для шаблона
    articles_with_comments = []
    for item in favorites_data:
        articles_with_comments.append({
            'article': item,
            'comments': item.get('comments', [])
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
@csrf_exempt
def toggle_favorite(request):
    """
    API endpoint для добавления/удаления статьи из избранного.
    Работает через User Content Service.
    """
    try:
        data = json.loads(request.body)
        print(f"Received data: {data}")

         # Получаем source_name с дефолтным значением
        source = data.get('source', {})
        source_name = source.get('name', '')
        
        # Если source_name пустой, используем значение по умолчанию
        if not source_name or source_name.strip() == '':
            source_name = 'Lenta.ru'
        
         # Получаем urlToImage, если пусто - None
        url_to_image = data.get('urlToImage') or data.get('image', '')
        if not url_to_image or url_to_image.strip() == '':
            url_to_image = None
        
        # Получаем published_at, если пусто - None
        published_at = data.get('publishedAt')
        if not published_at or published_at.strip() == '':
            published_at = None
        
        # Получаем title, если пусто - дефолтное значение
        title = data.get('title', '')
        if not title or title.strip() == '':
            title = 'Новость без заголовка'
        
        # Извлекаем данные статьи
        article_data = {
            'url': data.get('url'),
            'title': title,
            'description': data.get('description', ''),
            'url_to_image': url_to_image,
            'source_name': source_name,
            'published_at': published_at,
        }
        print(f"Sending to service: {article_data}")
        
        user_content_client = get_user_content_client()
        result = user_content_client.toggle_favorite(request.user.id, article_data)
        
        return JsonResponse(result, status=result.get('status', 200))
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def add_reaction(request):
    """
    API endpoint для добавления/изменения/удаления реакции на новость.
    Работает через Reactions Service.
    """
    try:
        data = json.loads(request.body)
        article_url = data.get('url')
        reaction_type = data.get('reaction_type')
        
        if not article_url or not reaction_type:
            return JsonResponse(
                {'success': False, 'error': 'Missing url or reaction_type'},
                status=400
            )
        
        reactions_client = get_reactions_client()
        result = reactions_client.toggle_reaction(
            request.user.id,
            article_url,
            reaction_type
        )
        
        # Получаем обновлённые счётчики для этой новости
        if result.get('success'):
            counts = reactions_client.get_reaction_counts(article_url)
            result['reactions_count'] = counts
        
        return JsonResponse(result, status=result.get('status', 200))
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def add_comment(request):
    """
    API endpoint для добавления комментария к избранной статье.
    Работает через User Content Service.
    """
    try:
        data = json.loads(request.body)
        article_id = data.get('article_id')
        text = data.get('text', '').strip()
        
        if not article_id:
            return JsonResponse(
                {'success': False, 'error': 'Missing article_id'},
                status=400
            )
        
        if not text:
            return JsonResponse(
                {'success': False, 'error': 'Comment text is empty'},
                status=400
            )
        
        user_content_client = get_user_content_client()
        result = user_content_client.add_comment(
            request.user.id,
            article_id,
            text
        )
        
        # Форматируем дату для отображения
        if result.get('success') and result.get('comment'):
            from datetime import datetime
            comment = result['comment']
            if comment.get('created_at'):
                dt = datetime.fromisoformat(comment['created_at'].replace('Z', '+00:00'))
                comment['created_at'] = dt.strftime('%d.%m.%Y %H:%M')
        
        return JsonResponse(result, status=result.get('status', 200))
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def edit_comment(request, comment_id):
    """
    API endpoint для редактирования комментария.
    Работает через User Content Service.
    """
    try:
        data = json.loads(request.body)
        text = data.get('text', '').strip()
        
        if not text:
            return JsonResponse(
                {'success': False, 'error': 'Comment text is empty'},
                status=400
            )
        
        user_content_client = get_user_content_client()
        result = user_content_client.edit_comment(
            request.user.id,
            comment_id,
            text
        )
        
        # Форматируем дату для отображения
        if result.get('success') and result.get('comment'):
            from datetime import datetime
            comment = result['comment']
            if comment.get('created_at'):
                dt = datetime.fromisoformat(comment['created_at'].replace('Z', '+00:00'))
                comment['created_at'] = dt.strftime('%d.%m.%Y %H:%M')
        
        return JsonResponse(result, status=result.get('status', 200))
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def delete_comment(request, comment_id):
    """
    API endpoint для удаления комментария.
    Работает через User Content Service.
    """
    try:
        user_content_client = get_user_content_client()
        result = user_content_client.delete_comment(
            request.user.id,
            comment_id
        )
        
        return JsonResponse(result, status=result.get('status', 200))
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ============ Дополнительные эндпоинты для администрирования ============

@login_required
def admin_stats(request):
    """
    Страница со статистикой из всех микросервисов (только для суперпользователя)
    """
    if not request.user.is_superuser:
        messages.error(request, 'Доступ запрещён')
        return redirect('news:home')
    
    feed_client = get_feed_client()
    reactions_client = get_reactions_client()
    user_content_client = get_user_content_client()
    
    context = {
        'feed_stats': feed_client.get_stats(),
        'reactions_service': {
            'url': REACTIONS_SERVICE_URL,
            'status': 'checking...'
        },
        'user_content_service': {
            'url': USER_CONTENT_SERVICE_URL,
            'status': 'checking...'
        }
    }
    
    # Проверяем здоровье сервисов
    try:
        import requests
        resp = requests.get(f"{REACTIONS_SERVICE_URL}/", timeout=2)
        context['reactions_service']['status'] = 'healthy' if resp.status_code == 200 else 'unhealthy'
    except:
        context['reactions_service']['status'] = 'unreachable'
    
    try:
        resp = requests.get(f"{USER_CONTENT_SERVICE_URL}/internal/health", timeout=2)
        context['user_content_service']['status'] = 'healthy' if resp.status_code == 200 else 'unhealthy'
    except:
        context['user_content_service']['status'] = 'unreachable'
    
    return render(request, 'news/admin_stats.html', context)