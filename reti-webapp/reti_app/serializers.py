from rest_framework import serializers
from .models import IndirizzoIP, Vlan, StoricoResponsabile

class VlanSerializer(serializers.ModelSerializer):
    """Serializer semplificato per le VLAN"""
    class Meta:
        model = Vlan
        fields = ['numero', 'nome', 'subnets', 'num_indirizzi']

class StoricoResponsabileSerializer(serializers.ModelSerializer):
    """
    Serializer per lo storico dei responsabili di un IP
    """
    durata_giorni = serializers.SerializerMethodField()
    is_attuale = serializers.SerializerMethodField()
    vlan_numero = serializers.IntegerField(source='vlan.numero', read_only=True)
    vlan_nome = serializers.CharField(source='vlan.nome', read_only=True)
    
    class Meta:
        model = StoricoResponsabile
        fields = [
            'id', 'responsabile', 'utente_finale',
            'data_inizio', 'data_fine', 'motivo_cambio', 'note',
            'stato_rete', 'disponibilita', 'vlan_numero', 'vlan_nome',
            'durata_giorni', 'is_attuale', 'created_at', 'created_by'
        ]
    
    def get_durata_giorni(self, obj):
        """Restituisce la durata in giorni"""
        return obj.giorni_assegnazione
    
    def get_is_attuale(self, obj):
        """Verifica se è il record attuale"""
        return obj.is_attuale()

class IndirizzoIPSerializer(serializers.ModelSerializer):
    """
    Serializer completo per il modello IndirizzoIP.
    
    ## Campi di Base:
    - `ip`: Indirizzo IP (IPv4)
    - `mac_address`: Indirizzo MAC (opzionale)
    - `stato`: attivo/disattivo (indica se naviga in rete)
    - `disponibilita`: libero/usato (indica se richiesto da utente)
    - `responsabile`: Email del responsabile
    - `utente_finale`: Nome dell'utente finale
    - `note`: Note libere
    - `ultimo_controllo`: Timestamp ultimo controllo attività
    - `data_scadenza`: Data di scadenza calcolata
    - `assegnato_a_utente`: ID utente Django assegnato
    - `vlan`: Oggetto VLAN associato
    - `storico_responsabili`: Storico dei responsabili precedenti
    
    ## Campi Calcolati (sola lettura):
    - `is_anomalo`: True se IP attivo ma libero
    - `is_scaduto`: True se IP ha data scadenza nel passato
    - `ore_inattivita`: Ore di inattività
    - `giorni_alla_scadenza`: Giorni rimanenti alla scadenza
    """
    
    # Campi di relazione
    vlan = VlanSerializer(read_only=True)
    vlan_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    assegnato_a_utente_email = serializers.EmailField(source='assegnato_a_utente.email', read_only=True)
    storico_responsabili = StoricoResponsabileSerializer(many=True, read_only=True)
    
    # Campi calcolati (sola lettura)
    is_anomalo = serializers.SerializerMethodField()
    is_scaduto = serializers.SerializerMethodField()
    ore_inattivita = serializers.SerializerMethodField()
    giorni_alla_scadenza = serializers.SerializerMethodField()
    
    class Meta:
        model = IndirizzoIP
        fields = [
            # Campi base
            'ip', 'mac_address', 'stato', 'disponibilita', 
            'responsabile', 'utente_finale', 'note',
            'ultimo_controllo', 'data_creazione', 'data_modifica', 'data_scadenza',
            # Relazioni
            'vlan', 'vlan_id', 'assegnato_a_utente', 'assegnato_a_utente_email',
            'storico_responsabili',
            # Campi calcolati
            'is_anomalo', 'is_scaduto',
            'ore_inattivita', 'giorni_alla_scadenza'
        ]
        read_only_fields = [
            'data_creazione', 'data_modifica', 'storico_responsabili',
            'is_anomalo', 'is_scaduto',
            'ore_inattivita', 'giorni_alla_scadenza'
        ]
    
    def get_is_anomalo(self, obj):
        """IP anomalo: attivo ma libero o senza responsabile"""
        return obj.is_anomalo()
    
    def get_is_scaduto(self, obj):
        """IP scaduto: ha data scadenza nel passato"""
        return obj.is_scaduto()
    
    def get_ore_inattivita(self, obj):
        """Ore di inattività dall'ultimo controllo"""
        ore = obj.ore_inattivita()
        return None if ore == float('inf') else round(ore, 2)
    
    def get_giorni_alla_scadenza(self, obj):
        """Giorni rimanenti alla scadenza"""
        return obj.giorni_alla_scadenza()
    
    def validate_ip(self, value):
        """Validazione personalizzata per l'IP"""
        from .views import is_valid_ip_range
        
        # Verifica se l'IP è in un range valido
        is_valid, message = is_valid_ip_range(value)
        if not is_valid:
            raise serializers.ValidationError(f"IP non valido: {message}")
        
        return value
    
    def validate(self, data):
        """Validazione a livello di oggetto"""
        # Se l'IP è marcato come usato, deve avere un responsabile
        if data.get('disponibilita') == 'usato' and not data.get('responsabile'):
            raise serializers.ValidationError(
                "Un IP marcato come 'usato' deve avere un responsabile"
            )
        
        # Se c'è un responsabile, l'IP dovrebbe essere usato
        if data.get('responsabile') and data.get('disponibilita') == 'libero':
            raise serializers.ValidationError(
                "Un IP con responsabile dovrebbe essere marcato come 'usato'"
            )
        
        # Gestione VLAN
        if 'vlan_id' in data:
            try:
                vlan = Vlan.objects.get(numero=data['vlan_id'])
                data['vlan'] = vlan
            except Vlan.DoesNotExist:
                raise serializers.ValidationError(f"VLAN {data['vlan_id']} non trovata")
            del data['vlan_id']
        
        return data
    
    def to_representation(self, instance):
        """Personalizza la rappresentazione dell'oggetto"""
        data = super().to_representation(instance)
        
        # Formatta le date in modo più leggibile
        if data.get('ultimo_controllo'):
            try:
                from django.utils import timezone
                ultimo_controllo = instance.ultimo_controllo
                data['ultimo_controllo_formattato'] = ultimo_controllo.strftime('%d/%m/%Y %H:%M:%S')
                data['ore_fa'] = round((timezone.now() - ultimo_controllo).total_seconds() / 3600, 1)
            except:
                pass
        
        if data.get('data_scadenza'):
            try:
                data['data_scadenza_formattata'] = instance.data_scadenza.strftime('%d/%m/%Y %H:%M:%S')
            except:
                pass
        
        return data

class IndirizzoIPCreateSerializer(serializers.ModelSerializer):
    """
    Serializer semplificato per la creazione di nuovi IP.
    Nasconde i campi complessi e si concentra sui dati essenziali.
    """
    vlan_id = serializers.IntegerField(required=False, allow_null=True)
    
    class Meta:
        model = IndirizzoIP
        fields = [
            'ip', 'mac_address', 'stato', 'disponibilita',
            'responsabile', 'utente_finale', 'note', 'vlan_id'
        ]
    
    def validate(self, data):
        """Validazione per la creazione"""
        # Usa la stessa validazione del serializer principale
        serializer = IndirizzoIPSerializer()
        return serializer.validate(data)

class IndirizzoIPUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer per aggiornamenti parziali.
    Permette di modificare solo alcuni campi specifici.
    """
    vlan_id = serializers.IntegerField(required=False, allow_null=True)
    
    class Meta:
        model = IndirizzoIP
        fields = [
            'mac_address', 'stato', 'disponibilita',
            'responsabile', 'utente_finale', 'note', 'data_scadenza',
            'vlan_id'
        ]
    
    def validate(self, data):
        """Validazione per gli aggiornamenti"""
        # Gestione VLAN - usa la stessa logica del serializer principale
        if 'vlan_id' in data:
            if data['vlan_id'] is None:
                # Rimuovi la VLAN (imposta a null)
                data['vlan'] = None
            else:
                try:
                    vlan = Vlan.objects.get(numero=data['vlan_id'])
                    data['vlan'] = vlan
                except Vlan.DoesNotExist:
                    raise serializers.ValidationError(f"VLAN {data['vlan_id']} non trovata")
            del data['vlan_id']
        
        return data 