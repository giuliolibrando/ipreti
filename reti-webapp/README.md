# IP Reti - Applicazione di Gestione Indirizzi IP

Applicazione web per la gestione degli indirizzi IP dell'università. Questa è una reimplementazione moderna dell'applicazione originale basata su Drupal, utilizzando Django e un'architettura REST API.

## Caratteristiche principali

- Gestione completa degli indirizzi IP (CRUD)
- Monitoraggio dello stato (attivo/inattivo/riservato)
- Tracking dei MAC address associati
- API REST complete per integrazioni con gli script esistenti
- Interfaccia amministrativa moderna e intuitiva

## Requisiti di sistema

- Docker e Docker Compose
- Git

## Installazione

1. Clona il repository:
   ```
   git clone https://github.com/tuorepository/ip-reti-django.git
   cd ip-reti-django
   ```

2. Crea il file `.env` a partire dall'esempio:
   ```
   cp .env.example .env
   ```
   Modifica i valori secondo le tue necessità.

3. Avvia l'applicazione con Docker Compose:
   ```
   docker-compose up -d
   ```

4. Crea un superuser per accedere all'interfaccia amministrativa:
   ```
   docker-compose exec web python manage.py createsuperuser
   ```

5. Accedi a:
   - Interfaccia web: http://localhost:8000/
   - Admin panel: http://localhost:8000/admin/
   - API docs: http://localhost:8000/swagger/

## Migrazione dati dal vecchio sistema

Per migrare i dati dal vecchio sistema Drupal, è possibile utilizzare lo script di importazione fornito:

```
docker-compose exec web python manage.py import_drupal_data --file=/path/to/dump.sql
```

## 🔗 API Endpoints

L'applicazione espone una API REST completa per la gestione degli indirizzi IP:

- `GET /api/ips/` - Lista di tutti gli indirizzi IP
- `POST /api/ips/` - Crea un nuovo indirizzo IP
- `GET /api/ips/{ip}/` - Dettagli di un indirizzo IP specifico
- `PUT /api/ips/{ip}/` - Aggiornamento completo di un indirizzo IP
- `PATCH /api/ips/{ip}/` - Aggiornamento parziale di un indirizzo IP
- `DELETE /api/ips/{ip}/` - Elimina un indirizzo IP
- `GET /api/ips/getbyip/?title={ip}` - Endpoint compatibile con il vecchio sistema Drupal

Per ulteriori dettagli sulle API, consultare la documentazione Swagger all'indirizzo: `/swagger/`

## Sviluppo

Per lavorare in modalità sviluppo:

1. Crea un ambiente virtuale Python:
   ```
   python -m venv venv
   source venv/bin/activate  # Per Linux/Mac
   venv\Scripts\activate  # Per Windows
   ```

2. Installa i requisiti:
   ```
   pip install -r requirements.txt
   ```

3. Esegui le migrazioni:
   ```
   python manage.py migrate
   ```

4. Avvia il server di sviluppo:
   ```
   python manage.py runserver
   ```


# Aggiorna scadenze ogni ora
0 * * * * python manage.py gestisci_scadenze_ip --aggiorna-scadenze

# Libera IP scaduti ogni notte alle 2:00
0 2 * * * python manage.py gestisci_scadenze_ip --libera-scaduti

# Report settimanale
0 9 * * 1 python manage.py gestisci_scadenze_ip --dry-run --verbose

## Comandi di Management

L'applicazione include diversi comandi di management per operazioni amministrative:

### inizializza_storico

Inizializza lo storico dei responsabili per gli IP esistenti. Questo comando è utile quando si aggiunge la funzionalità di storico responsabili a un database esistente.

```bash
# Visualizza quanti IP verranno processati senza applicare modifiche
python manage.py inizializza_storico --dry-run

# Inizializza lo storico per tutti gli IP con responsabile esistenti
python manage.py inizializza_storico
```

**Cosa fa il comando:**
- Trova tutti gli IP che hanno un responsabile ma non hanno ancora uno storico
- Crea un record iniziale nello storico per ciascun IP utilizzando:
  - Mail responsabile e utente finale correnti
  - Data di creazione dell'IP come data di inizio assegnazione
  - Motivo "assegnazione"
  - Note esplicative

**Quando usarlo:**
- Dopo aver aggiunto la funzionalità di storico responsabili a un database esistente
- Quando si vuole inizializzare il tracking storico per IP già assegnati

### import_drupal_data

Importa dati dal vecchio sistema Drupal:

```bash
python manage.py import_drupal_data --file=/path/to/dump.sql
```

### gestisci_scadenze_ip

Gestisce le scadenze degli indirizzi IP:

```bash
# Aggiorna le scadenze
python manage.py gestisci_scadenze_ip --aggiorna-scadenze

# Libera IP scaduti
python manage.py gestisci_scadenze_ip --libera-scaduti

# Visualizza report senza modifiche
python manage.py gestisci_scadenze_ip --dry-run --verbose
```