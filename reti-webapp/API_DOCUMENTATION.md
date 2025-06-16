# 🚀 IP Reti - API Documentation

## 📝 Overview

L'API REST del sistema di gestione indirizzi IP offre endpoints completi per la gestione di indirizzi IP, VLAN e utenti.

**Base URL:** `http://localhost:8000/api/`

---

## 🌐 IP Address Management

### 📋 List IP Addresses

**Endpoint:** `GET /api/ips/`

Recupera una lista paginata di tutti gli indirizzi IP con possibilità di filtri e ricerca.

**Parametri di query disponibili:**
- `stato`: `attivo`, `disattivo`
- `disponibilita`: `libero`, `usato`, `riservato`
- `responsabile`: email del responsabile
- `mac_address`: MAC address
- `vlan`: numero VLAN
- `anomalo`: `si`, `no` - filtra IP anomali (attivi ma liberi)
- `scaduto`: `si`, `no` - filtra IP scaduti
- `search`: cerca in IP, utente finale, note
- `ordering`: `ip`, `ultimo_controllo`, `data_modifica`, `data_scadenza`
- `page`: numero pagina
- `page_size`: elementi per pagina (default: 20, max: 100)

**Esempio:**
```bash
curl "http://localhost:8000/api/ips/?stato=attivo&disponibilita=usato&anomalo=si"
```

### 🔍 Get IP Address Details

**Endpoint:** `GET /api/ips/{ip}/`

Recupera i dettagli di un indirizzo IP specifico.

**Esempio:**
```bash
curl "http://localhost:8000/api/ips/192.168.1.100/"
```

**Risposta:**
```json
{
    "ip": "192.168.1.100",
    "mac_address": "00:1A:2B:3C:4D:5E",
    "stato": "attivo",
    "disponibilita": "usato",
    "responsabile": "user@uniroma1.it",
    "utente_finale": "John Doe",
    "note": "Computer laboratorio",
    "ultimo_controllo": "2025-01-16T14:30:00Z",
    "data_scadenza": "2025-07-16T00:00:00Z",
    "data_creazione": "2025-01-01T10:00:00Z",
    "data_modifica": "2025-01-16T14:30:00Z",
    "vlan": {
        "numero": 100,
        "nome": "Lab_Network",
        "descrizione": "Rete laboratorio informatico"
    },
    "assegnato_a_utente": {
        "username": "user@uniroma1.it",
        "email": "user@uniroma1.it",
        "first_name": "Mario",
        "last_name": "Rossi"
    },
    "is_scaduto": false,
    "giorni_alla_scadenza": 150,
    "is_anomalo": false
}
```

### ➕ Create New IP Address

**Endpoint:** `POST /api/ips/`

Crea un nuovo indirizzo IP.

**Esempio:**
```bash
curl -X POST "http://localhost:8000/api/ips/" \
     -H "Content-Type: application/json" \
     -H "Authorization: Token your_token_here" \
     -d '{
       "ip": "192.168.1.200",
       "mac_address": "00:1A:2B:3C:4D:5F",
       "stato": "attivo",
       "disponibilita": "usato",
       "responsabile": "admin@uniroma1.it",
       "utente_finale": "Jane Doe",
       "note": "Nuovo computer",
       "vlan": 100
     }'
```

### ✏️ Update IP Address (Full)

**Endpoint:** `PUT /api/ips/{ip}/`

Aggiorna completamente un indirizzo IP (tutti i campi sono richiesti).

### ✏️ Update IP Address (Partial)

**Endpoint:** `PATCH /api/ips/{ip}/`

Aggiorna parzialmente un indirizzo IP (solo i campi forniti).

**Esempio:**
```bash
curl -X PATCH "http://localhost:8000/api/ips/192.168.1.100/" \
     -H "Content-Type: application/json" \
     -H "Authorization: Token your_token_here" \
     -d '{"note": "Computer aggiornato"}'
```

### 🗑️ Delete IP Address

**Endpoint:** `DELETE /api/ips/{ip}/`

Elimina un indirizzo IP dal sistema.

---

## 🔧 Special Endpoints

### 🔍 Drupal Compatibility

**Endpoint:** `GET /api/ips/getbyip/?title={ip}`

Endpoint per compatibilità con il vecchio sistema Drupal.

**Esempio:**
```bash
curl "http://localhost:8000/api/ips/getbyip/?title=192.168.1.100"
```

### ✅ IP Range Validation

**Endpoint:** `GET /api/ips/validate_ip_range/?ip={ip}`

Valida se un IP è in un range privato consentito.

**Esempio:**
```bash
curl "http://localhost:8000/api/ips/validate_ip_range/?ip=192.168.1.200"
```

**Risposta:**
```json
{
    "ip": "192.168.1.200",
    "valid": true,
    "range_type": "192.168.x.x",
    "message": "IP valido nel range privato"
}
```

### 🔄 Update Status Only

**Endpoint:** `PATCH /api/ips/{ip}/update_stato/`

Aggiorna solo lo stato di rete di un IP.

**Esempio:**
```bash
curl -X PATCH "http://localhost:8000/api/ips/192.168.1.100/update_stato/" \
     -H "Content-Type: application/json" \
     -H "Authorization: Token your_token_here" \
     -d '{"stato": "attivo"}'
```

### 📡 Update Last Check

**Endpoint:** `POST /api/ips/{ip}/aggiorna_controllo/`

Aggiorna il timestamp dell'ultimo controllo per un IP.

**Esempio:**
```bash
curl -X POST "http://localhost:8000/api/ips/192.168.1.100/aggiorna_controllo/" \
     -H "Authorization: Token your_token_here"
```

### ⏰ Update Expiration Date

**Endpoint:** `POST /api/ips/{ip}/aggiorna_scadenza/`

Aggiorna automaticamente la data di scadenza se necessario.

### 🔓 Release IP

**Endpoint:** `POST /api/ips/{ip}/libera/`

Libera un IP se scaduto o con parametri specifici.

**Parametri:**
- `force` (boolean): Forza la liberazione
- `motivo` (string): Motivo della liberazione
- `note` (string): Note aggiuntive

### 📊 Statistics

**Endpoint:** `GET /api/ips/statistiche/`

Recupera statistiche aggregate sugli indirizzi IP.

**Esempio:**
```bash
curl "http://localhost:8000/api/ips/statistiche/"
```

**Risposta:**
```json
{
    "totale": 1000,
    "per_stato": {
        "attivo": 600,
        "disattivo": 400
    },
    "per_disponibilita": {
        "libero": 300,
        "usato": 700
    },
    "anomali": 15,
    "scaduti": 8,
    "per_vlan": {
        "100": 250,
        "200": 150
    }
}
```

---

## 🌐 VLAN Management

### 📋 List VLANs

**Endpoint:** `GET /api/vlans/`

### 🔍 Get VLAN Details

**Endpoint:** `GET /api/vlans/{numero}/`

### ➕ Create VLAN

**Endpoint:** `POST /api/vlans/`

### ✏️ Update VLAN

**Endpoint:** `PUT /api/vlans/{numero}/` o `PATCH /api/vlans/{numero}/`

### 🗑️ Delete VLAN

**Endpoint:** `DELETE /api/vlans/{numero}/`

---

## 🔐 Authentication

L'API utilizza Token Authentication di Django REST Framework.

### Ottenere un token:
```bash
curl -X POST "http://localhost:8000/api-auth/login/" \
     -d "username=your_username&password=your_password"
```

### Usare il token:
```bash
curl -H "Authorization: Token your_token_here" \
     "http://localhost:8000/api/ips/"
```

---

## 📖 Examples

### Scenario 1: Monitoring Script

Script per aggiornare lo stato di IP attivi:

```bash
#!/bin/bash
API_BASE="http://localhost:8000/api/ips"
TOKEN="your_token_here"

# Lista IP attivi
ACTIVE_IPS=("192.168.1.100" "192.168.1.101" "192.168.1.102")

for IP in "${ACTIVE_IPS[@]}"; do
    echo "Aggiornando controllo per $IP..."
    curl -X POST "$API_BASE/$IP/aggiorna_controllo/" \
         -H "Authorization: Token $TOKEN"
done

# Aggiorna stato di tutti gli IP attivi
for IP in "${ACTIVE_IPS[@]}"; do
    curl -X PATCH "$API_BASE/$IP/update_stato/" \
         -H "Content-Type: application/json" \
         -H "Authorization: Token $TOKEN" \
         -d '{"stato": "attivo"}'
done

# Libera IP scaduti
SCADUTI=$(curl -s "$API_BASE/?scaduto=si" | jq -r '.results[].ip')

for IP in $SCADUTI; do
    echo "Releasing expired IP: $IP"
    curl -X POST "$API_BASE/$IP/libera/" \
         -H "Authorization: Token $TOKEN"
done
```

### Scenario 2: Python Integration

```python
import requests

class IPManager:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.headers = {'Authorization': f'Token {token}'}
    
    def get_ip_stats(self):
        response = requests.get('http://localhost:8000/api/ips/', params={
            'anomalo': 'si'
        }, headers=self.headers)
        return response.json()
    
    def update_ip_check(self, ip):
        requests.post(f'http://localhost:8000/api/ips/192.168.1.100/aggiorna_controllo/')

# Utilizzo
manager = IPManager('http://localhost:8000/api', 'your_token')
stats = manager.get_ip_stats()
```

### Scenario 3: JavaScript Frontend

```javascript
// Verifica disponibilità IP
async function checkIPAvailability(ip) {
    const response = await fetch(`/api/ips/getbyip/?title=${ip}`);
    return await response.json();
}

// Aggiorna stato IP
async function updateIPStatus(ip, status) {
    const response = await fetch(`/api/ips/${ip}/update_stato/`, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Token ' + getToken()
        },
        body: JSON.stringify({stato: status})
    });
    return await response.json();
}
```

---

## 📊 Monitoring & Maintenance

### Endpoint per monitoraggio:

```bash
# Statistiche complete
curl "http://localhost:8000/api/ips/statistiche/"

# IP anomali (attivi ma liberi)
curl "http://localhost:8000/api/ips/?anomalo=si"

# IP scaduti
curl "http://localhost:8000/api/ips/?scaduto=si"

# Health check
curl "http://localhost:8000/health/"
``` 