from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Получить значение из словаря по ключу"""
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def get_nested_item(dictionary, key_path):
    """Получить значение из вложенного словаря по пути ключей (например, 'key1.key2')"""
    if dictionary is None:
        return None
    keys = key_path.split('.')
    value = dictionary
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
            if value is None:
                return None
        else:
            return None
    return value

