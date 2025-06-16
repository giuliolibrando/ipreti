#!/usr/bin/env python3

import json
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

class StatsManager:
    """Manages collection statistics for the data collector dashboard"""
    
    def __init__(self, stats_file='/var/log/data-collector/stats.json'):
        self.stats_file = stats_file
        self.ensure_stats_dir()
        
    def ensure_stats_dir(self):
        """Ensure the stats directory exists"""
        Path(self.stats_file).parent.mkdir(parents=True, exist_ok=True)
        
    def load_stats(self):
        """Load existing statistics from file"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    return json.load(f)
            else:
                return self.get_default_stats()
        except Exception as e:
            logger.error(f"Error loading stats: {e}")
            return self.get_default_stats()
    
    def get_default_stats(self):
        """Return default statistics structure"""
        return {
            'last_update': None,
            'total_runs': 0,
            'total_ips_created': 0,
            'total_ips_updated': 0,
            'total_errors': 0,
            'uptime_since': datetime.now().isoformat(),
            'collection_history': [],
            'device_stats': {
                'routers': {},
                'firewalls': {},
                'f5_devices': {},
                'maintenance': {}  # Add maintenance operations like cleanup
            },
            'recent_errors': [],
            'last_successful_run': None,
            'cron_status': 'running'
        }
    
    def save_stats(self, stats):
        """Save statistics to file"""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(stats, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving stats: {e}")
    
    def update_collection_stats(self, source_name, source_type, stats_data):
        """Update statistics after a collection run"""
        current_stats = self.load_stats()
        current_time = datetime.now().isoformat()
        
        # Update totals
        current_stats['last_update'] = current_time
        current_stats['total_runs'] += 1
        current_stats['total_ips_created'] += stats_data.get('created', 0)
        current_stats['total_ips_updated'] += stats_data.get('updated', 0)
        current_stats['total_errors'] += stats_data.get('errors', 0)
        
        # Update last successful run if no errors
        if stats_data.get('errors', 0) == 0:
            current_stats['last_successful_run'] = current_time
        
        # Update device-specific stats
        if source_type not in current_stats['device_stats']:
            current_stats['device_stats'][source_type] = {}
            
        if source_name not in current_stats['device_stats'][source_type]:
            current_stats['device_stats'][source_type][source_name] = {
                'total_created': 0,
                'total_updated': 0,
                'total_errors': 0,
                'last_collection': None,
                'last_success': None,
                'collection_count': 0
            }
        
        device_stats = current_stats['device_stats'][source_type][source_name]
        device_stats['total_created'] += stats_data.get('created', 0)
        device_stats['total_updated'] += stats_data.get('updated', 0)
        device_stats['total_errors'] += stats_data.get('errors', 0)
        device_stats['last_collection'] = current_time
        device_stats['collection_count'] += 1
        
        if stats_data.get('errors', 0) == 0:
            device_stats['last_success'] = current_time
        
        # Add to collection history (keep last 50 runs)
        history_entry = {
            'timestamp': current_time,
            'source': source_name,
            'type': source_type,
            'created': stats_data.get('created', 0),
            'updated': stats_data.get('updated', 0),
            'errors': stats_data.get('errors', 0),
            'duration': stats_data.get('duration', 0)
        }
        
        current_stats['collection_history'].append(history_entry)
        current_stats['collection_history'] = current_stats['collection_history'][-50:]  # Keep last 50
        
        self.save_stats(current_stats)
        logger.info(f"Stats updated for {source_name} ({source_type}): {stats_data}")
    
    def reset_collection_totals(self):
        """Reset IP creation/update totals at the start of each collection run"""
        current_stats = self.load_stats()
        
        # Reset only the IP totals that accumulate too much
        current_stats['total_ips_updated'] = 0
        current_stats['total_ips_created'] = 0
        # Keep total_errors and total_runs as they're useful for debugging
        
        self.save_stats(current_stats)
        logger.info("Collection totals reset for new run (IPs created/updated)")
        return current_stats
    
    def add_error(self, error_message, source=None):
        """Add an error to the recent errors list"""
        current_stats = self.load_stats()
        
        error_entry = {
            'timestamp': datetime.now().isoformat(),
            'message': error_message,
            'source': source
        }
        
        current_stats['recent_errors'].append(error_entry)
        current_stats['recent_errors'] = current_stats['recent_errors'][-20:]  # Keep last 20 errors
        
        self.save_stats(current_stats)
        logger.error(f"Error added to stats: {error_message}")
    
    def update_cron_status(self, status):
        """Update cron job status"""
        current_stats = self.load_stats()
        current_stats['cron_status'] = status
        current_stats['last_update'] = datetime.now().isoformat()
        self.save_stats(current_stats)
    
    def get_dashboard_data(self):
        """Get formatted data for the dashboard"""
        stats = self.load_stats()
        
        # Calculate uptime
        if stats.get('uptime_since'):
            try:
                uptime_start = datetime.fromisoformat(stats['uptime_since'].replace('Z', '+00:00'))
                uptime_duration = datetime.now() - uptime_start.replace(tzinfo=None)
                uptime_str = str(uptime_duration).split('.')[0]  # Remove microseconds
            except:
                uptime_str = "Unknown"
        else:
            uptime_str = "Unknown"
        
        # Get recent activity (last 24 hours)
        twenty_four_hours_ago = datetime.now() - timedelta(hours=24)
        recent_activity = []
        
        for entry in reversed(stats.get('collection_history', [])):
            try:
                entry_time = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
                if entry_time.replace(tzinfo=None) > twenty_four_hours_ago:
                    recent_activity.append(entry)
            except:
                continue
        
        # Calculate totals for last 24h
        last_24h_created = sum(entry.get('created', 0) for entry in recent_activity)
        last_24h_updated = sum(entry.get('updated', 0) for entry in recent_activity)
        last_24h_errors = sum(entry.get('errors', 0) for entry in recent_activity)
        
        return {
            'general': {
                'uptime': uptime_str,
                'last_update': stats.get('last_update'),
                'last_successful_run': stats.get('last_successful_run'),
                'cron_status': stats.get('cron_status', 'unknown'),
                'total_runs': stats.get('total_runs', 0)
            },
            'totals': {
                'ips_created': stats.get('total_ips_created', 0),
                'ips_updated': stats.get('total_ips_updated', 0),
                'total_errors': stats.get('total_errors', 0)
            },
            'last_24h': {
                'ips_created': last_24h_created,
                'ips_updated': last_24h_updated,
                'errors': last_24h_errors,
                'collections': len(recent_activity)
            },
            'devices': stats.get('device_stats', {}),
            'recent_errors': stats.get('recent_errors', [])[-10:],  # Last 10 errors
            'recent_activity': recent_activity[:10]  # Last 10 activities
        } 