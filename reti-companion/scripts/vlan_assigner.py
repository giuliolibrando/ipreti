#!/usr/bin/env python3
import sys
import os
import logging
from datetime import datetime
import ipaddress
import argparse

# Add the project root to Python path
sys.path.insert(0, '/app')

from django_client import DjangoAPIClient
from config.config import LOG_FILE, LOG_LEVEL, DJANGO_API_BASE_URL, DJANGO_API_TOKEN

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def fix_subnet_format(subnet):
    """Fix common subnet format issues"""
    if not subnet or not subnet.strip():
        return None
    
    subnet = subnet.strip()
    
    # Handle subnets ending with ./XX (missing last octet)
    if './' in subnet:
        parts = subnet.split('/')
        if len(parts) == 2:
            ip_part = parts[0]
            prefix = parts[1]
            
            # If IP ends with dot, add .0
            if ip_part.endswith('.'):
                fixed_ip = ip_part + '0'
                subnet = f"{fixed_ip}/{prefix}"
    
    # Handle leading zeros in octets (e.g., 172.016.112.)
    if '.' in subnet:
        parts = subnet.split('/')
        ip_part = parts[0]
        prefix = parts[1] if len(parts) > 1 else ''
        
        # Split IP into octets and remove leading zeros
        octets = ip_part.split('.')
        fixed_octets = []
        for octet in octets:
            if octet and octet != '0':
                # Remove leading zeros but keep single 0
                fixed_octet = octet.lstrip('0') or '0'
                fixed_octets.append(fixed_octet)
            else:
                fixed_octets.append(octet)
        
        fixed_ip = '.'.join(fixed_octets)
        subnet = f"{fixed_ip}/{prefix}" if prefix else fixed_ip
    
    # Try to validate and fix host bits set issues
    try:
        network = ipaddress.IPv4Network(subnet, strict=False)
        return str(network)
    except:
        return None

def update_ip_vlans():
    django_client = DjangoAPIClient()
    
    # Log configurazione per debug
    logger.info(f"API Base URL: {DJANGO_API_BASE_URL}")
    logger.info(f"API Token configurato: {'Sì' if DJANGO_API_TOKEN else 'No'}")
    logger.info(f"API Token (primi 10 caratteri): {DJANGO_API_TOKEN[:10] if DJANGO_API_TOKEN else 'N/A'}")
    
    # Verifica che l'API sia raggiungibile prima di iniziare
    logger.info("Verifica connessione API...")
    if not django_client.health_check():
        logger.error("API non raggiungibile, interrompo l'esecuzione")
        return
    
    # 1. Recupera tutte le VLAN e le subnet
    logger.info("Recupero VLAN...")
    vlans = django_client.get_all_vlans()  # Ogni vlan: {'numero': ..., 'subnets': ...}
    logger.info(f"Trovate {len(vlans)} VLAN")
    
    vlan_subnet_map = []
    for vlan in vlans:
        logger.debug(f"Processando VLAN {vlan.get('numero', 'N/A')}: {vlan}")
        subnets = vlan.get('subnets', [])
        if isinstance(subnets, str):
            # Gestisce caso stringa separata da virgole o newline
            subnets = [s.strip() for s in subnets.replace('\n', ',').split(',') if s.strip()]
        
        logger.debug(f"VLAN {vlan.get('numero')} ha subnets: {subnets}")
        
        for subnet in subnets:
            try:
                # Fix common subnet format issues
                fixed_subnet = fix_subnet_format(subnet)
                if fixed_subnet:
                    vlan_subnet_map.append((ipaddress.IPv4Network(fixed_subnet), vlan['numero']))
                    logger.debug(f"Aggiunta subnet {fixed_subnet} per VLAN {vlan['numero']}")
                else:
                    logger.warning(f"Impossibile correggere subnet '{subnet}' per VLAN {vlan['numero']}")
            except Exception as e:
                logger.warning(f"Subnet non valida '{subnet}' per VLAN {vlan['numero']}: {e}")
                continue

    logger.info(f"Mappatura subnet-VLAN creata con {len(vlan_subnet_map)} entry")

    # 2. Recupera tutti gli IP
    logger.info("Recupero IP...")
    all_ips = django_client.get_all_ips()
    logger.info(f"Trovati {len(all_ips)} IP")
    
    updated = 0
    checked = 0
    no_vlan_fixed = 0  # IP che non avevano VLAN e sono stati assegnati
    wrong_vlan_fixed = 0  # IP che avevano VLAN errata e sono stati corretti
    already_correct = 0  # IP che avevano già la VLAN corretta
    no_subnet_match = 0  # IP che non appartengono a nessuna subnet conosciuta
    vlan_updates = {}  # Traccia le VLAN che hanno avuto cambiamenti
    
    for ip_data in all_ips:
        ip_addr = ip_data['ip']
        current_vlan = ip_data.get('vlan')
        found_vlan = None
        
        logger.debug(f"Processing IP {ip_addr}, current VLAN: {current_vlan}")
        
        for subnet, vlan_num in vlan_subnet_map:
            try:
                if ipaddress.IPv4Address(ip_addr) in subnet:
                    found_vlan = vlan_num
                    logger.debug(f"IP {ip_addr} appartiene alla subnet {subnet} (VLAN {vlan_num})")
                    break
            except Exception as e:
                logger.warning(f"Errore parsing IP {ip_addr}: {e}")
                continue
        
        checked += 1
        
        # 1. Get current VLAN
        current_vlan_num = None
        if current_vlan:
            if isinstance(current_vlan, dict):
                current_vlan_num = current_vlan.get('numero')
            else:
                current_vlan_num = current_vlan
        
        logger.debug(f"IP {ip_addr}: current VLAN={current_vlan_num}, found VLAN={found_vlan}")
        
        # 2. Find the VLAN this IP should belong to
        found_vlan_obj = None
        for vlan in vlans:
            if vlan['numero'] == found_vlan:
                found_vlan_obj = ipaddress.IPv4Network(vlan['subnets'][0])
                break
        
        # 3. Analyze and update if necessary
        if found_vlan:
            if current_vlan_num == found_vlan:
                # IP already correct
                already_correct += 1
                logger.debug(f"IP {ip_addr} already correct (VLAN {found_vlan})")
            else:
                # IP needs VLAN update
                updated += 1
                if current_vlan is None:
                    no_vlan_fixed += 1
                    logger.info(f"Assigning VLAN {found_vlan} to IP {ip_addr} (previously no VLAN)")
                else:
                    wrong_vlan_fixed += 1
                    logger.info(f"Correcting VLAN for IP {ip_addr}: {current_vlan_num} -> {found_vlan}")
                
                # Update via API
                update_data = {'vlan': found_vlan}
                success = django_client.update_ip(ip_addr, update_data)
                if not success:
                    logger.error(f"Failed to update VLAN for IP {ip_addr}")
        else:
            # IP that doesn't belong to any known subnet
            no_subnet_match += 1
            logger.debug(f"IP {ip_addr} doesn't belong to any known subnet")
    
    # Print final report
    logger.info("VLAN ASSIGNMENT REPORT")
    logger.info("=" * 50)
    logger.info(f"IPs checked: {checked}")
    logger.info(f"IPs already with correct VLAN: {already_correct}")
    logger.info(f"IPs without VLAN (now assigned): {no_vlan_fixed}")
    logger.info(f"IPs with wrong VLAN (now corrected): {wrong_vlan_fixed}")
    logger.info(f"IPs without matching subnet: {no_subnet_match}")
    logger.info(f"TOTAL IPs updated: {updated}")
    logger.info("=" * 50)
    
    # 4. Update num_indirizzi count for all VLANs
    logger.info("Updating IP count in VLANs...")
    update_vlan_counts(django_client)

def update_vlan_counts(django_client):
    """Update the num_indirizzi count for all VLANs"""
    try:
        logger.info("Retrieving all VLANs...")
        vlans = django_client.get_all_vlans()
        logger.info(f"Found {len(vlans)} VLANs")
        
        logger.info("Retrieving all IPs...")
        ips = django_client.get_all_ips()
        logger.info(f"Found {len(ips)} IPs")
        
        # Count IPs by VLAN
        vlan_counts = {}
        for ip in ips:
            vlan_info = ip.get('vlan')
            if vlan_info:
                vlan_numero = vlan_info.get('numero')
                if vlan_numero:
                    vlan_counts[vlan_numero] = vlan_counts.get(vlan_numero, 0) + 1
        
        logger.info(f"IP count by VLAN: {vlan_counts}")
        
        updated_count = 0
        for vlan in vlans:
            vlan_numero = vlan.get('numero')
            current_count = vlan.get('num_indirizzi', 0)
            count = vlan_counts.get(vlan_numero, 0)
            
            if count != current_count:
                logger.info(f"Update needed for VLAN {vlan_numero}: {current_count} -> {count}")
                update_data = {'num_indirizzi': count}
                result = django_client.update_vlan(vlan_numero, update_data)
                if result:
                    logger.info(f"VLAN {vlan_numero} ({vlan.get('nome', '')}): updated from {current_count} to {count} IP addresses")
                    updated_count += 1
                else:
                    logger.error(f"Error updating count for VLAN {vlan_numero}")
            else:
                logger.debug(f"VLAN {vlan_numero} ({vlan.get('nome', '')}): count already correct ({count} IP addresses)")
        
        logger.info(f"Update completed: {updated_count} VLANs updated")
            
    except Exception as e:
        logger.error(f"Error during VLAN count update: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

def test_api_connection():
    """Test di connessione API per debug"""
    django_client = DjangoAPIClient()
    
    logger.info("=== TEST API CONNECTION ===")
    
    # Test health check
    health = django_client.health_check()
    logger.info(f"Health check: {'OK' if health else 'FAILED'}")
    
    if not health:
        logger.error("Health check fallito, impossibile continuare")
        return False
    
    # Test recupero VLAN
    try:
        vlans = django_client.get_all_vlans()
        logger.info(f"Test VLAN: Recuperate {len(vlans)} VLAN")
        if vlans:
            logger.info(f"Prima VLAN: {vlans[0]}")
    except Exception as e:
        logger.error(f"Errore recupero VLAN: {e}")
        return False
    
    # Test recupero IP
    try:
        ips = django_client.get_all_ips()
        logger.info(f"Test IP: Recuperati {len(ips)} IP")
        if ips:
            logger.info(f"Primo IP: {ips[0]}")
    except Exception as e:
        logger.error(f"Errore recupero IP: {e}")
        return False
    
    logger.info("=== FINE TEST ===")
    return True

def test_ip_update():
    """Specific test to verify if IP update works"""
    logger.info("=== IP UPDATE TEST ===")
    
    django_client = DjangoAPIClient()
    
    # 1. Check if we can retrieve a test IP
    test_ip = "151.100.83.4"  # Use a known IP in our database
    
    logger.info(f"1. Getting IP {test_ip}...")
    ip_data = django_client.get_ip_by_address(test_ip)
    
    if not ip_data:
        logger.error(f"Could not find IP {test_ip}")
        return False
    
    logger.info(f"Found IP: {ip_data}")
    
    # 2. Try to update the VLAN
    current_vlan = ip_data.get('vlan')
    if isinstance(current_vlan, dict):
        current_vlan_num = current_vlan.get('numero')
    else:
        current_vlan_num = current_vlan
    
    logger.info(f"Current VLAN: {current_vlan_num}")
    
    # Try updating with a simple format
    update_data = {'vlan': 777}  # Use a test VLAN
    
    logger.info(f"2. Attempting update with data: {update_data}")
    result = django_client.update_ip(test_ip, update_data)
    
    if result:
        logger.info("✅ Update succeeded!")
        logger.info(f"Result: {result}")
        
        # 3. Verify the change
        logger.info("3. Verifying the change...")
        updated_ip = django_client.get_ip_by_address(test_ip)
        if updated_ip:
            new_vlan = updated_ip.get('vlan')
            if isinstance(new_vlan, dict):
                new_vlan_num = new_vlan.get('numero')
            else:
                new_vlan_num = new_vlan
            logger.info(f"New VLAN: {new_vlan_num}")
            
            if new_vlan_num == 777:
                logger.info("✅ Change verified successfully!")
                
                # 4. Restore original VLAN
                if current_vlan_num:
                    restore_data = {'vlan': current_vlan_num}
                    logger.info(f"4. Restoring original VLAN: {restore_data}")
                    restore_result = django_client.update_ip(test_ip, restore_data)
                    if restore_result:
                        logger.info("✅ Original VLAN restored")
                    else:
                        logger.warning("⚠️ Could not restore original VLAN")
                
                return True
            else:
                logger.error(f"❌ Change not applied. Expected: 777, Got: {new_vlan_num}")
        else:
            logger.error("❌ Could not retrieve IP after update")
    else:
        logger.error("❌ Update failed")
    
    logger.info("Possible causes:")
    logger.info("1. VLAN 777 doesn't exist")
    logger.info("2. Missing permissions")
    logger.info("3. The field might expect a different format")
    logger.info("4. Special permissions might be required")
    
    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='VLAN Assigner Script')
    parser.add_argument('--test', action='store_true', help='Run only API connection test')
    parser.add_argument('--test-update', action='store_true', help='Specific test to verify if IP update works')
    parser.add_argument('--debug', action='store_true', help='Enable DEBUG logging')
    
    args = parser.parse_args()
    
    if args.debug:
        # Change logging level to DEBUG
        logging.getLogger().setLevel(logging.DEBUG)
        for handler in logging.getLogger().handlers:
            handler.setLevel(logging.DEBUG)
    
    logger.info(f"--- Starting VLAN IP assignment ({datetime.now().isoformat()}) ---")
    
    if args.test:
        logger.info("API TEST mode activated")
        test_api_connection()
    elif args.test_update:
        logger.info("TEST UPDATE mode activated")
        test_ip_update()
    else:
        update_ip_vlans()
    
    logger.info(f"--- End VLAN IP assignment ({datetime.now().isoformat()}) ---") 