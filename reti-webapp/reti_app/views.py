from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Q, Count
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.translation import gettext as _
import ipaddress
import json
import logging
from datetime import timedelta

from .models import IndirizzoIP, Vlan
from .serializers import IndirizzoIPSerializer, VlanSerializer
from .forms import LoginForm, IndirizzoIPForm, FiltroIndirizziForm

# Inizializza logger
logger = logging.getLogger(__name__)

# Viste per API REST
class IndirizzoIPViewSet(viewsets.ModelViewSet):
    """
    API REST per la gestione degli indirizzi IP e VLAN

    Questa API fornisce endpoints per:

    ## 🌐 Indirizzi IP

    ### Endpoints principali:
    - `GET /api/ips/` - Lista tutti gli IP con filtri
    - `POST /api/ips/` - Crea nuovo IP
    - `GET /api/ips/{ip}/` - Dettaglio IP specifico
    - `PUT /api/ips/{ip}/` - Aggiorna completamente un IP
    - `PATCH /api/ips/{ip}/` - Aggiorna parzialmente un IP
    - `DELETE /api/ips/{ip}/` - Elimina un IP

    ### Endpoints speciali:
    - `GET /api/ips/getbyip/?title={ip}` - Compatibilità Drupal
    - `GET /api/ips/validate_ip_range/?ip={ip}` - Validazione range IP
    - `PATCH /api/ips/{ip}/update_stato/` - Aggiorna solo stato
    - `POST /api/ips/{ip}/aggiorna_controllo/` - Aggiorna ultimo controllo
    - `POST /api/ips/{ip}/aggiorna_scadenza/` - Aggiorna data scadenza
    - `POST /api/ips/{ip}/libera/` - Libera IP se scaduto
    
    ## Filtri Disponibili:
    - `stato`: attivo, disattivo
    - `disponibilita`: libero, usato  
    - `responsabile`: email responsabile
    - `mac_address`: MAC address
    - `vlan`: numero VLAN
    - `anomalo`: si/no per IP anomali
    - `scaduto`: si/no per IP scaduti
    
    ## Ordinamento:
    - `ordering`: ip, ultimo_controllo, data_modifica, data_scadenza
    
    ## Ricerca:
    - `search`: cerca in IP, utente_finale, note
    """
    queryset = IndirizzoIP.objects.all()
    serializer_class = IndirizzoIPSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['ip', 'stato', 'disponibilita', 'responsabile', 'mac_address', 'vlan']
    search_fields = ['ip', 'utente_finale', 'note']
    ordering_fields = ['ip', 'ultimo_controllo', 'data_modifica', 'data_scadenza']
    ordering = ['ip']  # Default ordering (sarà sostituito nel get_queryset)
    lookup_field = 'ip'
    lookup_value_regex = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
    permission_classes = [IsAuthenticatedOrReadOnly]  # Restored secure permissions
    
    def get_queryset(self):
        """Applica filtri aggiuntivi al queryset"""
        queryset = super().get_queryset()
        
        # Usa ordinamento numerico per IP se non è specificato un ordinamento personalizzato
        ordering = self.request.query_params.get('ordering', None)
        if not ordering or ordering == 'ip':
            # Applica ordinamento numerico per IP
            from django.db import connection
            if 'mysql' in connection.vendor:
                queryset = queryset.extra(
                    select={'ip_as_int': 'INET_ATON(ip)'}, 
                    order_by=['ip_as_int']
                )
            else:
                queryset = queryset.order_by('ip')
        
        # Filtro per IP anomali
        anomalo = self.request.query_params.get('anomalo', None)
        if anomalo == 'si':
            queryset = queryset.filter(
                stato='attivo'
            ).filter(
                Q(disponibilita='libero') | Q(responsabile__isnull=True) | Q(responsabile='')
            )
        elif anomalo == 'no':
            # Escludi IP anomali
            anomali_ids = []
            for ip in queryset:
                if ip.is_anomalo():
                    anomali_ids.append(ip.pk)
            queryset = queryset.exclude(pk__in=anomali_ids)
        
        # Filtro per IP scaduti
        scaduto = self.request.query_params.get('scaduto', None)
        if scaduto == 'si':
            scaduti_ids = []
            for ip in queryset:
                if ip.is_da_liberare_automaticamente():
                    scaduti_ids.append(ip.pk)
            queryset = queryset.filter(pk__in=scaduti_ids)
        elif scaduto == 'no':
            scaduti_ids = []
            for ip in queryset:
                if ip.is_da_liberare_automaticamente():
                    scaduti_ids.append(ip.pk)
            queryset = queryset.exclude(pk__in=scaduti_ids)
            
        # Filtro per VLAN
        vlan = self.request.query_params.get('vlan', None)
        if vlan:
            queryset = queryset.filter(vlan__numero=vlan)
            
        return queryset.select_related('vlan', 'assegnato_a_utente')
    
    def perform_create(self, serializer):
        """Personalizza la creazione di un nuovo IP"""
        # Trova automaticamente la VLAN per il nuovo IP
        ip_address = serializer.validated_data.get('ip')
        if ip_address and not serializer.validated_data.get('vlan'):
            vlan_trovata = Vlan.find_vlan_for_ip(ip_address)
            if vlan_trovata:
                serializer.validated_data['vlan'] = vlan_trovata
        
        # Imposta l'utente corrente come assegnato se è il responsabile
        if self.request.user.is_authenticated:
            responsabile = serializer.validated_data.get('responsabile')
            if responsabile == self.request.user.email:
                serializer.validated_data['assegnato_a_utente'] = self.request.user
                
        serializer.save()
    
    def perform_update(self, serializer):
        """Personalizza l'aggiornamento di un IP"""
        # Aggiorna ultimo_controllo se lo stato diventa attivo
        if serializer.validated_data.get('stato') == 'attivo':
            serializer.validated_data['ultimo_controllo'] = timezone.now()
            
        serializer.save()
    
    @action(detail=False, methods=['get'])
    def getbyip(self, request):
        """
        **Endpoint di compatibilità con il vecchio sistema Drupal.**
        
        Cerca un IP specifico usando il parametro 'title'.
        
        **Parametri:**
        - `title` (string): Indirizzo IP da cercare
        
        **Esempio:**
        ```
        GET /api/ips/getbyip/?title=192.168.1.100
        ```
        
        **Risposta:**
        ```json
        [{
            "nid": "192.168.1.100",
            "Stato": "attivo",
            "disponibilita": "usato",
            "Mac Address": "aa:bb:cc:dd:ee:ff",
            "ip": "192.168.1.100",
            "Mail responsabile": "user@uniroma1.it",
            "Note": "PC ufficio",
            "Utente finale": "Mario Rossi",
            "ultimo controllo": "2025-05-30 14:30:00",
            "data_scadenza": "2025-08-30 14:30:00",
            "is_anomalo": false,
            "is_scaduto": false,
            "ore_inattivita": 0,
            "stato_scadenza": "Nessuna"
        }]
        ```
        """
        ip = request.query_params.get('title', None)
        if ip:
            try:
                indirizzo = IndirizzoIP.objects.get(ip=ip)
                data = {
                    'nid': str(indirizzo.ip),
                    'Stato': indirizzo.stato,
                    'disponibilita': indirizzo.disponibilita,
                    'Mac Address': indirizzo.mac_address or '',
                    'ip': indirizzo.ip,
                    'Mail responsabile': indirizzo.responsabile or '',
                    'Note': indirizzo.note or '',
                    'Utente finale': indirizzo.utente_finale or '',
                    'ultimo controllo': indirizzo.ultimo_controllo.strftime('%Y-%m-%d %H:%M:%S'),
                    'data_scadenza': indirizzo.data_scadenza.strftime('%Y-%m-%d %H:%M:%S') if indirizzo.data_scadenza else None,
                    'is_anomalo': indirizzo.is_anomalo(),
                    'is_scaduto': indirizzo.is_scaduto(),
                    'ore_inattivita': indirizzo.ore_inattivita(),
                    'stato_scadenza': 'attivo' if indirizzo.stato == 'attivo' else 'disattivo'
                }
                return Response([data])
            except IndirizzoIP.DoesNotExist:
                return Response([])
        return Response({'error': 'IP non specificato nel parametro title'}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def validate_ip_range(self, request):
        """
        **Valida se un IP è in un range valido per l'assegnazione.**
        
        **Parametri:**
        - `ip` (string): Indirizzo IP da validare
        
        **Esempio:**
        ```
        GET /api/ips/validate_ip_range/?ip=192.168.1.100
        ```
        
        **Risposta:**
        ```json
        {
            "ip": "192.168.1.100",
            "valid": true,
            "message": "IP valido"
        }
        ```
        """
        ip = request.query_params.get('ip', None)
        if not ip:
            return Response({'error': 'IP non specificato'}, status=status.HTTP_400_BAD_REQUEST)
            
        is_valid, message = is_valid_ip_range(ip)
        return Response({
            'ip': ip,
            'valid': is_valid,
            'message': message
        })
    
    @action(detail=True, methods=['patch'])
    def update_stato(self, request, ip=None):
        """
        **Aggiorna solo lo stato di un indirizzo IP.**
        
        Automaticamente aggiorna anche ultimo_controllo.
        
        **Parametri:**
        - `stato` (string): attivo o disattivo
        
        **Esempio:**
        ```
        PATCH /api/ips/192.168.1.100/update_stato/
        Content-Type: application/json
        
        {
            "stato": "attivo"
        }
        ```
        """
        indirizzo = self.get_object()
        nuovo_stato = request.data.get('stato', None)
        
        if nuovo_stato and nuovo_stato in dict(IndirizzoIP.STATO_CHOICES).keys():
            indirizzo.stato = nuovo_stato
            indirizzo.ultimo_controllo = timezone.now()
            indirizzo.save()
            return Response(self.get_serializer(indirizzo).data)
            
        return Response(
            {'error': f'Stato non valido. Valori permessi: {[c[0] for c in IndirizzoIP.STATO_CHOICES]}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=True, methods=['post'])
    def aggiorna_controllo(self, request, ip=None):
        """
        **Aggiorna il campo ultimo_controllo dell'IP.**
        
        Utilizzato dagli script di monitoraggio per segnalare che l'IP è attivo.
        
        **Esempio:**
        ```
        POST /api/ips/192.168.1.100/aggiorna_controllo/
        ```
        
        **Risposta:**
        ```json
        {
            "ip": "192.168.1.100",
            "ultimo_controllo": "2025-05-30T14:30:00Z",
            "stato": "attivo",
            "message": "Ultimo controllo aggiornato con successo"
        }
        ```
        """
        indirizzo = self.get_object()
        indirizzo.ultimo_controllo = timezone.now()
        
        # Se l'IP era inattivo e ora è attivo, aggiorna anche lo stato
        if indirizzo.stato == 'disattivo':
            indirizzo.stato = 'attivo'
            
        indirizzo.save()
        
        return Response({
            'ip': indirizzo.ip,
            'ultimo_controllo': indirizzo.ultimo_controllo,
            'stato': indirizzo.stato,
            'message': 'Ultimo controllo aggiornato con successo'
        })
    
    @action(detail=True, methods=['post'])
    def aggiorna_scadenza(self, request, ip=None):
        """
        **Aggiorna automaticamente la data di scadenza se necessario.**
        
        **Esempio:**
        ```
        POST /api/ips/192.168.1.100/aggiorna_scadenza/
        ```
        
        **Risposta:**
        ```json
        {
            "ip": "192.168.1.100",
            "data_scadenza": "2025-08-30T14:30:00Z",
            "aggiornato": true,
            "message": "Data scadenza aggiornata"
        }
        ```
        """
        indirizzo = self.get_object()
        
        # Aggiorna data scadenza solo se è vuota e l'IP è scaduto
        aggiornato = False
        if not indirizzo.data_scadenza and indirizzo.is_scaduto():
            # Imposta una scadenza di 3 mesi da ora se l'IP è già scaduto
            indirizzo.data_scadenza = timezone.now() + timedelta(days=90)
            aggiornato = True
            
        if aggiornato:
            indirizzo.save()
            message = 'Data scadenza aggiornata automaticamente'
        else:
            message = 'Nessun aggiornamento necessario'
            
        return Response({
            'ip': indirizzo.ip,
            'data_scadenza': indirizzo.data_scadenza,
            'aggiornato': aggiornato,
            'message': message
        })
    
    @action(detail=True, methods=['post'])
    def libera(self, request, ip=None):
        """
        **Libera un IP se è scaduto secondo le regole configurate.**
        
        **Parametri opzionali:**
        - `force` (boolean): Forza la liberazione anche se non scaduto (solo staff)
        - `motivo` (string): Motivo della liberazione (default: 'scadenza')
        - `note` (string): Note aggiuntive per lo storico
        - `created_by` (string): Chi ha effettuato l'operazione
        
        **Esempio:**
        ```
        POST /api/ips/192.168.1.100/libera/
        {
            "force": true,
            "motivo": "inattivita",
            "note": "Liberazione automatica per inattività prolungata",
            "created_by": "script_automatico"
        }
        ```
        
        **Risposta:**
        ```json
        {
            "ip": "192.168.1.100",
            "liberato": true,
            "message": "IP liberato automaticamente",
            "era_assegnato_a": "user@uniroma1.it"
        }
        ```
        """
        indirizzo = self.get_object()
        force = request.data.get('force', False)
        motivo = request.data.get('motivo', 'scadenza')
        note = request.data.get('note', None)
        created_by = request.data.get('created_by', None)
        
        # Controlla se l'utente può forzare la liberazione
        if force and not request.user.is_staff:
            return Response(
                {'error': 'Solo gli staff possono forzare la liberazione'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Memorizza chi era assegnato prima
        era_assegnato_a = indirizzo.responsabile
        
        # Se non è forzato, controlla se è scaduto
        if not force and not indirizzo.is_scaduto():
            return Response({
                'ip': indirizzo.ip,
                'liberato': False,
                'message': 'IP non scaduto - usa force=true per liberare comunque',
                'scadenza': indirizzo.data_scadenza.isoformat() if indirizzo.data_scadenza else None
            })
        
        # Se l'IP è già libero
        if indirizzo.disponibilita == 'libero':
            return Response({
                'ip': indirizzo.ip,
                'liberato': False,
                'message': 'IP già libero',
                'era_assegnato_a': None
            })
        
        # Libera l'IP usando il nuovo metodo con storico
        try:
            nota_completa = note or f"IP liberato automaticamente - {motivo}"
            if request.user.is_authenticated:
                created_by = created_by or request.user.username
            
            indirizzo.rilascia_ip(
                motivo=motivo,
                note=nota_completa,
                created_by=created_by
            )
            
            return Response({
                'ip': indirizzo.ip,
                'liberato': True,
                'message': 'IP liberato automaticamente',
                'era_assegnato_a': era_assegnato_a,
                'motivo': motivo
            })
            
        except Exception as e:
            logger.error(f"Errore nella liberazione dell'IP {indirizzo.ip}: {str(e)}")
            return Response(
                {'error': f'Errore nella liberazione: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def statistiche(self, request):
        """
        **Restituisce statistiche aggregate sugli IP.**
        
        **Esempio:**
        ```
        GET /api/ips/statistiche/
        ```
        
        **Risposta:**
        ```json
        {
            "totale": 1000,
            "per_stato": {
                "attivo": 600,
                "disattivo": 400
            },
            "per_disponibilita": {
                "libero": 300,
                "usato": 700
            },
            "anomali": 15,
            "scaduti": 8,
            "in_scadenza": 25
        }
        ```
        """
        from django.db.models import Count
        
        # Statistiche base con aggregazione
        stats = {
            'totale': IndirizzoIP.objects.count(),
            'per_stato': dict(IndirizzoIP.objects.values('stato').annotate(count=Count('stato')).values_list('stato', 'count')),
            'per_disponibilita': dict(IndirizzoIP.objects.values('disponibilita').annotate(count=Count('disponibilita')).values_list('disponibilita', 'count')),
        }
        
        # Statistiche che richiedono iterazione (ottimizzabile con query personalizzate)
        ip_usati = IndirizzoIP.objects.filter(disponibilita='usato').iterator()
        anomali = scaduti = in_scadenza = 0
        
        for ip in ip_usati:
            if ip.is_anomalo():
                anomali += 1
            if ip.is_scaduto():
                scaduti += 1
        
        stats.update({
            'anomali': anomali,
            'scaduti': scaduti,
            'in_scadenza': 0  # Non più supportato
        })
        
        return Response(stats)

class VlanViewSet(viewsets.ModelViewSet):
    queryset = Vlan.objects.all()
    serializer_class = VlanSerializer
    lookup_field = 'numero'
    permission_classes = [IsAuthenticatedOrReadOnly]

# Viste per l'interfaccia web
def login_view(request):
    """Vista per la pagina di login"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Aggiungi il suffisso @uniroma1.it se non presente
        if username and '@' not in username:
            username = f"{username}@uniroma1.it"
            
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            # Controlla se l'errore è per utente disabilitato
            login_error_type = request.session.pop('login_error_type', None)
            if login_error_type == 'user_disabled':
                messages.error(request, _('Il tuo account non è abilitato al login. Contatta l\'amministratore.'))
            else:
                messages.error(request, _('Credenziali non valide'))
    
    return render(request, 'reti_app/login.html')

def logout_view(request):
    """Vista per il logout"""
    logout(request)
    return redirect('login')

@login_required
def dashboard(request):
    """Vista per la dashboard principale"""
    context = {}
    
    # Informazioni di base presenti per tutti gli utenti
    oggi = timezone.now()
    tra_30_giorni = oggi + timezone.timedelta(days=30)
    
    if request.user.is_staff:
        # *** Dashboard per amministratori ***
        
        # Esegui le query più pesanti con ottimizzazioni
        
        # 1. Conteggio degli indirizzi IP per tipo di stato - usa valori aggregati per evitare di caricare oggetti
        status_counts = IndirizzoIP.objects.values('stato').annotate(
            count=Count('stato')
        ).order_by('stato')
        
        # Converte i risultati in un dizionario per facile accesso
        stato_count = {item['stato']: item['count'] for item in status_counts}
        ip_attivi_count = stato_count.get('attivo', 0)
        
        # CAMBIATO: "IP ASSEGNATI MA NON USATI" invece di "IP DISATTIVI" 
        # (IP con disponibilita='usato' ma stato='disattivo')
        ip_assegnati_non_usati_count = IndirizzoIP.objects.filter(
            disponibilita='usato', 
            stato='disattivo'
        ).count()
        
        # CAMBIATO: "IP IN SCADENZA" invece di "IP RISERVATI"
        # (IP con data_scadenza nei prossimi 30 giorni)
        ip_in_scadenza_admin_count = IndirizzoIP.objects.filter(
            data_scadenza__range=[oggi, tra_30_giorni]
        ).count()
        
        # 2. Conteggi totali - usa Count direttamente senza caricare oggetti
        ip_totali_count = sum(stato_count.values())
        vlan_count = Vlan.objects.count()
        
        # 3. Ultimi indirizzi IP modificati - limita i campi e usa select_related
        ip_recenti = IndirizzoIP.objects.select_related('vlan').only(
            'ip', 'stato', 'mac_address', 'responsabile', 'vlan', 'data_modifica', 'note'
        ).order_by('-data_modifica')[:15]
        
        # 4. Indirizzi IP in scadenza - limita i campi e usa select_related con ordinamento numerico
        from django.db import connection
        if 'mysql' in connection.vendor:
            ip_in_scadenza = IndirizzoIP.objects.select_related('vlan').only(
                'ip', 'stato', 'mac_address', 'responsabile', 'vlan', 'data_scadenza'
            ).filter(
                data_scadenza__range=[oggi, tra_30_giorni]
            ).extra(
                select={'ip_as_int': 'INET_ATON(ip)'}, 
                order_by=['data_scadenza', 'ip_as_int']
            )[:10]
        else:
            ip_in_scadenza = IndirizzoIP.objects.select_related('vlan').only(
                'ip', 'stato', 'mac_address', 'responsabile', 'vlan', 'data_scadenza'
            ).filter(
                data_scadenza__range=[oggi, tra_30_giorni]
            ).order_by('data_scadenza', 'ip')[:10]
        
        # 5. IP senza MAC - usa Count direttamente
        ip_senza_mac = IndirizzoIP.objects.filter(
            Q(mac_address__isnull=True) | Q(mac_address='')
        ).count()
        
        # 6. Distribuzione degli IP per subnet/VLAN
        # Usa il campo preimpostato num_indirizzi invece di calcolare in tempo reale
        vlan_stats = Vlan.objects.values(
            'numero', 'nome', 'subnets', 'num_indirizzi'
        ).order_by('-num_indirizzi')[:5]
        
        # Converti il formato delle subnet per la visualizzazione
        for vlan in vlan_stats:
            vlan['num_ip'] = vlan['num_indirizzi']  # Mantiene la compatibilità con il template
            if vlan['subnets']:
                vlan['subnets'] = [s.strip() for s in vlan['subnets'].replace('\n', ',').split(',') if s.strip()]
            else:
                vlan['subnets'] = []
        
        # Aggiunta dei dati al contesto
        context.update({
            'is_staff': True,
            'ip_attivi_count': ip_attivi_count,
            'ip_assegnati_non_usati_count': ip_assegnati_non_usati_count,  # CAMBIATO
            'ip_in_scadenza_admin_count': ip_in_scadenza_admin_count,      # CAMBIATO
            'ip_totali_count': ip_totali_count,
            'vlan_count': vlan_count,
            'ip_recenti': ip_recenti,
            'ip_in_scadenza': ip_in_scadenza,
            'ip_senza_mac': ip_senza_mac,
            'vlan_stats': vlan_stats,
        })
        
    else:
        # *** Dashboard per utenti normali ***
        
        # 1. IP assegnati all'utente corrente - ottimizzato con select_related e only con ordinamento numerico
        from django.db import connection
        if 'mysql' in connection.vendor:
            ip_assegnati = IndirizzoIP.objects.select_related('vlan').only(
                'ip', 'stato', 'mac_address', 'responsabile', 'vlan', 'data_scadenza'
            ).filter(
                assegnato_a_utente=request.user
            ).extra(
                select={'ip_as_int': 'INET_ATON(ip)'}, 
                order_by=['ip_as_int']
            )
        else:
            ip_assegnati = IndirizzoIP.objects.select_related('vlan').only(
                'ip', 'stato', 'mac_address', 'responsabile', 'vlan', 'data_scadenza'
            ).filter(
                assegnato_a_utente=request.user
            ).order_by('ip')
        
        # 2. IP in scadenza assegnati all'utente - ottimizzato con select_related e only con ordinamento numerico
        if 'mysql' in connection.vendor:
            ip_in_scadenza = IndirizzoIP.objects.select_related('vlan').only(
                'ip', 'stato', 'mac_address', 'responsabile', 'vlan', 'data_scadenza'
            ).filter(
                assegnato_a_utente=request.user, 
                data_scadenza__range=[oggi, tra_30_giorni]
            ).extra(
                select={'ip_as_int': 'INET_ATON(ip)'}, 
                order_by=['data_scadenza', 'ip_as_int']
            )
        else:
            ip_in_scadenza = IndirizzoIP.objects.select_related('vlan').only(
                'ip', 'stato', 'mac_address', 'responsabile', 'vlan', 'data_scadenza'
            ).filter(
                assegnato_a_utente=request.user, 
                data_scadenza__range=[oggi, tra_30_giorni]
            ).order_by('data_scadenza', 'ip')
        
        # 3. Conteggi per l'utente - usa i conteggi esistenti per evitare query aggiuntive
        ip_assegnati_count = ip_assegnati.count()
        ip_in_scadenza_count = ip_in_scadenza.count()
        
        # Aggiunta dei dati al contesto
        context.update({
            'is_staff': False,
            'ip_assegnati': ip_assegnati,
            'ip_assegnati_count': ip_assegnati_count,
            'ip_in_scadenza': ip_in_scadenza,
            'ip_in_scadenza_count': ip_in_scadenza_count
        })
    
    return render(request, 'reti_app/dashboard.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff, login_url='/login/')
def ip_assegnati_non_usati(request):
    """Vista per mostrare IP assegnati ma non usati (disponibilita='usato' ma stato='disattivo')"""
    
    # Query per IP assegnati ma non usati con ordinamento numerico
    from django.db import connection
    if 'mysql' in connection.vendor:
        ip_assegnati_non_usati = IndirizzoIP.objects.select_related('vlan', 'assegnato_a_utente').filter(
            disponibilita='usato',
            stato='disattivo'
        ).extra(
            select={'ip_as_int': 'INET_ATON(ip)'}, 
            order_by=['ip_as_int']
        )
    else:
        ip_assegnati_non_usati = IndirizzoIP.objects.select_related('vlan', 'assegnato_a_utente').filter(
            disponibilita='usato',
            stato='disattivo'
        ).order_by('ip')
    
    # Conteggio per il titolo
    count = ip_assegnati_non_usati.count()
    
    context = {
        'ip_list': ip_assegnati_non_usati,
        'count': count,
        'title': 'IP Assegnati ma Non Usati',
        'description': 'Indirizzi IP marcati come "usati" ma attualmente "disattivi" in rete.',
        'empty_message': 'Non ci sono IP assegnati ma non usati.'
    }
    
    return render(request, 'reti_app/ip_special_list.html', context)

@login_required  
@user_passes_test(lambda u: u.is_staff, login_url='/login/')
def ip_in_scadenza_admin(request):
    """Vista per mostrare IP in scadenza nei prossimi 30 giorni"""
    
    # Calcola il range di date
    oggi = timezone.now()
    tra_30_giorni = oggi + timezone.timedelta(days=30)
    
    # Query per IP in scadenza con ordinamento numerico
    from django.db import connection
    if 'mysql' in connection.vendor:
        ip_in_scadenza = IndirizzoIP.objects.select_related('vlan', 'assegnato_a_utente').filter(
            data_scadenza__range=[oggi, tra_30_giorni]
        ).extra(
            select={'ip_as_int': 'INET_ATON(ip)'}, 
            order_by=['data_scadenza', 'ip_as_int']
        )
    else:
        ip_in_scadenza = IndirizzoIP.objects.select_related('vlan', 'assegnato_a_utente').filter(
            data_scadenza__range=[oggi, tra_30_giorni]
        ).order_by('data_scadenza', 'ip')
    
    # Conteggio per il titolo
    count = ip_in_scadenza.count()
    
    context = {
        'ip_list': ip_in_scadenza,
        'count': count,
        'title': 'IP in Scadenza',
        'description': f'Indirizzi IP che scadranno nei prossimi 30 giorni (entro il {tra_30_giorni.strftime("%d/%m/%Y")}).',
        'empty_message': 'Non ci sono IP in scadenza nei prossimi 30 giorni.',
        'show_scadenza': True  # Flag per mostrare la colonna scadenza
    }
    
    return render(request, 'reti_app/ip_special_list.html', context)

@login_required
def indirizzi_ip_list(request):
    """Vista per l'elenco di tutti gli indirizzi IP"""
    ip_cercato_non_esistente = None

    # Base queryset ottimizzata con select_related per ridurre query al database
    from django.db import connection
    indirizzi = IndirizzoIP.objects.select_related('vlan')
    
    # Gestione dell'ordinamento
    order_by = request.GET.get('order_by', 'ip')  # Default: ordina per IP
    order_dir = request.GET.get('order_dir', 'asc')  # Default: ascendente
    
    # Campi ordinabili e loro mapping nel database
    orderable_fields = {
        'ip': 'ip',
        'mac_address': 'mac_address', 
        'stato': 'stato',
        'disponibilita': 'disponibilita',
        'vlan': 'vlan__numero',
        'responsabile': 'responsabile',
        'utente_finale': 'utente_finale',
        'ultimo_controllo': 'ultimo_controllo'
    }
    
    # Validazione del campo di ordinamento
    if order_by not in orderable_fields:
        order_by = 'ip'
    
    # Validazione della direzione
    if order_dir not in ['asc', 'desc']:
        order_dir = 'asc'
    
    # Applica l'ordinamento
    field_name = orderable_fields[order_by]
    if order_dir == 'desc':
        field_name = f'-{field_name}'
    
    # Per l'IP usiamo ordinamento numerico se supportato dal database
    if order_by == 'ip':
        if 'mysql' in connection.vendor:
            if order_dir == 'asc':
                indirizzi = indirizzi.extra(
                    select={'ip_as_int': 'INET_ATON(ip)'}, 
                    order_by=['ip_as_int']
                )
            else:
                indirizzi = indirizzi.extra(
                    select={'ip_as_int': 'INET_ATON(ip)'}, 
                    order_by=['-ip_as_int']
                )
        else:
            indirizzi = indirizzi.order_by(field_name)
    else:
        indirizzi = indirizzi.order_by(field_name)
        
    ip_filtro = request.GET.get('ip', '').strip()
    if ip_filtro:
        indirizzi = indirizzi.filter(
            Q(ip__icontains=ip_filtro) |
            Q(mac_address__icontains=ip_filtro) |
            Q(responsabile__icontains=ip_filtro) |
            Q(utente_finale__icontains=ip_filtro) |
            Q(note__icontains=ip_filtro)
        )
    
    if 'stato' in request.GET and request.GET['stato']:
        indirizzi = indirizzi.filter(stato=request.GET['stato'])
        
    disponibilita_anomalo = request.GET.get('disponibilita_anomalo', '').strip()
    if disponibilita_anomalo == 'libero':
        indirizzi = indirizzi.filter(disponibilita='libero')
    elif disponibilita_anomalo == 'usato':
        indirizzi = indirizzi.filter(disponibilita='usato')
    elif disponibilita_anomalo == 'riservato':
        indirizzi = indirizzi.filter(disponibilita='riservato')
    elif disponibilita_anomalo == 'anomalo':
        indirizzi = indirizzi.filter(
            stato='attivo'
        ).filter(
            Q(disponibilita='libero') | Q(responsabile__isnull=True) | Q(responsabile='')
        )
        
    if 'vlan' in request.GET and request.GET['vlan']:
        indirizzi = indirizzi.filter(vlan__numero=request.GET['vlan'])
    
    # Ottiene l'elenco di tutte le VLAN per il dropdown di filtro - limita a campi necessari
    vlans = Vlan.objects.only('numero', 'nome').order_by('numero')
    
    # Se abbiamo un IP virtuale da mostrare, convertiamo tutto in lista
    if ip_cercato_non_esistente:
        # Crea una lista con solo l'IP virtuale
        indirizzi_list = [ip_cercato_non_esistente]
        
        # Crea un oggetto simile al paginator per compatibilità con il template
        class VirtualPaginator:
            def __init__(self, object_list):
                self.object_list = object_list
                self.count = len(object_list)
                self.num_pages = 1
                self.page_range = range(1, 2)
                
        class VirtualPage:
            def __init__(self, object_list, paginator):
                self.object_list = object_list
                self.paginator = paginator
                self.number = 1
                
            def __iter__(self):
                return iter(self.object_list)
                
            def has_previous(self):
                return False
                
            def has_next(self):
                return False
                
            def previous_page_number(self):
                return None
                
            def next_page_number(self):
                return None
        
        paginator = VirtualPaginator(indirizzi_list)
        page_obj = VirtualPage(indirizzi_list, paginator)
    else:
        # Aggiungi paginazione normale
        paginator = Paginator(indirizzi, 50)  # 50 indirizzi per pagina
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
    
    return render(request, 'reti_app/indirizzi_list.html', {
        'indirizzi': page_obj,
        'vlans': vlans,
        'ip_virtuale': ip_cercato_non_esistente,
        'current_order_by': order_by,
        'current_order_dir': order_dir,
    })

@login_required
def indirizzi_ip_assegnati(request):
    """Vista per l'elenco degli indirizzi IP assegnati all'utente corrente"""
    from django.db import connection
    if 'mysql' in connection.vendor:
        indirizzi_assegnati = IndirizzoIP.objects.filter(
            assegnato_a_utente=request.user
        ).extra(
            select={'ip_as_int': 'INET_ATON(ip)'}, 
            order_by=['ip_as_int']
        )
    else:
        indirizzi_assegnati = IndirizzoIP.objects.filter(
            assegnato_a_utente=request.user
        ).order_by('ip')
        
    return render(request, 'reti_app/indirizzi_assegnati.html', {'indirizzi': indirizzi_assegnati})

@login_required
def gestione_indirizzi_ip(request):
    """Vista per la gestione degli indirizzi IP (admin)"""
    indirizzi = IndirizzoIP.objects.all()
    return render(request, 'reti_app/gestione_indirizzi.html', {'indirizzi': indirizzi})

@login_required
def indirizzo_ip_detail(request, ip):
    """Vista dettaglio di un indirizzo IP"""
    indirizzo = get_object_or_404(IndirizzoIP, pk=ip)
    
    # Form di modifica per tutti gli utenti che possiedono l'IP (staff e non-staff)
    if request.method == 'POST':
        # Verifica che l'IP sia assegnato all'utente corrente
        if indirizzo.assegnato_a_utente != request.user:
            messages.error(request, "Non hai i permessi per modificare questo indirizzo IP.")
            return redirect('indirizzo_ip_detail', ip=ip)
        
        # Permetti modifica dei campi tramite form
        responsabile = request.POST.get('responsabile', '').strip()
        utente_finale = request.POST.get('utente_finale', '').strip()
        note = request.POST.get('note', '').strip()
        
        # Aggiorna i campi
        indirizzo.responsabile = responsabile if responsabile else None
        indirizzo.utente_finale = utente_finale if utente_finale else None
        indirizzo.note = note if note else None
        
        try:
            indirizzo.save()
            messages.success(request, "Indirizzo IP aggiornato con successo!")
        except Exception as e:
            messages.error(request, f"Errore durante l'aggiornamento: {str(e)}")
        
        return redirect('indirizzo_ip_detail', ip=ip)
    
    # Nuova logica di permessi più flessibile:
    user_owns_ip = (indirizzo.assegnato_a_utente == request.user)
    
    # Form edit: disponibile per tutti gli utenti che possiedono l'IP (staff e non-staff)
    can_edit_via_form = user_owns_ip
    
    # Admin access: disponibile solo per staff
    can_edit_via_admin = request.user.is_staff
    
    return render(request, 'reti_app/indirizzo_detail.html', {
        'indirizzo': indirizzo,
        'can_edit_via_form': can_edit_via_form,
        'can_edit_via_admin': can_edit_via_admin,
        'user_owns_ip': user_owns_ip,
    })

@login_required
def richiedi_nuovo_ip(request):
    """Vista per richiedere un nuovo indirizzo IP"""
    if request.method == 'POST':
        # Recupera i dati dal form
        ip_richiesto = request.POST.get('ip', '').strip()
        mac_address = request.POST.get('mac_address', '').strip() or None
        responsabile = request.POST.get('responsabile', '').strip()
        email_responsabile = request.POST.get('email_responsabile', '').strip()
        utente_finale = request.POST.get('utente_finale', '').strip()
        note = request.POST.get('note', '').strip() or None
        
        # Validazione base
        if not responsabile or not email_responsabile or not utente_finale:
            messages.error(request, 'I campi Responsabile, Email Responsabile e Utente Finale sono obbligatori.')
            return render(request, 'reti_app/richiedi_ip.html')
        
        # Se è stato specificato un IP, verifica che sia disponibile
        if ip_richiesto:
            # Prima validazione: formato e range IP valido
            is_valid, error_message = is_valid_ip_range(ip_richiesto)
            if not is_valid:
                messages.error(
                    request,
                    f'L\'indirizzo IP {ip_richiesto} non è valido: {error_message}. '
                    'Inserisci un IP valido o lascia vuoto il campo per ottenere un IP automatico.'
                )
                return render(request, 'reti_app/richiedi_ip.html')
            
            try:
                # Prova a recuperare l'IP se esiste già
                indirizzo_esistente = IndirizzoIP.objects.get(ip=ip_richiesto)
                
                # Verifica che sia disponibile (non assegnato)
                if indirizzo_esistente.disponibilita == 'usato' and indirizzo_esistente.responsabile:
                    messages.error(
                        request, 
                        f'L\'IP {ip_richiesto} è già assegnato a {indirizzo_esistente.responsabile}. Scegli un altro IP.'
                    )
                    return render(request, 'reti_app/richiedi_ip.html')
                
                # Assegna l'IP esistente usando il nuovo metodo con storico
                indirizzo_esistente.assegna_ip(
                    responsabile=email_responsabile,
                    utente_finale=utente_finale,
                    note=f'IP assegnato tramite interfaccia web. {note or ""}',
                    created_by=request.user.email or request.user.username
                )
                
                # Aggiorna altri campi
                indirizzo_esistente.assegnato_a_utente = request.user
                if mac_address:
                    indirizzo_esistente.mac_address = mac_address
                indirizzo_esistente.ultimo_controllo = timezone.now()
                
                # Trova automaticamente la VLAN
                vlan_trovata = Vlan.find_vlan_for_ip(ip_richiesto)
                if vlan_trovata:
                    indirizzo_esistente.vlan = vlan_trovata
                
                indirizzo_esistente.save()
                
                messages.success(
                    request, 
                    f'Richiesta completata! L\'IP {ip_richiesto} è stato assegnato con successo.'
                )
                
            except IndirizzoIP.DoesNotExist:
                # L'IP non esiste nel database - crealo come nuovo
                vlan_trovata = Vlan.find_vlan_for_ip(ip_richiesto)
                
                nuovo_indirizzo = IndirizzoIP.objects.create(
                    ip=ip_richiesto,
                    mac_address=mac_address,
                    stato='disattivo',  # Default: disattivo finché non viene configurato
                    disponibilita='usato',
                    responsabile=email_responsabile,
                    utente_finale=utente_finale,
                    assegnato_a_utente=request.user,
                    note=note,
                    vlan=vlan_trovata,
                    ultimo_controllo=timezone.now()
                )
                
                # Crea il record iniziale nello storico
                nuovo_indirizzo.assegna_ip(
                    responsabile=email_responsabile,
                    utente_finale=utente_finale,
                    note=f'IP creato e assegnato tramite interfaccia web. {note or ""}',
                    created_by=request.user.email or request.user.username
                )
                
                messages.success(
                    request, 
                    f'Richiesta completata! L\'IP {ip_richiesto} è stato creato e assegnato con successo.'
                )
        
        else:
            # IP non specificato - blocca la richiesta
            messages.error(
                request,
                'Devi specificare un indirizzo IP. La richiesta automatica non è più consentita.'
            )
            return render(request, 'reti_app/richiedi_ip.html')
        
        return redirect('indirizzi_ip_assegnati')
        
    return render(request, 'reti_app/richiedi_ip.html')

@login_required
def ricerca_indirizzo(request):
    """Vista per ricercare un indirizzo IP"""
    query = request.GET.get('q', '')
    risultati = []
    
    if query:
        risultati = IndirizzoIP.objects.filter(
            Q(ip__icontains=query) | 
            Q(mac_address__icontains=query) | 
            Q(responsabile__icontains=query) | 
            Q(utente_finale__icontains=query) |
            Q(note__icontains=query)
        )
        
    return render(request, 'reti_app/ricerca.html', {'risultati': risultati, 'query': query})

@login_required
def vlan_list(request):
    """Vista per l'elenco delle VLAN"""
    vlans = Vlan.objects.all()
    return render(request, 'reti_app/vlan_list.html', {'vlans': vlans})

@login_required
def profilo_utente(request):
    """Vista per il profilo utente"""
    indirizzi = IndirizzoIP.objects.filter(assegnato_a_utente=request.user)
    return render(request, 'reti_app/profilo_utente.html', {
        'user': request.user,
        'indirizzi': indirizzi
    })

@login_required
def vlan_detail(request, vlan_numero):
    """Vista di dettaglio di una VLAN con i suoi IP"""
    vlan = get_object_or_404(Vlan, numero=vlan_numero)
    
    # IP della VLAN con ordinamento numerico
    from django.db import connection
    if 'mysql' in connection.vendor:
        ip_vlan = IndirizzoIP.objects.filter(vlan=vlan).extra(
            select={'ip_as_int': 'INET_ATON(ip)'}, 
            order_by=['ip_as_int']
        )
    else:
        ip_vlan = IndirizzoIP.objects.filter(vlan=vlan).order_by('ip')
    
    # Calcola statistiche per la VLAN
    total_count = ip_vlan.count()
    ip_attivi_count = ip_vlan.filter(stato='attivo').count()
    ip_usati_count = ip_vlan.filter(disponibilita='usato').count()
    ip_liberi_count = ip_vlan.filter(disponibilita='libero').count()
    
    context = {
        'vlan': vlan,
        'indirizzi': ip_vlan,
        'ip_list': ip_vlan,  # Aggiunto per compatibilità con il template
        'total_count': total_count,
        'count': total_count,  # Aggiunto per compatibilità con il template
        'ip_attivi_count': ip_attivi_count,
        'ip_usati_count': ip_usati_count,
        'ip_liberi_count': ip_liberi_count,
        'title': f'VLAN {vlan.numero} - {vlan.nome}',
        'description': _('Elenco degli indirizzi IP assegnati alla VLAN %(numero)s (%(nome)s)') % {'numero': vlan.numero, 'nome': vlan.nome},
        'empty_message': _('Nessun indirizzo IP trovato per la VLAN %(numero)s.') % {'numero': vlan.numero}
    }
    
    return render(request, 'reti_app/vlan_detail.html', context)

def is_valid_ip_range(ip_str):
    """
    Valida che l'IP sia in un range valido per l'assegnazione.
    Esclude:
    - 0.0.0.0/8 (rete "this network")
    - 127.0.0.0/8 (loopback)
    - 169.254.0.0/16 (link-local)
    - 224.0.0.0/4 (multicast)
    - 240.0.0.0/4 (riservato)
    - IP broadcast e di rete
    """
    try:
        ip = ipaddress.IPv4Address(ip_str)
        
        # Verifica che non sia in range riservati
        if ip.is_reserved:
            return False, "IP in range riservato"
        
        if ip.is_loopback:
            return False, "IP di loopback non assegnabile"
            
        if ip.is_link_local:
            return False, "IP link-local non assegnabile"
            
        if ip.is_multicast:
            return False, "IP multicast non assegnabile"
            
        # Verifica range specifici
        if ip in ipaddress.IPv4Network('0.0.0.0/8'):
            return False, "Range 0.0.0.0/8 non assegnabile"
            
        if ip in ipaddress.IPv4Network('240.0.0.0/4'):
            return False, "Range 240.0.0.0/4 riservato per uso futuro"
        
        # Verifica che non sia un indirizzo di rete o broadcast
        # Controllo per le reti più comuni
        common_networks = [
            '10.0.0.0/8',
            '172.16.0.0/12', 
            '192.168.0.0/16',
            '151.100.0.0/16',  # Range specifico università
        ]
        
        for network_str in common_networks:
            network = ipaddress.IPv4Network(network_str)
            if ip in network:
                # Verifica che non sia l'indirizzo di rete o broadcast
                if ip == network.network_address:
                    return False, f"Indirizzo di rete {network_str} non assegnabile"
                if ip == network.broadcast_address:
                    return False, f"Indirizzo broadcast {network_str} non assegnabile"
        
        return True, "IP valido"
        
    except (ipaddress.AddressValueError, ValueError):
        return False, "Formato IP non valido"

# Vista semplice per il controllo disponibilità IP senza autenticazione
@csrf_exempt
@require_http_methods(["GET"])
def check_ip_availability(request):
    """
    Endpoint semplice per controllare la disponibilità di un IP senza autenticazione.
    """
    ip = request.GET.get('ip')
    if not ip:
        return JsonResponse({'error': 'IP non specificato'}, status=400)
    
    try:
        indirizzo = IndirizzoIP.objects.get(ip=ip)
        return JsonResponse({
            'ip': indirizzo.ip,
            'exists': True,
            'stato': indirizzo.stato,
            'disponibilita': indirizzo.disponibilita,
            'responsabile': indirizzo.responsabile or '',
            'is_anomalo': indirizzo.is_anomalo()
        })
    except IndirizzoIP.DoesNotExist:
        return JsonResponse({
            'ip': ip,
            'exists': False,
            'available': True
        })

@login_required
def rilascia_ip(request, ip):
    """Vista per rilasciare un indirizzo IP assegnato all'utente"""
    # Ottieni l'indirizzo IP
    indirizzo = get_object_or_404(IndirizzoIP, ip=ip)
    
    # Verifica che l'IP sia effettivamente assegnato all'utente corrente
    if indirizzo.assegnato_a_utente != request.user:
        messages.error(request, 'Non hai i permessi per rilasciare questo IP.')
        return redirect('indirizzi_ip_assegnati')
    
    if request.method == 'POST':
        # Usa il nuovo metodo che gestisce automaticamente lo storico
        indirizzo.rilascia_ip(
            motivo='rilascio',
            note=f'IP rilasciato tramite interfaccia web da {request.user.get_full_name() or request.user.username}',
            created_by=request.user.email or request.user.username
        )
        
        messages.success(
            request, 
            f'L\'IP {ip} è stato rilasciato con successo ed è ora disponibile per altri utenti. Lo storico è stato aggiornato.'
        )
        return redirect('indirizzi_ip_assegnati')
    
    # Se GET, mostra una pagina di conferma
    return render(request, 'reti_app/conferma_rilascio.html', {'indirizzo': indirizzo})

def health_check(request):
    """Health check endpoint for container monitoring"""
    return JsonResponse({'status': 'healthy', 'timestamp': timezone.now().isoformat()}) 