from django.core.management.base import BaseCommand
from django.utils import timezone
from reti_app.models import IndirizzoIP

class Command(BaseCommand):
    help = 'Inizializza lo storico dei responsabili per gli IP esistenti'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra cosa verrebbe fatto senza applicare modifiche',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('MODALITÀ DRY-RUN: nessuna modifica verrà applicata'))
        
        # Trova tutti gli IP che hanno un responsabile ma non hanno storico
        ips_senza_storico = IndirizzoIP.objects.filter(
            responsabile__isnull=False
        ).exclude(
            responsabile=''
        ).filter(
            storico_responsabili__isnull=True
        )
        
        count = ips_senza_storico.count()
        self.stdout.write(f'Trovati {count} IP con responsabile ma senza storico')
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('Nessun IP da processare'))
            return
        
        if not dry_run:
            # Conferma dall'utente
            confirm = input(f'Vuoi inizializzare lo storico per {count} IP? (y/N): ')
            if confirm.lower() != 'y':
                self.stdout.write('Operazione annullata')
                return
        
        created_count = 0
        
        for ip in ips_senza_storico:
            if dry_run:
                self.stdout.write(f'[DRY-RUN] Creeresti storico per {ip.ip} - {ip.responsabile}')
            else:
                # Crea il record iniziale nello storico
                record = ip.storico_responsabili.create(
                    responsabile=ip.responsabile,
                    utente_finale=ip.utente_finale,
                    data_inizio=ip.data_creazione or timezone.now(),
                    motivo_cambio='assegnazione',
                    note="Record iniziale creato durante inizializzazione storico",
                    stato_rete=ip.stato,
                    disponibilita=ip.disponibilita,
                    vlan=ip.vlan,
                    created_by='comando_inizializza_storico'
                )
                created_count += 1
                self.stdout.write(f'Creato storico per {ip.ip} - {ip.responsabile}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'[DRY-RUN] Verrebbero creati {count} record di storico'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Inizializzazione completata: {created_count} record di storico creati')) 