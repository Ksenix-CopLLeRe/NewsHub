"""
Шаблонные теги для работы с данными из микросервисов
"""

from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Получить значение из словаря по ключу.
    Использование: {{ dict|get_item:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def get_reaction_emoji(reaction_type):
    """
    Получить эмодзи для типа реакции
    """
    emojis = {
        'important': '🔥',
        'interesting': '🤔',
        'shocking': '😱',
        'useful': '💡',
        'liked': '❤️'
    }
    return emojis.get(reaction_type, '❓')


@register.filter
def format_date_ru(date_str):
    """
    Форматирует дату в русский формат
    """
    if not date_str:
        return ''
    
    try:
        from datetime import datetime
        # Парсим ISO формат
        if 'T' in date_str:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(date_str)
        
        # Форматируем
        return dt.strftime('%d.%m.%Y %H:%M')
    except:
        return date_str


@register.filter
def reaction_counts_json(reactions_count):
    """
    Преобразует счётчики реакций в JSON для JavaScript
    """
    if not reactions_count:
        return '{}'
    return mark_safe(json.dumps(reactions_count))


@register.filter
def reaction_type_class(reaction_type):
    """
    Возвращает CSS класс для кнопки реакции
    """
    classes = {
        'important': 'reaction-important',
        'interesting': 'reaction-interesting',
        'shocking': 'reaction-shocking',
        'useful': 'reaction-useful',
        'liked': 'reaction-liked'
    }
    return classes.get(reaction_type, 'reaction-default')


@register.simple_tag
def get_reaction_count(reactions_count, reaction_type):
    """
    Получить количество реакций определённого типа
    """
    if not reactions_count:
        return 0
    return reactions_count.get(reaction_type, 0)


@register.simple_tag
def total_reactions(reactions_count):
    """
    Получить общее количество реакций
    """
    if not reactions_count:
        return 0
    return sum(reactions_count.values())