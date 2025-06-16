#!/usr/bin/env python3
"""
Script di esempio per testare le API del sistema IP.
Dimostra l'uso completo delle API REST.

Utilizzo:
    python test_api_examples.py

Assicurati che il server Django sia in esecuzione su http://localhost:8000
"""

import requests
import json
import sys
from datetime import datetime

# Configurazione base
BASE_URL = "http://localhost:8000/api/indirizzi"
HEADERS = {
    'Content-Type': 'application/json'
}

def print_response(response, description):
    """Stampa la risposta dell'API in modo formattato"""
    print(f"\n{'='*50}")
    print(f"TEST: {description}")
    print(f"{'='*50}")
    print(f"Status Code: {response.status_code}")
    
    try:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
    except:
        print(f"Response: {response.text}")
    
    return response.status_code < 400

def test_list_ips():
    """Test 1: Lista tutti gli IP"""
    response = requests.get(f"{BASE_URL}/")
    return print_response(response, "Lista tutti gli IP")

def test_filter_ips():
    """Test 2: Filtra IP per stato attivo"""
    params = {'stato': 'attivo', 'page_size': 5}
    response = requests.get(f"{BASE_URL}/", params=params)
    return print_response(response, "Filtra IP attivi (primi 5)")

def test_search_ips():
    """Test 3: Ricerca IP"""
    params = {'search': 'admin'}
    response = requests.get(f"{BASE_URL}/", params=params)
    return print_response(response, "Ricerca IP con testo 'admin'")

def test_get_ip_detail():
    """Test 4: Dettaglio IP specifico"""
    # Prima ottieni un IP dalla lista
    response = requests.get(f"{BASE_URL}/", params={'page_size': 1})
    if response.status_code == 200:
        data = response.json()
        if data.get('results'):
            ip = data['results'][0]['ip']
            detail_response = requests.get(f"{BASE_URL}/{ip}/")
            return print_response(detail_response, f"Dettaglio IP {ip}")
    
    print("\nNessun IP trovato per test dettaglio")
    return False

def test_validate_ip_range():
    """Test 5: Validazione range IP"""
    params = {'ip': '192.168.1.200'}
    response = requests.get(f"{BASE_URL}/validate_ip_range/", params=params)
    return print_response(response, "Validazione IP 192.168.1.200")

def test_drupal_compatibility():
    """Test 6: Endpoint compatibilità Drupal"""
    params = {'title': '192.168.1.1'}
    response = requests.get(f"{BASE_URL}/getbyip/", params=params)
    return print_response(response, "Endpoint compatibilità Drupal")

def test_statistics():
    """Test 7: Statistiche aggregate"""
    response = requests.get(f"{BASE_URL}/statistiche/")
    return print_response(response, "Statistiche aggregate")

def test_create_ip():
    """Test 8: Creazione nuovo IP (solo se autenticato)"""
    new_ip = {
        'ip': '192.168.99.200',
        'mac_address': 'aa:bb:cc:dd:ee:99',
        'stato': 'disattivo',
        'disponibilita': 'usato',
        'responsabile': 'test@uniroma1.it',
        'utente_finale': 'Test API User',
        'note': 'IP creato tramite test API'
    }
    
    response = requests.post(f"{BASE_URL}/", json=new_ip, headers=HEADERS)
    success = print_response(response, "Creazione nuovo IP (test)")
    
    # Se creato con successo, eliminalo
    if success and response.status_code == 201:
        delete_response = requests.delete(f"{BASE_URL}/192.168.99.200/")
        print_response(delete_response, "Eliminazione IP di test")
    
    return success

def test_update_ip_status():
    """Test 9: Aggiornamento stato IP"""
    # Prima trova un IP
    response = requests.get(f"{BASE_URL}/", params={'page_size': 1})
    if response.status_code == 200:
        data = response.json()
        if data.get('results'):
            ip = data['results'][0]['ip']
            current_state = data['results'][0]['stato']
            
            # Prova a cambiare stato (solo toggle per test)
            new_state = 'disattivo' if current_state == 'attivo' else 'attivo'
            
            update_response = requests.patch(
                f"{BASE_URL}/{ip}/update_stato/",
                json={'stato': new_state},
                headers=HEADERS
            )
            
            success = print_response(update_response, f"Aggiornamento stato IP {ip}")
            
            # Ripristina stato originale
            if success:
                restore_response = requests.patch(
                    f"{BASE_URL}/{ip}/update_stato/",
                    json={'stato': current_state},
                    headers=HEADERS
                )
                print_response(restore_response, f"Ripristino stato originale IP {ip}")
            
            return success
    
    print("\nNessun IP trovato per test aggiornamento")
    return False

def test_update_last_check():
    """Test 10: Aggiornamento ultimo controllo"""
    # Prima trova un IP
    response = requests.get(f"{BASE_URL}/", params={'page_size': 1})
    if response.status_code == 200:
        data = response.json()
        if data.get('results'):
            ip = data['results'][0]['ip']
            
            check_response = requests.post(f"{BASE_URL}/{ip}/aggiorna_controllo/")
            return print_response(check_response, f"Aggiornamento ultimo controllo IP {ip}")
    
    print("\nNessun IP trovato per test aggiornamento controllo")
    return False

def main():
    """Esegue tutti i test delle API"""
    print("🚀 Test Suite API Sistema Gestione IP")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        test_list_ips,
        test_filter_ips,
        test_search_ips,
        test_get_ip_detail,
        test_validate_ip_range,
        test_drupal_compatibility,
        test_statistics,
        test_create_ip,
        test_update_ip_status,
        test_update_last_check
    ]
    
    results = []
    for i, test in enumerate(tests, 1):
        try:
            success = test()
            results.append(('✅' if success else '❌', test.__doc__.split(':')[1].strip()))
        except Exception as e:
            print(f"\n❌ ERRORE nel test {i}: {str(e)}")
            results.append(('❌', f"{test.__doc__.split(':')[1].strip()} - ERRORE: {str(e)}"))
    
    # Riepilogo finale
    print(f"\n{'='*60}")
    print("📊 RIEPILOGO RISULTATI TEST")
    print(f"{'='*60}")
    
    for status, description in results:
        print(f"{status} {description}")
    
    successful = sum(1 for status, _ in results if status == '✅')
    total = len(results)
    
    print(f"\n📈 Test completati: {successful}/{total}")
    
    if successful == total:
        print("🎉 Tutti i test sono passati con successo!")
        return 0
    else:
        print("⚠️  Alcuni test sono falliti. Controlla i dettagli sopra.")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrotti dall'utente")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("\n❌ Errore di connessione. Assicurati che il server Django sia in esecuzione su http://localhost:8000")
        sys.exit(1) 