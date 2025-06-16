# IP Network Management – REST API Documentation

This document describes the REST API endpoints for the Django-based IP address management system.

## 🔐 **Authentication**

All API endpoints require authentication via Token-based authentication.

### Get Authentication Token

1. **Admin Interface**: Access `/admin/authtoken/token/` and create a token
2. **Command line**: `python manage.py drf_create_token <username>`

### Usage

Include the token in the `Authorization` header:

```bash
curl -H "Authorization: Token your_api_token_here" \
     http://localhost:8000/api/ips/
```

## 📍 **Base URL**

```
http://localhost:8000/api/
```

## 🎯 **Endpoints Overview**

| Resource | Endpoint | Methods | Description |
|----------|----------|---------|-------------|
| IP Addresses | `/ips/` | GET, POST | List and create IP addresses |
| IP Detail | `/ips/{ip}/` | GET, PUT, PATCH, DELETE | Manage specific IP |
| IP Statistics | `/ips/statistiche/` | GET | Network usage statistics |
| VLANs | `/vlans/` | GET, POST | VLAN management |
| VLAN Detail | `/vlans/{id}/` | GET, PUT, PATCH, DELETE | Specific VLAN operations |
| VLAN Statistics | `/vlans/{id}/statistiche/` | GET | VLAN-specific statistics |

## 📊 **IP Address Management**

### List IP Addresses

**Endpoint**: `GET /api/ips/`

**Description**: Returns paginated list of all IP addresses with filtering support.

**Query Parameters**:
- `vlan` (int): Filter by VLAN ID
- `stato` (string): Filter by status (`attivo`, `disattivo`)
- `disponibilita` (string): Filter by availability (`libero`, `usato`, `riservato`)
- `search` (string): Search in IP address, MAC, user, notes
- `page` (int): Page number for pagination
- `page_size` (int): Items per page (default: 20, max: 100)

**Example Request**:
```bash
curl -H "Authorization: Token your_token" \
     "http://localhost:8000/api/ips/?vlan=1&stato=attivo&page=2"
```

**Example Response**:
```json
{
  "count": 1247,
  "next": "http://localhost:8000/api/ips/?page=3",
  "previous": "http://localhost:8000/api/ips/?page=1",
  "results": [
    {
      "indirizzo": "192.168.1.100",
      "vlan": {
        "id": 1,
        "nome": "LAN_Students",
        "descrizione": "Student network",
        "subnet": "192.168.1.0/24"
      },
      "stato": "attivo",
      "disponibilita": "usato",
      "mac_address": "aa:bb:cc:dd:ee:ff",
      "assegnato_a_utente": "mario.rossi@uniroma1.it",
      "responsabile": "Prof. Giovanni Bianchi",
      "utente_finale": "Mario Rossi",
      "data_creazione": "2025-01-01T10:30:00Z",
      "ultimo_controllo": "2025-01-06T15:45:00Z",
      "note": "Student workstation – Room A101"
    }
  ]
}
```

### Get Specific IP

**Endpoint**: `GET /api/ips/{ip_address}/`

**Description**: Returns detailed information about a specific IP address.

**Example Request**:
```bash
curl -H "Authorization: Token your_token" \
     "http://localhost:8000/api/ips/192.168.1.100/"
```

**Example Response**:
```json
{
  "indirizzo": "192.168.1.100",
  "vlan": {
    "id": 1,
    "nome": "LAN_Students", 
    "descrizione": "Student network",
    "subnet": "192.168.1.0/24"
  },
  "stato": "attivo",
  "disponibilita": "usato",
  "mac_address": "aa:bb:cc:dd:ee:ff",
  "assegnato_a_utente": "mario.rossi@uniroma1.it",
  "responsabile": "Prof. Giovanni Bianchi",
  "utente_finale": "Mario Rossi",
  "data_creazione": "2025-01-01T10:30:00Z",
  "ultimo_controllo": "2025-01-06T15:45:00Z",
  "note": "Student workstation – Room A101",
  "storico_responsabili": [
    {
      "id": 1,
      "responsabile_precedente": "Prof. Luigi Verdi",
      "nuovo_responsabile": "Prof. Giovanni Bianchi", 
      "data_cambio": "2025-01-03T14:20:00Z",
      "motivo": "trasferimento"
    }
  ]
}
```

### Create New IP

**Endpoint**: `POST /api/ips/`

**Description**: Creates a new IP address entry.

**Required Fields**:
- `indirizzo` (string): IP address in dotted decimal notation
- `vlan` (int): VLAN ID

**Optional Fields**:
- `stato` (string): Status (`attivo`, `disattivo`) – default: `disattivo`
- `disponibilita` (string): Availability (`libero`, `usato`, `riservato`) – default: `libero`
- `mac_address` (string): MAC address in format xx:xx:xx:xx:xx:xx
- `assegnato_a_utente` (string): Assigned user email
- `responsabile` (string): Responsible person name
- `utente_finale` (string): End user name
- `note` (string): Additional notes

**Example Request**:
```bash
curl -X POST \
     -H "Authorization: Token your_token" \
     -H "Content-Type: application/json" \
     -d '{
       "indirizzo": "192.168.1.150",
       "vlan": 1,
       "stato": "attivo",
       "disponibilita": "usato",
       "mac_address": "bb:cc:dd:ee:ff:aa",
       "assegnato_a_utente": "anna.verdi@uniroma1.it",
       "responsabile": "Prof. Marco Neri",
       "note": "New assignment for laboratory"
     }' \
     "http://localhost:8000/api/ips/"
```

**Example Response**:
```json
{
  "indirizzo": "192.168.1.150",
  "vlan": {
    "id": 1,
    "nome": "LAN_Students",
    "descrizione": "Student network", 
    "subnet": "192.168.1.0/24"
  },
  "stato": "attivo",
  "disponibilita": "usato",
  "mac_address": "bb:cc:dd:ee:ff:aa",
  "assegnato_a_utente": "anna.verdi@uniroma1.it",
  "responsabile": "Prof. Marco Neri",
  "utente_finale": null,
  "data_creazione": "2025-01-06T16:30:00Z",
  "ultimo_controllo": "2025-01-06T16:30:00Z",
  "note": "New assignment for laboratory"
}
```

### Update IP Address

**Endpoint**: `PUT /api/ips/{ip_address}/` or `PATCH /api/ips/{ip_address}/`

**Description**: Updates an existing IP address. Use `PUT` for complete updates, `PATCH` for partial updates.

**Example Request** (PATCH):
```bash
curl -X PATCH \
     -H "Authorization: Token your_token" \
     -H "Content-Type: application/json" \
     -d '{
       "stato": "attivo",
       "mac_address": "cc:dd:ee:ff:aa:bb",
       "note": "Updated MAC address after device replacement"
     }' \
     "http://localhost:8000/api/ips/192.168.1.100/"
```

### Delete IP Address

**Endpoint**: `DELETE /api/ips/{ip_address}/`

**Description**: Removes an IP address from the system.

**Example Request**:
```bash
curl -X DELETE \
     -H "Authorization: Token your_token" \
     "http://localhost:8000/api/ips/192.168.1.100/"
```

**Response**: `204 No Content` on success

## 📊 **Statistics**

### Network Statistics

**Endpoint**: `GET /api/ips/statistiche/`

**Description**: Returns overall network usage statistics.

**Example Request**:
```bash
curl -H "Authorization: Token your_token" \
     "http://localhost:8000/api/ips/statistiche/"
```

**Example Response**:
```json
{
  "totale_ip": 2847,
  "ip_usati": 1423,
  "ip_liberi": 1324,
  "ip_riservati": 100,
  "utilizzo_percentuale": 49.98,
  "ip_attivi": 1203,
  "ip_disattivi": 1644,
  "per_vlan": [
    {
      "vlan_id": 1,
      "vlan_nome": "LAN_Students",
      "totale": 254,
      "usati": 187,
      "liberi": 67,
      "utilizzo_percentuale": 73.62
    },
    {
      "vlan_id": 2, 
      "vlan_nome": "LAN_Staff",
      "totale": 100,
      "usati": 89,
      "liberi": 11,
      "utilizzo_percentuale": 89.0
    }
  ],
  "ultima_sincronizzazione": "2025-01-06T15:45:00Z"
}
```

## 🌐 **VLAN Management**

### List VLANs

**Endpoint**: `GET /api/vlans/`

**Description**: Returns list of all configured VLANs.

**Example Request**:
```bash
curl -H "Authorization: Token your_token" \
     "http://localhost:8000/api/vlans/"
```

**Example Response**:
```json
[
  {
    "id": 1,
    "nome": "LAN_Students", 
    "descrizione": "Student network – classrooms and labs",
    "subnet": "192.168.1.0/24",
    "gateway": "192.168.1.1",
    "vlan_id": 100,
    "data_creazione": "2024-09-01T10:00:00Z"
  },
  {
    "id": 2,
    "nome": "LAN_Staff",
    "descrizione": "Staff and administrative network", 
    "subnet": "192.168.2.0/24",
    "gateway": "192.168.2.1",
    "vlan_id": 200,
    "data_creazione": "2024-09-01T10:00:00Z"
  }
]
```

### VLAN Statistics

**Endpoint**: `GET /api/vlans/{id}/statistiche/`

**Description**: Returns detailed statistics for a specific VLAN.

**Example Request**:
```bash
curl -H "Authorization: Token your_token" \
     "http://localhost:8000/api/vlans/1/statistiche/"
```

**Example Response**:
```json
{
  "vlan": {
    "id": 1,
    "nome": "LAN_Students",
    "descrizione": "Student network",
    "subnet": "192.168.1.0/24"
  },
  "totale_ip": 254,
  "ip_usati": 187,
  "ip_liberi": 67,
  "ip_riservati": 0,
  "utilizzo_percentuale": 73.62,
  "ip_attivi": 156,
  "ip_disattivi": 98,
  "ultimo_aggiornamento": "2025-01-06T15:45:00Z",
  "top_users": [
    {
      "utente": "mario.rossi@uniroma1.it",
      "ip_count": 3
    },
    {
      "utente": "anna.verdi@uniroma1.it", 
      "ip_count": 2
    }
  ]
}
```

## 🔍 **Search and Filtering**

### Advanced Search

The API supports advanced search across multiple fields using the `search` parameter:

**Searchable Fields**:
- IP address (exact or partial match)
- MAC address
- Assigned user email
- Responsible person name  
- End user name
- Notes

**Example Requests**:
```bash
# Search by partial IP
curl -H "Authorization: Token your_token" \
     "http://localhost:8000/api/ips/?search=192.168.1"

# Search by MAC address
curl -H "Authorization: Token your_token" \
     "http://localhost:8000/api/ips/?search=aa:bb:cc"

# Search by user
curl -H "Authorization: Token your_token" \
     "http://localhost:8000/api/ips/?search=mario.rossi"

# Combined filters
curl -H "Authorization: Token your_token" \
     "http://localhost:8000/api/ips/?vlan=1&stato=attivo&search=lab"
```

## 📄 **Pagination**

All list endpoints support pagination with the following parameters:

- `page`: Page number (starting from 1)
- `page_size`: Items per page (default: 20, maximum: 100)

**Response includes**:
- `count`: Total number of items
- `next`: URL for next page (null if last page)
- `previous`: URL for previous page (null if first page)
- `results`: Array of items for current page

## ⚠️ **Error Handling**

### Standard HTTP Status Codes

- `200 OK`: Successful GET/PUT/PATCH
- `201 Created`: Successful POST
- `204 No Content`: Successful DELETE
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Missing or invalid authentication
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource already exists
- `500 Internal Server Error`: Server error

### Error Response Format

```json
{
  "error": "Validation failed",
  "details": {
    "indirizzo": ["This field is required."],
    "mac_address": ["Invalid MAC address format."]
  }
}
```

### Common Validation Errors

**IP Address**:
```json
{
  "error": "Invalid IP address",
  "details": {
    "indirizzo": ["Invalid IP address format."]
  }
}
```

**MAC Address**:
```json
{
  "error": "Invalid MAC address", 
  "details": {
    "mac_address": ["MAC address must be in format xx:xx:xx:xx:xx:xx"]
  }
}
```

**Duplicate IP**:
```json
{
  "error": "IP address already exists",
  "details": {
    "indirizzo": ["IP address 192.168.1.100 already exists."]
  }
}
```

## 🔄 **Data Collector Integration**

The API provides special endpoints used by the data collector container:

### Bulk Update

**Endpoint**: `POST /api/ips/bulk_update/`

**Description**: Updates multiple IP addresses in a single request (used by data collector).

**Example Request**:
```bash
curl -X POST \
     -H "Authorization: Token collector_token" \
     -H "Content-Type: application/json" \
     -d '{
       "updates": [
         {
           "indirizzo": "192.168.1.100",
           "stato": "attivo",
           "mac_address": "aa:bb:cc:dd:ee:ff",
           "ultimo_controllo": "2025-01-06T15:45:00Z"
         },
         {
           "indirizzo": "192.168.1.101", 
           "stato": "disattivo",
           "ultimo_controllo": "2025-01-06T15:45:00Z"
         }
       ]
     }' \
     "http://localhost:8000/api/ips/bulk_update/"
```

### Auto-Discovery

**Endpoint**: `POST /api/ips/discover/`

**Description**: Creates new IP addresses discovered by network scanning.

**Example Request**:
```bash
curl -X POST \
     -H "Authorization: Token collector_token" \
     -H "Content-Type: application/json" \
     -d '{
       "discoveries": [
         {
           "indirizzo": "192.168.1.200",
           "mac_address": "dd:ee:ff:aa:bb:cc",
           "vlan": 1,
           "note": "Detected from Cisco Router – 192.168.1.1"
         }
       ]
     }' \
     "http://localhost:8000/api/ips/discover/"
```

## 🧪 **Testing the API**

### Using curl

Basic authentication test:
```bash
curl -H "Authorization: Token your_token" \
     "http://localhost:8000/api/ips/?page_size=1"
```

### Using Python requests

```python
import requests

# Setup
API_BASE = 'http://localhost:8000/api'
TOKEN = 'your_api_token_here'
headers = {'Authorization': f'Token {TOKEN}'}

# Get statistics
response = requests.get(f'{API_BASE}/ips/statistiche/', headers=headers)
stats = response.json()
print(f"Total IPs: {stats['totale_ip']}")

# Search for specific IP
response = requests.get(f'{API_BASE}/ips/192.168.1.100/', headers=headers)
if response.status_code == 200:
    ip_data = response.json()
    print(f"IP {ip_data['indirizzo']} is {ip_data['stato']}")
else:
    print("IP not found")

# Create new IP
new_ip = {
    'indirizzo': '192.168.1.250',
    'vlan': 1,
    'stato': 'attivo',
    'disponibilita': 'usato',
    'note': 'Created via API'
}
response = requests.post(f'{API_BASE}/ips/', json=new_ip, headers=headers)
if response.status_code == 201:
    print("IP created successfully")
```

## 📚 **Additional Resources**

### Interactive API Documentation

When Django is running in development mode (`DEBUG=True`), you can access:

- **Browsable API**: `http://localhost:8000/api/` (Django REST Framework interface)
- **Admin Interface**: `http://localhost:8000/admin/` (Django admin for token management)

### Rate Limiting

API endpoints are rate-limited to prevent abuse:
- **Authenticated users**: 1000 requests per hour
- **Data collector**: 5000 requests per hour
- **Anonymous users**: 100 requests per hour

### API Versioning

Current API version: `v1`

Future versions will be accessible via:
- URL versioning: `/api/v2/ips/`
- Header versioning: `Accept: application/vnd.api+json; version=2`

---

## 📝 **Examples and Use Cases**

### Network Monitoring Integration

```python
# Monitor network utilization
import requests
import time

def check_network_usage():
    headers = {'Authorization': 'Token your_token'}
    response = requests.get('http://localhost:8000/api/ips/statistiche/', 
                          headers=headers)
    stats = response.json()
    
    if stats['utilizzo_percentuale'] > 90:
        send_alert(f"Network utilization high: {stats['utilizzo_percentuale']}%")
    
    return stats

# Run every hour
while True:
    stats = check_network_usage()
    print(f"Current utilization: {stats['utilizzo_percentuale']}%")
    time.sleep(3600)
```

### Automated IP Assignment

```python
# Assign IP to new device
def assign_ip_to_device(mac_address, user_email, vlan_id=1):
    headers = {'Authorization': 'Token your_token'}
    
    # Find available IP in VLAN
    response = requests.get(
        f'http://localhost:8000/api/ips/?vlan={vlan_id}&disponibilita=libero&page_size=1',
        headers=headers
    )
    
    available_ips = response.json()['results']
    if not available_ips:
        raise Exception("No available IPs in VLAN")
    
    ip_address = available_ips[0]['indirizzo']
    
    # Assign IP
    update_data = {
        'stato': 'attivo',
        'disponibilita': 'usato',
        'mac_address': mac_address,
        'assegnato_a_utente': user_email,
        'note': f'Auto-assigned via API at {datetime.now()}'
    }
    
    response = requests.patch(
        f'http://localhost:8000/api/ips/{ip_address}/',
        json=update_data,
        headers=headers
    )
    
    if response.status_code == 200:
        return ip_address
    else:
        raise Exception(f"Assignment failed: {response.text}")

# Usage
assigned_ip = assign_ip_to_device(
    mac_address='aa:bb:cc:dd:ee:ff',
    user_email='student@university.edu',
    vlan_id=1
)
print(f"Assigned IP: {assigned_ip}")
```

### Bulk Data Export

```python
# Export all IP data to CSV
import csv
import requests

def export_ips_to_csv(filename='ip_export.csv'):
    headers = {'Authorization': 'Token your_token'}
    all_ips = []
    page = 1
    
    while True:
        response = requests.get(
            f'http://localhost:8000/api/ips/?page={page}&page_size=100',
            headers=headers
        )
        data = response.json()
        all_ips.extend(data['results'])
        
        if not data['next']:
            break
        page += 1
    
    # Write to CSV
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['indirizzo', 'vlan', 'stato', 'disponibilita', 
                     'mac_address', 'assegnato_a_utente', 'responsabile']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for ip in all_ips:
            row = {field: ip.get(field, '') for field in fieldnames}
            row['vlan'] = ip['vlan']['nome'] if ip['vlan'] else ''
            writer.writerow(row)
    
    print(f"Exported {len(all_ips)} IPs to {filename}")

export_ips_to_csv()
```

---

**For more examples and detailed implementation guides, see the main [README.md](README.md) and [project documentation](https://github.com/your-username/ip-reti-django).** 