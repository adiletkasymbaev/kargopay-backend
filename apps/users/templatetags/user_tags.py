from django import template

register = template.Library()


@register.filter
def split(value, arg=','):
    """Разбивает строку на список по разделителю"""
    if not value:
        return []
    return value.split(arg)


@register.filter
def length(value):
    """Возвращает длину списка или строки"""
    if not value:
        return 0
    return len(value)
