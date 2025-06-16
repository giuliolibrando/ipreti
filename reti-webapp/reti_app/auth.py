from django.contrib.auth.backends import ModelBackend
from django_auth_ldap.backend import LDAPBackend
from django.contrib.auth.models import User
from django.utils.translation import gettext as _


class UserDisabledException(Exception):
    """Eccezione personalizzata per utente disabilitato"""
    pass


class RootOrLDAPBackend(LDAPBackend):
    """
    Backend di autenticazione personalizzato che:
    1. Usa solo ModelBackend (autenticazione locale) per l'utente "root"
    2. Utilizza l'autenticazione LDAP per tutti gli altri utenti
    3. Controlla il flag login_enabled nel profilo utente
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Se l'username è "root", non provare a usare LDAP
        if username == 'root':
            # Delega l'autenticazione al ModelBackend (gestirà il superuser locale)
            return None  # Ritorna None per permettere al ModelBackend di processare l'autenticazione
        
        # Per tutti gli altri utenti, usa il backend LDAP standard
        user = super().authenticate(request, username, password, **kwargs)
        
        # Se l'autenticazione LDAP è riuscita, controlla il flag login_enabled
        if user is not None:
            # Importa qui per evitare dipendenze circolari
            from .models import UserProfile
            
            try:
                # Controlla se l'utente ha un profilo e se il login è abilitato
                profile = user.profile
                if not profile.login_enabled:
                    # Aggiungi un attributo speciale per distinguere il tipo di errore
                    if hasattr(request, 'session'):
                        request.session['login_error_type'] = 'user_disabled'
                    return None  # Blocca il login se il flag è disabilitato
            except UserProfile.DoesNotExist:
                # Se non esiste un profilo, crealo con login disabilitato di default
                # tranne per admin, staff e superuser
                login_enabled = user.is_staff or user.is_superuser or user.username == 'root'
                UserProfile.objects.create(user=user, login_enabled=login_enabled)
                if not login_enabled:
                    if hasattr(request, 'session'):
                        request.session['login_error_type'] = 'user_disabled'
                    return None
        
        return user 