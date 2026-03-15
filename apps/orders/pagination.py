from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import date, timedelta
from decimal import Decimal
from dateutil import parser as date_parser


class DateGroupedPagination(PageNumberPagination):
    """
    Пагинатор с группировкой по датам.
    Группирует результаты по категориям: "Сегодня", "Вчера", "7 дней назад", "Ранее"
    """
    page_size = 10
    max_page_size = 100
    page_size_query_param = 'page_size'
    
    def get_date_group(self, dt):
        """Определяет группу даты"""
        now = timezone.now()
        today = now.date()
        
        # Если dt это строка, парсим её
        if isinstance(dt, str):
            dt = date_parser.parse(dt)
        
        # Получаем дату из datetime
        dt_date = dt.date() if hasattr(dt, 'date') else dt
        
        if dt_date == today:
            return _('Сегодня')
        elif dt_date == today - timedelta(days=1):
            return _('Вчера')
        elif dt_date >= today - timedelta(days=6):
            days_ago = (today - dt_date).days
            return _('{days} дн. назад').format(days=days_ago)
        else:
            # Форматируем дату как "ДД.ММ.ГГГГ"
            return dt_date.strftime('%d.%m.%Y')
    
    def get_paginated_response(self, data):
        """Формирует ответ с группировкой по датам"""
        # Группируем результаты по датам
        grouped_results = {}
        date_order = []
        
        for item in data:
            # Получаем дату из created_at
            created_at = item.get('created_at')
            if created_at:
                date_group = self.get_date_group(created_at)
                
                if date_group not in grouped_results:
                    grouped_results[date_group] = []
                    date_order.append(date_group)
                
                grouped_results[date_group].append(item)
        
        # Формируем структуру ответа
        groups = []
        for group_name in date_order:
            groups.append({
                'date': group_name,
                'items': grouped_results[group_name]
            })
        
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'groups': groups,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
        })
