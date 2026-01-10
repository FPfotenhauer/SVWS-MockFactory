#!/usr/bin/env python3
"""
School data initialization module for SVWS Mock Factory
Patches school stammdaten with test values after database initialization
"""

import requests
import urllib3
from requests.auth import HTTPBasicAuth


# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def patch_schulstammdaten(config):
    """
    Aktualisiert die Schulstammdaten mit vorgegebenen Testwerten.
    
    Args:
        config: Konfiguration mit Server- und Auth-Daten
    
    Returns:
        bool: True bei erfolgreicher Aktualisierung, sonst False
    """
    db = config['database']
    server = db['server']
    port = db['httpsport']
    schema = db['schema']
    username = db['username']
    password = db['password']

    url = f"https://{server}:{port}/db/{schema}/schule/stammdaten"

    try:
        print("\nPatching Schulstammdaten...")

        # Testwerte für PATCH-Request
        patch_data = {
            "bezeichnung1": "Testschule aus gernerierten Daten",
            "bezeichnung2": "MockFactory Schule",
            "bezeichnung3": "Generierte Daten",
            "strassenname": "Hauptstraße",
            "hausnummer": "76",
            "hausnummerZusatz": "",
            "plz": "42287",
            "ort": "Wuppertal",
            "telefon": "012345-6876876",
            "fax": "012345-766766",
            "email": "mockschule@schule.example.com",
            "webAdresse": "https://meineschule.de",
        }

        # PATCH-Request senden (nur die zu ändernden Felder)
        patch_resp = requests.patch(
            url,
            auth=HTTPBasicAuth(username, password),
            headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
            json=patch_data,
            verify=False,
            timeout=30,
        )

        if patch_resp.status_code in [200, 204]:
            print("✓ Schulstammdaten erfolgreich aktualisiert!")
            return True

        print(f"⚠ Aktualisierung fehlgeschlagen: HTTP {patch_resp.status_code}")
        if patch_resp.text:
            print(f"Antwort: {patch_resp.text}")
        return False

    except requests.exceptions.RequestException as e:
        print(f"⚠ Fehler bei der Aktualisierung der Schulstammdaten: {e}")
        return False


def main():
    """Main entry point for testing"""
    from check_server import load_config
    
    print("SVWS Mock Factory - School Data Patch")
    print("=" * 50)
    
    try:
        config = load_config()
        success = patch_schulstammdaten(config)
        
        if success:
            print("\nSchool data patch completed successfully.")
            return 0
        else:
            print("\nSchool data patch failed.")
            return 1
            
    except FileNotFoundError:
        print("Error: config.json not found!")
        return 1
    except KeyError as e:
        print(f"Error: Missing configuration key: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
