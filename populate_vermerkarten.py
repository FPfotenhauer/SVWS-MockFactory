"""
Populate Vermerkarten catalog from katalogdaten/vermerkarten.txt
"""

import os
import requests
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings for self-signed certificates
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def load_vermerkarten_data():
    """Load Vermerkarten from text file."""
    data = []
    txt_path = os.path.join(os.path.dirname(__file__), 'katalogdaten', 'vermerkarten.txt')

    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            for line in f:
                entry = line.strip()
                if entry:
                    data.append(entry)
    except FileNotFoundError:
        print(f"❌ Datei nicht gefunden: {txt_path}")
        return None
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"❌ Fehler beim Lesen der Datei: {exc}")
        return None

    return data


def populate_vermerkarten(config):
    """Populate Vermerkarten catalog via REST API."""
    print("\nBefülle Katalog 'Vermerkarten' aus katalogdaten/vermerkarten.txt...")

    vermerkarten = load_vermerkarten_data()
    if not vermerkarten:
        return 0, 1

    server = config['database']['server']
    port = config['database']['httpsport']
    schema = config['database']['schema']
    username = config['database']['username']
    password = config['database']['password']

    url = f"https://{server}:{port}/db/{schema}/schule/vermerkarten/new"

    print(f"URL: {url}")
    print(f"Using username: {username}\n")

    created = 0
    failed = 0

    for idx, bezeichnung in enumerate(vermerkarten, 1):
        payload = {
            'bezeichnung': bezeichnung,
            'sortierung': idx,
            'istSichtbar': True,
        }

        try:
            response = requests.post(
                url,
                json=payload,
                auth=HTTPBasicAuth(username, password),
                verify=False,
                timeout=10,
            )

            if response.status_code in [200, 201]:
                print(f"[{idx}/{len(vermerkarten)}] {bezeichnung}: ✓ (HTTP {response.status_code})")
                created += 1
            else:
                try:
                    error_msg = response.json().get('message', response.text)
                except Exception:
                    error_msg = response.text

                print(f"[{idx}/{len(vermerkarten)}] {bezeichnung}: ❌ HTTP {response.status_code} - {error_msg}")
                failed += 1

        except requests.exceptions.RequestException as exc:  # pragma: no cover - network failure
            print(f"[{idx}/{len(vermerkarten)}] {bezeichnung}: ❌ Fehler: {str(exc)}")
            failed += 1

    print(f"\nErgebnis: {created} erfolgreich, {failed} fehlgeschlagen")

    if failed == 0:
        print("✓ Alle Vermerkarten erfolgreich erstellt!")
    else:
        print(f"⚠️  {failed} Vermerkarten konnten nicht erstellt werden")

    return created, failed


if __name__ == '__main__':
    from check_server import load_config

    CONFIG = load_config()
    populate_vermerkarten(CONFIG)
