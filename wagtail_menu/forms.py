from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from wagtail.admin.widgets.chooser import AdminPageChooser
from wagtail.models import Page

from wagtail_menu.models import Menu, MenuItem


class MenuForm(forms.ModelForm):
    """Форма для редактирования меню"""

    class Meta:
        model = Menu
        fields = ['name', 'slug']
        labels = {
            'name': _('Название меню'),
            'slug': _('Слаг'),
        }
        help_texts = {
            'name': _('Внутреннее название для идентификации меню'),
            'slug': _('Уникальный идентификатор для использования в шаблонах'),
        }


class MenuItemForm(forms.ModelForm):
    """Форма для редактирования пункта меню"""

    # Поле для выбора родителя с ограничением по глубине
    parent = forms.ModelChoiceField(
        queryset=MenuItem.objects.none(),
        required=False,
        label=_('Родительский пункт'),
        help_text=_('Выберите родительский пункт для создания подменю'),
        widget=forms.Select(attrs={'class': 'parent-selector'})
    )
    
    # Поле для выбора страницы с помощью PageChooser
    page = forms.ModelChoiceField(
        queryset=Page.objects.live(),
        required=False,
        label=_('Страница'),
        help_text=_('Выберите страницу Wagtail для ссылки (для типа "Страница сайта")'),
        widget=AdminPageChooser()
    )

    class Meta:
        model = MenuItem
        fields = [
            'parent', 'link_type', 'page', 'title', 'url',
            'sort_order', 'open_in_new_tab'
        ]
        labels = {
            'link_type': _('Тип ссылки'),
            'title': _('Заголовок'),
            'url': _('URL'),
            'sort_order': _('Порядок'),
            'open_in_new_tab': _('Открывать в новой вкладке'),
        }
        widgets = {
            'sort_order': forms.NumberInput(attrs={'class': 'sort-order-input', 'min': 0}),
        }

    def __init__(self, *args, **kwargs):
        self.menu = kwargs.pop('menu', None)
        self.exclude_item = kwargs.pop('exclude_item', None)
        super().__init__(*args, **kwargs)

        # Фильтруем родителей: только пункты текущего меню
        # Исключаем текущий пункт (нельзя быть родителем самому себе)
        queryset = MenuItem.objects.filter(menu=self.menu)
        if self.exclude_item and self.exclude_item.pk:
            queryset = queryset.exclude(pk=self.exclude_item.pk)

        self.fields['parent'].queryset = queryset

        # Устанавливаем начальное значение для link_type
        if self.instance.pk and not self.data.get('link_type'):
            self.fields['link_type'].initial = self.instance.link_type
        
        # Устанавливаем начальное значение для page
        if self.instance.pk and self.instance.page_id:
            self.fields['page'].initial = self.instance.page_id

        # Добавляем классы для JS
        self.fields['link_type'].widget.attrs['class'] = 'link-type-selector'
        self.fields['url'].widget.attrs['class'] = 'url-input'

    def clean(self):
        cleaned_data = super().clean()
        link_type = cleaned_data.get('link_type')
        page = cleaned_data.get('page')
        url = cleaned_data.get('url')
        parent = cleaned_data.get('parent')

        # Проверка: для типа 'page' страница обязательна
        if link_type == 'page' and not page:
            raise ValidationError({
                'page': _('Для типа ссылки "Страница сайта" необходимо выбрать страницу')
            })

        # Проверка: для типа 'custom' или 'anchor' URL обязателен
        if link_type in ('custom', 'anchor') and not url:
            raise ValidationError({
                'url': _('Для типа ссылки "{}" необходимо указать URL'.format(
                    self.fields['link_type'].choices[int(link_type == 'custom') + int(link_type == 'anchor') - 1][1]
                    if link_type in ('custom', 'anchor') else link_type
                ))
            })

        # Проверка: страница должна быть опубликована
        if page and not page.live:
            raise ValidationError({
                'page': _('Выбранная страница не опубликована')
            })

        # Проверка на циклическую ссылку
        if parent:
            ancestor = parent
            while ancestor:
                if ancestor.pk == self.instance.pk:
                    raise ValidationError({
                        'parent': _('Обнаружена циклическая ссылка в структуре меню')
                    })
                ancestor = ancestor.parent

        # Проверка глубины вложенности (максимум 4 уровня)
        if parent:
            depth = 1
            current = parent
            while current.parent:
                depth += 1
                current = current.parent
                if depth >= 4:
                    raise ValidationError({
                        'parent': _('Максимальная глубина вложенности — 4 уровня')
                    })

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Сохраняем связь с страницей
        if self.cleaned_data.get('page'):
            instance.page = self.cleaned_data['page']
        
        if commit:
            instance.save()
        
        return instance


class MenuItemFormSet(forms.BaseFormSet):
    """Формсет для управления коллекцией пунктов меню"""

    def __init__(self, *args, **kwargs):
        self.menu = kwargs.pop('menu', None)
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs['menu'] = self.menu
        # Исключаем текущий пункт из возможных родителей
        if self.forms[index].instance.pk:
            kwargs['exclude_item'] = self.forms[index].instance
        return kwargs
