#!/usr/bin/env python3

import sys
import os
import logging
from datetime import datetime
from flask import Flask, render_template_string, jsonify

# Add the project root to Python path
sys.path.insert(0, '/app')

from stats_manager import StatsManager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
stats_manager = StatsManager()

# HTML Template for the dashboard
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Data Collector Dashboard - UniRoma1</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(45deg, #2c3e50, #3498db);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            opacity: 0.9;
            font-size: 1.1em;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            padding: 30px;
        }
        
        .stat-card {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            border: 1px solid #e9ecef;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        }
        
        .stat-number {
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 10px;
        }
        
        .stat-label {
            color: #6c757d;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .status-good { color: #28a745; }
        .status-warning { color: #ffc107; }
        .status-error { color: #dc3545; }
        
        .section {
            margin: 30px;
            background: #f8f9fa;
            border-radius: 10px;
            overflow: hidden;
        }
        
        .section-header {
            background: #495057;
            color: white;
            padding: 15px 20px;
            font-size: 1.2em;
            font-weight: bold;
        }
        
        .section-content {
            padding: 20px;
        }
        
        .device-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
        }
        
        .device-card {
            background: white;
            border-radius: 8px;
            padding: 15px;
            border: 1px solid #dee2e6;
        }
        
        .device-name {
            font-weight: bold;
            color: #495057;
            margin-bottom: 10px;
            font-size: 1.1em;
        }
        
        .device-stats {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 10px;
            text-align: center;
        }
        
        .device-stat {
            padding: 8px;
            border-radius: 5px;
            background: #f8f9fa;
        }
        
        .device-stat-number {
            font-weight: bold;
            font-size: 1.2em;
        }
        
        .device-stat-label {
            font-size: 0.8em;
            color: #6c757d;
            margin-top: 3px;
        }
        
        .activity-log {
            max-height: 400px;
            overflow-y: auto;
            background: white;
            border-radius: 8px;
            border: 1px solid #dee2e6;
        }
        
        .log-entry {
            padding: 12px;
            border-bottom: 1px solid #f1f3f4;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .log-entry:last-child {
            border-bottom: none;
        }
        
        .log-entry:nth-child(even) {
            background: #f8f9fa;
        }
        
        .log-time {
            color: #6c757d;
            font-size: 0.9em;
        }
        
        .log-details {
            flex-grow: 1;
            margin-left: 15px;
        }
        
        .log-source {
            font-weight: bold;
            color: #495057;
        }
        
        .log-stats {
            font-size: 0.9em;
            color: #6c757d;
        }
        
        .error-entry {
            background: #f8d7da;
            color: #721c24;
        }
        
        .auto-refresh {
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 10px 15px;
            border-radius: 20px;
            font-size: 0.9em;
        }
        
        @media (max-width: 768px) {
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            .device-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="auto-refresh">
        🔄 Auto-refresh: 30s
    </div>
    
    <div class="container">
        <div class="header">
            <h1>📊 Data Collector Dashboard</h1>
            <p>Sistema di Gestione IP </p>
            <p style="margin-top: 10px; font-size: 0.9em;">
                Last Update: {{ data.general.last_update or 'Never' }} | 
                Uptime: {{ data.general.uptime }} | 
                Status: <span class="{% if data.general.cron_status == 'running' %}status-good{% else %}status-error{% endif %}">
                    {{ data.general.cron_status|title }}
                </span>
            </p>
        </div>
        
        <!-- Statistics Overview -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number status-good">{{ data.totals.ips_created }}</div>
                <div class="stat-label">IP Creati (Totale)</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-number status-good">{{ data.totals.ips_updated }}</div>
                <div class="stat-label">IP Aggiornati (Totale)</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-number {% if data.totals.total_errors > 0 %}status-warning{% else %}status-good{% endif %}">
                    {{ data.totals.total_errors }}
                </div>
                <div class="stat-label">Errori (Totale)</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-number status-good">{{ data.general.total_runs }}</div>
                <div class="stat-label">Esecuzioni Totali</div>
            </div>
        </div>
        
        <!-- Last 24h Statistics -->
        <div class="section">
            <div class="section-header">📈 Attività delle Ultime 24 Ore</div>
            <div class="section-content">
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-number status-good">{{ data.last_24h.ips_created }}</div>
                        <div class="stat-label">IP Creati</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-number status-good">{{ data.last_24h.ips_updated }}</div>
                        <div class="stat-label">IP Aggiornati</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-number {% if data.last_24h.errors > 0 %}status-warning{% else %}status-good{% endif %}">
                            {{ data.last_24h.errors }}
                        </div>
                        <div class="stat-label">Errori</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-number status-good">{{ data.last_24h.collections }}</div>
                        <div class="stat-label">Raccolte Dati</div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Device Statistics -->
        <div class="section">
            <div class="section-header">🌐 Statistiche per Dispositivo</div>
            <div class="section-content">
                {% for device_type, devices in data.devices.items() %}
                    {% if devices %}
                    <h3 style="margin: 20px 0 15px 0; color: #495057; text-transform: capitalize;">{{ device_type.replace('_', ' ') }}</h3>
                    <div class="device-grid">
                        {% for device_name, device_data in devices.items() %}
                        <div class="device-card">
                            <div class="device-name">{{ device_name }}</div>
                            <div class="device-stats">
                                <div class="device-stat">
                                    <div class="device-stat-number status-good">{{ device_data.total_created }}</div>
                                    <div class="device-stat-label">Creati</div>
                                </div>
                                <div class="device-stat">
                                    <div class="device-stat-number status-good">{{ device_data.total_updated }}</div>
                                    <div class="device-stat-label">Aggiornati</div>
                                </div>
                                <div class="device-stat">
                                    <div class="device-stat-number {% if device_data.total_errors > 0 %}status-warning{% else %}status-good{% endif %}">
                                        {{ device_data.total_errors }}
                                    </div>
                                    <div class="device-stat-label">Errori</div>
                                </div>
                            </div>
                            <div style="margin-top: 10px; font-size: 0.8em; color: #6c757d;">
                                Ultima raccolta: {{ device_data.last_collection or 'Mai' }}<br>
                                Raccolte totali: {{ device_data.collection_count }}
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                    {% endif %}
                {% endfor %}
            </div>
        </div>
        
        <!-- Recent Activity -->
        <div class="section">
            <div class="section-header">🕐 Attività Recente</div>
            <div class="section-content">
                <div class="activity-log">
                    {% for activity in data.recent_activity %}
                    <div class="log-entry">
                        <div class="log-time">{{ activity.timestamp }}</div>
                        <div class="log-details">
                            <div class="log-source">{{ activity.source }} ({{ activity.type }})</div>
                            <div class="log-stats">
                                Creati: {{ activity.created }}, Aggiornati: {{ activity.updated }}, Errori: {{ activity.errors }}
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                    
                    {% if not data.recent_activity %}
                    <div class="log-entry">
                        <div style="text-align: center; color: #6c757d; padding: 20px;">
                            Nessuna attività recente
                        </div>
                    </div>
                    {% endif %}
                </div>
            </div>
        </div>
        
        <!-- Recent Errors -->
        {% if data.recent_errors %}
        <div class="section">
            <div class="section-header">⚠️ Errori Recenti</div>
            <div class="section-content">
                <div class="activity-log">
                    {% for error in data.recent_errors %}
                    <div class="log-entry error-entry">
                        <div class="log-time">{{ error.timestamp }}</div>
                        <div class="log-details">
                            <div class="log-source">{{ error.source or 'Sistema' }}</div>
                            <div class="log-stats">{{ error.message }}</div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
        {% endif %}
    </div>
    
    <script>
        // Auto-refresh every 30 seconds
        setTimeout(function() {
            window.location.reload();
        }, 30000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """Main dashboard page"""
    try:
        data = stats_manager.get_dashboard_data()
        return render_template_string(DASHBOARD_TEMPLATE, data=data)
    except Exception as e:
        logger.error(f"Error rendering dashboard: {e}")
        return f"Error loading dashboard: {e}", 500

@app.route('/api/stats')
def api_stats():
    """API endpoint for statistics data"""
    try:
        data = stats_manager.get_dashboard_data()
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def api_health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'data-collector-dashboard'
    })

if __name__ == '__main__':
    # Run the Flask app
    logger.info("Starting Data Collector Dashboard on port 8001")
    app.run(host='0.0.0.0', port=8001, debug=False) 