"""
Assign one random Betrieb (company) to each existing student.

Reads student IDs from .schueler_cache.json (created by populate_schueler.py),
loads available Betriebe via GET /db/{schema}/betriebe,
and creates one assignment per student via:
POST /db/{schema}/betriebe/schuelerbetrieb/new/schueler/{idSchueler}/betrieb/{idBetrieb}
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

import requests
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

RAND = random.Random()


def load_cache() -> List[dict]:
    cache_file = Path(__file__).parent / '.schueler_cache.json'
    if not cache_file.exists():
        print(f"❌ Cache-Datei nicht gefunden: {cache_file}")
        print('   Bitte zuerst --populate-schueler ausführen!')
        return []

    with open(cache_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_id(entry: dict) -> Optional[int]:
    value = entry.get('id')
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def fetch_betriebe(config, auth: HTTPBasicAuth) -> List[int]:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/betriebe"
    resp = requests.get(url, auth=auth, verify=False, timeout=20)
    resp.raise_for_status()

    data = resp.json()
    ids: List[int] = []
    for item in data:
        betriebs_id = extract_id(item)
        if betriebs_id is not None:
            ids.append(betriebs_id)

    unique_ids: List[int] = []
    seen = set()
    for item_id in ids:
        if item_id in seen:
            continue
        seen.add(item_id)
        unique_ids.append(item_id)

    return unique_ids


def build_payload(schueler_id: int, betrieb_id: int) -> dict:
    vertragsbeginn = date.today()
    vertragsende = vertragsbeginn + timedelta(days=1)

    return {
        'id': 0,
        'schueler_id': schueler_id,
        'betrieb_id': betrieb_id,
        'beschaeftigungsart_id': 1,
        'vertragsbeginn': vertragsbeginn.isoformat(),
        'vertragsende': vertragsende.isoformat(),
        'ausbilder': None,
        'allgadranschreiben': False,
        'praktikum': False,
        'sortierung': None,
        'ansprechpartner_id': None,
        'betreuungslehrer_id': None,
    }


def patch_schueler_company(config):
    print('\nLade Schüler aus Cache...')
    schueler_list = load_cache()
    if not schueler_list:
        print('⚠️  Keine Schüler im Cache gefunden.')
        return 0, 0, 0

    db = config['database']
    auth = HTTPBasicAuth(db['username'], db['password'])

    print('Lade Betriebe...')
    try:
        betriebe_ids = fetch_betriebe(config, auth)
    except requests.exceptions.RequestException as exc:
        print(f"❌ Betriebe konnten nicht geladen werden: {exc}")
        return 0, 0, len(schueler_list)

    if not betriebe_ids:
        print('❌ Keine Betrieb-IDs gefunden.')
        return 0, 0, len(schueler_list)

    total = len(schueler_list)
    created = 0
    skipped = 0
    failed = 0

    print(f'Gefunden: {total} Schüler im Cache')
    print(f'Verfügbare Betriebe: {len(betriebe_ids)}')

    for idx, schueler in enumerate(schueler_list, start=1):
        schueler_id = extract_id(schueler)
        vorname = schueler.get('vorname', '')
        nachname = schueler.get('nachname', '')

        if schueler_id is None:
            failed += 1
            print(f"[{idx}/{total}] {vorname} {nachname}: ⚠️  Keine ID im Cache")
            continue

        betrieb_id = RAND.choice(betriebe_ids)
        payload = build_payload(schueler_id, betrieb_id)
        url = (
            f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}"
            f"/betriebe/schuelerbetrieb/new/schueler/{schueler_id}/betrieb/{betrieb_id}"
        )

        try:
            resp = requests.post(url, json=payload, auth=auth, verify=False, timeout=20)
            if resp.status_code in (200, 201):
                created += 1
                print(f"[{idx}/{total}] {vorname} {nachname}: ✓ Betrieb {betrieb_id} zugeordnet")
            elif resp.status_code == 409:
                skipped += 1
                print(f"[{idx}/{total}] {vorname} {nachname}: ↷ bereits zugeordnet")
            else:
                failed += 1
                print(
                    f"[{idx}/{total}] {vorname} {nachname}: ✗ {resp.status_code} "
                    f"{resp.text[:180]}"
                )
        except requests.exceptions.RequestException as exc:
            failed += 1
            print(f"[{idx}/{total}] {vorname} {nachname}: ✗ Request-Fehler: {exc}")

    print(f"\nErgebnis: {created} erstellt, {skipped} übersprungen, {failed} fehlgeschlagen")
    if failed == 0:
        print('✓ Schüler-Betrieb-Zuordnung abgeschlossen!')
    else:
        print(f"⚠️  {failed} Zuordnungen konnten nicht erstellt werden")

    return created, skipped, failed


if __name__ == '__main__':
    from check_server import load_config

    cfg = load_config()
    patch_schueler_company(cfg)
