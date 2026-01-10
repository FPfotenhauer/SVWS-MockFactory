"""
Modul zum Befüllen des Katalogs 'Fahrschülerarten' im SVWS-Server.
"""

import requests
import json
import urllib3
from pathlib import Path

# SSL-Warnungen deaktivieren (für selbstsignierte Zertifikate)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def load_config(config_file='config.json'):
    """Lädt die Konfiguration aus der JSON-Datei."""
    config_path = Path(__file__).parent / config_file
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def populate_fahrschuelerarten(config, count=15):
    """
    Befüllt den Katalog 'Fahrschülerarten' mit Einträgen.
    
    Args:
        config: Konfigurationsdictionary mit Verbindungsdaten
        count: Anzahl der zu erstellenden Einträge (Standard: 15)
    """
    db_config = config['database']
    
    server = db_config['server']
    port = db_config['httpsport']
    schema = db_config['schema']
    username = db_config['username']
    password = db_config['password']
    
    url = f"https://{server}:{port}/db/{schema}/schueler/fahrschuelerarten/create"
    
    print(f"Befülle Katalog 'Fahrschülerarten' mit {count} Einträgen...")
    print(f"URL: {url}")
    print(f"Using username: {username}")
    print()
    
    created_count = 0
    failed_count = 0
    
    for i in range(1, count + 1):
        body = {
            "bezeichnung": f"Busunternehmen {i}",
            "istSichtbar": True,
            "istAenderbar": True,
            "sortierung": i
        }
        
        try:
            response = requests.post(
                url,
                auth=(username, password),
                json=body,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                verify=False,
                timeout=30
            )
            
            print(f"[{i}/{count}] Busunternehmen {i}: ", end="")
            
            if response.status_code == 200 or response.status_code == 201:
                print(f"✓ (HTTP {response.status_code})")
                created_count += 1
            else:
                print(f"✗ (HTTP {response.status_code})")
                print(f"  Response: {response.text[:200]}")
                failed_count += 1
                
        except requests.exceptions.RequestException as e:
            print(f"[{i}/{count}] Busunternehmen {i}: ✗ Fehler: {e}")
            failed_count += 1
    
    print()
    print(f"Ergebnis: {created_count} erfolgreich, {failed_count} fehlgeschlagen")
    
    if failed_count == 0:
        print("✓ Alle Fahrschülerarten erfolgreich erstellt!")
    else:
        print(f"⚠ {failed_count} Einträge konnten nicht erstellt werden.")
    
    return created_count, failed_count


if __name__ == '__main__':
    config = load_config()
    populate_fahrschuelerarten(config)
