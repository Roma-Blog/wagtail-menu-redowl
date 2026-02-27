from django import template
from django.template.loader import get_template

from wagtail_menu.models import Menu

register = template.Library()


@register.simple_tag(takes_context=True)
def render_menu(context, slug, template='wagtail_menu/menu.html', max_depth=4):
    """
    Шаблонный тег для отображения меню.
    
    Использование:
        {% load menu_tags %}
        {% render_menu 'main_menu' %}
        {% render_menu 'main_menu' template='menu/custom.html' %}
        {% render_menu 'main_menu' max_depth=2 %}
    
    Args:
        slug: Слаг меню (например, 'main_menu')
        template: Шаблон для рендеринга
        max_depth: Максимальная глубина вложенности
    """
    try:
        menu = Menu.objects.prefetch_related('menu_items__children').get(slug=slug)
    except Menu.DoesNotExist:
        return ''
    
    # Получаем пункты верхнего уровня
    top_level_items = menu.menu_items.filter(parent__isnull=True).order_by('sort_order')
    
    # Строим дерево
    menu_tree = build_menu_tree(top_level_items, max_depth=max_depth)
    
    # Рендерим шаблон
    t = get_template(template)
    return t.render({
        'menu': menu,
        'menu_items': menu_tree,
        'request': context.get('request'),
    })


def build_menu_tree(items, max_depth=4, current_depth=1):
    """
    Рекурсивно строит дерево меню с дочерними элементами.
    
    Args:
        items: QuerySet пунктов меню
        max_depth: Максимальная глубина
        current_depth: Текущая глубина
    
    Returns:
        Список словарей с пунктами меню и их детьми
    """
    tree = []
    
    for item in items:
        menu_item = {
            'item': item,
            'title': item.get_title(),
            'url': item.get_url(),
            'open_in_new_tab': item.open_in_new_tab,
            'css_class': item.css_class if hasattr(item, 'css_class') else '',
            'has_children': False,
            'children': [],
            'level': current_depth,
        }
        
        # Добавляем детей, если не достигли макс. глубины
        if current_depth < max_depth:
            children = item.get_children()
            if children.exists():
                menu_item['has_children'] = True
                menu_item['children'] = build_menu_tree(
                    children, 
                    max_depth=max_depth, 
                    current_depth=current_depth + 1
                )
        
        tree.append(menu_item)
    
    return tree


@register.simple_tag
def get_menu(slug):
    """
    Возвращает объект меню по слагu.
    
    Использование:
        {% get_menu 'main_menu' as menu %}
    """
    try:
        return Menu.objects.get(slug=slug)
    except Menu.DoesNotExist:
        return None


@register.filter
def filter_children(all_items, parent_item):
    """
    Фильтрует детей для конкретного пункта меню.
    Использование: {% with children=all_items|filter_children:item %}
    """
    return [item for item in all_items if item.parent_id == parent_item.pk]
