from django.contrib import admin
from .models import FavoriteArticle, Comment, RSSNews, Reaction

@admin.register(FavoriteArticle)
class FavoriteArticleAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'source_name', 'added_at']
    list_filter = ['source_name', 'added_at']
    search_fields = ['title', 'description', 'note']
    readonly_fields = ['added_at']


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['user', 'article', 'text_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = ['text', 'user__username']
    readonly_fields = ['created_at']

    def text_preview(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    
    text_preview.short_description = 'Текст комментария'


@admin.register(RSSNews)
class RSSNewsAdmin(admin.ModelAdmin):
    list_display = ['title', 'source', 'category', 'published_at', 'created_at']
    list_filter = ['category', 'source', 'published_at']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at']


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'reaction_type', 'article_url_preview', 'created_at']
    list_filter = ['reaction_type', 'created_at']
    search_fields = ['user__username', 'article_url']
    readonly_fields = ['created_at']
    
    def article_url_preview(self, obj):
        return obj.article_url[:50] + '...' if len(obj.article_url) > 50 else obj.article_url
    
    article_url_preview.short_description = 'Ссылка на статью'