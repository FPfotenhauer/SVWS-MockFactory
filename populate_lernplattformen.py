"""
Populate Lernplattformen (learning platforms) from katalogdaten/lernplattformen.txt
"""

import requests
import os
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings for self-signed certificates
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def load_lernplattformen_data():
    """Load Lernplattformen from text file"""
    entries = []
    txt_path = os.path.join(os.path.dirname(__file__), 'katalogdaten', 'lernplattformen.txt')
    
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:  # Skip empty lines
                    entries.append(line)
    except FileNotFoundError:
        print(f"❌ Datei nicht gefunden: {txt_path}")
        return None
    except Exception as e:
        print(f"❌ Fehler beim Lesen der Datei: {e}")
        return None
    
    return entries


def populate_lernplattformen(config):
    """Populate Lernplattformen catalog via REST API"""
    print("\nBefülle Katalog 'Lernplattformen' aus katalogdaten/lernplattformen.txt...")
    
    data = load_lernplattformen_data()
    if not data:
        return 0, 1
    
    server = config['database']['server']
    port = config['database']['httpsport']
    schema = config['database']['schema']
    username = config['database']['username']
    password = config['database']['password']
    
    url = f"https://{server}:{port}/db/{schema}/schule/lernplattformen/create"
    
    print(f"URL: {url}")
    print(f"Using username: {username}\n")
    
    created = 0
    failed = 0
    
    total = len(data)
    for idx, bezeichnung in enumerate(data, 1):
        payload = {
            'bezeichnung': bezeichnung
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
                print(f"[{idx}/{total}] {bezeichnung}: ✓ (HTTP {response.status_code})")
                created += 1
            else:
                try:
                    error_msg = response.json().get('message', response.text)
                except Exception:
                    error_msg = response.text
                print(f"[{idx}/{total}] {bezeichnung}: ❌ HTTP {response.status_code} - {error_msg}")
                failed += 1
        except requests.exceptions.RequestException as e:
            print(f"[{idx}/{total}] {bezeichnung}: ❌ Fehler: {str(e)}")
            failed += 1
    
    print(f"\nErgebnis: {created} erfolgreich, {failed} fehlgeschlagen")
    
    if failed == 0:
        print("✓ Alle Lernplattformen erfolgreich erstellt!")
    else:
        print(f"⚠️  {failed} Lernplattformen konnten nicht erstellt werden")
    
    return created, failed
