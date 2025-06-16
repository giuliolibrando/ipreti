# Data Collector Container

This companion container replaces the original Python scripts (`reti-services3.py`, `getarptable3.py`) with a modernized version that uses Django REST APIs.

## 🎯 **Features**

The data collector is responsible for:

1. **Network device data collection** via SNMP
   - Cisco 6500 Routers
   - Palo Alto Firewalls (SNMPv3)
   - PfSense Switches
   - F5 Load Balancer files

2. **Django synchronization** via REST API
   - Automatic creation of new detected IPs
   - Status updates (active/inactive) and MAC addresses
   - Last check timestamp management

3. **Automatic scheduling** with cron jobs
   - Complete update every 30 minutes
   - F5 processing every 5 minutes
   - Router scan every 15 minutes
   - Firewall scan every 20 minutes

4. **IP lifecycle management**
   - Automatic cleanup for inactive IP deactivation (every 30 min)
   - Automatic release of long-term inactive IPs (daily)
   - Complete responsible history tracking

## 🎯 **Architecture**

```
docker/data-collector/
├── Dockerfile              # Container configuration
├── requirements.txt        # Python dependencies  
├── entrypoint.sh           # Container startup script
├── crontab                 # Scheduled jobs
├── config/
│   ├── config.py          # Network devices configuration
│   └── config_example.txt # Configuration example and template
├── scripts/
│   ├── data_collector.py  # Main collection script
│   ├── django_client.py   # Django API client
│   └── snmp_collector.py  # SNMP data collection
└── test_api.py            # API connection test
```

## 🔧 **Configuration**

### ⚠️ **IMPORTANT: Device Configuration Required**

Before deploying, you **MUST** configure your specific network devices:

1. **Copy the example configuration:**
   ```bash
   cp config/config_example.txt config/config.py
   ```

2. **Edit `config/config.py` with your network details:**
   - **Router IPs and SNMP communities** - Update with your actual Cisco routers
   - **Firewall IPs and SNMPv3 credentials** - Configure your Palo Alto devices
   - **F5 Load Balancer file paths** - Set correct paths for MAC address exports
   - **Django API URL and token** - Point to your Django server

3. **Security considerations:**
   - Use strong SNMP community strings
   - Rotate API tokens regularly
   - Limit SNMP access with firewall rules

See `config/config_example.txt` for detailed configuration examples and security best practices.

### Environment Variables

```bash
# Django API Configuration
DJANGO_API_BASE_URL=http://web:8000/api
DJANGO_API_TOKEN=your_token_here

# Logging
LOG_LEVEL=INFO
SYNC_INTERVAL_MINUTES=30
```

### Network Devices

Devices are configured in `config/config.py`:

```python
ROUTERS = {
    'MainRouter': {
        'ip': '192.168.1.1',
        'community': 'your_snmp_community',
        'query': '.1.3.6.1.2.1.3.1.1.2',
        'type': 'snmp_v2c'
    },
    # Add your routers here
}

FIREWALLS = {
    'gateway_01': {
        'ip': '192.168.77.92',
        'secname': 'your_snmp_user',
        'authprotocol': 'SHA',
        'authpassword': 'your_secure_password',
        'query': '1.3.6.1.2.1.3.1.1.2',
        'contexts': ['vsys1', 'vsys2']
    },
    # Add your firewalls here
}
```

## 🚀 **Usage**

### Docker Compose Startup

```bash
# Start entire stack (Django + Data Collector)
docker-compose up -d

# View data collector logs
docker-compose logs -f data-collector

# Restart only data collector
docker-compose restart data-collector
```

### Manual Commands

```bash
# Enter container
docker-compose exec data-collector bash

# Complete update from all devices
python scripts/data_collector.py -c update

# Routers only
python scripts/data_collector.py -c routers

# Firewalls only  
python scripts/data_collector.py -c firewalls

# F5 files only
python scripts/data_collector.py -c f5

# Create LAN range
python scripts/data_collector.py -c create -e lan -i 192.168.100.0/24
```

## 📊 **Monitoring**

### Log Files

- **Container logs**: `docker-compose logs data-collector`
- **Collector logs**: `/var/log/data-collector/collector.log`
- **Cron logs**: `/var/log/data-collector/cron.log`

### Health Check

```bash
# Test API connection
python test_api.py

# Django health endpoint
curl http://localhost:8000/health/
```

### API Statistics

```bash
# Aggregated statistics via API
curl http://localhost:8000/api/ips/statistiche/
```

## 🔄 **Migration from Original Scripts**

### Command Equivalences

| Original Script | Container Command |
|------------------|-------------------|
| `python reti-services3.py -c update` | `python scripts/data_collector.py -c update` |
| `python reti-services3.py -c create -e lan -i 192.168.1.0/24` | `python scripts/data_collector.py -c create -e lan -i 192.168.1.0/24` |
| `updateall3.sh` | Automatic via cron every 30 minutes |

### Key Differences

1. **REST API** instead of direct Drupal database calls
2. **Containerization** for isolation and portability  
3. **Structured logging** with configurable levels
4. **Modern scheduling** with dedicated cron
5. **Configuration as code** in Python instead of hardcoded values

## 🗂️ **Management Scripts**

### release_old_ips.py

Script for **automatic release of long-term inactive IPs**.

**Release criteria:**
- `ultimo_controllo` > threshold days (default: 30 days)
- `stato` = 'disattivo' 
- `disponibilita` = 'usato'

**Actions performed:**
- Completely releases IP (disponibilita → 'libero')
- Removes user assignment (assegnato_a_utente → None)
- Clears responsible and end user
- Updates responsible history with reason 'inattivita'

**Usage:**

```bash
# Test dry-run (shows what would be done)
python scripts/release_old_ips.py --dry-run

# Release IPs inactive for more than 45 days
python scripts/release_old_ips.py --days 45

# Verbose mode for debugging
python scripts/release_old_ips.py --days 30 --verbose

# Example output
2025-01-06 03:00:01 - INFO - Starting processing of old and inactive IPs
2025-01-06 03:00:01 - INFO - Inactivity threshold: 30 days
2025-01-06 03:00:02 - INFO - Retrieved 2847 IPs from system
2025-01-06 03:00:02 - INFO - Analyzing 2847 IPs...
2025-01-06 03:00:03 - INFO - 🎯 Candidate IP: 192.168.1.100 - Inactive for 45 days (threshold: 30)
2025-01-06 03:00:03 - INFO - ✅ IP 192.168.1.100 released successfully. Was assigned to: mario.rossi@uniroma1.it
2025-01-06 03:00:10 - INFO - Processing completed:
2025-01-06 03:00:10 - INFO -   📊 Total IPs analyzed: 2847
2025-01-06 03:00:10 - INFO -   🎯 Candidate IPs for release: 12
2025-01-06 03:00:10 - INFO -   ✅ IPs released successfully: 12
2025-01-06 03:00:10 - INFO -   ❌ Release errors: 0
```

**Scheduling:** 
- **Automatic**: daily at 3:00 AM via cron
- **Threshold**: 30 days of inactivity (configurable)
- **Logs**: `/var/log/data-collector/release_old_ips.log`

### network_cleanup.py 

Script for **deactivation of short-term inactive IPs**.

**Deactivation criteria:**
- `ultimo_controllo` > threshold hours (default: 2 hours)
- Does not change responsible, only network status

**Scheduling:**
- **Automatic**: every 30 minutes via cron  
- **Threshold**: 2 hours of inactivity

## 🛠️ **Development**

### Adding New Devices

1. Edit `config/config.py`
2. Add device to `ROUTERS` or `FIREWALLS`
3. Restart container: `docker-compose restart data-collector`

### Local Testing

```bash
# Build container
docker build -t data-collector ./docker/data-collector/

# Run test
docker run --rm data-collector python test_api.py
```

## 🔐 **Security**

- **SNMP credentials** configured via environment variables
- **API Token** for Django authentication
- **Container isolation** for security boundary
- **Centralized logs** for audit trail

## 📈 **Performance**

- **Bulk operations** for multiple updates
- **Connection pooling** for HTTP API
- **Selective updates** to reduce database load
- **Parallel processing** for multiple device collection

## 🚨 **Configuration Checklist**

Before deploying to production:

- [ ] Copy `config_example.txt` to `config.py`
- [ ] Update all router IP addresses and SNMP communities
- [ ] Configure firewall SNMPv3 credentials
- [ ] Set Django API URL and authentication token
- [ ] Adjust F5 file paths for your environment
- [ ] Test SNMP connectivity to all devices
- [ ] Verify API access to Django server
- [ ] Check container resource limits
- [ ] Review security settings and credentials
- [ ] Configure log rotation and monitoring