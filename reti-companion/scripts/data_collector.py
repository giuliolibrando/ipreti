#!/usr/bin/env python3

import sys
import os
import logging
import argparse
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, '/app')

from django_client import DjangoAPIClient
from snmp_collector import SNMPCollector
from stats_manager import StatsManager
from config.config import ROUTERS, FIREWALLS, F5_FILES, LOG_FILE, LOG_LEVEL

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

class DataCollector:
    def __init__(self):
        self.django_client = DjangoAPIClient()
        self.snmp_collector = SNMPCollector()
        self.stats_manager = StatsManager()
    
    def collect_from_all_routers(self):
        """Collect MAC tables from all configured routers"""
        logger.info("Starting collection from all routers")
        total_stats = {'created': 0, 'updated': 0, 'errors': 0}
        
        for router_name, router_config in ROUTERS.items():
            logger.info(f"Collecting from router: {router_name}")
            start_time = datetime.now()
            
            try:
                mac_table = self.snmp_collector.collect_from_router(router_config, router_name)
                
                if mac_table:
                    stats = self.django_client.bulk_update_ips_from_router(mac_table, router_name)
                    
                    # Calculate duration
                    duration = (datetime.now() - start_time).total_seconds()
                    stats['duration'] = duration
                    
                    # Update statistics
                    self.stats_manager.update_collection_stats(router_name, 'routers', stats)
                    
                    total_stats['created'] += stats['created']
                    total_stats['updated'] += stats['updated']
                    total_stats['errors'] += stats['errors']
                else:
                    logger.warning(f"No MAC addresses collected from {router_name}")
                    self.stats_manager.add_error(f"No MAC addresses collected from {router_name}", router_name)
                    
            except Exception as e:
                logger.error(f"Failed to collect from router {router_name}: {e}")
                self.stats_manager.add_error(f"Failed to collect from router {router_name}: {e}", router_name)
                total_stats['errors'] += 1
        
        logger.info(f"Router collection complete - Total: {total_stats}")
        return total_stats
    
    def collect_from_all_firewalls(self):
        """Collect MAC tables from all configured firewalls"""
        logger.info("Starting collection from all firewalls")
        total_stats = {'created': 0, 'updated': 0, 'errors': 0}
        
        for firewall_name, firewall_config in FIREWALLS.items():
            logger.info(f"Collecting from firewall: {firewall_name}")
            
            try:
                mac_table = self.snmp_collector.collect_from_firewall(firewall_config, firewall_name)
                
                if mac_table:
                    stats = self.django_client.bulk_update_ips_from_router(mac_table, firewall_name)
                    total_stats['created'] += stats['created']
                    total_stats['updated'] += stats['updated']
                    total_stats['errors'] += stats['errors']
                else:
                    logger.warning(f"No MAC addresses collected from {firewall_name}")
                    
            except Exception as e:
                logger.error(f"Failed to collect from firewall {firewall_name}: {e}")
                total_stats['errors'] += 1
        
        logger.info(f"Firewall collection complete - Total: {total_stats}")
        return total_stats
    
    def collect_from_f5_files(self):
        """Collect MAC addresses from F5 load balancer files"""
        logger.info("Starting collection from F5 files")
        total_stats = {'created': 0, 'updated': 0, 'errors': 0}
        
        for f5_name, filepath in F5_FILES.items():
            if os.path.exists(filepath):
                logger.info(f"Processing F5 file: {f5_name} ({filepath})")
                
                try:
                    mac_table = self.snmp_collector.read_f5_file(filepath)
                    
                    if mac_table:
                        stats = self.django_client.bulk_update_ips_from_router(mac_table, f5_name)
                        total_stats['created'] += stats['created']
                        total_stats['updated'] += stats['updated']
                        total_stats['errors'] += stats['errors']
                        
                        # Remove processed file
                        os.remove(filepath)
                        logger.info(f"Removed processed F5 file: {filepath}")
                    else:
                        logger.warning(f"No data in F5 file {filepath}")
                        
                except Exception as e:
                    logger.error(f"Failed to process F5 file {filepath}: {e}")
                    total_stats['errors'] += 1
            else:
                logger.debug(f"F5 file not found: {filepath}")
        
        logger.info(f"F5 collection complete - Total: {total_stats}")
        return total_stats
    
    def update_all_sources(self):
        """Update from all data sources (equivalent to old 'update' command)"""
        logger.info("=== Starting full network update ===")
        start_time = datetime.now()
        
        # Reset IP totals before starting collection to avoid huge accumulating numbers
        self.stats_manager.reset_collection_totals()
        
        total_stats = {'created': 0, 'updated': 0, 'errors': 0}
        
        # Collect from routers
        router_stats = self.collect_from_all_routers()
        total_stats['created'] += router_stats['created']
        total_stats['updated'] += router_stats['updated']
        total_stats['errors'] += router_stats['errors']
        
        # Collect from firewalls
        firewall_stats = self.collect_from_all_firewalls()
        total_stats['created'] += firewall_stats['created']
        total_stats['updated'] += firewall_stats['updated']
        total_stats['errors'] += firewall_stats['errors']
        
        # Collect from F5 files
        f5_stats = self.collect_from_f5_files()
        total_stats['created'] += f5_stats['created']
        total_stats['updated'] += f5_stats['updated']
        total_stats['errors'] += f5_stats['errors']
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        logger.info(f"=== Full network update complete ===")
        logger.info(f"Duration: {duration}")
        logger.info(f"Total results: {total_stats}")
        
        return total_stats
    
    def create_lan_range(self, network_cidr):
        """Create all IPs in a LAN range"""
        logger.info(f"Creating LAN range: {network_cidr}")
        created_count = self.django_client.create_lan_range(network_cidr)
        logger.info(f"Created {created_count} IPs for LAN {network_cidr}")
        return created_count

def main():
    parser = argparse.ArgumentParser(description='Network Data Collector for IP Management')
    parser.add_argument('-c', '--command', required=True, 
                       choices=['update', 'create', 'routers', 'firewalls', 'f5', 'cleanup'],
                       help='Command to execute')
    parser.add_argument('-e', '--entity', 
                       help='Entity to work with (for create: lan, for specific collections)')
    parser.add_argument('-i', '--ip', 
                       help='IP or network range (CIDR notation for create lan)')
    parser.add_argument('--hours', 
                       type=int, 
                       default=2,
                       help='Inactivity threshold in hours for cleanup (default: 2)')
    parser.add_argument('--dry-run', 
                       action='store_true',
                       help='Show what would be done without making changes (for cleanup)')
    
    args = parser.parse_args()
    
    collector = DataCollector()
    
    try:
        if args.command == 'update':
            # Full update from all sources
            collector.update_all_sources()
            
        elif args.command == 'create':
            if args.entity == 'lan':
                if not args.ip:
                    logger.error("Network CIDR required for create lan (use -i parameter)")
                    sys.exit(1)
                collector.create_lan_range(args.ip)
            else:
                logger.error("Only 'lan' entity supported for create command")
                sys.exit(1)
                
        elif args.command == 'routers':
            # Collect only from routers
            collector.collect_from_all_routers()
            
        elif args.command == 'firewalls':
            # Collect only from firewalls
            collector.collect_from_all_firewalls()
            
        elif args.command == 'f5':
            # Collect only from F5 files
            collector.collect_from_f5_files()
            
        elif args.command == 'cleanup':
            # Run network cleanup
            from network_cleanup import NetworkCleanup
            cleanup = NetworkCleanup(inactivity_hours=args.hours)
            stats = cleanup.cleanup_inactive_ips(dry_run=args.dry_run)
            logger.info(f"Cleanup completed: {stats}")
            
        else:
            logger.error(f"Unknown command: {args.command}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Collection interrupted by user")
    except Exception as e:
        logger.error(f"Collection failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 