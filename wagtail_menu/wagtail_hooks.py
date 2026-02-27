from django.urls import path, include
from django.utils.translation import gettext_lazy as _

from wagtail import hooks
from wagtail.admin.menu import MenuItem as WagtailMenuItem

from wagtail_menu import views


@hooks.register('register_admin_menu_item')
def register_menus_menu():
    """Регистрация пункта меню в админке"""
    return WagtailMenuItem(
        label=_('Menus'),
        url='/admin/menus/',
        icon_name='list-ul',
        order=500,
    )


@hooks.register('register_admin_urls')
def register_admin_urls():
    """Регистрация URL для управления меню"""
    return [
        path('menus/', include((
            [
                path('', views.menu_index, name='menu_index'),
                path('create/', views.menu_create, name='menu_create'),
                path('<int:pk>/', views.menu_edit, name='menu_edit'),
                path('<int:pk>/delete/', views.menu_delete, name='menu_delete'),
                path('<int:menu_pk>/items/create/', views.menu_item_create, name='menu_item_create'),
                path('<int:menu_pk>/items/<int:item_pk>/', views.menu_item_edit, name='menu_item_edit'),
                path('<int:menu_pk>/items/<int:item_pk>/delete/', views.menu_item_delete, name='menu_item_delete'),
                path('<int:menu_pk>/items/<int:item_pk>/move/<str:direction>/', views.menu_item_move, name='menu_item_move'),
                # AJAX endpoints
                path('<int:menu_pk>/items/<int:item_pk>/move-ajax/<str:direction>/', views.menu_item_move_ajax, name='menu_item_move_ajax'),
                path('<int:menu_pk>/items/reorder-ajax/', views.menu_item_reorder_ajax, name='menu_item_reorder_ajax'),
            ],
            'wagtail_menu',
        ))),
    ]
