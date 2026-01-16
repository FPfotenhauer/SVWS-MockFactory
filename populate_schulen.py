"""
Populate Schulen (Schools) catalog from JSON file.

This module provides functionality to populate the Schulen catalog in SVWS
from the katalogdaten/schulen.json file.
"""

import csv
import json
import requests
from pathlib import Path
from typing import Tuple, Optional
import urllib3

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Mapping from SchulformKrz to idSchulform (based on SVWS database from Schulform.json)
SCHULFORM_MAPPING = {
    'BK': 1000,  # Berufskolleg
    'GG': 3000,  # Grundschule
    'GE': 4000,  # Gesamtschule
    'GY': 6000,  # Gymnasium
    'GH': 7000,  # Hauptschule (assuming GH = Gymnasium-Hauptschule or similar)
    'RS': 10000, # Realschule
    'FÖ': 11000, # Förderschule (S)
    'SK': 15000, # Sekundarschule
    'V': 17000,  # Volksschule
    'PS': 9000,  # Schulversuch PRIMUS
    'FW': 2000,  # Freie Waldorfschule
    'EG': 3000,  # Evangelische Grundschule (same as Grundschule)
    'KG': 3000,  # Katholische Grundschule (same as Grundschule)
    # Add more as needed
}


def load_schulen_data(config: Optional[dict] = None) -> list:
    """
    Load school data. If `config['database']['test']` is True, load
    `katalogdaten/SchulenTest.csv`; otherwise load `katalogdaten/Schulen.csv`.
    If no config provided or CSV is missing, fall back to
    `katalogdaten/schulen.json`.
    """
    cfg_test = False
    if config:
        try:
            cfg_test = bool(config.get('database', {}).get('test'))
        except Exception:
            cfg_test = False

    base = Path(__file__).parent / 'katalogdaten'
    csv_name = 'SchulenTest.csv' if cfg_test else 'Schulen.csv'
    csv_path = base / csv_name

    if csv_path.exists():
        schulen = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Map CSV columns to expected JSON keys
                def norm(v):
                    return v.strip() if isinstance(v, str) else v

                kurz = norm(row.get('KurzBez') or row.get('Kurzbezeichnung') or '')
                schulnr = norm(row.get('SchulNr') or row.get('Schulnummer') or '')
                name = norm(row.get('Name') or '')
                strassen = norm(row.get('Strassenname') or '')
                hausnr = norm(row.get('HausNr') or '')
                zusatz = norm(row.get('HausNrZusatz') or '')
                plz = norm(row.get('PLZ') or '')
                ort = norm(row.get('Ort') or '')
                telefon = norm(row.get('Telefon') or '')
                fax = norm(row.get('Fax') or '')
                email = norm(row.get('Email') or '')
                schulleiter = norm(row.get('Schulleiter') or '')
                kuerzel = norm(row.get('Kuerzel') or '')
                sortierung = row.get('Sortierung')
                try:
                    sortierung = int(sortierung) if sortierung not in (None, '') else 32000
                except Exception:
                    sortierung = 32000
                sichtbar = norm(row.get('Sichtbar') or '')
                istSichtbar = True if sichtbar == '+' else False
                schulform_krz = norm(row.get('SchulformKrz') or '')
                idSchulform = SCHULFORM_MAPPING.get(schulform_krz)

                entry = {
                    'kuerzel': kuerzel or None,
                    'kurzbezeichnung': kurz or None,
                    'schulnummerStatistik': schulnr or None,
                    'name': name or None,
                    'idSchulform': idSchulform,
                    'strassenname': strassen or None,
                    'hausnummer': hausnr or None,
                    'zusatzHausnummer': zusatz or None,
                    'plz': plz or None,
                    'ort': ort or None,
                    'telefon': telefon or None,
                    'fax': fax or None,
                    'email': email or None,
                    'schulleiter': schulleiter or None,
                    'sortierung': sortierung,
                    'istSichtbar': istSichtbar,
                }
                schulen.append(entry)
        # Also write out a schulen.json so other tools can use the generated data
        try:
            json_path = base / 'schulen.json'
            with open(json_path, 'w', encoding='utf-8') as jf:
                json.dump(schulen, jf, ensure_ascii=False, indent=2)
            print(f"Wrote {json_path} ({len(schulen)} Einträge)")
        except Exception:
            pass

        return schulen

    # Fallback to JSON file
    json_path = base / 'schulen.json'
    if json_path.exists():
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    # Nothing found
    return []


def populate_schulen(config: dict) -> Tuple[int, int]:
    """
    Populate the Schulen catalog via the SVWS API.
    
    Skips schools that already exist (checks by schulnummerStatistik).
    
    Args:
        config: Configuration dictionary with database settings
        
    Returns:
        Tuple of (created_count, failed_count)
    """
    server = config['database']['server']
    port = config['database']['httpsport']
    schema = config['database']['schema']
    username = config['database']['username']
    password = config['database']['password']
    
    # Load school data (may use CSV depending on config)
    schulen = load_schulen_data(config)
    total = len(schulen)

    print(f"\nBefülle Katalog 'Schulen' ({total} Einträge)...")
    
    # API endpoint
    url = f"https://{server}:{port}/db/{schema}/schule/schulen/create"
    print(f"URL: {url}")
    print(f"Using username: {username}\n")
    
    created_count = 0
    failed_count = 0
    skipped_count = 0
    
    # Create each school entry
    for idx, schule in enumerate(schulen, start=1):
        kurzbezeichnung = schule.get('kurzbezeichnung', 'Unbekannt')
        schulnummer = schule.get('schulnummerStatistik', 'Unbekannt')
        
        try:
            response = requests.post(
                url,
                json=schule,
                auth=(username, password),
                verify=False,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                print(f"[{idx}/{total}] {kurzbezeichnung}: ✓ (HTTP {response.status_code})")
                created_count += 1
            elif response.status_code == 409 or 'bereits' in response.text or 'exists' in response.text:
                # School already exists - skip it
                print(f"[{idx}/{total}] {kurzbezeichnung}: ⊘ (Existiert bereits)")
                skipped_count += 1
            else:
                print(f"[{idx}/{total}] {kurzbezeichnung}: ✗ (HTTP {response.status_code})")
                print(f"    Response: {response.text[:200]}")
                failed_count += 1
                
        except requests.exceptions.RequestException as e:
            print(f"[{idx}/{total}] {kurzbezeichnung}: ✗ (Error: {str(e)[:100]})")
            failed_count += 1
    
    # Summary
    print(f"\nErgebnis: {created_count} erfolgreich, {skipped_count} übersprungen, {failed_count} fehlgeschlagen")
    
    if failed_count == 0:
        if skipped_count > 0:
            print(f"✓ {created_count} neue Schulen erstellt, {skipped_count} existierten bereits!")
        else:
            print("✓ Alle Schulen erfolgreich erstellt!")
    else:
        print(f"⚠ {failed_count} Schulen konnten nicht erstellt werden")
    
    return created_count, failed_count


if __name__ == "__main__":
    from check_server import load_config

    cfg = load_config()
    created, failed = populate_schulen(cfg)
    print(f"\n✓ Created {created} Schulen entries")
    if failed > 0:
        print(f"✗ Failed to create {failed} entries")
