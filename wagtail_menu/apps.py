from django.apps import AppConfig


class WagtailMenuConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "wagtail_menu"
    verbose_name = "Меню сайта"
    label = "wagtail_menu"
