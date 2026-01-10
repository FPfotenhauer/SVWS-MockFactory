"""
Modul zum Befüllen des Katalogs 'Einwilligungsarten' im SVWS-Server.
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


def load_einwilligungen_data():
    """Lädt die Einwilligungen aus der JSON-Datei."""
    data_path = Path(__file__).parent / 'katalogdaten' / 'einwilligungen.json'
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data['einwilligungen']


def populate_einwilligungsarten(config):
    """
    Befüllt den Katalog 'Einwilligungsarten' mit Einträgen aus der JSON-Datei.
    
    Args:
        config: Konfigurationsdictionary mit Verbindungsdaten
    """
    db_config = config['database']
    
    server = db_config['server']
    port = db_config['httpsport']
    schema = db_config['schema']
    username = db_config['username']
    password = db_config['password']
    
    url = f"https://{server}:{port}/db/{schema}/schule/einwilligungsarten/new"
    
    # Lade Einwilligungen aus JSON
    try:
        einwilligungen = load_einwilligungen_data()
    except Exception as e:
        print(f"Fehler beim Laden der Einwilligungen-Datei: {e}")
        return 0, 1
    
    print(f"Befülle Katalog 'Einwilligungsarten' mit {len(einwilligungen)} Einträgen...")
    print(f"URL: {url}")
    print(f"Using username: {username}")
    print()
    
    created_count = 0
    failed_count = 0
    
    for i, einwilligung in enumerate(einwilligungen, 1):
        body = {
            "bezeichnung": einwilligung['bezeichnung'],
            "schluessel": einwilligung['schluessel'],
            "beschreibung": einwilligung['beschreibung'],
            "idPersonTyp": einwilligung['idPersonTyp'],
            "sortierung": einwilligung['sortierung'],
            "istSichtbar": einwilligung['istSichtbar']
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
            
            print(f"[{i}/{len(einwilligungen)}] {einwilligung['bezeichnung']}: ", end="")
            
            if response.status_code == 200 or response.status_code == 201:
                print(f"✓ (HTTP {response.status_code})")
                created_count += 1
            else:
                print(f"✗ (HTTP {response.status_code})")
                print(f"  Response: {response.text[:200]}")
                failed_count += 1
                
        except requests.exceptions.RequestException as e:
            print(f"[{i}/{len(einwilligungen)}] {einwilligung['bezeichnung']}: ✗ Fehler: {e}")
            failed_count += 1
    
    print()
    print(f"Ergebnis: {created_count} erfolgreich, {failed_count} fehlgeschlagen")
    
    if failed_count == 0:
        print("✓ Alle Einwilligungsarten erfolgreich erstellt!")
    else:
        print(f"⚠ {failed_count} Einträge konnten nicht erstellt werden.")
    
    return created_count, failed_count


if __name__ == '__main__':
    config = load_config()
    populate_einwilligungsarten(config)
