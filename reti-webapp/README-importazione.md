# Importazione dati nella nuova applicazione IP-Reti

Questo README fornisce le istruzioni per importare i dati dai file CSV al database MariaDB della nuova applicazione Django.

## Opzione 1: Importazione tramite interfaccia Admin Django

Il modo più semplice per importare dati è utilizzare l'interfaccia amministrativa di Django che ora include funzionalità di importazione CSV sia per le VLAN che per gli indirizzi IP.

### Procedura
1. Accedi all'interfaccia di amministrazione Django (http://localhost:8000/admin/ o altro URL configurato)
2. Vai alla sezione "VLAN" o "Indirizzi IP" a seconda dei dati che desideri importare
3. Clicca sul pulsante "Importa CSV" nella parte superiore della pagina
4. Seleziona il file CSV e clicca su "Importa"

### Formato dei file CSV per l'importazione tramite Admin

#### VLAN
```
"VLAN ID","VLAN Name","Device Count","Port Count"
1,default,96,2463
2,VLAN0002,2,3
```

#### Indirizzi IP
```
IP,MAC Address,Stato,Responsabile,Utente Finale,Note,Ultimo Controllo,Data Scadenza
192.168.1.1,AA:BB:CC:DD:EE:FF,attivo,admin@example.com,Mario Rossi,Server web principale,2023-01-01 12:00:00,2024-01-01 12:00:00
192.168.1.2,11:22:33:44:55:66,attivo,tech@example.com,Dipartimento IT,Server database,2023-01-15 08:30:00,2023-12-31 23:59:59
```

I file di esempio `ip_sample.csv` e `vlan_sample.csv` sono disponibili nella directory del progetto.

## Opzione 2: Importazione tramite Django Management Command

Un'alternativa più flessibile è utilizzare il comando Django creato appositamente per importare i file CSV.

### Prerequisiti
1. Ambiente Django configurato e funzionante
2. File CSV degli IP e delle VLAN in un formato compatibile

### Procedura
1. Accedi al container Docker di Django o attiva l'ambiente virtuale della tua installazione:
   ```bash
   docker exec -it ip-reti-django bash
   # oppure
   source /path/to/venv/bin/activate
   ```

2. Posiziona i file CSV nella directory del progetto o in una posizione accessibile

3. Esegui il comando di importazione:
   ```bash
   # Importare solo gli indirizzi IP
   python manage.py import_csv --ip /path/to/ip.csv
   
   # Importare solo le VLAN
   python manage.py import_csv --vlan /path/to/vlan.csv
   
   # Importare entrambi
   python manage.py import_csv --ip /path/to/ip.csv --vlan /path/to/vlan.csv
   
   # Eliminare i dati esistenti prima dell'importazione
   python manage.py import_csv --ip /path/to/ip.csv --vlan /path/to/vlan.csv --delete
   ```

4. Verifica che l'importazione sia avvenuta correttamente accedendo all'interfaccia admin di Django

## Opzione 3: Importazione tramite SQL

Un'alternativa è utilizzare direttamente SQL per importare i dati dai file CSV.

### Prerequisiti
1. Accesso a MariaDB/MySQL con privilegi sufficienti
2. File CSV degli IP e delle VLAN accessibili dal server database

### Procedura
1. Modifica il file `import_data.sql` per decommentare le istruzioni LOAD DATA e specificare correttamente i percorsi dei file CSV

2. Accedi al database:
   ```bash
   # Da Docker
   docker exec -it ip-reti-mariadb bash -c "mysql -u root -p"
   # oppure
   mysql -u username -p
   ```

3. Esegui lo script SQL:
   ```bash
   mysql -u username -p ip_reti_db < import_data.sql
   ```

4. Verifica che l'importazione sia avvenuta correttamente con le query:
   ```sql
   SELECT COUNT(*) FROM reti_app_indirizzoip;
   SELECT COUNT(*) FROM reti_app_vlan;
   ```

## Formato dei file CSV originali

### File degli IP (ip.csv)
Il file CSV originale ha la seguente struttura:
```
"Indirizzo IP","Stato","Disponibilita","Mac Address","Mail responsabile","ultimo controllo","note (db access)","Utente finale (fleetmanagement)"
"192.168.99.99","disattivo","libero","","undefined","29/07/2015","",""
"192.168.99.98","disattivo","libero","","undefined","29/07/2015","",""
```

### File delle VLAN (vlan.csv)
Il file CSV originale ha la seguente struttura:
```
"Numero","Nome","Descrizione","Subnet","Gateway"
"10","Rete test","Descrizione di test","192.168.0.0/24","192.168.0.1"
```

## Integrazione degli indirizzi IP con le VLAN

Per associare gli indirizzi IP alle VLAN corrispondenti dopo l'importazione, puoi eseguire questo comando SQL:

```sql
UPDATE reti_app_indirizzoip ip
JOIN reti_app_vlan vlan ON SUBSTRING_INDEX(ip.ip, '.', 3) = SUBSTRING_INDEX(vlan.subnet, '.', 3)
SET ip.vlan_id = vlan.numero
WHERE vlan.subnet IS NOT NULL;
```

## Note sulla sicurezza
Prima di qualsiasi operazione di importazione su un database di produzione, è fortemente consigliato:
1. Eseguire un backup completo del database
2. Testare l'importazione su un ambiente di staging
3. Verificare i dati importati prima di rendere disponibile l'applicazione agli utenti 