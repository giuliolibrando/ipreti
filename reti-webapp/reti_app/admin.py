from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django import forms
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.template.response import TemplateResponse
from django.utils.translation import gettext_lazy as _
from .models import IndirizzoIP, Vlan, StoricoResponsabile, UserProfile
import csv
import io
from django.utils import timezone
import datetime
import re
import ldap
from django.conf import settings

class CsvImportForm(forms.Form):
    csv_file = forms.FileField(
        label='Seleziona un file CSV',
        help_text='Il file deve avere il formato adeguato per il tipo di dati da importare'
    )
    format_choice = forms.ChoiceField(
        label='Formato del file',
        choices=[
            ('nuovo', 'Nuovo formato (IP,MAC,Stato Rete,Disponibilità,Responsabile,Utente,Note,Controllo,Scadenza)'),
            ('originale', 'Formato originale (IP,Stato Rete,Disponibilità,MAC,Mail,Controllo,Note,Utente)'),
        ],
        initial='nuovo',
        help_text='Seleziona il formato del file CSV che stai importando.<br>'
                  '<strong>Stato Rete:</strong> attivo/disattivo (se naviga in rete)<br>'
                  '<strong>Disponibilità:</strong> libero/usato (se è stato richiesto da qualche utente)'
    )

def check_ldap_user_and_create(email):
    """
    Verifica se l'utente esiste nell'LDAP e lo crea in Django se non è già presente
    
    Args:
        email: Email dell'utente da cercare
        
    Returns:
        User o None: Restituisce l'utente Django creato/trovato o None se non trovato nell'LDAP
    """
    # Salta se l'email è vuota o già un indirizzo email non valido
    if not email or '@' not in email:
        return None
        
    # Controllo se l'utente esiste già nel database Django
    try:
        return User.objects.get(username=email)
    except User.DoesNotExist:
        pass  # Procedi con il controllo LDAP
    
    try:
        # Inizializza la connessione LDAP
        ldap_conn = ldap.initialize(settings.AUTH_LDAP_SERVER_URI)
        ldap_conn.set_option(ldap.OPT_REFERRALS, 0)
        ldap_conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
        
        # Esegui bind anonimo se le credenziali non sono fornite
        if settings.AUTH_LDAP_BIND_DN:
            ldap_conn.simple_bind_s(settings.AUTH_LDAP_BIND_DN, settings.AUTH_LDAP_BIND_PASSWORD)
        else:
            ldap_conn.simple_bind_s()
        
        # Costruisci il filtro di ricerca per l'email
        search_filter = f"(mail={email})"
        base_dn = "OU=Ateneo,O=uniroma1,C=it"
        
        # Esegui la ricerca
        result = ldap_conn.search_s(
            base_dn, 
            ldap.SCOPE_SUBTREE, 
            search_filter, 
            ['givenName', 'sn', 'mail']
        )
        
        # Se l'utente esiste nell'LDAP, crealo in Django
        if result and len(result) > 0:
            _, attrs = result[0]
            
            # Estrai attributi
            first_name = attrs.get('givenName', [b''])[0].decode('utf-8')
            last_name = attrs.get('sn', [b''])[0].decode('utf-8')
            mail = attrs.get('mail', [b''])[0].decode('utf-8')
            
            # Crea l'utente Django
            user = User.objects.create(
                username=email,
                email=mail,
                first_name=first_name,
                last_name=last_name
            )
            
            return user
            
    except Exception as e:
        print(f"Errore durante la verifica LDAP: {str(e)}")
    
    return None

class StoricoResponsabileInline(admin.TabularInline):
    model = StoricoResponsabile
    extra = 0
    readonly_fields = ('data_inizio', 'data_fine', 'motivo_cambio', 'durata_assegnazione_display', 'created_at', 'created_by')
    fields = ('responsabile', 'utente_finale', 'data_inizio', 'data_fine', 'motivo_cambio', 'durata_assegnazione_display', 'note', 'created_by')
    ordering = ['-data_inizio']
    
    def durata_assegnazione_display(self, obj):
        """Mostra la durata dell'assegnazione in formato leggibile"""
        if obj.data_inizio:
            durata = obj.durata_assegnazione
            giorni = durata.days
            ore = durata.seconds // 3600
            if giorni > 0:
                return f"{giorni} giorni, {ore} ore"
            else:
                return f"{ore} ore"
        return "-"
    durata_assegnazione_display.short_description = _("Durata")

@admin.register(IndirizzoIP)
class IndirizzoIPAdmin(admin.ModelAdmin):
    list_display = ('ip', 'mac_address', 'stato', 'disponibilita', 'responsabile', 'utente_finale', 'ultimo_controllo')
    list_filter = ('stato', 'disponibilita', 'vlan')
    search_fields = ('ip', 'mac_address', 'responsabile', 'utente_finale', 'note')
    readonly_fields = ('data_creazione', 'data_modifica')
    change_list_template = 'admin/change_list_import_csv.html'
    actions = ['elimina_indirizzi_ip', 'export_selected_ips']
    inlines = [StoricoResponsabileInline]
    
    fieldsets = (
        (_('Informazioni Principali'), {
            'fields': ('ip', 'mac_address', 'stato', 'disponibilita', 'vlan')
        }),
        (_('Assegnazione'), {
            'fields': ('responsabile', 'utente_finale', 'assegnato_a_utente')
        }),
        (_('Date'), {
            'fields': ('ultimo_controllo', 'data_scadenza', 'data_creazione', 'data_modifica')
        }),
        (_('Note'), {
            'fields': ('note',)
        }),
    )
    
    def elimina_indirizzi_ip(self, request, queryset):
        """Azione per eliminare tutti gli indirizzi IP selezionati"""
        num_deleted, _ = queryset.delete()
        self.message_user(
            request, 
            _("Eliminati {} indirizzi IP con successo.").format(num_deleted), 
            messages.SUCCESS
        )
    elimina_indirizzi_ip.short_description = _("Elimina gli indirizzi IP selezionati")
    
    def export_selected_ips(self, request, queryset):
        """Esporta gli indirizzi IP selezionati in formato CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="indirizzi_ip_selezionati_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        # Intestazione CSV
        writer.writerow([
            'IP', 'MAC Address', 'Stato Rete', 'Disponibilità', 'VLAN', 
            'Responsabile', 'Utente Finale', 'Note', 'Ultimo Controllo', 'Data Scadenza'
        ])
        
        # Dati
        for ip in queryset.select_related('vlan'):
            writer.writerow([
                ip.ip,
                ip.mac_address or '',
                ip.get_stato_display(),
                ip.get_disponibilita_display(),
                f"{ip.vlan.numero} - {ip.vlan.nome}" if ip.vlan else '',
                ip.responsabile or '',
                ip.utente_finale or '',
                ip.note or '',
                ip.ultimo_controllo.strftime('%Y-%m-%d %H:%M:%S') if ip.ultimo_controllo else '',
                ip.data_scadenza.strftime('%Y-%m-%d %H:%M:%S') if ip.data_scadenza else ''
            ])
        
        self.message_user(request, _("Esportati {} indirizzi IP selezionati.").format(queryset.count()), messages.SUCCESS)
        return response
    export_selected_ips.short_description = _("Esporta gli indirizzi IP selezionati in CSV")
    
    def export_all_ips_view(self, request):
        """Vista per esportare tutti gli indirizzi IP in formato CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="tutti_indirizzi_ip_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        # Intestazione CSV
        writer.writerow([
            'IP', 'MAC Address', 'Stato Rete', 'Disponibilità', 'VLAN', 
            'Responsabile', 'Utente Finale', 'Note', 'Ultimo Controllo', 'Data Scadenza'
        ])
        
        # Ottieni tutti gli IP con ottimizzazione delle query
        all_ips = IndirizzoIP.objects.select_related('vlan').order_by('ip')
        
        # Dati
        for ip in all_ips:
            writer.writerow([
                ip.ip,
                ip.mac_address or '',
                ip.get_stato_display(),
                ip.get_disponibilita_display(),
                f"{ip.vlan.numero} - {ip.vlan.nome}" if ip.vlan else '',
                ip.responsabile or '',
                ip.utente_finale or '',
                ip.note or '',
                ip.ultimo_controllo.strftime('%Y-%m-%d %H:%M:%S') if ip.ultimo_controllo else '',
                ip.data_scadenza.strftime('%Y-%m-%d %H:%M:%S') if ip.data_scadenza else ''
            ])
        
        return response
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-csv/', self.admin_site.admin_view(self.import_csv_view), name='import_ip_csv'),
            path('delete-all/', self.admin_site.admin_view(self.delete_all_view), name='delete_all_ip'),
            path('export-all-csv/', self.admin_site.admin_view(self.export_all_ips_view), name='export_all_ip_csv'),
        ]
        return custom_urls + urls
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['import_csv_url'] = reverse('admin:import_ip_csv')
        extra_context['delete_all_url'] = reverse('admin:delete_all_ip')
        extra_context['export_all_csv_url'] = reverse('admin:export_all_ip_csv')
        return super().changelist_view(request, extra_context=extra_context)
    
    def delete_all_view(self, request):
        """Vista per eliminare tutti gli indirizzi IP"""
        if request.method == "POST":
            if 'confirm' in request.POST:
                count, _ = IndirizzoIP.objects.all().delete()
                self.message_user(
                    request, 
                    _("Eliminati {} indirizzi IP con successo.").format(count), 
                    messages.SUCCESS
                )
                return HttpResponseRedirect(reverse('admin:reti_app_indirizzoip_changelist'))
            else:
                return HttpResponseRedirect(reverse('admin:reti_app_indirizzoip_changelist'))
                
        context = {
            'title': _("Conferma eliminazione di tutti gli indirizzi IP"),
            'count': IndirizzoIP.objects.count(),
            'opts': self.model._meta,
            'app_label': self.model._meta.app_label,
        }
        
        return TemplateResponse(
            request,
            "admin/delete_all_confirmation.html",
            context,
        )
    
    def import_csv_view(self, request):
        if request.method == "POST":
            form = CsvImportForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES['csv_file']
                format_choice = form.cleaned_data['format_choice']
                
                # Verifica se è un file CSV
                if not csv_file.name.endswith('.csv'):
                    self.message_user(request, 'Il file non è in formato CSV', level=messages.ERROR)
                    return HttpResponseRedirect(request.path_info)
                
                # Leggi il file
                data_set = csv_file.read().decode('utf-8')
                io_string = io.StringIO(data_set)
                header_line = next(io_string)  # Salva l'intestazione
                
                # Leggi tutte le righe in una lista
                csv_reader = csv.reader(io_string, delimiter=',', quotechar='"')
                all_lines = list(csv_reader)
                total_lines = len(all_lines)
                
                # Statistiche
                count = 0
                errors = 0
                users_created = 0
                ips_assigned = 0
                vlan_associations = 0
                
                # Processa in batch di 100 righe
                batch_size = 100
                
                for start_idx in range(0, total_lines, batch_size):
                    end_idx = min(start_idx + batch_size, total_lines)
                    batch_lines = all_lines[start_idx:end_idx]
                    
                    self.message_user(
                        request,
                        f"Processando batch {start_idx//batch_size + 1}/{(total_lines+batch_size-1)//batch_size}: righe {start_idx+1}-{end_idx}",
                        level=messages.INFO
                    )
                    
                    # Lista di IP nel batch corrente che richiedono associazione VLAN
                    batch_ip_addresses = []
                    
                    # Processa ogni riga nel batch corrente
                    for line in batch_lines:
                        try:
                            if format_choice == 'nuovo':
                                # Formato nuovo: IP,MAC Address,Stato,Disponibilita,Responsabile,Utente Finale,Note,Ultimo Controllo,Data Scadenza
                                if len(line) >= 1:  # Almeno l'IP è necessario
                                    ip_address = line[0].strip()
                                    mac_address = line[1].strip() if len(line) > 1 and line[1] else None
                                    stato = line[2].lower().strip() if len(line) > 2 and line[2] else 'disattivo'
                                    
                                    # Verifica che lo stato sia valido
                                    if stato not in [choice[0] for choice in IndirizzoIP.STATO_CHOICES]:
                                        stato = 'disattivo'
                                    
                                    # Disponibilità
                                    disponibilita = line[3].lower().strip() if len(line) > 3 and line[3] else 'libero'
                                    if disponibilita not in [choice[0] for choice in IndirizzoIP.DISPONIBILITA_CHOICES]:
                                        disponibilita = 'libero'
                                    
                                    # Campi opzionali
                                    responsabile = line[4].strip() if len(line) > 4 and line[4] else None
                                    utente_finale = line[5].strip() if len(line) > 5 and line[5] else None
                                    note = line[6].strip() if len(line) > 6 and line[6] else None
                                    
                                    # Data ultimo controllo
                                    ultimo_controllo = timezone.now()
                                    if len(line) > 7 and line[7]:
                                        try:
                                            naive_datetime = datetime.datetime.strptime(line[7].strip(), "%Y-%m-%d %H:%M:%S")
                                            # Converti in formato aware con il timezone corrente
                                            ultimo_controllo = timezone.make_aware(naive_datetime)
                                        except ValueError:
                                            ultimo_controllo = timezone.now()
                                    
                                    # Data scadenza
                                    data_scadenza = None
                                    if len(line) > 8 and line[8]:
                                        try:
                                            naive_datetime = datetime.datetime.strptime(line[8].strip(), "%Y-%m-%d %H:%M:%S")
                                            # Converti in formato aware con il timezone corrente
                                            data_scadenza = timezone.make_aware(naive_datetime)
                                        except ValueError:
                                            pass
                                else:
                                    continue  # Salta righe senza IP
                                    
                            else:
                                # Formato originale: Indirizzo IP,Stato,Disponibilita,Mac Address,Mail responsabile,
                                #                    ultimo controllo,note (db access),Utente finale (fleetmanagement)
                                if len(line) >= 1:  # Almeno l'IP è necessario
                                    ip_address = line[0].strip()
                                    
                                    # Decodifica stato rete (solo attivo/disattivo)
                                    stato = 'disattivo'  # default
                                    if len(line) > 1 and line[1]:
                                        stato_orig = line[1].lower().strip()
                                        if 'attiv' in stato_orig:
                                            stato = 'attivo'
                                        else:
                                            stato = 'disattivo'
                                    
                                    # Decodifica disponibilità (libero/usato)
                                    disponibilita = 'libero'  # default
                                    if len(line) > 2 and line[2]:
                                        disp_orig = line[2].lower().strip()
                                        if 'usato' in disp_orig or 'occupato' in disp_orig:
                                            disponibilita = 'usato'
                                        else:
                                            disponibilita = 'libero'
                                    
                                    # Mac Address
                                    mac_address = line[3].strip() if len(line) > 3 and line[3] and line[3].lower() != 'undefined' else None
                                    
                                    # Mail responsabile
                                    responsabile = line[4].strip() if len(line) > 4 and line[4] and line[4].lower() != 'undefined' else None
                                    
                                    # Ultimo controllo (formato italiano DD/MM/YYYY)
                                    ultimo_controllo = timezone.now()
                                    if len(line) > 5 and line[5] and line[5].lower() != 'undefined':
                                        try:
                                            # Converte da formato italiano DD/MM/YYYY a formato Python
                                            data_parts = re.split(r'[/.-]', line[5].strip())
                                            if len(data_parts) == 3:
                                                giorno, mese, anno = data_parts
                                                # Crea datetime e rendi aware
                                                naive_datetime = datetime.datetime(int(anno), int(mese), int(giorno))
                                                ultimo_controllo = timezone.make_aware(naive_datetime)
                                        except (ValueError, IndexError):
                                            ultimo_controllo = timezone.now()
                                    
                                    # Note
                                    note = line[6].strip() if len(line) > 6 and line[6] else None
                                    
                                    # Utente finale
                                    utente_finale = line[7].strip() if len(line) > 7 and line[7] else None
                                    
                                    # Data scadenza: non presente nel formato originale
                                    data_scadenza = None
                                else:
                                    continue  # Salta righe senza IP
                                
                            # Controlla se l'email del responsabile esiste nell'LDAP e crea l'utente
                            utente_django = None
                            if responsabile and '@' in responsabile:
                                utente_django = check_ldap_user_and_create(responsabile)
                                if utente_django:
                                    users_created += 1
                                
                            # Crea o aggiorna l'indirizzo IP
                            obj, created = IndirizzoIP.objects.update_or_create(
                                ip=ip_address,
                                defaults={
                                    'mac_address': mac_address,
                                    'stato': stato,
                                    'disponibilita': disponibilita,
                                    'responsabile': responsabile,
                                    'utente_finale': utente_finale,
                                    'note': note,
                                    'ultimo_controllo': ultimo_controllo,
                                    'data_scadenza': data_scadenza,
                                    'assegnato_a_utente': utente_django,  # Assegna l'utente se trovato
                                }
                            )
                            
                            # Aggiungi alla lista degli IP da associare alla VLAN
                            if not obj.vlan:
                                batch_ip_addresses.append(ip_address)
                            
                            if utente_django:
                                ips_assigned += 1
                            
                            if created:
                                count += 1
                        except Exception as e:
                            errors += 1
                            self.message_user(
                                request, 
                                f'Errore nella riga {start_idx + batch_lines.index(line) + 1}: {str(e)}', 
                                level=messages.ERROR
                            )
                    
                    # Associa gli IP alle VLAN all'interno dello stesso batch
                    if batch_ip_addresses:
                        self.message_user(
                            request,
                            f"Associando VLAN per {len(batch_ip_addresses)} indirizzi IP nel batch corrente...",
                            level=messages.INFO
                        )
                        
                        # Ottimizzazione: Ottieni un dizionario di prefissi IP per filtrare rapidamente
                        # la maggior parte degli IP che non possono appartenere a una VLAN
                        ip_prefix_map = {}
                        for ip in batch_ip_addresses:
                            # Estrai il prefisso dell'IP (es. da 192.168.1.1 ottieni 192.168)
                            parts = ip.split('.')
                            if len(parts) >= 2:
                                prefix = '.'.join(parts[:2])  # Primi due ottetti (es. 192.168)
                                if prefix not in ip_prefix_map:
                                    ip_prefix_map[prefix] = []
                                ip_prefix_map[prefix].append(ip)
                        
                        # Ottieni tutte le VLAN con subnet
                        vlans = Vlan.objects.exclude(subnets__isnull=True).exclude(subnets='')
                        vlan_map = {}  # Dizionario per memorizzare la mappatura IP -> VLAN
                        
                        # Per ogni VLAN, controlla solo gli IP con prefissi compatibili
                        for vlan in vlans:
                            subnet_prefixes = set()
                            for subnet in vlan.get_subnets_list():
                                try:
                                    # Estrai il prefisso dalla subnet (es. da 192.168.1.0/24 ottieni 192.168)
                                    subnet_parts = subnet.split('/')
                                    if len(subnet_parts) > 0:
                                        ip_part = subnet_parts[0]
                                        parts = ip_part.split('.')
                                        if len(parts) >= 2:
                                            subnet_prefixes.add('.'.join(parts[:2]))
                                except (ValueError, IndexError):
                                    continue
                            
                            # Controlla solo gli IP con prefissi compatibili con questa VLAN
                            ip_to_check = []
                            for prefix in subnet_prefixes:
                                if prefix in ip_prefix_map:
                                    ip_to_check.extend(ip_prefix_map[prefix])
                            
                            # Ora controlla solo questi IP contro questa VLAN
                            for ip in ip_to_check:
                                if ip not in vlan_map and vlan.contains_ip(ip):
                                    vlan_map[ip] = vlan
                        
                        # Aggiorna gli IP in blocco in base alla mappa costruita
                        vlan_associations = 0
                        for ip, vlan in vlan_map.items():
                            try:
                                # Aggiorna l'indirizzo IP con la VLAN trovata
                                IndirizzoIP.objects.filter(ip=ip).update(vlan=vlan)
                                vlan_associations += 1
                            except Exception as e:
                                self.message_user(
                                    request,
                                    f"Errore nell'associazione VLAN per IP {ip}: {str(e)}",
                                    level=messages.ERROR
                                )
                
                self.message_user(
                    request,
                    f"Associati {vlan_associations} indirizzi IP alle VLAN corrispondenti",
                    level=messages.SUCCESS
                )
                
                self.message_user(request, 
                    f'Importazione CSV completata: {count} nuovi IP creati, {users_created} utenti trovati in LDAP, ' 
                    f'{ips_assigned} indirizzi IP assegnati, {errors} errori riscontrati', 
                    level=messages.SUCCESS)
                return HttpResponseRedirect(reverse('admin:reti_app_indirizzoip_changelist'))
        else:
            form = CsvImportForm()
        
        context = {
            'form': form,
            'title': _("Importa Indirizzi IP da CSV"),
            'opts': self.model._meta,
            'app_label': self.model._meta.app_label,
        }
        
        return TemplateResponse(
            request,
            "admin/csv_import.html",
            context,
        )

@admin.register(Vlan)
class VlanAdmin(admin.ModelAdmin):
    list_display = ('numero', 'nome', 'get_all_subnets', 'num_indirizzi')
    search_fields = ('numero', 'nome', 'descrizione', 'subnets')
    change_list_template = 'admin/change_list_import_csv.html'
    actions = ['export_selected_vlans']
    
    def get_all_subnets(self, obj):
        """Mostra tutte le subnet nella vista elenco"""
        if not obj.subnets:
            return "-"
        subnets_list = [s.strip() for s in obj.subnets.replace('\n', ',').split(',')]
        return ", ".join(subnets_list)
    
    get_all_subnets.short_description = _("Subnets")
    
    def export_selected_vlans(self, request, queryset):
        """Esporta le VLAN selezionate in formato CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="vlan_selezionate_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        # Intestazione CSV
        writer.writerow([
            'Numero VLAN', 'Nome', 'Descrizione', 'Subnets', 'Numero Indirizzi IP'
        ])
        
        # Dati
        for vlan in queryset:
            # Formatta le subnet in una singola stringa
            subnets_str = ""
            if vlan.subnets:
                subnets_list = [s.strip() for s in vlan.subnets.replace('\n', ',').split(',') if s.strip()]
                subnets_str = "; ".join(subnets_list)
            
            writer.writerow([
                vlan.numero,
                vlan.nome or '',
                vlan.descrizione or '',
                subnets_str,
                vlan.num_indirizzi
            ])
        
        self.message_user(request, f"Esportate {queryset.count()} VLAN selezionate.", messages.SUCCESS)
        return response
    export_selected_vlans.short_description = _("Esporta le VLAN selezionate in CSV")
    
    def export_all_vlans_view(self, request):
        """Vista per esportare tutte le VLAN in formato CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="tutte_vlan_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        # Intestazione CSV
        writer.writerow([
            'Numero VLAN', 'Nome', 'Descrizione', 'Subnets', 'Numero Indirizzi IP'
        ])
        
        # Ottieni tutte le VLAN ordinate per numero
        all_vlans = Vlan.objects.all().order_by('numero')
        
        # Dati
        for vlan in all_vlans:
            # Formatta le subnet in una singola stringa
            subnets_str = ""
            if vlan.subnets:
                subnets_list = [s.strip() for s in vlan.subnets.replace('\n', ',').split(',') if s.strip()]
                subnets_str = "; ".join(subnets_list)
            
            writer.writerow([
                vlan.numero,
                vlan.nome or '',
                vlan.descrizione or '',
                subnets_str,
                vlan.num_indirizzi
            ])
        
        return response
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-csv/', self.admin_site.admin_view(self.import_csv_view), name='import_vlan_csv'),
            path('export-all-csv/', self.admin_site.admin_view(self.export_all_vlans_view), name='export_all_vlan_csv'),
        ]
        return custom_urls + urls
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['import_csv_url'] = reverse('admin:import_vlan_csv')
        extra_context['export_all_csv_url'] = reverse('admin:export_all_vlan_csv')
        return super().changelist_view(request, extra_context=extra_context)
    
    def import_csv_view(self, request):
        if request.method == "POST":
            form = CsvImportForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES['csv_file']
                
                if not csv_file.name.endswith('.csv'):
                    self.message_user(request, 'Il file non è in formato CSV', level=messages.ERROR)
                    return HttpResponseRedirect(request.path_info)
                
                # Leggi il file
                data_set = csv_file.read().decode('utf-8')
                io_string = io.StringIO(data_set)
                
                # Leggi l'intestazione per determinare il formato
                header = next(csv.reader(io_string, delimiter=',', quotechar='"'))
                header = [col.strip().lower().replace('"', '') for col in header]
                
                # Riposiziona il puntatore all'inizio del file dopo l'intestazione
                io_string.seek(0)
                next(io_string)  # Salta l'intestazione
                
                count = 0
                errors = 0
                
                # Determina il formato in base all'intestazione
                has_subnets = 'subnets' in header
                has_device_count = 'device count' in header
                has_port_count = 'port count' in header
                
                # Trova gli indici delle colonne
                vlan_id_index = next((i for i, col in enumerate(header) if 'vlan id' in col or 'id' in col), 0)
                vlan_name_index = next((i for i, col in enumerate(header) if 'vlan name' in col or 'name' in col), 1)
                subnets_index = next((i for i, col in enumerate(header) if 'subnets' in col), 2 if has_subnets else None)
                device_count_index = next((i for i, col in enumerate(header) if 'device count' in col), 2 if has_device_count else None)
                port_count_index = next((i for i, col in enumerate(header) if 'port count' in col), 3 if has_port_count else None)
                description_index = next((i for i, col in enumerate(header) if 'description' in col or 'descrizione' in col), None)
                
                for line in csv.reader(io_string, delimiter=',', quotechar='"'):
                    try:
                        if len(line) >= 2:  # Almeno ID e Nome sono necessari
                            vlan_numero = int(line[vlan_id_index].strip())
                            vlan_nome = line[vlan_name_index].strip()
                            
                            # Inizializza i valori predefiniti
                            vlan_subnets = None
                            vlan_descrizione = None
                            
                            # Estrai subnet se disponibile
                            if has_subnets and subnets_index is not None and len(line) > subnets_index:
                                vlan_subnets = line[subnets_index].strip()
                            
                            # Usa device_count e port_count come descrizione se non ci sono subnet
                            if not has_subnets and has_device_count and has_port_count:
                                device_count = line[device_count_index].strip() if len(line) > device_count_index else ""
                                port_count = line[port_count_index].strip() if len(line) > port_count_index else ""
                                vlan_descrizione = f"Device Count: {device_count}, Port Count: {port_count}"
                            
                            # Usa la descrizione esplicita se disponibile
                            if description_index is not None and len(line) > description_index:
                                vlan_descrizione = line[description_index].strip()
                            
                            # Crea o aggiorna la VLAN
                            obj, created = Vlan.objects.update_or_create(
                                numero=vlan_numero,
                                defaults={
                                    'nome': vlan_nome,
                                    'subnets': vlan_subnets,
                                    'descrizione': vlan_descrizione,
                                }
                            )
                            
                            if created:
                                count += 1
                    except Exception as e:
                        errors += 1
                        self.message_user(
                            request, 
                            f'Errore nella riga {count+errors}: {str(e)}', 
                            level=messages.ERROR
                        )
                
                self.message_user(
                    request, 
                    f'Importazione CSV completata: {count} nuove VLAN create, {errors} errori riscontrati', 
                    level=messages.SUCCESS
                )
                return HttpResponseRedirect(reverse('admin:reti_app_vlan_changelist'))
        else:
            form = CsvImportForm()
        
        context = {
            'form': form,
            'title': _("Importa VLAN da CSV"),
            'opts': self.model._meta,
            'app_label': self.model._meta.app_label,
        }
        
        return TemplateResponse(
            request,
            "admin/csv_import.html",
            context,
        ) 

@admin.register(StoricoResponsabile)
class StoricoResponsabileAdmin(admin.ModelAdmin):
    list_display = ('indirizzo_ip', 'responsabile', 'data_inizio', 'data_fine', 'motivo_cambio', 'durata_display', 'created_by')
    list_filter = ('motivo_cambio', 'data_inizio', 'data_fine', 'created_by')
    search_fields = ('indirizzo_ip__ip', 'responsabile', 'utente_finale', 'note')
    readonly_fields = ('durata_assegnazione', 'giorni_assegnazione', 'created_at', 'is_attuale')
    date_hierarchy = 'data_inizio'
    
    fieldsets = (
        ('Informazioni Principali', {
            'fields': ('indirizzo_ip', 'responsabile', 'utente_finale')
        }),
        ('Date e Durata', {
            'fields': ('data_inizio', 'data_fine', 'durata_assegnazione', 'giorni_assegnazione', 'is_attuale')
        }),
        ('Dettagli', {
            'fields': ('motivo_cambio', 'note', 'stato_rete', 'disponibilita', 'vlan')
        }),
        ('Audit', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def durata_display(self, obj):
        """Mostra la durata in formato compatto per la lista"""
        if obj.data_inizio:
            durata = obj.durata_assegnazione
            giorni = durata.days
            if giorni > 0:
                return f"{giorni}g"
            else:
                ore = durata.seconds // 3600
                return f"{ore}h"
        return "-"
    durata_display.short_description = _("Durata")
    
    def get_queryset(self, request):
        """Ottimizza le query includendo le relazioni"""
        return super().get_queryset(request).select_related('indirizzo_ip', 'vlan') 

# Inline per UserProfile
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Permessi Login'
    fields = ('login_enabled',)

# Estendo l'admin del User per includere il profilo
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_login_enabled')
    list_filter = BaseUserAdmin.list_filter + ('profile__login_enabled',)
    actions = ['abilita_login', 'disabilita_login']  # Aggiungo le azioni personalizzate
    
    def get_login_enabled(self, obj):
        try:
            return obj.profile.login_enabled
        except UserProfile.DoesNotExist:
            # Crea automaticamente il profilo se non esiste
            # Abilita il login solo per admin, staff e superuser
            login_enabled = obj.is_staff or obj.is_superuser or obj.username == 'root'
            UserProfile.objects.create(user=obj, login_enabled=login_enabled)
            return login_enabled
    get_login_enabled.short_description = _("Login Abilitato")
    get_login_enabled.boolean = True
    
    def abilita_login(self, request, queryset):
        """Abilita il login per gli utenti selezionati"""
        updated = 0
        for user in queryset:
            try:
                user.profile.login_enabled = True
                user.profile.save()
                updated += 1
            except UserProfile.DoesNotExist:
                # Crea il profilo se non esiste
                UserProfile.objects.create(user=user, login_enabled=True)
                updated += 1
        
        if updated == 1:
            message = f"Login abilitato per 1 utente."
        else:
            message = f"Login abilitato per {updated} utenti."
        
        self.message_user(request, message, messages.SUCCESS)
    abilita_login.short_description = _("✅ Abilita login per utenti selezionati")
    
    def disabilita_login(self, request, queryset):
        """Disabilita il login per gli utenti selezionati"""
        updated = 0
        protected_users = []
        
        for user in queryset:
            # Proteggi admin, staff e superuser dalla disabilitazione
            if user.is_staff or user.is_superuser or user.username == 'root':
                protected_users.append(user.username)
                continue
                
            try:
                user.profile.login_enabled = False
                user.profile.save()
                updated += 1
            except UserProfile.DoesNotExist:
                # Crea il profilo disabilitato se non esiste
                UserProfile.objects.create(user=user, login_enabled=False)
                updated += 1
        
        # Costruisci il messaggio di risposta
        messages_list = []
        if updated > 0:
            if updated == 1:
                messages_list.append(f"Login disabilitato per 1 utente.")
            else:
                messages_list.append(f"Login disabilitato per {updated} utenti.")
        
        if protected_users:
            protected_str = ", ".join(protected_users[:3])  # Mostra solo i primi 3
            if len(protected_users) > 3:
                protected_str += f" e altri {len(protected_users) - 3}"
            messages_list.append(f"Utenti protetti non modificati: {protected_str}")
        
        final_message = " ".join(messages_list)
        message_level = messages.WARNING if protected_users else messages.SUCCESS
        self.message_user(request, final_message, message_level)
        
    disabilita_login.short_description = _("❌ Disabilita login per utenti selezionati")

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin) 