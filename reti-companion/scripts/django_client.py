import requests
import json
import logging
from datetime import datetime
from config.config import DJANGO_API_BASE_URL, DJANGO_API_TOKEN
import time

logger = logging.getLogger(__name__)

class DjangoAPIClient:
    def __init__(self):
        self.base_url = DJANGO_API_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Authorization': f'Token {DJANGO_API_TOKEN}' if DJANGO_API_TOKEN else ''
        })
    
    def health_check(self):
        """Verifica che l'API sia raggiungibile e l'autenticazione funzioni"""
        try:
            url = f"{self.base_url.replace('/api', '')}/health/"
            response = self.session.get(url, timeout=5)
            if response.status_code == 200:
                logger.debug("API health check passed")
                return True
            else:
                logger.warning(f"API health check failed with status {response.status_code}")
                return False
        except Exception as e:
            logger.warning(f"API health check failed: {e}")
            return False
    
    def get_ip_by_address(self, ip_address):
        """Get IP address details by IP string"""
        try:
            url = f"{self.base_url}/ips/"
            params = {'ip': ip_address}
            logger.debug(f"Searching for IP {ip_address} at {url} with params {params}")
            response = self.session.get(url, params=params)
            
            # Debug authentication
            if response.status_code == 401:
                logger.error(f"Authentication failed! Token: {'SET' if DJANGO_API_TOKEN else 'NOT SET'}")
                return None
            elif response.status_code == 403:
                logger.error(f"Permission denied for IP lookup: {ip_address}")
                return None
                
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            logger.debug(f"Found {len(results)} results for IP {ip_address}")
            return results[0] if results else None
            
        except requests.RequestException as e:
            logger.error(f"Error getting IP {ip_address}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response content: {e.response.text}")
            return None
    
    def create_ip(self, ip_data):
        """Create a new IP address entry"""
        try:
            url = f"{self.base_url}/ips/"
            logger.debug(f"Creating IP with data: {ip_data}")
            response = self.session.post(url, json=ip_data)
            
            # Debug validation errors
            if response.status_code == 400:
                logger.error(f"Validation error creating IP {ip_data.get('ip', '')}: {response.text}")
                return None
            elif response.status_code == 401:
                logger.error(f"Authentication failed for IP creation: {ip_data.get('ip', '')}")
                return None
            elif response.status_code == 403:
                logger.error(f"Permission denied for IP creation: {ip_data.get('ip', '')}")
                return None
                
            response.raise_for_status()
            created_ip = response.json()
            logger.debug(f"Successfully created IP: {created_ip.get('ip', '')}")
            return created_ip
            
        except requests.RequestException as e:
            logger.error(f"Error creating IP {ip_data.get('ip', '')}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response content: {e.response.text}")
            return None
    
    def update_ip(self, ip_address, ip_data):
        """Update an existing IP address entry using IP as identifier"""
        try:
            url = f"{self.base_url}/ips/{ip_address}/"
            logger.debug(f"Updating IP {ip_address} at URL: {url}")
            logger.debug(f"Update data: {ip_data}")
            
            response = self.session.patch(url, json=ip_data)
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response content: {response.text}")
            
            if response.status_code == 404:
                logger.error(f"IP {ip_address} not found on server (404)")
                return None
            elif response.status_code == 400:
                logger.error(f"Bad request for IP {ip_address}: {response.text}")
                return None
            
            response.raise_for_status()
            result = response.json()
            logger.debug(f"Update successful, returned: {result}")
            return result
            
        except requests.RequestException as e:
            logger.error(f"Error updating IP {ip_address}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response content: {e.response.text}")
            return None
    
    def create_or_update_ip(self, ip_address, mac_address, router_name):
        """Create or update IP with MAC address and router info"""
        # First try to get existing IP
        existing_ip = self.get_ip_by_address(ip_address)
        
        current_time = datetime.now().isoformat()
        
        if existing_ip:
            # Update existing IP
            update_data = {
                'mac_address': mac_address,
                'stato': 'attivo',
                'ultimo_controllo': current_time
            }
            
            # Add note if IP was inactive
            if existing_ip.get('stato') != 'attivo':
                note = f"IP reactivated from {router_name}: {current_time}"
                update_data['note'] = note
            
            result = self.update_ip(ip_address, update_data)
            if result:
                logger.info(f"Updated IP {ip_address} from {router_name}")
                return result
        else:
            # Create new IP
            create_data = {
                'ip': ip_address,
                'mac_address': mac_address,
                'stato': 'attivo',
                'disponibilita': 'libero',  # Changed from 'usato' - auto-discovered IPs should be free until assigned
                'responsabile': None,  # Changed from 'undefined' to None - no responsible person yet
                'note': f"Detected from {router_name}: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                'ultimo_controllo': datetime.now().isoformat()
            }
            
            result = self.create_ip(create_data)
            if result:
                logger.info(f"Created new IP {ip_address} from {router_name}")
                return result
        
        return None
    
    def bulk_update_ips_from_router(self, ip_mac_dict, router_name):
        """Update multiple IPs from a router's ARP table"""
        logger.info(f"Processing {len(ip_mac_dict)} IPs from {router_name}")
        
        created_count = 0
        updated_count = 0
        error_count = 0
        
        for ip_address, mac_address in ip_mac_dict.items():
            try:
                logger.debug(f"Processing IP {ip_address} with MAC {mac_address}")
                existing_ip = self.get_ip_by_address(ip_address)
                
                if existing_ip:
                    logger.debug(f"IP {ip_address} exists, updating...")
                    # Update existing
                    update_data = {
                        'mac_address': mac_address,
                        'stato': 'attivo',
                        'ultimo_controllo': datetime.now().isoformat()
                    }
                    
                    if self.update_ip(ip_address, update_data):
                        updated_count += 1
                        logger.debug(f"Successfully updated IP {ip_address}")
                    else:
                        error_count += 1
                        logger.error(f"Failed to update IP {ip_address}")
                else:
                    logger.debug(f"IP {ip_address} does not exist, creating...")
                    # Create new
                    create_data = {
                        'ip': ip_address,
                        'mac_address': mac_address,
                        'stato': 'attivo',
                        'disponibilita': 'libero',  # Changed from 'usato' - auto-discovered IPs should be free until assigned
                        'responsabile': None,  # Changed from 'undefined' to None - no responsible person yet
                        'note': f"Detected from {router_name}: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                        'ultimo_controllo': datetime.now().isoformat()
                    }
                    
                    if self.create_ip(create_data):
                        created_count += 1
                        logger.debug(f"Successfully created IP {ip_address}")
                    else:
                        error_count += 1
                        logger.error(f"Failed to create IP {ip_address}")
                        
            except Exception as e:
                logger.error(f"Error processing IP {ip_address}: {e}")
                error_count += 1
        
        logger.info(f"Router {router_name} - Created: {created_count}, Updated: {updated_count}, Errors: {error_count}")
        return {
            'created': created_count,
            'updated': updated_count,
            'errors': error_count
        }
    
    def create_lan_range(self, network_cidr):
        """Create all IPs in a LAN range"""
        try:
            from netaddr import IPNetwork
            
            net = IPNetwork(network_cidr)
            created_count = 0
            
            for ip in net:
                # Skip network and broadcast addresses
                if ip in [net.network, net.broadcast]:
                    continue
                
                ip_str = str(ip)
                existing = self.get_ip_by_address(ip_str)
                
                if not existing:
                    create_data = {
                        'ip': ip_str,
                        'stato': 'disattivo',
                        'disponibilita': 'libero',
                        'responsabile': 'undefined',
                        'note': f"Automatically created for LAN {network_cidr}",
                        'ultimo_controllo': datetime.now().isoformat()
                    }
                    
                    if self.create_ip(create_data):
                        created_count += 1
                        logger.info(f"Created IP {ip_str} in LAN {network_cidr}")
                else:
                    logger.info(f"IP {ip_str} already exists")
            
            logger.info(f"Created {created_count} new IPs for LAN {network_cidr}")
            return created_count
            
        except Exception as e:
            logger.error(f"Error creating LAN range {network_cidr}: {e}")
            return 0
    
    def get_all_vlans(self):
        """Recupera tutte le VLAN dal backend Django tramite API REST"""
        url = f"{self.base_url}/vlans/"
        vlans = []
        while url:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            # Supporta sia paginato che non paginato
            if isinstance(data, dict) and 'results' in data:
                vlans.extend(data['results'])
                url = data.get('next')
            else:
                vlans.extend(data)
                url = None
        return vlans
    
    def get_all_ips(self):
        """Recupera tutti gli indirizzi IP dal backend Django tramite API REST"""
        try:
            url = f"{self.base_url}/ips/"
            ips = []
            
            while url:
                response = self.session.get(url)
                response.raise_for_status()
                data = response.json()
                
                # Supporta sia paginato che non paginato
                if isinstance(data, dict) and 'results' in data:
                    ips.extend(data['results'])
                    url = data.get('next')
                else:
                    ips.extend(data)
                    url = None
                    
            logger.info(f"Retrieved {len(ips)} IP addresses from API")
            return ips
            
        except requests.RequestException as e:
            logger.error(f"Error retrieving all IPs: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response content: {e.response.text}")
            return []

    def update_vlan(self, vlan_numero, vlan_data):
        """Aggiorna una VLAN esistente usando il numero VLAN come identificatore"""
        try:
            url = f"{self.base_url}/vlans/{vlan_numero}/"
            response = self.session.patch(url, json=vlan_data)
            response.raise_for_status()
            logger.debug(f"Successfully updated VLAN {vlan_numero}")
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Error updating VLAN {vlan_numero}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response content: {e.response.text}")
            return None 