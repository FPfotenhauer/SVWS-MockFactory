"""
Populate Floskeln (phrase snippets) from katalogdaten/Floskeln.csv
"""

import requests
import json
import csv
import os
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings for self-signed certificates
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Maps CSV group names to Floskelgruppe kuerzel
GRUPPE_NAME_TO_KUERZEL = {
    'Allgemeine Floskeln': 'ALLG',
    'Floskeln für Arbeits- und Sozialverhalten': 'ASV',
    'Floskeln für außerunterrichtliche Aktivitäten': 'AUE',
    'Fachbezogene Floskeln': 'FACH',
    'Bemerkungen zum Förderschwerpunkt': 'FSP',
    'Bemerkung zum Förderschwerpunkt': 'FSP',
    'Floskeln für Fördermaßnahmen': 'FOERD',
    'Floskeln für Vermerke': 'VERM',
    'Bemerkung zur Versetzung': 'VERS',
    'Floskeln für Zeugnisbemerkungen': 'ZB',
    'Floskeln für Lernentwicklung und Leistungsstand': 'LELS',
    'Floskeln für Übergangsempfehlungen': 'UEG45',
}


def fetch_floskelgruppen_map(server, port, schema, auth) -> dict:
    """Returns {kuerzel: id} for all Floskelgruppen in the DB."""
    url = f"https://{server}:{port}/db/{schema}/schule/floskelgruppen"
    resp = requests.get(url, auth=auth, verify=False, timeout=10)
    resp.raise_for_status()
    return {g['kuerzel']: g['id'] for g in resp.json()}


def load_floskeln_data():
    """Load Floskeln from CSV file"""
    floskeln = []
    csv_path = os.path.join(os.path.dirname(__file__), 'katalogdaten', 'Floskeln.csv')
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                floskeln.append({
                    'gruppe': row['Gruppe'].strip(),
                    'kuerzel': row['Kürzel'].strip(),
                    'fach': row['Fach'].strip(),
                    'jahrgaenge': row['Jahrgänge'].strip(),
                    'text': row['Text'].strip(),
                })
    except FileNotFoundError:
        print(f"❌ Datei nicht gefunden: {csv_path}")
        return None
    except Exception as e:
        print(f"❌ Fehler beim Lesen der Datei: {e}")
        return None
    
    return floskeln


def populate_floskeln(config):
    """Populate Floskeln catalog via REST API"""
    print("\nBefülle Katalog 'Floskeln' aus katalogdaten/Floskeln.csv...")
    
    floskeln_data = load_floskeln_data()
    if not floskeln_data:
        return 0, 1
    
    server = config['database']['server']
    port = config['database']['httpsport']
    schema = config['database']['schema']
    username = config['database']['username']
    password = config['database']['password']
    
    auth = HTTPBasicAuth(username, password)
    url = f"https://{server}:{port}/db/{schema}/schule/floskeln/create"

    print(f"URL: {url}")
    print(f"Using username: {username}\n")

    kuerzel_to_id = fetch_floskelgruppen_map(server, port, schema, auth)
    if not kuerzel_to_id:
        print("❌ Keine Floskelgruppen in der DB gefunden. Bitte zuerst --populate-floskelgruppen ausführen.")
        return 0, 1

    created = 0
    failed = 0

    for idx, floskel in enumerate(floskeln_data, 1):
        gruppe_name = floskel['gruppe']
        kuerzel = GRUPPE_NAME_TO_KUERZEL.get(gruppe_name)
        id_floskelgruppe = kuerzel_to_id.get(kuerzel) if kuerzel else None

        if not id_floskelgruppe:
            print(f"[{idx}/{len(floskeln_data)}] {floskel['kuerzel']}: ❌ Unbekannte Floskelgruppe: {gruppe_name}")
            failed += 1
            continue
        
        # Parse Jahrgänge (comma-separated values, empty array if not specified)
        jahrgaenge = []
        if floskel['jahrgaenge']:
            try:
                jahrgaenge = [int(x.strip()) for x in floskel['jahrgaenge'].split(',')]
            except ValueError:
                jahrgaenge = []
        
        # Create Floskel payload
        payload = {
            'kuerzel': floskel['kuerzel'],
            'text': floskel['text'],
            'idFloskelgruppe': id_floskelgruppe,
            'idFach': None,  # Will be parsed if present
            'niveau': 1,  # Default niveau
            'sortierung': idx,
            'idsJahrgaenge': jahrgaenge,
        }
        
        # Add Fach ID if present
        if floskel['fach']:
            try:
                payload['idFach'] = int(floskel['fach'])
            except ValueError:
                payload['idFach'] = None
        
        try:
            response = requests.post(
                url,
                json=payload,
                auth=auth,
                verify=False,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                display_text = floskel['text'][:40] + ('...' if len(floskel['text']) > 40 else '')
                print(f"[{idx}/{len(floskeln_data)}] {floskel['kuerzel']}: ✓ (HTTP {response.status_code})")
                created += 1
            else:
                try:
                    error_msg = response.json().get('message', response.text)
                except:
                    error_msg = response.text
                
                print(f"[{idx}/{len(floskeln_data)}] {floskel['kuerzel']}: ❌ HTTP {response.status_code} - {error_msg}")
                failed += 1
        
        except requests.exceptions.RequestException as e:
            print(f"[{idx}/{len(floskeln_data)}] {floskel['kuerzel']}: ❌ Fehler: {str(e)}")
            failed += 1
    
    print(f"\nErgebnis: {created} erfolgreich, {failed} fehlgeschlagen")
    
    if failed == 0:
        print("✓ Alle Floskeln erfolgreich erstellt!")
    else:
        print(f"⚠️  {failed} Floskeln konnten nicht erstellt werden")
    
    return created, failed
