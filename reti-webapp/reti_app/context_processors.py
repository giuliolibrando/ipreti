from django.conf import settings


def app_settings(request):
    """
    Context processor che rende disponibili alcune impostazioni nei template
    """
    return {
        'settings': {
            'FOOTER_TEXT': settings.FOOTER_TEXT,
        }
    } 