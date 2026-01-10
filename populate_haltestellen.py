"""
Populate Haltestellen (bus stops) from katalogdaten/haltestellen.txt
"""

import requests
import os
import random
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings for self-signed certificates
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def load_haltestellen_data():
    """Load Haltestellen from text file"""
    haltestellen = []
    txt_path = os.path.join(os.path.dirname(__file__), 'katalogdaten', 'haltestellen.txt')
    
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:  # Skip empty lines
                    haltestellen.append(line)
    except FileNotFoundError:
        print(f"❌ Datei nicht gefunden: {txt_path}")
        return None
    except Exception as e:
        print(f"❌ Fehler beim Lesen der Datei: {e}")
        return None
    
    return haltestellen


def populate_haltestellen(config):
    """Populate Haltestellen catalog via REST API"""
    print("\nBefülle Katalog 'Haltestellen' aus katalogdaten/haltestellen.txt...")
    
    haltestellen_data = load_haltestellen_data()
    if not haltestellen_data:
        return 0, 1
    
    server = config['database']['server']
    port = config['database']['httpsport']
    schema = config['database']['schema']
    username = config['database']['username']
    password = config['database']['password']
    
    url = f"https://{server}:{port}/db/{schema}/haltestellen/create"
    
    print(f"URL: {url}")
    print(f"Using username: {username}\n")
    
    created = 0
    failed = 0
    
    for idx, bezeichnung in enumerate(haltestellen_data, 1):
        # Create Haltestelle payload
        payload = {
            'bezeichnung': bezeichnung,
            'entfernungSchule': random.randint(1, 10),  # Random distance 1-10
            'sortierung': idx,
            'istSichtbar': True,
        }
        
        try:
            response = requests.post(
                url,
                json=payload,
                auth=HTTPBasicAuth(username, password),
                verify=False,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                print(f"[{idx}/{len(haltestellen_data)}] {bezeichnung}: ✓ (HTTP {response.status_code})")
                created += 1
            else:
                try:
                    error_msg = response.json().get('message', response.text)
                except:
                    error_msg = response.text
                
                print(f"[{idx}/{len(haltestellen_data)}] {bezeichnung}: ❌ HTTP {response.status_code} - {error_msg}")
                failed += 1
        
        except requests.exceptions.RequestException as e:
            print(f"[{idx}/{len(haltestellen_data)}] {bezeichnung}: ❌ Fehler: {str(e)}")
            failed += 1
    
    print(f"\nErgebnis: {created} erfolgreich, {failed} fehlgeschlagen")
    
    if failed == 0:
        print("✓ Alle Haltestellen erfolgreich erstellt!")
    else:
        print(f"⚠️  {failed} Haltestellen konnten nicht erstellt werden")
    
    return created, failed
