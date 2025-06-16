from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class RetiAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reti_app'
    verbose_name = _('IP Network Management') 