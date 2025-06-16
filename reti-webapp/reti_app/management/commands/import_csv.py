import csv
import io
import datetime
import re
from django.core.management.base import BaseCommand
from django.utils import timezone
from reti_app.models import IndirizzoIP, Vlan
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Importa indirizzi IP da un file CSV'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path del file CSV da importare')
        parser.add_argument('--format', type=str, default='nuovo', choices=['nuovo', 'originale'],
                           help='Formato del file CSV (nuovo o originale)')
        parser.add_argument('--delete', action='store_true', help='Elimina tutti i dati esistenti prima dell\'importazione')

    def handle(self, *args, **options):
        if options['delete']:
            self.stdout.write(self.style.WARNING('Eliminazione dei dati esistenti...'))
            IndirizzoIP.objects.all().delete()
            Vlan.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Dati eliminati con successo'))

        csv_file_path = options['csv_file']
        format_choice = options['format']
        
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as file:
                # Leggi il file
                data_set = file.read()
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
                    
                    self.stdout.write(f"Processando batch {start_idx//batch_size + 1}/{(total_lines+batch_size-1)//batch_size}: righe {start_idx+1}-{end_idx}")
                    
                    # Lista di IP nel batch corrente che richiedono associazione VLAN
                    batch_ip_addresses = []
                    
                    # Processa ogni riga nel batch corrente
                    for line in batch_lines:
                        try:
                            if format_choice == 'nuovo':
                                # Formato nuovo: IP,MAC Address,Stato,Responsabile,Utente Finale,Note,Ultimo Controllo,Data Scadenza
                                if len(line) >= 1:  # Almeno l'IP è necessario
                                    ip_address = line[0].strip()
                                    mac_address = line[1].strip() if len(line) > 1 and line[1] else None
                                    stato = line[2].lower().strip() if len(line) > 2 and line[2] else 'disattivo'
                                    
                                    # Verifica che lo stato sia valido
                                    if stato not in [choice[0] for choice in IndirizzoIP.STATO_CHOICES]:
                                        stato = 'disattivo'
                                    
                                    # Campi opzionali
                                    responsabile = line[3].strip() if len(line) > 3 and line[3] else None
                                    utente_finale = line[4].strip() if len(line) > 4 and line[4] else None
                                    note = line[5].strip() if len(line) > 5 and line[5] else None
                                    
                                    # Data ultimo controllo
                                    ultimo_controllo = timezone.now()
                                    if len(line) > 6 and line[6]:
                                        try:
                                            naive_datetime = datetime.datetime.strptime(line[6].strip(), "%Y-%m-%d %H:%M:%S")
                                            # Converti in formato aware con il timezone corrente
                                            ultimo_controllo = timezone.make_aware(naive_datetime)
                                        except ValueError:
                                            ultimo_controllo = timezone.now()
                                    
                                    # Data scadenza
                                    data_scadenza = None
                                    if len(line) > 7 and line[7]:
                                        try:
                                            naive_datetime = datetime.datetime.strptime(line[7].strip(), "%Y-%m-%d %H:%M:%S")
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
                                    
                                    # Decodifica stato (considerando anche disponibilità)
                                    stato = 'disattivo'
                                    if len(line) > 1 and line[1]:
                                        stato_orig = line[1].lower().strip()
                                        if 'attiv' in stato_orig:
                                            stato = 'attivo'
                                        elif 'riserv' in stato_orig:
                                            stato = 'riservato'
                                    
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
                                
                            # Controlla se l'email del responsabile esiste e crea l'utente Django
                            utente_django = None
                            if responsabile and '@' in responsabile:
                                try:
                                    utente_django = User.objects.get(username=responsabile)
                                    users_created += 1
                                except User.DoesNotExist:
                                    pass
                                    
                            # Crea o aggiorna l'indirizzo IP
                            obj, created = IndirizzoIP.objects.update_or_create(
                                ip=ip_address,
                                defaults={
                                    'mac_address': mac_address,
                                    'stato': stato,
                                    'responsabile': responsabile,
                                    'utente_finale': utente_finale,
                                    'note': note,
                                    'ultimo_controllo': ultimo_controllo,
                                    'data_scadenza': data_scadenza,
                                    'assegnato_a_utente': utente_django,
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
                            self.stderr.write(f'Errore nella riga {start_idx + batch_lines.index(line) + 1}: {str(e)}')
                    
                    # Associa gli IP alle VLAN all'interno dello stesso batch
                    if batch_ip_addresses:
                        self.stdout.write(f"Associando VLAN per {len(batch_ip_addresses)} indirizzi IP nel batch corrente...")
                        
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
                                self.stdout.write(f"IP {ip} associato a VLAN {vlan.numero} ({vlan.nome})")
                            except Exception as e:
                                self.stderr.write(f"Errore nell'associazione VLAN per IP {ip}: {str(e)}")
                
                self.stdout.write(self.style.SUCCESS(
                    f"Associati {vlan_associations} indirizzi IP alle VLAN corrispondenti"
                ))
                
                self.stdout.write(self.style.SUCCESS(
                    f'Importazione CSV completata: {count} nuovi IP creati, {users_created} utenti trovati, ' 
                    f'{ips_assigned} indirizzi IP assegnati, {errors} errori riscontrati'
                ))
                
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f'File {csv_file_path} non trovato!'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Errore durante l\'importazione: {str(e)}')) 