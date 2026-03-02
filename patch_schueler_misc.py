"""
Create miscellaneous student notes (Vermerke) for existing students.

Reads student IDs from .schueler_cache.json (created by populate_schueler.py),
loads available Vermerkarten IDs via /db/{schema}/schule/vermerkarten,
and creates one note per student via POST /db/{schema}/schueler/vermerke.
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
    'Eltern haben nicht zugestimmt',
    'Rückmeldung der Erziehungsberechtigten steht aus',
    'Gespräch mit Klassenleitung erforderlich',
    'Entschuldigung wurde nachgereicht',
    'Teilnahme an AG dokumentiert',
    'Hinweis im Beratungsgespräch aufgenommen',
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


def fetch_vermerkarten_ids(config) -> List[int]:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/schule/vermerkarten"

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


def build_vermerk_payload(schueler_id: int, vermerkarten_ids: List[int]) -> dict:
    return {
        'idSchueler': schueler_id,
        'idVermerkart': RAND.choice(vermerkarten_ids),
        'bemerkung': RAND.choice(BEMERKUNGEN),
    }


def patch_schueler_misc(config):
    print('\nLade Schüler aus Cache...')
    schueler_list = load_cache()

    if not schueler_list:
        print('⚠️  Keine Schüler im Cache gefunden.')
        return 0, 0

    print('Lade Vermerkarten...')
    try:
        vermerkarten_ids = fetch_vermerkarten_ids(config)
    except requests.exceptions.RequestException as exc:
        print(f"❌ Vermerkarten konnten nicht geladen werden: {exc}")
        return 0, len(schueler_list)

    if not vermerkarten_ids:
        print('❌ Keine Vermerkarten-IDs gefunden.')
        return 0, len(schueler_list)

    total = len(schueler_list)
    print(f'Gefunden: {total} Schüler im Cache')
    print(f'Verfügbare Vermerkarten: {len(vermerkarten_ids)}')

    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/schueler/vermerke"
    auth = HTTPBasicAuth(db['username'], db['password'])

    print(f"\nErzeuge Vermerke für {total} Schüler...")
    print(f"URL: {url}\n")

    created = 0
    failed = 0
    entries_per_student = 3

    for idx, schueler in enumerate(schueler_list, start=1):
        schueler_id = extract_id(schueler)
        vorname = schueler.get('vorname', '')
        nachname = schueler.get('nachname', '')

        if schueler_id is None:
            failed += 1
            print(f"[{idx}/{total}] {vorname} {nachname}: ⚠️  Keine ID im Cache")
            continue

        student_failed = 0
        for _ in range(entries_per_student):
            payload = build_vermerk_payload(schueler_id, vermerkarten_ids)

            try:
                resp = requests.post(
                    url,
                    json=payload,
                    auth=auth,
                    verify=False,
                    timeout=20,
                )

                if resp.status_code in (200, 201):
                    created += 1
                else:
                    failed += 1
                    student_failed += 1

            except requests.exceptions.RequestException:
                failed += 1
                student_failed += 1

        if student_failed == 0:
            print(f"[{idx}/{total}] {vorname} {nachname}: ✓ ({entries_per_student} Vermerke)")
        else:
            print(f"[{idx}/{total}] {vorname} {nachname}: ⚠️  {entries_per_student - student_failed}/{entries_per_student} Vermerke")

    print(f"\nErgebnis: {created} Vermerke erfolgreich, {failed} fehlgeschlagen")
    if failed == 0:
        print('✓ Alle Schüler-Vermerke erfolgreich angelegt!')
    else:
        print(f"⚠️  {failed} Schüler-Vermerke konnten nicht angelegt werden")

    return created, failed


if __name__ == '__main__':
    from check_server import load_config

    cfg = load_config()
    patch_schueler_misc(cfg)
