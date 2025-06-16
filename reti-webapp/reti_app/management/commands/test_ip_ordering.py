from django.core.management.base import BaseCommand
from reti_app.models import IndirizzoIP
from django.db import connection

class Command(BaseCommand):
    help = 'Testa l\'ordinamento numerico degli IP'

    def handle(self, *args, **options):
        # Test 1: Ordinamento base
        self.stdout.write("Test 1: Ordinamento base")
        ips = IndirizzoIP.objects.all()[:10]  # Prendi i primi 10 IP
        self.stdout.write("IP ordinati alfabeticamente:")
        for ip in ips:
            self.stdout.write(f"- {ip.ip}")
            
        # Test 2: Ordinamento numerico
        self.stdout.write("\nTest 2: Ordinamento numerico")
        if 'mysql' in connection.vendor:
            ips = IndirizzoIP.objects.extra(
                select={'ip_as_int': 'INET_ATON(ip)'}, 
                order_by=['ip_as_int']
            )[:10]
            self.stdout.write("IP ordinati numericamente (MySQL INET_ATON):")
            for ip in ips:
                self.stdout.write(f"- {ip.ip}")
        else:
            self.stdout.write("Database non MySQL - usando ordinamento alfabetico")
            
        # Test 3: Ordinamento con metodo della classe
        self.stdout.write("\nTest 3: Ordinamento con metodo della classe")
        ips = IndirizzoIP.objects_ordered_by_ip()[:10]
        self.stdout.write("IP ordinati con metodo della classe:")
        for ip in ips:
            self.stdout.write(f"- {ip.ip}") 