from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
import ipaddress

class UserProfile(models.Model):
    """
    Estensione del modello User per aggiungere campi personalizzati
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name=_("Utente"))
    login_enabled = models.BooleanField(default=False, verbose_name=_("Login Abilitato"), 
                                       help_text=_("Se disabilitato, l'utente non potrà fare login anche se autenticato tramite LDAP"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Creato il"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Aggiornato il"))
    
    class Meta:
        verbose_name = _("Profilo Utente")
        verbose_name_plural = _("Profili Utente")
        
    def __str__(self):
        return f"Profilo di {self.user.username} - Login: {'Abilitato' if self.login_enabled else 'Disabilitato'}"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Crea automaticamente un profilo utente quando viene creato un nuovo utente
    """
    if created:
        # Abilita il login solo per admin, staff e superuser
        login_enabled = instance.is_staff or instance.is_superuser or instance.username == 'root'
        UserProfile.objects.create(user=instance, login_enabled=login_enabled)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Salva il profilo utente quando viene salvato l'utente
    """
    try:
        instance.profile.save()
    except UserProfile.DoesNotExist:
        # Abilita il login solo per admin, staff e superuser
        login_enabled = instance.is_staff or instance.is_superuser or instance.username == 'root'
        UserProfile.objects.create(user=instance, login_enabled=login_enabled)

class Vlan(models.Model):
    """
    Modello per rappresentare le VLAN
    """
    numero = models.IntegerField(primary_key=True, verbose_name=_("Numero VLAN"))
    nome = models.CharField(max_length=100, verbose_name=_("Nome VLAN"))
    descrizione = models.TextField(blank=True, null=True, verbose_name=_("Descrizione"))
    subnets = models.TextField(blank=True, null=True, verbose_name=_("Subnets"), 
                              help_text=_("Lista di subnet separate da virgola o nuova linea"))
    gateway = models.GenericIPAddressField(protocol='IPv4', blank=True, null=True, verbose_name=_("Gateway"))
    num_indirizzi = models.IntegerField(default=0, verbose_name=_("Numero di indirizzi IP"), help_text=_("Campo aggiornato periodicamente tramite cron job"))
    
    class Meta:
        verbose_name = _("VLAN")
        verbose_name_plural = _("VLAN")
        ordering = ['numero']
        
    def __str__(self):
        return f"{self.numero} - {self.nome}"
        
    @property
    def subnet(self):
        """
        Backward compatibility per il campo subnet originale
        Restituisce la prima subnet della lista
        """
        if not self.subnets:
            return None
            
        # Divide per virgola o nuova linea e restituisce il primo elemento
        subnets_list = [s.strip() for s in self.subnets.replace('\n', ',').split(',')]
        return subnets_list[0] if subnets_list else None
        
    def get_subnets_list(self):
        """
        Restituisce una lista di tutte le subnet associate alla VLAN,
        normalizzando eventuali formati incompleti
        """
        if not self.subnets:
            return []
            
        subnet_list = [s.strip() for s in self.subnets.replace('\n', ',').split(',') if s.strip()]
        normalized_subnets = []
        
        for subnet in subnet_list:
            # Controlla se è una subnet con formato incompleto (es. 192.168.254./24)
            if '/' in subnet:
                ip_part, mask = subnet.split('/')
                # Se termina con un punto seguito dalla maschera, aggiungi '0'
                if ip_part.endswith('.'):
                    subnet = f"{ip_part}0/{mask}"
            
            normalized_subnets.append(subnet)
            
        return normalized_subnets
    
    def contains_ip(self, ip_address):
        """
        Verifica se l'indirizzo IP specificato appartiene a una delle subnet della VLAN
        
        Args:
            ip_address: Indirizzo IP da verificare (stringa)
            
        Returns:
            bool: True se l'IP appartiene a una delle subnet, False altrimenti
        """
        if not self.subnets or not ip_address:
            # Disabilitato per performance: print(f"DEBUG - VLAN {self.numero}: nessuna subnet o IP non valido")
            return False
            
        try:
            # Converti l'indirizzo IP in un oggetto ipaddress.IPv4Address
            ip = ipaddress.IPv4Address(ip_address)
            # Disabilitato per performance: print(f"DEBUG - VLAN {self.numero}: verificando IP {ip_address}")
            
            # Controlla ogni subnet
            for subnet_cidr in self.get_subnets_list():
                try:
                    # Crea un oggetto network dalla subnet CIDR
                    network = ipaddress.IPv4Network(subnet_cidr, strict=False)
                    # Disabilitato per performance: print(f"DEBUG - VLAN {self.numero}: confrontando con subnet {subnet_cidr}")
                    
                    # Verifica se l'IP è nella subnet
                    if ip in network:
                        # Disabilitato per performance: print(f"DEBUG - VLAN {self.numero}: trovata corrispondenza per {ip_address} in {subnet_cidr}")
                        return True
                except ValueError as e:
                    # Ignora subnet non valide
                    # Disabilitato per performance: print(f"DEBUG - VLAN {self.numero}: errore subnet non valida {subnet_cidr}: {str(e)}")
                    continue
                    
            # Disabilitato per performance: print(f"DEBUG - VLAN {self.numero}: nessuna corrispondenza trovata per {ip_address}")
            return False
        except ValueError as e:
            # Indirizzo IP non valido
            # Disabilitato per performance: print(f"DEBUG - VLAN {self.numero}: IP non valido {ip_address}: {str(e)}")
            return False
            
    @classmethod
    def find_vlan_for_ip(cls, ip_address):
        """
        Trova la VLAN a cui appartiene l'indirizzo IP specificato
        
        Args:
            ip_address: Indirizzo IP da cercare (stringa)
            
        Returns:
            Vlan o None: Oggetto VLAN se trovato, altrimenti None
        """
        if not ip_address:
            return None
            
        # Ottimizzazione: filtra prima le VLAN con subnet
        vlans_with_subnets = cls.objects.exclude(subnets__isnull=True).exclude(subnets='')
        
        # Verifica con priorità le VLAN più comuni
        for vlan in vlans_with_subnets:
            if vlan.contains_ip(ip_address):
                return vlan
                
        return None


class IndirizzoIP(models.Model):
    """
    Modello per rappresentare un indirizzo IP.
    Basato sui dati precedentemente gestiti in Drupal con il tipo di contenuto 'indirizzo_ip'.
    """
    STATO_CHOICES = [
        ('attivo', _('Attivo')),
        ('disattivo', _('Disattivo')),
    ]
    
    DISPONIBILITA_CHOICES = [
        ('libero', _('Libero')),
        ('usato', _('Usato')),
        ('riservato', _('Riservato')),
    ]
    
    ip = models.GenericIPAddressField(primary_key=True, protocol='IPv4', verbose_name=_("Indirizzo IP"))
    mac_address = models.CharField(max_length=17, blank=True, null=True, verbose_name=_("MAC Address"), db_index=True)
    stato = models.CharField(max_length=20, choices=STATO_CHOICES, default='disattivo', verbose_name=_("Stato Rete"), db_index=True, help_text=_("Indica se l'IP sta navigando in rete"))
    disponibilita = models.CharField(max_length=20, choices=DISPONIBILITA_CHOICES, default='libero', verbose_name=_("Disponibilità"), db_index=True, help_text=_("Libero: disponibile per richieste | Usato: assegnato a un utente | Riservato: non assegnabile temporaneamente"))
    responsabile = models.EmailField(max_length=255, blank=True, null=True, verbose_name=_("Mail Responsabile"), db_index=True)
    utente_finale = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Utente Finale"))
    note = models.TextField(blank=True, null=True, verbose_name=_("Note"))
    ultimo_controllo = models.DateTimeField(default=timezone.now, verbose_name=_("Ultimo Controllo"))
    data_creazione = models.DateTimeField(auto_now_add=True, verbose_name=_("Data Creazione"))
    data_modifica = models.DateTimeField(auto_now=True, verbose_name=_("Data Modifica"), db_index=True)
    data_scadenza = models.DateTimeField(blank=True, null=True, verbose_name=_("Data Scadenza"), db_index=True)
    assegnato_a_utente = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, 
                                          verbose_name=_("Assegnato a"), related_name='indirizzi_assegnati', db_index=True)
    vlan = models.ForeignKey(Vlan, on_delete=models.SET_NULL, blank=True, null=True, 
                            verbose_name=_("VLAN"), related_name='indirizzi', db_index=True)
    
    class Meta:
        verbose_name = _("Indirizzo IP")
        verbose_name_plural = _("Indirizzi IP")
        ordering = ['ip']
        indexes = [
            models.Index(fields=['stato', 'vlan']),
            models.Index(fields=['stato', 'assegnato_a_utente']),
            models.Index(fields=['data_scadenza', 'stato']),
            models.Index(fields=['disponibilita', 'stato']),
        ]
    
    def __str__(self):
        return self.ip
    
    def is_scaduto(self):
        """Verifica se l'indirizzo IP è scaduto"""
        if self.data_scadenza:
            return self.data_scadenza < timezone.now()
        return False
    
    def giorni_alla_scadenza(self):
        """Calcola i giorni rimanenti alla scadenza"""
        if self.data_scadenza:
            delta = self.data_scadenza - timezone.now()
            return delta.days
        return None
    
    def is_disponibile(self):
        """Verifica se l'IP è disponibile per la richiesta"""
        return self.disponibilita == 'libero'
    
    def is_anomalo(self):
        """Verifica se l'IP è in uno stato anomalo (attivo ma libero/senza responsabile)"""
        return self.stato == 'attivo' and (self.disponibilita == 'libero' or not self.responsabile)
    
    def get_stato_completo(self):
        """Restituisce una descrizione completa dello stato dell'IP"""
        stato_rete = self.get_stato_display()
        disponibilita = self.get_disponibilita_display()
        if self.is_anomalo():
            return f"{stato_rete} - {disponibilita} (ANOMALO)"
        return f"{stato_rete} - {disponibilita}"
    
    def is_inattivo_da_ore(self, ore):
        """Verifica se l'IP è inattivo da più di X ore"""
        if not self.ultimo_controllo:
            return True
        delta = timezone.now() - self.ultimo_controllo
        return delta.total_seconds() > (ore * 3600)
    
    def ore_inattivita(self):
        """Calcola le ore di inattività dell'IP"""
        if not self.ultimo_controllo:
            return float('inf')
        delta = timezone.now() - self.ultimo_controllo
        return delta.total_seconds() / 3600 
    
    def get_storico_responsabili(self):
        """Restituisce lo storico dei responsabili ordinato dal più recente"""
        return self.storico_responsabili.all().order_by('-data_inizio')
    
    def get_responsabile_attuale_da_storico(self):
        """Restituisce il responsabile attuale dallo storico (quello senza data_fine)"""
        try:
            return self.storico_responsabili.filter(data_fine__isnull=True).first()
        except:
            return None
    
    def cambia_responsabile(self, nuovo_responsabile, utente_finale=None, motivo='cambio', note=None, created_by=None):
        """
        Cambia il responsabile dell'IP e aggiorna lo storico
        
        Args:
            nuovo_responsabile: Email del nuovo responsabile (None per liberare)
            utente_finale: Nome utente finale
            motivo: Motivo del cambio (da MOTIVO_CHOICES)
            note: Note aggiuntive
            created_by: Chi ha effettuato il cambio
        """
        vecchio_responsabile = self.responsabile
        vecchio_utente_finale = self.utente_finale
        now = timezone.now()
        
        # Se c'è un cambio effettivo di responsabile
        if vecchio_responsabile != nuovo_responsabile:
            # Chiudi il record precedente se esiste
            record_attuale = self.get_responsabile_attuale_da_storico()
            if record_attuale:
                record_attuale.data_fine = now
                if note:
                    record_attuale.note = (record_attuale.note or '') + f"\n[{now.strftime('%d/%m/%Y %H:%M')}] {note}"
                record_attuale.save()
            
            # Se stiamo rilasciando (nuovo_responsabile è None), usa i dati attuali per lo storico
            if nuovo_responsabile is None:
                # Crea un record di rilascio con i dati precedenti
                nuovo_record = self.storico_responsabili.create(
                    responsabile=None,  # Il nuovo stato è libero
                    utente_finale=None,  # Il nuovo stato è libero
                    data_inizio=now,
                    motivo_cambio=motivo,
                    note=f"Rilasciato da {vecchio_responsabile or 'N/A'} ({vecchio_utente_finale or 'N/A'}). {note or ''}",
                    stato_rete=self.stato,
                    disponibilita='libero',  # Nuovo stato
                    vlan=self.vlan,
                    created_by=created_by or 'sistema'
                )
                
                # Aggiorna il record principale - libera tutto
                self.responsabile = None
                self.utente_finale = None
                self.assegnato_a_utente = None  # IMPORTANTE: rimuovi assegnazione utente
                self.disponibilita = 'libero'
                # IMPORTANTE: Svuota il campo note quando l'IP viene rilasciato
                self.note = None
            else:
                # Crea nuovo record nello storico per assegnazione
                nuovo_record = self.storico_responsabili.create(
                    responsabile=nuovo_responsabile,
                    utente_finale=utente_finale or self.utente_finale,
                    data_inizio=now,
                    motivo_cambio=motivo,
                    note=note,
                    stato_rete=self.stato,
                    disponibilita='usato',  # Nuovo stato
                    vlan=self.vlan,
                    created_by=created_by or 'sistema'
                )
                
                # Aggiorna il record principale
                self.responsabile = nuovo_responsabile
                if utente_finale is not None:
                    self.utente_finale = utente_finale
                self.disponibilita = 'usato'
                
                # Aggiungi nota al campo note principale solo quando si assegna (non quando si rilascia)
                if note:
                    if self.note:
                        self.note += f"\n[{now.strftime('%d/%m/%Y %H:%M')}] {note}"
                    else:
                        self.note = f"[{now.strftime('%d/%m/%Y %H:%M')}] {note}"
            
            self.save()
            return nuovo_record
        
        return None
    
    def rilascia_ip(self, motivo='rilascio', note=None, created_by=None):
        """
        Rilascia l'IP (libera il responsabile)
        """
        return self.cambia_responsabile(
            nuovo_responsabile=None,
            utente_finale=None,
            motivo=motivo,
            note=note or f"IP rilasciato - {motivo}",
            created_by=created_by
        )
    
    def assegna_ip(self, responsabile, utente_finale=None, note=None, created_by=None):
        """
        Assegna l'IP a un nuovo responsabile
        """
        # Se l'IP non ha ancora uno storico, inizializzalo prima
        if not self.storico_responsabili.exists() and self.responsabile:
            # Crea il record iniziale per l'assegnazione precedente
            self.storico_responsabili.create(
                responsabile=self.responsabile,
                utente_finale=self.utente_finale,
                data_inizio=self.data_creazione or timezone.now(),
                motivo_cambio='assegnazione',
                note="Record iniziale per assegnazione precedente",
                stato_rete=self.stato,
                disponibilita=self.disponibilita,
                vlan=self.vlan,
                created_by='sistema_inizializzazione'
            )
        
        return self.cambia_responsabile(
            nuovo_responsabile=responsabile,
            utente_finale=utente_finale,
            motivo='assegnazione',
            note=note or f"IP assegnato a {responsabile}",
            created_by=created_by
        )
    
    def inizializza_storico(self, created_by='migrazione'):
        """
        Inizializza lo storico per IP esistenti (da usare nella migrazione)
        """
        # Controlla se esiste già uno storico
        if self.storico_responsabili.exists():
            return None
            
        # Se l'IP ha un responsabile, crea il record iniziale
        if self.responsabile:
            return self.storico_responsabili.create(
                responsabile=self.responsabile,
                utente_finale=self.utente_finale,
                data_inizio=self.data_creazione or timezone.now(),
                motivo_cambio='assegnazione',
                note="Record iniziale creato durante migrazione",
                stato_rete=self.stato,
                disponibilita=self.disponibilita,
                vlan=self.vlan,
                created_by=created_by
            )
        
        return None

    def is_attuale(self):
        """Verifica se questo è il record attuale (senza data_fine)"""
        return self.data_fine is None

    @classmethod
    def objects_ordered_by_ip(cls):
        """
        Restituisce un queryset ordinato numericamente per IP usando INET_ATON di MySQL
        
        Returns:
            QuerySet: QuerySet ordinato per IP numerico
        """
        from django.db import connection
        if 'mysql' in connection.vendor:
            # MySQL: usa INET_ATON per ordinamento numerico
            return cls.objects.extra(
                select={'ip_as_int': 'INET_ATON(ip)'}, 
                order_by=['ip_as_int']
            )
        else:
            # Fallback per altri database: ordinamento alfabetico
            return cls.objects.order_by('ip')


class StoricoResponsabile(models.Model):
    """
    Modello per tracciare lo storico dei responsabili di un indirizzo IP
    """
    MOTIVO_CHOICES = [
        ('assegnazione', _('Assegnazione Iniziale')),
        ('rilascio', _('Rilascio Volontario')),
        ('inattivita', _('Liberazione per Inattività')),
        ('scadenza', _('Liberazione per Scadenza')),
        ('cambio', _('Cambio Responsabile')),
        ('pulizia_automatica', _('Pulizia Automatica')),
        ('admin', _('Modifica Amministratore')),
    ]
    
    indirizzo_ip = models.ForeignKey(IndirizzoIP, on_delete=models.CASCADE, 
                                   related_name='storico_responsabili', 
                                   verbose_name=_("Indirizzo IP"), db_index=True)
    responsabile = models.EmailField(max_length=255, blank=True, null=True, 
                                   verbose_name=_("Mail Responsabile"), db_index=True)
    utente_finale = models.CharField(max_length=255, blank=True, null=True, 
                                   verbose_name=_("Utente Finale"))
    data_inizio = models.DateTimeField(verbose_name=_("Data Inizio Assegnazione"), db_index=True)
    data_fine = models.DateTimeField(blank=True, null=True, 
                                   verbose_name=_("Data Fine Assegnazione"), db_index=True)
    motivo_cambio = models.CharField(max_length=30, choices=MOTIVO_CHOICES, 
                                   blank=True, null=True, verbose_name=_("Motivo Cambio"))
    note = models.TextField(blank=True, null=True, verbose_name=_("Note"))
    
    # Campi per tracciare lo stato al momento dell'assegnazione/rilascio
    stato_rete = models.CharField(max_length=20, blank=True, null=True, 
                                verbose_name=_("Stato Rete al momento"))
    disponibilita = models.CharField(max_length=20, blank=True, null=True, 
                                   verbose_name=_("Disponibilità al momento"))
    vlan = models.ForeignKey(Vlan, on_delete=models.SET_NULL, blank=True, null=True, 
                           verbose_name=_("VLAN al momento"))
    
    # Timestamp per audit
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Creato il"))
    created_by = models.CharField(max_length=100, blank=True, null=True, 
                                verbose_name=_("Creato da"), 
                                help_text=_("Sistema o utente che ha creato il record"))
    
    class Meta:
        verbose_name = _("Storico Responsabile")
        verbose_name_plural = _("Storico Responsabili")
        ordering = ['-data_inizio']
        indexes = [
            models.Index(fields=['indirizzo_ip', '-data_inizio']),
            models.Index(fields=['responsabile', '-data_inizio']),
            models.Index(fields=['data_inizio', 'data_fine']),
        ]
    
    def __str__(self):
        if self.responsabile:
            periodo = f"dal {self.data_inizio.strftime('%d/%m/%Y %H:%M')}"
            if self.data_fine:
                periodo += f" al {self.data_fine.strftime('%d/%m/%Y %H:%M')}"
            else:
                periodo += " (attuale)"
            return f"{self.indirizzo_ip.ip} - {self.responsabile} {periodo}"
        else:
            return f"{self.indirizzo_ip.ip} - Libero dal {self.data_inizio.strftime('%d/%m/%Y %H:%M')}"
    
    @property
    def durata_assegnazione(self):
        """Calcola la durata dell'assegnazione"""
        fine = self.data_fine or timezone.now()
        return fine - self.data_inizio
    
    @property
    def giorni_assegnazione(self):
        """Restituisce il numero di giorni di assegnazione"""
        return self.durata_assegnazione.days
    
    def is_attuale(self):
        """Verifica se questo è il record attuale (senza data_fine)"""
        return self.data_fine is None

    @classmethod
    def order_by_inet_aton(cls, ip_field):
        """
        Ordina i queryset di IP numericamente usando INET_ATON di MySQL
        
        Args:
            ip_field: Campo del modello che contiene l'indirizzo IP
            
        Returns:
            QuerySet: QuerySet ordinato
        """
        return cls.objects.extra(select={'ip_aton': 'INET_ATON(%s)' % ip_field}, order_by='ip_aton')
    
    def get_ip_aton(self):
        """Restituisce il valore INET_ATON dell'indirizzo IP"""
        return ipaddress.IPv4Address(self.indirizzo_ip.ip).packed.hex() 