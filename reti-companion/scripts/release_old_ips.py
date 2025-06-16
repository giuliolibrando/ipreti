#!/usr/bin/env python3
"""
Script for automatic release of long-term inactive IPs.

This script checks all IPs via API and automatically releases
those that meet the criteria:
- ultimo_controllo > threshold days (default 30 days)
- stato = 'disattivo'
- disponibilita = 'usato'

When an IP is released:
- disponibilita → 'libero'
- responsabile → None
- utente_finale → None
- assegnato_a_utente → None
- note → cleaned (optional)
- storico_responsabili → updated with reason 'inattivita'
"""

import requests
import json
import argparse
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import os
from stats_manager import StatsManager

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/data-collector/release_old_ips.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class OldIPReleaser:
    """Class for managing automatic release of old IPs"""
    
    def __init__(self, base_url: str = None, token: str = None):
        """
        Initialize the client for IP release
        
        Args:
            base_url: Django API base URL (default: web:8000)
            token: Authentication token (default: from environment variable)
        """
        self.base_url = base_url or os.getenv('DJANGO_BASE_URL', 'http://ipreti-web:8200')
        self.token = token or os.getenv('DJANGO_API_TOKEN')
        
        self.session = requests.Session()
        if self.token:
            self.session.headers.update({'Authorization': f'Token {self.token}'})
        
        # Initialize stats manager to track operations
        try:
            self.stats = StatsManager()
        except Exception as e:
            logger.warning(f"Unable to initialize StatsManager: {e}")
            self.stats = None
    
    def get_all_ips(self) -> List[Dict]:
        """
        Retrieve all IPs from the system via API
        
        Returns:
            List of dictionaries with IP data
        """
        try:
            url = f"{self.base_url}/api/ips/"
            all_ips = []
            
            while url:
                logger.debug(f"Fetching: {url}")
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                all_ips.extend(data.get('results', []))
                url = data.get('next')  # Pagination
                
            logger.info(f"Retrieved {len(all_ips)} IPs from system")
            return all_ips
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving IPs: {e}")
            return []
    
    def is_ip_candidate_for_release(self, ip_data: Dict, days_threshold: int) -> Dict:
        """
        Check if an IP is a candidate for release
        
        Args:
            ip_data: IP data
            days_threshold: Threshold days of inactivity
            
        Returns:
            Dict with 'eligible' (bool) and 'reason' (str)
        """
        ip_address = ip_data.get('ip')
        ultimo_controllo = ip_data.get('ultimo_controllo')
        stato = ip_data.get('stato')
        disponibilita = ip_data.get('disponibilita')
        responsabile = ip_data.get('responsabile')
        
        # Check basic conditions
        if disponibilita != 'usato':
            return {'eligible': False, 'reason': f'Availability: {disponibilita} (not used)'}
        
        if stato != 'disattivo':
            return {'eligible': False, 'reason': f'Status: {stato} (not inactive)'}
        
        if not responsabile:
            return {'eligible': False, 'reason': 'No responsible person assigned'}
        
        # Check last control date
        if not ultimo_controllo:
            logger.warning(f"IP {ip_address}: ultimo_controllo is None, considered very old")
            return {'eligible': True, 'reason': f'Last check: Never (considered > {days_threshold} days)'}
        
        try:
            # Parse date (ISO format)
            if ultimo_controllo.endswith('Z'):
                ultimo_controllo = ultimo_controllo[:-1] + '+00:00'
            
            last_check = datetime.fromisoformat(ultimo_controllo.replace('Z', '+00:00'))
            now = datetime.now(last_check.tzinfo)
            days_inactive = (now - last_check).days
            
            if days_inactive >= days_threshold:
                return {'eligible': True, 'reason': f'Inactive for {days_inactive} days (threshold: {days_threshold})'}
            else:
                return {'eligible': False, 'reason': f'Inactive for only {days_inactive} days (threshold: {days_threshold})'}
                
        except (ValueError, TypeError) as e:
            logger.error(f"Date parsing error for IP {ip_address}: {e}")
            return {'eligible': False, 'reason': f'Date parsing error: {e}'}
    
    def release_ip(self, ip_address: str, reason: str, dry_run: bool = False) -> bool:
        """
        Release an IP using the API's rilascia_ip method
        
        Args:
            ip_address: IP address to release
            reason: Reason for release
            dry_run: If True, simulate operation without applying
            
        Returns:
            True if operation succeeded, False otherwise
        """
        if dry_run:
            logger.info(f"[DRY-RUN] Would release IP {ip_address}: {reason}")
            return True
        
        try:
            # Use the release endpoint that automatically handles history
            url = f"{self.base_url}/api/ips/{ip_address}/libera/"
            
            payload = {
                'force': True,  # Force release even if not expired
                'motivo': 'inattivita',
                'note': f"Automatic release due to prolonged inactivity: {reason}",
                'created_by': 'script_release_old_ips'
            }
            
            logger.info(f"Releasing IP {ip_address}: {reason}")
            response = self.session.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ IP {ip_address} released successfully. Was assigned to: {result.get('era_assegnato_a', 'N/A')}")
                
                return True
            else:
                logger.error(f"❌ Error releasing IP {ip_address}: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error releasing IP {ip_address}: {e}")
            return False
    
    def process_old_ips(self, days_threshold: int = 30, dry_run: bool = False, 
                       clear_notes: bool = False) -> Dict:
        """
        Process all IPs to release old and inactive ones
        
        Args:
            days_threshold: Threshold days of inactivity
            dry_run: If True, simulate operations without applying
            clear_notes: If True, also clear notes (not implemented in current API)
            
        Returns:
            Dict with operation statistics
        """
        logger.info(f"{'[DRY-RUN] ' if dry_run else ''}Starting processing of old and inactive IPs")
        logger.info(f"Inactivity threshold: {days_threshold} days")
        
        # Statistics
        stats = {
            'total_ips': 0,
            'candidates_found': 0,
            'released_successfully': 0,
            'release_errors': 0,
            'skipped': 0
        }
        
        # Retrieve all IPs
        all_ips = self.get_all_ips()
        if not all_ips:
            logger.error("No IPs retrieved, stopping processing")
            return stats
        
        stats['total_ips'] = len(all_ips)
        
        logger.info(f"Analyzing {len(all_ips)} IPs...")
        
        for ip_data in all_ips:
            ip_address = ip_data.get('ip')
            
            # Check if it's a candidate for release
            check_result = self.is_ip_candidate_for_release(ip_data, days_threshold)
            
            if check_result['eligible']:
                stats['candidates_found'] += 1
                logger.info(f"🎯 Candidate IP: {ip_address} - {check_result['reason']}")
                
                # Try to release the IP
                if self.release_ip(ip_address, check_result['reason'], dry_run):
                    stats['released_successfully'] += 1
                else:
                    stats['release_errors'] += 1
            else:
                stats['skipped'] += 1
                logger.debug(f"⏭️  Skipped IP: {ip_address} - {check_result['reason']}")
        
        # Final log
        logger.info(f"{'[DRY-RUN] ' if dry_run else ''}Processing completed:")
        logger.info(f"  📊 Total IPs analyzed: {stats['total_ips']}")
        logger.info(f"  🎯 Candidate IPs for release: {stats['candidates_found']}")
        logger.info(f"  ✅ IPs released successfully: {stats['released_successfully']}")
        logger.info(f"  ❌ Release errors: {stats['release_errors']}")
        logger.info(f"  ⏭️  Skipped IPs: {stats['skipped']}")
        
        # Update global statistics using correct methods
        if self.stats and not dry_run:
            # Use update_collection_stats to track operation
            self.stats.update_collection_stats(
                source_name='release_old_ips',
                source_type='maintenance',
                stats_data={
                    'created': 0,  # We don't create IPs, we release them
                    'updated': stats['released_successfully'],  # Released IPs = updates
                    'errors': stats['release_errors'],
                    'duration': 0,  # You could add timing if needed
                    'total_analyzed': stats['total_ips'],
                    'candidates_found': stats['candidates_found']
                }
            )
        
        return stats

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Automatically release long-term inactive IPs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check what would be released without applying changes
  python release_old_ips.py --dry-run
  
  # Release IPs inactive for more than 45 days
  python release_old_ips.py --days 45
  
  # Run in verbose mode
  python release_old_ips.py --days 30 --verbose
        """
    )
    
    parser.add_argument(
        '--days', 
        type=int, 
        default=30,
        help='Inactivity threshold in days to release an IP (default: 30)'
    )
    
    parser.add_argument(
        '--dry-run', 
        action='store_true',
        help='Simulate operations without applying changes'
    )
    
    parser.add_argument(
        '--verbose', 
        action='store_true',
        help='More detailed output'
    )
    
    parser.add_argument(
        '--clear-notes', 
        action='store_true',
        help='Also clear notes of released IPs (future feature)'
    )
    
    args = parser.parse_args()
    
    # Configure logging based on verbosity
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Initialize the releaser
        releaser = OldIPReleaser()
        
        # Execute processing
        stats = releaser.process_old_ips(
            days_threshold=args.days,
            dry_run=args.dry_run,
            clear_notes=args.clear_notes
        )
        
        # Exit code based on results
        if stats['release_errors'] > 0:
            logger.warning(f"Completed with {stats['release_errors']} errors")
            sys.exit(1)
        else:
            logger.info("Completed successfully")
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Critical error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main() 
