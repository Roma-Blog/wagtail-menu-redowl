from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.forms import formset_factory
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from wagtail.admin import messages as wagtail_messages

from wagtail_menu.models import Menu, MenuItem
from wagtail_menu.forms import MenuForm, MenuItemForm


def menu_index(request):
    """
    Список всех меню.
    """
    menus = Menu.objects.all().prefetch_related('menu_items').order_by('name')
    
    context = {
        'menus': menus,
    }
    return render(request, 'wagtail_menu/admin/menu_index.html', context)


def menu_create(request):
    """
    Создание нового меню.
    """
    if request.method == 'POST':
        form = MenuForm(request.POST)
        if form.is_valid():
            menu = form.save()
            wagtail_messages.success(request, _("Menu '%(name)s' created.") % {'name': menu.name})
            return redirect('wagtail_menu:menu_edit', pk=menu.pk)
    else:
        form = MenuForm()
    
    context = {
        'form': form,
        'title': _('Create Menu'),
        'action': 'create',
    }
    return render(request, 'wagtail_menu/admin/menu_form.html', context)


def menu_edit(request, pk):
    """
    Редактирование меню с пунктами.
    """
    menu = get_object_or_404(Menu, pk=pk)
    
    if request.method == 'POST':
        form = MenuForm(request.POST, instance=menu)
        
        # Получаем данные для пунктов меню из POST
        item_forms_data = []
        for key, value in request.POST.items():
            if key.startswith('item_'):
                item_id = key.replace('item_', '')
                item_forms_data.append((item_id, value))
        
        if form.is_valid():
            form.save()
            
            # Обрабатываем пункты меню
            process_menu_items(request, menu)
            
            wagtail_messages.success(request, _("Menu '%(name)s' updated.") % {'name': menu.name})
            return redirect('wagtail_menu:menu_edit', pk=menu.pk)
    else:
        form = MenuForm(instance=menu)
    
    # Получаем все пункты меню, отсортированные по дереву
    menu_items = get_menu_items_tree(menu)
    
    context = {
        'form': form,
        'menu': menu,
        'menu_items': menu_items,
        'title': _('Edit Menu: %(name)s') % {'name': menu.name},
    }
    return render(request, 'wagtail_menu/admin/menu_edit.html', context)


def menu_delete(request, pk):
    """
    Удаление меню.
    """
    menu = get_object_or_404(Menu, pk=pk)
    
    if request.method == 'POST':
        menu_name = menu.name
        menu.delete()
        wagtail_messages.success(request, _("Menu '%(name)s' deleted.") % {'name': menu_name})
        return redirect('wagtail_menu:menu_index')
    
    context = {
        'menu': menu,
        'title': _('Delete Menu'),
    }
    return render(request, 'wagtail_menu/admin/menu_delete.html', context)


def menu_item_create(request, menu_pk):
    """
    Создание нового пункта меню.
    """
    menu = get_object_or_404(Menu, pk=menu_pk)
    
    if request.method == 'POST':
        form = MenuItemForm(request.POST, menu=menu)
        if form.is_valid():
            item = form.save(commit=False)
            item.menu = menu
            item.save()
            wagtail_messages.success(request, _("Menu item created."))
            return redirect('wagtail_menu:menu_edit', pk=menu.pk)
    else:
        form = MenuItemForm(menu=menu)
    
    context = {
        'form': form,
        'menu': menu,
        'title': _('Add Menu Item'),
        'action': 'create',
    }
    return render(request, 'wagtail_menu/admin/menu_item_form.html', context)


def menu_item_edit(request, menu_pk, item_pk):
    """
    Редактирование пункта меню.
    """
    menu = get_object_or_404(Menu, pk=menu_pk)
    item = get_object_or_404(MenuItem, pk=item_pk, menu=menu)
    
    if request.method == 'POST':
        form = MenuItemForm(request.POST, instance=item, menu=menu, exclude_item=item)
        if form.is_valid():
            form.save()
            wagtail_messages.success(request, _("Menu item updated."))
            return redirect('wagtail_menu:menu_edit', pk=menu.pk)
    else:
        form = MenuItemForm(instance=item, menu=menu, exclude_item=item)
    
    context = {
        'form': form,
        'menu': menu,
        'item': item,
        'title': _('Edit Menu Item'),
        'action': 'edit',
    }
    return render(request, 'wagtail_menu/admin/menu_item_form.html', context)


def menu_item_delete(request, menu_pk, item_pk):
    """
    Удаление пункта меню.
    """
    menu = get_object_or_404(Menu, pk=menu_pk)
    item = get_object_or_404(MenuItem, pk=item_pk, menu=menu)
    
    if request.method == 'POST':
        item.delete()
        wagtail_messages.success(request, _("Menu item deleted."))
        return redirect('wagtail_menu:menu_edit', pk=menu.pk)
    
    context = {
        'menu': menu,
        'item': item,
        'title': _('Delete Menu Item'),
    }
    return render(request, 'wagtail_menu/admin/menu_item_delete.html', context)


def menu_item_move(request, menu_pk, item_pk, direction):
    """
    Перемещение пункта меню вверх/вниз.
    direction: 'up' или 'down'
    """
    menu = get_object_or_404(Menu, pk=menu_pk)
    item = get_object_or_404(MenuItem, pk=item_pk, menu=menu)
    
    # Получаем siblings (пункты с тем же родителем)
    siblings = MenuItem.objects.filter(parent=item.parent, menu=menu).order_by('sort_order')
    siblings_list = list(siblings)
    
    current_index = siblings_list.index(item)
    
    if direction == 'up' and current_index > 0:
        # Меняем местами с предыдущим
        prev_item = siblings_list[current_index - 1]
        item.sort_order, prev_item.sort_order = prev_item.sort_order, item.sort_order
        item.save()
        prev_item.save()
        wagtail_messages.success(request, _("Menu item moved up."))
    elif direction == 'down' and current_index < len(siblings_list) - 1:
        # Меняем местами со следующим
        next_item = siblings_list[current_index + 1]
        item.sort_order, next_item.sort_order = next_item.sort_order, item.sort_order
        item.save()
        next_item.save()
        wagtail_messages.success(request, _("Menu item moved down."))
    
    return redirect('wagtail_menu:menu_edit', pk=menu.pk)


def process_menu_items(request, menu):
    """
    Обработка данных пунктов меню при сохранении.
    """
    # Получаем все item_id из POST
    item_ids = request.POST.getlist('item_id[]')
    
    for item_id in item_ids:
        try:
            item = MenuItem.objects.get(pk=item_id, menu=menu)
            
            # Обновляем sort_order из data-атрибута
            sort_order_key = f'sort_order_{item_id}'
            if sort_order_key in request.POST:
                item.sort_order = int(request.POST[sort_order_key])
                item.save()
        except MenuItem.DoesNotExist:
            continue


def get_menu_items_tree(menu):
    """
    Возвращает пункты меню в виде дерева с отступами.
    """
    items = MenuItem.objects.filter(menu=menu).order_by('sort_order', 'title')

    def build_tree(parent=None, level=0):
        tree = []
        children = items.filter(parent=parent)
        for child in children:
            child.level = level
            child.indent = level * 20  # Для CSS отступа
            tree.append(child)
            # Рекурсивно добавляем потомков (максимум 4 уровня)
            if level < 3:
                tree.extend(build_tree(parent=child, level=level + 1))
        return tree

    return build_tree()


@require_POST
def menu_item_move_ajax(request, menu_pk, item_pk, direction):
    """
    AJAX перемещение пункта меню вверх/вниз без перезагрузки.
    direction: 'up' или 'down'
    """
    menu = get_object_or_404(Menu, pk=menu_pk)
    item = get_object_or_404(MenuItem, pk=item_pk, menu=menu)

    # Получаем siblings (пункты с тем же родителем)
    siblings = MenuItem.objects.filter(parent=item.parent, menu=menu).order_by('sort_order', 'pk')
    siblings_list = list(siblings)

    current_index = siblings_list.index(item)

    if direction == 'up' and current_index > 0:
        # Перемещаем элемент вверх: удаляем и вставляем на новую позицию
        prev_index = current_index - 1
        
        # Пересчитываем sort_order для всех элементов
        for i, sibling in enumerate(siblings_list):
            if i == prev_index:
                sibling.sort_order = current_index
            elif i == current_index:
                sibling.sort_order = prev_index
            else:
                sibling.sort_order = i
            sibling.save()

        return JsonResponse({
            'success': True,
            'message': _('Item moved up'),
            'new_order': [s.pk for s in siblings_list]
        })
    elif direction == 'down' and current_index < len(siblings_list) - 1:
        # Перемещаем элемент вниз: удаляем и вставляем на новую позицию
        next_index = current_index + 1
        
        # Пересчитываем sort_order для всех элементов
        for i, sibling in enumerate(siblings_list):
            if i == next_index:
                sibling.sort_order = current_index
            elif i == current_index:
                sibling.sort_order = next_index
            else:
                sibling.sort_order = i
            sibling.save()

        return JsonResponse({
            'success': True,
            'message': _('Item moved down'),
            'new_order': [s.pk for s in siblings_list]
        })

    return JsonResponse({
        'success': False,
        'message': _('Cannot move item')
    }, status=400)


@require_POST
def menu_item_reorder_ajax(request, menu_pk):
    """
    AJAX обновление порядка пунктов меню.
    Ожидает JSON: {'items': [{'id': 1, 'sort_order': 0}, ...]}
    """
    menu = get_object_or_404(Menu, pk=menu_pk)
    
    try:
        import json
        data = json.loads(request.body)
        items_data = data.get('items', [])
        
        for item_data in items_data:
            item_id = item_data.get('id')
            sort_order = item_data.get('sort_order')
            
            if item_id and sort_order is not None:
                try:
                    item = MenuItem.objects.get(pk=item_id, menu=menu)
                    item.sort_order = sort_order
                    item.save()
                except MenuItem.DoesNotExist:
                    continue
        
        return JsonResponse({
            'success': True,
            'message': _('Order updated')
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)
