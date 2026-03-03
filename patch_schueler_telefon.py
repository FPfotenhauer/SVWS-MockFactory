"""
Create two phone entries for each existing student record.

Reads student IDs from .schueler_cache.json (created by populate_schueler.py),
loads available phone type IDs via /db/{schema}/schule/telefonarten,
and creates entries via POST /db/{schema}/schueler/{id}/telefon.
"""

import json
import random
from pathlib import Path
from typing import List, Optional

import requests
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

RAND = random.Random()
BEMERKUNGEN = [
    'Ist noch aktiv',
    'Nur tagsüber erreichbar',
    'Rückruf am Nachmittag',
    'Bei Notfällen bevorzugen',
    'Kontakt über Erziehungsberechtigte',
]


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


def fetch_telefonarten_ids(config) -> List[int]:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/schule/telefonarten"

    resp = requests.get(
        url,
        auth=HTTPBasicAuth(db['username'], db['password']),
        verify=False,
        timeout=20,
    )
    resp.raise_for_status()

    data = resp.json()
    ids: List[int] = []
    for item in data:
        item_id = extract_id(item)
        if item_id is not None:
            ids.append(item_id)

    unique_ids: List[int] = []
    seen = set()
    for item_id in ids:
        if item_id in seen:
            continue
        seen.add(item_id)
        unique_ids.append(item_id)

    return unique_ids


def random_phone() -> str:
    area = RAND.randint(1000, 99999)
    number = RAND.randint(100000, 999999)
    return f"0{area}-{number}"


def build_phone_entries(telefonarten_ids: List[int]) -> List[dict]:
    if len(telefonarten_ids) >= 2:
        chosen = RAND.sample(telefonarten_ids, 2)
    else:
        chosen = [telefonarten_ids[0], telefonarten_ids[0]]

    return [
        {
            'idTelefonArt': chosen[0],
            'telefonnummer': random_phone(),
            'bemerkung': RAND.choice(BEMERKUNGEN),
            'sortierung': 1,
            'istGesperrt': RAND.random() < 0.1,
        },
        {
            'idTelefonArt': chosen[1],
            'telefonnummer': random_phone(),
            'bemerkung': RAND.choice(BEMERKUNGEN),
            'sortierung': 2,
            'istGesperrt': RAND.random() < 0.1,
        },
    ]


def patch_schuler_telefon(config):
    print('\nLade Schüler aus Cache...')
    schueler_list = load_cache()

    if not schueler_list:
        print('⚠️  Keine Schüler im Cache gefunden.')
        return 0, 0

    print('Lade Telefonarten...')
    try:
        telefonarten_ids = fetch_telefonarten_ids(config)
    except requests.exceptions.RequestException as exc:
        print(f"❌ Telefonarten konnten nicht geladen werden: {exc}")
        return 0, len(schueler_list)

    if not telefonarten_ids:
        print('❌ Keine Telefonarten-IDs gefunden.')
        return 0, len(schueler_list)

    total = len(schueler_list)
    print(f'Gefunden: {total} Schüler im Cache')
    print(f'Verfügbare Telefonarten: {len(telefonarten_ids)}')

    db = config['database']
    url_base = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/schueler"
    auth = HTTPBasicAuth(db['username'], db['password'])

    print(f"\nErzeuge Telefon-Daten für {total} Schüler...")
    print(f"URL: {url_base}/{{id}}/telefon\n")

    created = 0
    failed = 0

    for idx, schueler in enumerate(schueler_list, start=1):
        schueler_id = extract_id(schueler)
        vorname = schueler.get('vorname', '')
        nachname = schueler.get('nachname', '')

        if schueler_id is None:
            failed += 1
            print(f"[{idx}/{total}] {vorname} {nachname}: ⚠️  Keine ID im Cache")
            continue

        entries = build_phone_entries(telefonarten_ids)
        url = f"{url_base}/{schueler_id}/telefon"

        student_ok = True
        last_status = 200

        for entry in entries:
            try:
                resp = requests.post(
                    url,
                    json=entry,
                    auth=auth,
                    verify=False,
                    timeout=20,
                )
            except requests.exceptions.RequestException as exc:
                student_ok = False
                failed += 1
                print(f"[{idx}/{total}] {vorname} {nachname}: ❌ Fehler: {exc}")
                break

            last_status = resp.status_code
            if resp.status_code not in (200, 201, 204):
                student_ok = False
                try:
                    err = resp.json().get('message', resp.text)
                except Exception:
                    err = resp.text
                failed += 1
                print(f"[{idx}/{total}] {vorname} {nachname}: ❌ HTTP {resp.status_code} - {err[:180]}")
                break

        if student_ok:
            created += 1
            print(f"[{idx}/{total}] {vorname} {nachname}: ✓ (HTTP {last_status})")

    print(f"\nErgebnis: {created} erfolgreich, {failed} fehlgeschlagen")
    if failed == 0:
        print('✓ Alle Schüler-Telefondaten erfolgreich angelegt!')
    else:
        print(f"⚠️  {failed} Schüler-Telefondaten konnten nicht angelegt werden")

    return created, failed


if __name__ == '__main__':
    from check_server import load_config

    cfg = load_config()
    patch_schuler_telefon(cfg)
