from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel, PageChooserPanel
from wagtail.models import Page


class Menu(models.Model):
    """
    Модель меню - контейнер для пунктов меню.
    
    Примеры: "Главное меню", "Меню в футере", "Мобильное меню"
    """
    name = models.CharField(
        max_length=255,
        verbose_name=_("Название меню"),
        help_text=_("Внутреннее название для идентификации меню")
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        verbose_name=_("Слаг"),
        help_text=_("Уникальный идентификатор для использования в шаблонах (например, 'main_menu')")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Активно"),
        help_text=_("Если отключено, меню не будет отображаться на сайте")
    )

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("name"),
                FieldPanel("slug"),
            ],
            heading=_("Настройки меню"),
        ),
        InlinePanel(
            "menu_items",
            label=_("Пункты меню"),
            help_text=_("Добавьте пункты меню. Для создания подменю укажите родительский пункт."),
        ),
    ]

    class Meta:
        verbose_name = _("Меню")
        verbose_name_plural = _("Меню")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_active_items(self):
        """Возвращает только активные пункты верхнего уровня"""
        return self.menu_items.filter(parent__isnull=True)


class MenuItem(models.Model):
    """
    Пункт меню. Поддерживает неограниченную вложенность через parent.
    Аналог nav_menu_item в WordPress.
    
    Типы ссылок:
    - page: страница Wagtail
    - custom: внешний URL
    - anchor: якорная ссылка (внутренняя)
    """
    
    LINK_TYPE_CHOICES = [
        ('page', _('Страница сайта')),
        ('custom', _('Внешний URL')),
        ('anchor', _('Якорная ссылка')),
    ]
    
    menu = models.ForeignKey(
        Menu,
        on_delete=models.CASCADE,
        related_name="menu_items",
        verbose_name=_("Меню")
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("Родительский пункт"),
        help_text=_("Выберите родительский пункт для создания подменю")
    )
    link_type = models.CharField(
        max_length=20,
        choices=LINK_TYPE_CHOICES,
        default='page',
        verbose_name=_("Тип ссылки"),
        help_text=_("Выберите тип ссылки: страница, внешний URL или якорь")
    )
    page = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("Страница"),
        help_text=_("Выберите страницу Wagtail для ссылки (для типа 'Страница сайта')")
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Заголовок"),
        help_text=_("Текст пункта меню. Если не указан, будет использован заголовок страницы")
    )
    url = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("URL"),
        help_text=_(
            "Внешний URL (например, 'https://example.com') или якорь (например, '#contacts' или '/page#anchor')"
        )
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Порядок отображения")
    )
    open_in_new_tab = models.BooleanField(
        default=False,
        verbose_name=_("Открывать в новой вкладке"),
        help_text=_("Открывать ссылку в новой вкладке/окне")
    )

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("link_type"),
                PageChooserPanel("page"),
                FieldPanel("url"),
                FieldPanel("title"),
            ],
            heading=_("Ссылка"),
        ),
        MultiFieldPanel(
            [
                FieldPanel("parent"),
                FieldPanel("sort_order"),
                FieldPanel("open_in_new_tab"),
            ],
            heading=_("Настройки"),
        ),
    ]

    class Meta:
        verbose_name = _("Пункт меню")
        verbose_name_plural = _("Пункты меню")
        ordering = ["sort_order", "title"]

    def __str__(self):
        return self.get_title()

    def clean(self):
        """Валидация пункта меню"""
        # Нельзя ссылаться на себя как на родителя
        if self.parent and self.parent.pk == self.pk:
            raise ValidationError({
                "parent": _("Пункт меню не может быть родителем самого себя")
            })
        
        # Проверка на циклическую ссылку
        if self.parent:
            ancestor = self.parent
            while ancestor:
                if ancestor.pk == self.pk:
                    raise ValidationError({
                        "parent": _("Обнаружена циклическая ссылка в структуре меню")
                    })
                ancestor = ancestor.parent
        
        # Для типа 'page' страница обязательна
        if self.link_type == 'page' and not self.page:
            raise ValidationError({
                "page": _("Для типа ссылки 'Страница сайта' необходимо выбрать страницу")
            })
        
        # Для типа 'custom' или 'anchor' URL обязателен
        if self.link_type in ('custom', 'anchor') and not self.url:
            raise ValidationError({
                "url": _("Для типа ссылки '{}' необходимо указать URL".format(self.get_link_type_display()))
            })
        
        # Проверка: страница должна быть опубликована
        if self.page and not self.page.live:
            raise ValidationError({
                "page": _("Выбранная страница не опубликована")
            })

    def get_url(self):
        """
        Возвращает URL пункта меню в зависимости от типа ссылки.
        """
        if self.link_type == 'page':
            if self.page:
                return self.page.url
            return "#"
        elif self.link_type == 'custom':
            return self.url or "#"
        elif self.link_type == 'anchor':
            if self.url:
                # Если якорь начинается с #, возвращаем как есть
                if self.url.startswith('#'):
                    return self.url
                # Если это полный путь с якорем (например, /page/#anchor)
                return self.url
            return "#"
        return "#"

    def get_title(self):
        """
        Возвращает заголовок пункта меню.
        Если title не задан, использует заголовок связанной страницы.
        """
        if self.title:
            return self.title
        if self.page:
            return self.page.title
        return self.url or "Без названия"

    def has_children(self):
        """Проверяет наличие активных дочерних элементов"""
        return self.children.exists()

    def get_children(self):
        """Возвращает дочерних элементов, отсортированных по порядку"""
        return self.children.order_by("sort_order")
