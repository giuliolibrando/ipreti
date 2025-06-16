from django.core.management.base import BaseCommand
from django.db.models import Count
from reti_app.models import Vlan, IndirizzoIP

class Command(BaseCommand):
    help = 'Aggiorna il conteggio degli indirizzi IP associati a ciascuna VLAN'
    
    def handle(self, *args, **options):
        self.stdout.write('Inizio aggiornamento conteggio IP nelle VLAN...')
        
        # Conteggio IP per VLAN (esplicito)
        vlan_counts = {}
        for vlan in Vlan.objects.all():
            # Conta gli indirizzi IP direttamente associati alla VLAN
            count = IndirizzoIP.objects.filter(vlan=vlan).count()
            vlan_counts[vlan.numero] = count
        
        # Aggiorna ogni VLAN con il conteggio calcolato
        for vlan in Vlan.objects.all():
            vlan.num_indirizzi = vlan_counts.get(vlan.numero, 0)
            vlan.save(update_fields=['num_indirizzi'])
            self.stdout.write(f'VLAN {vlan.numero} ({vlan.nome}): {vlan.num_indirizzi} indirizzi IP')
            
        self.stdout.write(self.style.SUCCESS('Conteggio IP aggiornato con successo!'))
        
        # Adesso controlla e associa gli IP senza VLAN
        self.stdout.write('Controllo indirizzi IP senza VLAN...')
        count = 0
        
        # Ottiene tutti gli IP senza VLAN assegnata
        ip_senza_vlan = IndirizzoIP.objects.filter(vlan__isnull=True)
        
        # Per ogni IP, trova la VLAN corrispondente in base alle subnet
        for ip_obj in ip_senza_vlan:
            vlan = Vlan.find_vlan_for_ip(ip_obj.ip)
            if vlan:
                # Associa l'IP alla VLAN trovata
                ip_obj.vlan = vlan
                ip_obj.save(update_fields=['vlan'])
                
                # Aggiorna il conteggio per questa VLAN
                vlan.num_indirizzi += 1
                vlan.save(update_fields=['num_indirizzi'])
                
                count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Associati {count} indirizzi IP alle VLAN corrispondenti')) 