"""
Populate Schulen (Schools) catalog from JSON file.

This module provides functionality to populate the Schulen catalog in SVWS
from the katalogdaten/schulen.json file.
"""

import json
import requests
from typing import Tuple
import urllib3

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def load_schulen_data() -> list:
    """
    Load school data from the JSON file.
    
    Returns:
        list: List of school dictionaries with all required fields
    """
    with open('katalogdaten/schulen.json', 'r', encoding='utf-8') as f:
        schulen = json.load(f)
    return schulen


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
    
    # Load school data
    schulen = load_schulen_data()
    total = len(schulen)
    
    print(f"\nBefülle Katalog 'Schulen' aus katalogdaten/schulen.json...")
    
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
    # Test configuration
    test_config = {
        'server': 'https://localhost:8443/api',
        'schema': 'mockingbird',
        'username': 'Admin',
        'password': 'Admin'
    }
    
    created, failed = populate_schulen(test_config)
    print(f"\n✓ Created {created} Schulen entries")
    if failed > 0:
        print(f"✗ Failed to create {failed} entries")
