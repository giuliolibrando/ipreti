import re
import os
import argparse
from django.core.management.base import BaseCommand
from django.utils import timezone
from reti_app.models import IndirizzoIP

class Command(BaseCommand):
    help = 'Importa i dati dal dump SQL del vecchio sistema Drupal'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, help='Percorso al file di dump SQL')

    def handle(self, *args, **options):
        dump_file = options['file']
        
        if not dump_file or not os.path.exists(dump_file):
            self.stdout.write(self.style.ERROR(f'File non trovato: {dump_file}'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Inizio importazione da {dump_file}'))
        
        # Contatori per le statistiche
        created = 0
        skipped = 0
        errors = 0
        
        # Estrai gli indirizzi IP dal dump
        try:
            with open(dump_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Cerca tutte le inserzioni nella tabella degli indirizzi IP
                # Adatta il pattern in base alla struttura effettiva del dump SQL
                ip_pattern = r"INSERT INTO `node`.*?VALUES \((.*?)\)"
                detail_pattern = r"INSERT INTO `field_data_field_(\w+)`.*?VALUES \((.*?)\)"
                
                # Raccogliamo prima i nodi base
                nodes = {}
                for match in re.finditer(ip_pattern, content, re.DOTALL):
                    try:
                        values = match.group(1).split(',')
                        # Estrai i valori necessari dai nodi
                        node_id = values[0].strip()
                        title = values[2].strip().strip("'").strip('"')  # Probabilmente l'indirizzo IP
                        
                        # Verifica se è un indirizzo IP
                        if re.match(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', title):
                            nodes[node_id] = {
                                'ip': title,
                                'mac_address': '',
                                'stato': 'disattivo',
                                'responsabile': '',
                                'utente_finale': '',
                                'note': '',
                                'ultimo_controllo': timezone.now()
                            }
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'Errore nel parsing del nodo: {e}'))
                
                # Ora raccogliamo i dettagli
                for field_type in ['mac_address', 'stato', 'mail_responsabile', 'utente_finale']:
                    pattern = detail_pattern.replace('(\w+)', field_type)
                    for match in re.finditer(pattern, content, re.DOTALL):
                        try:
                            values = match.group(2).split(',')
                            node_id = values[0].strip()
                            field_value = values[-1].strip().strip("'").strip('"')
                            
                            if node_id in nodes:
                                if field_type == 'mac_address':
                                    nodes[node_id]['mac_address'] = field_value
                                elif field_type == 'stato':
                                    nodes[node_id]['stato'] = field_value
                                elif field_type == 'mail_responsabile':
                                    nodes[node_id]['responsabile'] = field_value
                                elif field_type == 'utente_finale':
                                    nodes[node_id]['utente_finale'] = field_value
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(f'Errore nel parsing del campo {field_type}: {e}'))
                
                # Ora inseriamo i dati nel database
                for node_id, data in nodes.items():
                    try:
                        ip = data['ip']
                        
                        # Verifica se l'IP esiste già
                        if IndirizzoIP.objects.filter(ip=ip).exists():
                            self.stdout.write(self.style.WARNING(f'IP già esistente: {ip}'))
                            skipped += 1
                            continue
                        
                        # Crea il nuovo oggetto
                        IndirizzoIP.objects.create(
                            ip=ip,
                            mac_address=data['mac_address'],
                            stato=data['stato'],
                            responsabile=data['responsabile'],
                            utente_finale=data['utente_finale'],
                            note=data['note'],
                            ultimo_controllo=data['ultimo_controllo']
                        )
                        
                        created += 1
                        if created % 100 == 0:
                            self.stdout.write(self.style.SUCCESS(f'Importati {created} indirizzi IP...'))
                    
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Errore nell\'importazione dell\'IP {data["ip"]}: {e}'))
                        errors += 1
                        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Errore durante la lettura del file: {e}'))
            return
        
        self.stdout.write(self.style.SUCCESS(
            f'Importazione completata. Creati: {created}, Saltati: {skipped}, Errori: {errors}'
        )) 