#!/usr/bin/env python3
"""
Populate Floskelgruppen catalog from Floskelgruppenart.json
"""

import json
import requests
from check_server import load_config


def load_floskelgruppen_data():
    """Load Floskelgruppen data from JSON file"""
    try:
        with open('katalogdaten/Floskelgruppenart.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('daten', [])
    except Exception as e:
        print(f"Error loading Floskelgruppenart.json: {e}")
        return []


def get_color_for_index(index):
    """Generate a color for the Floskelgruppe based on index"""
    # Define a palette of colors for different phrase groups
    colors = [
        {"red": 220, "green": 220, "blue": 220},  # Light gray
        {"red": 173, "green": 216, "blue": 230},  # Light blue
        {"red": 144, "green": 238, "blue": 144},  # Light green
        {"red": 255, "green": 218, "blue": 185},  # Peach puff
        {"red": 230, "green": 230, "blue": 250},  # Lavender
        {"red": 255, "green": 228, "blue": 181},  # Moccasin
        {"red": 200, "green": 221, "blue": 242},  # Light blue (darker)
        {"red": 220, "green": 240, "blue": 220},  # Honeydew
        {"red": 240, "green": 230, "blue": 200},  # Wheat
        {"red": 230, "green": 220, "blue": 240},  # Thistle
        {"red": 255, "green": 240, "blue": 245},  # Lavender blush
    ]
    return colors[index % len(colors)]


def populate_floskelgruppen(config):
    """Populate Floskelgruppen catalog"""
    floskelgruppen_data = load_floskelgruppen_data()
    
    if not floskelgruppen_data:
        print("Error: No Floskelgruppen data found")
        return 0, 1
    
    schema = config.get('schema', 'mockingbird')
    username = config.get('username', 'Admin')
    password = config.get('password', '')
    server = config.get('server', 'localhost')
    https_port = config.get('httpsport', 8443)
    
    base_url = f"https://{server}:{https_port}"
    auth = (username, password)
    
    print(f"\nBefülle Katalog 'Floskelgruppen' mit {len(floskelgruppen_data)} Einträgen...")
    url = f"{base_url}/db/{schema}/schule/floskelgruppen/create"
    print(f"URL: {url}")
    print(f"Using username: {username}\n")
    
    created = 0
    failed = 0
    
    for index, gruppe in enumerate(floskelgruppen_data):
        # Get the latest history entry (most recent version)
        historie = gruppe.get('historie', [])
        if not historie:
            print(f"Warning: No history entry for {gruppe.get('bezeichner')}")
            failed += 1
            continue
        
        latest = historie[-1]  # Get the most recent history entry
        
        # Truncate long descriptions to 50 character limit
        text = latest.get('text', '')
        if len(text) > 50:
            text = text[:47] + "..."
        
        payload = {
            "kuerzel": latest.get('kuerzel', gruppe.get('bezeichner')),
            "bezeichnung": text,
            "idFloskelgruppenart": latest.get('id', index),
            "farbe": get_color_for_index(index)
        }
        
        try:
            response = requests.post(
                url,
                json=payload,
                auth=auth,
                verify=False
            )
            
            if response.status_code in [200, 201]:
                print(f"[{index + 1}/{len(floskelgruppen_data)}] {payload['kuerzel']} ({payload['bezeichnung'][:30]}): ✓ (HTTP {response.status_code})")
                created += 1
            else:
                print(f"[{index + 1}/{len(floskelgruppen_data)}] {payload['kuerzel']}: ✗ (HTTP {response.status_code})")
                print(f"  Response: {response.text[:100]}")
                failed += 1
        except Exception as e:
            print(f"[{index + 1}/{len(floskelgruppen_data)}] {payload['kuerzel']}: ✗ (Error: {str(e)[:50]})")
            failed += 1
    
    print(f"\nErgebnis: {created} erfolgreich, {failed} fehlgeschlagen")
    if failed == 0:
        print(f"✓ Alle Floskelgruppen erfolgreich erstellt!")
    
    return created, failed


if __name__ == "__main__":
    config = load_config()
    created, failed = populate_floskelgruppen(config)
    exit(0 if failed == 0 else 1)
