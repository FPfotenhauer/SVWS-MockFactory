"""
Modul zum Befüllen des Katalogs 'Foerderschwerpunkte' im SVWS-Server.
Basierend auf der Schulform aus den Stammdaten.
"""

import requests
import json
import urllib3
from pathlib import Path
from datetime import datetime

# SSL-Warnungen deaktivieren (für selbstsignierte Zertifikate)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def load_config(config_file='config.json'):
    """Lädt die Konfiguration aus der JSON-Datei."""
    config_path = Path(__file__).parent / config_file
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_school_data(config):
    """
    Ruft die Schuldaten vom Server ab, um die Schulform zu ermitteln.
    
    Args:
        config: Konfigurationsdictionary mit Verbindungsdaten
        
    Returns:
        dict: Schuldaten mit Schulform (schulform), oder None bei Fehler
    """
    db_config = config['database']
    server = db_config['server']
    port = db_config['httpsport']
    schema = db_config['schema']
    username = db_config['username']
    password = db_config['password']
    
    url = f"https://{server}:{port}/db/{schema}/schule/stammdaten"
    
    try:
        response = requests.get(
            url,
            auth=(username, password),
            headers={
                'Accept': 'application/json'
            },
            verify=False,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Fehler beim Abrufen der Schuldaten: HTTP {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Fehler beim Abrufen der Schuldaten: {e}")
        return None


def load_foerderschwerpunkt_data():
    """Lädt die Foerderschwerpunkte aus der JSON-Datei."""
    data_path = Path(__file__).parent / 'statistikdaten' / 'Foerderschwerpunkt.json'
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data['daten']


def get_current_year():
    """Gibt das aktuelle Jahr zurück."""
    return datetime.now().year


def filter_foerderschwerpunkte_for_schulform(foerderschwerpunkte_data, schulform):
    """
    Filtert die Foerderschwerpunkte für eine bestimmte Schulform.
    Verwendet die aktuellste gültige Version basierend auf dem aktuellen Jahr.
    
    Args:
        foerderschwerpunkte_data: Die Daten aus Foerderschwerpunkt.json
        schulform: Die Schulform (z.B. "GE")
        
    Returns:
        list: Liste der gültigen Foerderschwerpunkte
    """
    current_year = get_current_year()
    result = []
    
    for fs_group in foerderschwerpunkte_data:
        # Finde die aktuellste gültige Version
        best_entry = None
        for entry in fs_group['historie']:
            # Prüfe ob Schulform in dieser Variante unterstützt wird
            if schulform not in entry['schulformen']:
                continue
            
            # Prüfe ob diese Variante für das aktuelle Jahr gültig ist
            gueltig_von = entry.get('gueltigVon')
            gueltig_bis = entry.get('gueltigBis')
            
            is_valid = True
            if gueltig_von is not None and current_year < gueltig_von:
                is_valid = False
            if gueltig_bis is not None and current_year > gueltig_bis:
                is_valid = False
            
            if is_valid:
                # Wähle die neueste Variante (höchste gueltigVon)
                if best_entry is None or (entry.get('gueltigVon') or 0) > (best_entry.get('gueltigVon') or 0):
                    best_entry = entry
        
        if best_entry:
            result.append({
                'kuerzel': best_entry['kuerzel'],
                'kuerzelStatistik': best_entry['schluessel'],
                'sortierung': len(result) + 1
            })
    
    return result


def populate_foerderschwerpunkte(config):
    """
    Befüllt den Katalog 'Foerderschwerpunkte' basierend auf der Schulform.
    
    Args:
        config: Konfigurationsdictionary mit Verbindungsdaten
    """
    db_config = config['database']
    
    server = db_config['server']
    port = db_config['httpsport']
    schema = db_config['schema']
    username = db_config['username']
    password = db_config['password']
    
    # Abrufen der Schuldaten
    print("Rufe Schuldaten ab...")
    school_data = get_school_data(config)
    
    if not school_data:
        print("Fehler: Schuldaten konnten nicht abgerufen werden.")
        return 0, 1
    
    schulform = school_data.get('schulform')
    print(f"Schulform: {schulform}")
    print()
    
    # Laden der Foerderschwerpunkt-Daten
    try:
        foerderschwerpunkte_data = load_foerderschwerpunkt_data()
    except Exception as e:
        print(f"Fehler beim Laden der Foerderschwerpunkt-Datei: {e}")
        return 0, 1
    
    # Filtern für diese Schulform
    foerderschwerpunkte = filter_foerderschwerpunkte_for_schulform(foerderschwerpunkte_data, schulform)
    
    url = f"https://{server}:{port}/db/{schema}/foerderschwerpunkte/create"
    
    print(f"Befülle Katalog 'Foerderschwerpunkte' mit {len(foerderschwerpunkte)} Einträgen...")
    print(f"URL: {url}")
    print(f"Using username: {username}")
    print()
    
    created_count = 0
    failed_count = 0
    
    for i, fs in enumerate(foerderschwerpunkte, 1):
        body = {
            "kuerzel": fs['kuerzel'],
            "kuerzelStatistik": fs['kuerzelStatistik'],
            "istSichtbar": True,
            "sortierung": fs['sortierung']
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
            
            print(f"[{i}/{len(foerderschwerpunkte)}] {fs['kuerzel']} ({fs['kuerzelStatistik']}): ", end="")
            
            if response.status_code == 200 or response.status_code == 201:
                print(f"✓ (HTTP {response.status_code})")
                created_count += 1
            else:
                print(f"✗ (HTTP {response.status_code})")
                print(f"  Response: {response.text[:200]}")
                failed_count += 1
                
        except requests.exceptions.RequestException as e:
            print(f"[{i}/{len(foerderschwerpunkte)}] {fs['kuerzel']}: ✗ Fehler: {e}")
            failed_count += 1
    
    print()
    print(f"Ergebnis: {created_count} erfolgreich, {failed_count} fehlgeschlagen")
    
    if failed_count == 0:
        print("✓ Alle Foerderschwerpunkte erfolgreich erstellt!")
    else:
        print(f"⚠ {failed_count} Einträge konnten nicht erstellt werden.")
    
    return created_count, failed_count


if __name__ == '__main__':
    config = load_config()
    populate_foerderschwerpunkte(config)
