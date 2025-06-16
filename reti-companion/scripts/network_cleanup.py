#!/usr/bin/env python3

import sys
import os
import logging
import argparse
from datetime import datetime, timedelta

# Add the project root to Python path
sys.path.insert(0, '/app')

from django_client import DjangoAPIClient
from stats_manager import StatsManager
from config.config import LOG_FILE, LOG_LEVEL

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

class NetworkCleanup:
    """Manages automatic cleanup of inactive IP addresses"""
    
    def __init__(self, inactivity_hours=2):
        self.django_client = DjangoAPIClient()
        self.stats_manager = StatsManager()
        self.inactivity_threshold = timedelta(hours=inactivity_hours)
        
    def get_all_active_ips(self):
        """Get all IP addresses that are currently marked as active"""
        try:
            url = f"{self.django_client.base_url}/ips/"
            params = {'stato': 'attivo'}
            
            all_ips = []
            page = 1
            
            while True:
                params['page'] = page
                response = self.django_client.session.get(url, params=params)
                
                if response.status_code == 401:
                    logger.error("Authentication failed! Check API token.")
                    return []
                elif response.status_code == 403:
                    logger.error("Permission denied for IP listing.")
                    return []
                    
                response.raise_for_status()
                data = response.json()
                
                results = data.get('results', [])
                if not results:
                    break
                    
                all_ips.extend(results)
                
                # Check if there are more pages
                if not data.get('next'):
                    break
                    
                page += 1
                
            logger.info(f"Retrieved {len(all_ips)} active IP addresses")
            return all_ips
            
        except Exception as e:
            logger.error(f"Error retrieving active IPs: {e}")
            self.stats_manager.add_error(f"Error retrieving active IPs: {e}", "network_cleanup")
            return []
    
    def is_ip_inactive(self, ip_data):
        """Check if an IP is inactive based on last_check timestamp"""
        try:
            ultimo_controllo_str = ip_data.get('ultimo_controllo')
            if not ultimo_controllo_str:
                # No last check time - consider it inactive
                return True, "No last check time recorded"
            
            # Parse the timestamp
            try:
                # Handle different timestamp formats
                if ultimo_controllo_str.endswith('Z'):
                    ultimo_controllo = datetime.fromisoformat(ultimo_controllo_str.replace('Z', '+00:00'))
                    ultimo_controllo = ultimo_controllo.replace(tzinfo=None)
                else:
                    ultimo_controllo = datetime.fromisoformat(ultimo_controllo_str.split('+')[0])
            except ValueError:
                # Try parsing without timezone info
                ultimo_controllo = datetime.strptime(ultimo_controllo_str, '%Y-%m-%d %H:%M:%S')
            
            # Calculate time difference
            now = datetime.now()
            time_diff = now - ultimo_controllo
            
            if time_diff > self.inactivity_threshold:
                hours_inactive = time_diff.total_seconds() / 3600
                return True, f"Inactive for {hours_inactive:.1f} hours"
            
            return False, f"Active (last seen {time_diff} ago)"
            
        except Exception as e:
            logger.error(f"Error parsing timestamp for IP {ip_data.get('ip', 'unknown')}: {e}")
            return True, f"Error parsing timestamp: {e}"
    
    def deactivate_ip(self, ip_address, reason):
        """Deactivate a specific IP address"""
        try:
            # Semplicemente cambia lo stato senza modificare le note
            update_data = {
                'stato': 'disattivo'
            }

            result = self.django_client.update_ip(ip_address, update_data)
            if result:
                logger.info(f"Deactivated IP {ip_address}: {reason}")
                return True
            else:
                logger.error(f"Failed to deactivate IP {ip_address}")
                return False

        except Exception as e:
            logger.error(f"Error deactivating IP {ip_address}: {e}")
            return False
    
    def cleanup_inactive_ips(self, dry_run=False):
        """Main cleanup function to deactivate inactive IPs"""
        logger.info(f"Starting network cleanup (dry_run={dry_run})")
        start_time = datetime.now()
        
        # Get all active IPs
        active_ips = self.get_all_active_ips()
        if not active_ips:
            logger.warning("No active IPs found or error retrieving them")
            return {'checked': 0, 'deactivated': 0, 'errors': 0}
        
        stats = {
            'checked': len(active_ips),
            'deactivated': 0,
            'errors': 0,
            'skipped': 0
        }
        
        inactive_ips = []
        
        # Check each IP for inactivity
        for ip_data in active_ips:
            ip_address = ip_data.get('ip')
            
            try:
                is_inactive, reason = self.is_ip_inactive(ip_data)
                
                if is_inactive:
                    inactive_ips.append({
                        'ip': ip_address,
                        'reason': reason,
                        'ultimo_controllo': ip_data.get('ultimo_controllo'),
                        'responsabile': ip_data.get('responsabile', 'N/A'),
                        'mac_address': ip_data.get('mac_address', 'N/A')
                    })
                    
                    if dry_run:
                        logger.info(f"[DRY RUN] Would deactivate {ip_address}: {reason}")
                        stats['skipped'] += 1
                    else:
                        if self.deactivate_ip(ip_address, reason):
                            stats['deactivated'] += 1
                        else:
                            stats['errors'] += 1
                else:
                    logger.debug(f"IP {ip_address} is still active: {reason}")
                    
            except Exception as e:
                logger.error(f"Error processing IP {ip_address}: {e}")
                stats['errors'] += 1
        
        # Calculate duration and log results
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Network cleanup complete in {duration:.1f}s")
        logger.info(f"Checked: {stats['checked']}, Deactivated: {stats['deactivated']}, Errors: {stats['errors']}")
        
        if inactive_ips:
            logger.info(f"Found {len(inactive_ips)} inactive IPs:")
            for ip_info in inactive_ips[:10]:  # Show first 10
                logger.info(f"  - {ip_info['ip']} ({ip_info['responsabile']}) - {ip_info['reason']}")
            if len(inactive_ips) > 10:
                logger.info(f"  ... and {len(inactive_ips) - 10} more")
        
        # Update statistics
        if not dry_run:
            stats['duration'] = duration
            self.stats_manager.update_collection_stats('network_cleanup', 'maintenance', stats)
        
        return stats
    
    def get_inactive_candidates(self):
        """Get list of IPs that would be deactivated (for reporting)"""
        logger.info("Getting list of inactive IP candidates")
        
        active_ips = self.get_all_active_ips()
        if not active_ips:
            return []
        
        candidates = []
        
        for ip_data in active_ips:
            try:
                is_inactive, reason = self.is_ip_inactive(ip_data)
                if is_inactive:
                    candidates.append({
                        'ip': ip_data.get('ip'),
                        'ultimo_controllo': ip_data.get('ultimo_controllo'),
                        'responsabile': ip_data.get('responsabile', 'N/A'),
                        'utente_finale': ip_data.get('utente_finale', 'N/A'),
                        'mac_address': ip_data.get('mac_address', 'N/A'),
                        'reason': reason
                    })
            except Exception as e:
                logger.error(f"Error checking IP {ip_data.get('ip', 'unknown')}: {e}")
        
        logger.info(f"Found {len(candidates)} inactive candidates")
        return candidates

def main():
    parser = argparse.ArgumentParser(description='Network Cleanup - Deactivate inactive IP addresses')
    parser.add_argument('-c', '--command', 
                       choices=['cleanup', 'check', 'report'],
                       default='cleanup',
                       help='Command to execute (default: cleanup)')
    parser.add_argument('--hours', 
                       type=int, 
                       default=2,
                       help='Inactivity threshold in hours (default: 2)')
    parser.add_argument('--dry-run', 
                       action='store_true',
                       help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    # Create cleanup manager
    cleanup = NetworkCleanup(inactivity_hours=args.hours)
    
    try:
        if args.command == 'cleanup':
            # Perform cleanup
            stats = cleanup.cleanup_inactive_ips(dry_run=args.dry_run)
            print(f"Cleanup completed: {stats}")
            
        elif args.command == 'check':
            # Just check and report candidates
            candidates = cleanup.get_inactive_candidates()
            print(f"Found {len(candidates)} inactive IP candidates")
            for candidate in candidates:
                print(f"  {candidate['ip']} - {candidate['reason']} - {candidate['responsabile']}")
                
        elif args.command == 'report':
            # Generate detailed report
            candidates = cleanup.get_inactive_candidates()
            
            print("=== NETWORK CLEANUP REPORT ===")
            print(f"Threshold: {args.hours} hours")
            print(f"Found {len(candidates)} inactive IPs")
            print()
            
            if candidates:
                print("IP Address       | Last Check           | Responsible         | Reason")
                print("-" * 80)
                for candidate in candidates:
                    ip = candidate['ip'][:15].ljust(15)
                    last_check = candidate['ultimo_controllo'][:19] if candidate['ultimo_controllo'] else 'Never'
                    responsible = candidate['responsabile'][:18].ljust(18)
                    reason = candidate['reason'][:30]
                    print(f"{ip} | {last_check} | {responsible} | {reason}")
            
        else:
            logger.error(f"Unknown command: {args.command}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Cleanup interrupted by user")
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 