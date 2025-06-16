from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('health/', views.health_check, name='health_check'),
    path('ips/', views.indirizzi_ip_list, name='indirizzi_ip_list'),
    path('ips/assigned/', views.indirizzi_ip_assegnati, name='indirizzi_ip_assegnati'),
    path('ips/assigned-not-used/', views.ip_assegnati_non_usati, name='ip_assegnati_non_usati'),
    path('ips/expiring/', views.ip_in_scadenza_admin, name='ip_in_scadenza_admin'),
    path('ips/management/', views.gestione_indirizzi_ip, name='gestione_indirizzi_ip'),
    path('ips/request/', views.richiedi_nuovo_ip, name='richiedi_nuovo_ip'),
    path('ips/release/<str:ip>/', views.rilascia_ip, name='rilascia_ip'),
    path('ips/<str:ip>/', views.indirizzo_ip_detail, name='indirizzo_ip_detail'),
    path('search/', views.ricerca_indirizzo, name='ricerca_indirizzo'),
    path('vlans/', views.vlan_list, name='vlan_list'),
    path('vlans/<int:vlan_numero>/', views.vlan_detail, name='vlan_detail'),
    path('profile/', views.profilo_utente, name='profilo_utente'),
    path('api/check-ip/', views.check_ip_availability, name='check_ip_availability'),
] 