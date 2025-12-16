from django.db import models
from django.contrib.auth.models import User

class FavoriteArticle(models.Model):
    """
    Модель для хранения избранных статей пользователя.
    
    Позволяет пользователям сохранять интересные новости для последующего
    просмотра и комментирования. Каждый пользователь может добавить статью
    в избранное только один раз (уникальность по user и url).
    
    Attributes:
        user: Связь с пользователем (ForeignKey)
        title: Заголовок статьи
        description: Описание/краткое содержание
        url: Ссылка на оригинальную статью
        image_url: Ссылка на изображение статьи (опционально)
        source_name: Название источника новости
        published_at: Дата публикации статьи
        added_at: Дата добавления в избранное (автоматически)
        note: Личная заметка пользователя (опционально)
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='favorite_articles',
        verbose_name='Пользователь'
    )
    title = models.CharField(max_length=500, verbose_name='Заголовок')
    description = models.TextField(blank=True, verbose_name='Описание')
    url = models.URLField(verbose_name='Ссылка на статью')
    image_url = models.URLField(blank=True, verbose_name='Ссылка на изображение')
    source_name = models.CharField(max_length=200, verbose_name='Источник')
    published_at = models.DateTimeField(verbose_name='Дата публикации')
    added_at = models.DateTimeField(auto_now_add=True, verbose_name='Добавлено в избранное')
    note = models.TextField(blank=True, verbose_name='Личная заметка')

    class Meta:
        verbose_name = 'Избранная статья'
        verbose_name_plural = 'Избранные статьи'
        ordering = ['-added_at']
        unique_together = ['user', 'url']

    def __str__(self):
        return f"{self.user.username} - {self.title[:50]}"


class Comment(models.Model):
    """
    Модель для хранения комментариев к избранным статьям.
    
    Позволяет пользователям оставлять комментарии к сохраненным в избранном
    статьям. Комментарии видны только автору комментария.
    
    Attributes:
        article: Связь с избранной статьей (ForeignKey)
        user: Автор комментария (ForeignKey)
        text: Текст комментария
        created_at: Дата создания комментария (автоматически)
    """
    article = models.ForeignKey(
        FavoriteArticle,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Статья'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Автор'
    )
    text = models.TextField(verbose_name='Текст комментария')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.username} - {self.text[:30]}"


class RSSNews(models.Model):
    """
    Модель для кеширования новостей из RSS-ленты.
    
    Используется для хранения новостей, полученных из RSS-ленты Lenta.ru,
    что позволяет быстро получать новости даже при недоступности RSS-источника.
    Каждая новость хранится один раз (уникальность по url).
    
    Attributes:
        title: Заголовок новости
        description: Описание новости
        url: URL новости (уникальный)
        published_at: Дата публикации новости
        source: Источник новости (по умолчанию 'Lenta.ru')
        category: Категория новости (russia, world, economics, и т.д.)
        created_at: Дата добавления в БД (автоматически)
    """
    title = models.CharField(max_length=500, verbose_name='Заголовок')
    description = models.TextField(verbose_name='Описание')
    url = models.URLField(unique=True, verbose_name='Ссылка на статью')
    published_at = models.DateTimeField(verbose_name='Дата публикации')
    source = models.CharField(max_length=100, default='Lenta.ru', verbose_name='Источник')
    category = models.CharField(max_length=50, default='russia', verbose_name='Категория')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Добавлено в БД')
    
    class Meta:
        verbose_name = 'RSS Новость'
        verbose_name_plural = 'RSS Новости'
        ordering = ['-published_at']
    
    def __str__(self):
        return self.title


class Reaction(models.Model):
    """
    Модель для хранения эмоциональных реакций пользователей на новости.
    
    Позволяет пользователям выражать свое отношение к новостям через
    быстрые реакции. Каждый пользователь может поставить только одну
    реакцию на одну новость (уникальность по user и article_url).
    
    Attributes:
        user: Пользователь, поставивший реакцию (ForeignKey)
        article_url: URL новости, на которую поставлена реакция
        reaction_type: Тип реакции (выбор из REACTION_TYPES)
        created_at: Дата создания реакции (автоматически)
    
    Reaction Types:
        - important (🔥 важно)
        - interesting (🤔 интересно)
        - shocking (😱 шокирует)
        - useful (💡 полезно)
        - liked (❤️ нравится)
    """
    REACTION_TYPES = [
        ('important', '🔥 важно'),
        ('interesting', '🤔 интересно'),
        ('shocking', '😱 шокирует'),
        ('useful', '💡 полезно'),
        ('liked', '❤️ нравится'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reactions',
        verbose_name='Пользователь'
    )
    article_url = models.URLField(verbose_name='Ссылка на статью')
    reaction_type = models.CharField(
        max_length=20,
        choices=REACTION_TYPES,
        verbose_name='Тип реакции'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    
    class Meta:
        verbose_name = 'Реакция'
        verbose_name_plural = 'Реакции'
        unique_together = ['user', 'article_url']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_reaction_type_display()} - {self.article_url[:50]}"