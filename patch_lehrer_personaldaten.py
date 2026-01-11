"""
Patch existing teacher records with personnel data (Lehrerpersonaldaten).

This script reads teacher data from the cache file (.lehrer_cache.json) created
by populate_lehrer.py and adds Personaldaten via PATCH endpoint.
"""

import json
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings for self-signed certificates
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def load_cache():
    """
    Load teacher data from cache file.
    
    Returns:
        list: List of teacher dictionaries with all required fields
    """
    cache_file = Path(__file__).parent / '.lehrer_cache.json'
    if not cache_file.exists():
        print(f"❌ Cache-Datei nicht gefunden: {cache_file}")
        print("   Bitte zuerst --populate-lehrer ausführen!")
        return []
    
    with open(cache_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def patch_lehrer_personaldaten(config):
    """
    Patch all teachers from cache with Personaldaten.
    
    Args:
        config: Configuration dictionary with database settings
        
    Returns:
        Tuple of (patched_count, failed_count)
    """
    # Load cached teacher data
    print("\nLade Lehrkräfte aus Cache...")
    lehrer_list = load_cache()
    
    if not lehrer_list:
        print("⚠️  Keine Lehrkräfte im Cache gefunden.")
        return 0, 0
    
    total = len(lehrer_list)
    print(f"Gefunden: {total} Lehrkräfte im Cache")
    
    # Database connection
    db = config['database']
    server = db['server']
    port = db['httpsport']
    schema = db['schema']
    username = db['username']
    password = db['password']
    
    url_base = f"https://{server}:{port}/db/{schema}/lehrer"
    auth = HTTPBasicAuth(username, password)
    
    print(f"\nBefülle Personaldaten für {total} Lehrkräfte...")
    print(f"URL: {url_base}/{{id}}/personaldaten\n")
    
    patched = 0
    failed = 0
    
    for idx, lehrer in enumerate(lehrer_list, start=1):
        lehrer_id = lehrer.get('id')
        vorname = lehrer.get('vorname', '')
        nachname = lehrer.get('nachname', '')
        kuerzel = lehrer.get('kuerzel', '')
        
        if not lehrer_id:
            print(f"[{idx}/{total}] {kuerzel} {vorname} {nachname}: ⚠️  Keine ID im Cache")
            failed += 1
            continue
        
        # Prepare payload from cached data
        payload = {
            'identNrTeil1': lehrer.get('identNrTeil1'),
            'identNrTeil2SerNr': lehrer.get('identNrTeil2SerNr'),
            'personalaktennummer': lehrer.get('personalaktennummer'),
            'lbvPersonalnummer': lehrer.get('lbvPersonalnummer'),
            'lbvVerguetungsschluessel': 'A',
            'zugangsdatum': lehrer.get('zugangsdatum'),
            'zugangsgrund': 'NEU',
            'abgangsdatum': None,
            'abgangsgrund': None,
        }
        
        url = f"{url_base}/{lehrer_id}/personaldaten"
        try:
            resp = requests.patch(
                url,
                json=payload,
                auth=auth,
                verify=False,
                timeout=20,
            )
            
            if resp.status_code in (200, 204):
                patched += 1
                print(f"[{idx}/{total}] {kuerzel} {vorname} {nachname}: ✓ (HTTP {resp.status_code})")
            else:
                try:
                    err = resp.json().get('message', resp.text)
                except Exception:
                    err = resp.text
                failed += 1
                print(f"[{idx}/{total}] {kuerzel} {vorname} {nachname}: ❌ HTTP {resp.status_code} - {err[:180]}")
        
        except requests.exceptions.RequestException as exc:
            failed += 1
            print(f"[{idx}/{total}] {kuerzel} {vorname} {nachname}: ❌ Fehler: {exc}")
    
    print(f"\nErgebnis: {patched} erfolgreich, {failed} fehlgeschlagen")
    if failed == 0:
        print("✓ Alle Personaldaten erfolgreich gepacht!")
    else:
        print(f"⚠️  {failed} Personaldaten konnten nicht gepacht werden")
    
    return patched, failed


if __name__ == '__main__':
    from check_server import load_config
    
    cfg = load_config()
    patch_lehrer_personaldaten(cfg)
