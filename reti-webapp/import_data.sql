-- Script SQL per importare i dati dai file CSV nel database MariaDB per Django
-- Questo script presuppone che i file IP.csv e vlan.csv esistano nella directory corrente

-- Impostazioni per prevenire errori durante l'importazione
SET FOREIGN_KEY_CHECKS = 0;
SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";

-- Assicurati di essere nel database corretto
USE ip_reti_db;

-- =========== IMPORTAZIONE VLAN ===========
-- Creiamo una tabella temporanea per l'importazione
CREATE TEMPORARY TABLE temp_vlan (
    Numero VARCHAR(50),
    Nome VARCHAR(255),
    Descrizione TEXT,
    Subnet VARCHAR(100),
    Gateway VARCHAR(100)
);

-- Importiamo i dati dal CSV
-- NOTA: Il percorso del file deve essere accessibile dal server MySQL/MariaDB
-- LOAD DATA LOCAL INFILE 'vlan.csv'
-- INTO TABLE temp_vlan
-- FIELDS TERMINATED BY ',' ENCLOSED BY '"'
-- LINES TERMINATED BY '\n'
-- IGNORE 1 LINES
-- (Numero, Nome, Descrizione, Subnet, Gateway);

-- Inseriamo i dati nella tabella Django
INSERT INTO reti_app_vlan (numero, nome, descrizione, subnet, gateway)
SELECT Numero, Nome, Descrizione, Subnet, Gateway
FROM temp_vlan;

-- Eliminiamo la tabella temporanea
DROP TEMPORARY TABLE IF EXISTS temp_vlan;

-- =========== IMPORTAZIONE INDIRIZZI IP ===========
-- Creiamo una tabella temporanea per l'importazione
CREATE TEMPORARY TABLE temp_ip (
    `Indirizzo IP` VARCHAR(50),
    `Stato` VARCHAR(50),
    `Disponibilita` VARCHAR(50),
    `Mac Address` VARCHAR(100),
    `Mail responsabile` VARCHAR(255),
    `ultimo controllo` VARCHAR(50),
    `note (db access)` TEXT,
    `Utente finale (fleetmanagement)` VARCHAR(255)
);

-- Importiamo i dati dal CSV
-- NOTA: Il percorso del file deve essere accessibile dal server MySQL/MariaDB
-- LOAD DATA LOCAL INFILE 'ip.csv'
-- INTO TABLE temp_ip
-- FIELDS TERMINATED BY ',' ENCLOSED BY '"'
-- LINES TERMINATED BY '\n'
-- IGNORE 1 LINES
-- (`Indirizzo IP`, `Stato`, `Disponibilita`, `Mac Address`, `Mail responsabile`, 
--  `ultimo controllo`, `note (db access)`, `Utente finale (fleetmanagement)`);

-- Inseriamo i dati nella tabella Django
INSERT INTO reti_app_indirizzoip (indirizzo, stato, disponibilita, mac_address, 
                                 mail_responsabile, ultimo_controllo, note, utente_finale, vlan_id)
SELECT 
    `Indirizzo IP`,
    CASE WHEN LOWER(`Stato`) = 'attivo' THEN 1 ELSE 0 END,
    LOWER(`Disponibilita`),
    NULLIF(`Mac Address`, ''),
    CASE WHEN `Mail responsabile` = 'undefined' THEN NULL ELSE NULLIF(`Mail responsabile`, '') END,
    CASE 
        WHEN `ultimo controllo` = 'undefined' OR `ultimo controllo` = '' THEN NULL
        ELSE STR_TO_DATE(`ultimo controllo`, '%d/%m/%Y')
    END,
    NULLIF(`note (db access)`, ''),
    NULLIF(`Utente finale (fleetmanagement)`, ''),
    NULL -- vlan_id (sarà da impostare in base alla rete)
FROM temp_ip;

-- Eliminiamo la tabella temporanea
DROP TEMPORARY TABLE IF EXISTS temp_ip;

-- Ripristina le impostazioni
SET FOREIGN_KEY_CHECKS = 1;

-- Notifica di completamento
SELECT 'Importazione completata con successo!' AS Messaggio;

-- NOTA: Per eseguire questo script:
-- 1. Assicurati che i file CSV siano accessibili dal server MariaDB
-- 2. Rimuovi i commenti dalle istruzioni LOAD DATA LOCAL INFILE
-- 3. Esegui il comando: mysql -u username -p ip_reti_db < import_data.sql 