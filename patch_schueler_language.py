"""
Create language belegungen for selected students.

For students in year groups 05, 06, 07, 08, 09, 10, EF, Q1, Q2,
creates two language entries via:
POST /db/{schema}/schueler/{id}/sprachen/belegungen
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

TARGET_JAHRGAENGE = {'05', '06', '07', '08', '09', '10', 'EF', 'Q1', 'Q2'}
LANGUAGE_BELEGUNGEN = (
    {
        'sprache': 'E',
        'reihenfolge': 1,
        'belegungVonJahrgang': '05',
        'belegungVonAbschnitt': 1,
        'belegungBisAbschnitt': 2,
    },
    {
        'sprache': 'S',
        'reihenfolge': 2,
        'belegungVonJahrgang': '07',
        'belegungVonAbschnitt': 1,
        'belegungBisAbschnitt': 2,
    },
)


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


def normalize_jahrgang_kuerzel(value: Optional[str]) -> Optional[str]:
    if not isinstance(value, str):
        return None
    upper = value.strip().upper()
    if not upper:
        return None
    if upper in {'EF', 'Q1', 'Q2'}:
        return upper

    digits = ''.join(ch for ch in upper if ch.isdigit())
    if not digits:
        return upper
    return str(int(digits)).zfill(2)


def fetch_jahrgaenge(config, auth: HTTPBasicAuth) -> Dict[int, str]:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/jahrgaenge"
    resp = requests.get(url, auth=auth, verify=False, timeout=20)
    resp.raise_for_status()

    mapping: Dict[int, str] = {}
    for item in resp.json():
        if not isinstance(item, dict):
            continue
        item_id = item.get('id')
        kuerzel = normalize_jahrgang_kuerzel(item.get('kuerzel'))
        if isinstance(item_id, int) and kuerzel:
            mapping[item_id] = kuerzel
    return mapping


def resolve_jahrgang_kuerzel(student: dict, jahrgang_id_to_kuerzel: Dict[int, str]) -> Optional[str]:
    direct = normalize_jahrgang_kuerzel(student.get('jahrgangKuerzel'))
    if direct:
        return direct

    jahrgang_id = student.get('idJahrgang')
    if isinstance(jahrgang_id, int):
        return jahrgang_id_to_kuerzel.get(jahrgang_id)
    if isinstance(jahrgang_id, str) and jahrgang_id.isdigit():
        return jahrgang_id_to_kuerzel.get(int(jahrgang_id))
    return None


def patch_schuler_language(config) -> Tuple[int, int, int]:
    print('\nLade Schüler aus Cache...')
    schueler_list = load_cache()
    if not schueler_list:
        print('⚠️  Keine Schüler im Cache gefunden.')
        return 0, 0, 0

    db = config['database']
    auth = HTTPBasicAuth(db['username'], db['password'])

    print('Lade Jahrgänge...')
    try:
        jahrgang_id_to_kuerzel = fetch_jahrgaenge(config, auth)
    except requests.exceptions.RequestException as exc:
        print(f"❌ Jahrgänge konnten nicht geladen werden: {exc}")
        return 0, 0, len(schueler_list)

    total = len(schueler_list)
    created = 0
    skipped = 0
    failed = 0

    print(f'Gefunden: {total} Schüler im Cache')
    print('Zieljahrgänge: 05, 06, 07, 08, 09, 10, EF, Q1, Q2')

    for idx, schueler in enumerate(schueler_list, start=1):
        schueler_id = extract_id(schueler)
        vorname = schueler.get('vorname', '')
        nachname = schueler.get('nachname', '')

        if schueler_id is None:
            failed += 1
            print(f"[{idx}/{total}] {vorname} {nachname}: ⚠️  Keine ID im Cache")
            continue

        jahrgang_kuerzel = resolve_jahrgang_kuerzel(schueler, jahrgang_id_to_kuerzel)
        if jahrgang_kuerzel not in TARGET_JAHRGAENGE:
            skipped += 1
            print(f"[{idx}/{total}] {vorname} {nachname}: ↷ Jahrgang {jahrgang_kuerzel or '-'} nicht im Zielbereich")
            continue

        student_created = 0
        student_skipped = 0
        student_failed = 0

        for payload in LANGUAGE_BELEGUNGEN:
            url = (
                f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}"
                f"/schueler/{schueler_id}/sprachen/belegungen"
            )

            try:
                resp = requests.post(url, json=payload, auth=auth, verify=False, timeout=20)
                if resp.status_code in (200, 201):
                    created += 1
                    student_created += 1
                elif resp.status_code == 409:
                    skipped += 1
                    student_skipped += 1
                else:
                    failed += 1
                    student_failed += 1
                    error_text = resp.text[:180].replace('\n', ' ')
                    print(
                        f"[{idx}/{total}] {vorname} {nachname} ({jahrgang_kuerzel}) - {payload['sprache']}: "
                        f"✗ HTTP {resp.status_code} {error_text}"
                    )
            except requests.exceptions.RequestException as exc:
                failed += 1
                student_failed += 1
                print(
                    f"[{idx}/{total}] {vorname} {nachname} ({jahrgang_kuerzel}) - {payload['sprache']}: "
                    f"✗ Request-Fehler: {exc}"
                )

        if student_failed == 0:
            print(
                f"[{idx}/{total}] {vorname} {nachname} ({jahrgang_kuerzel}): "
                f"✓ erstellt={student_created}, übersprungen={student_skipped}"
            )

    print(f"\nErgebnis: {created} erstellt, {skipped} übersprungen, {failed} fehlgeschlagen")
    if failed == 0:
        print('✓ Sprach-Belegungen erfolgreich angelegt!')
    else:
        print(f'⚠️  {failed} Sprach-Belegungen konnten nicht angelegt werden')

    return created, skipped, failed


if __name__ == '__main__':
    from check_server import load_config

    cfg = load_config()
    patch_schuler_language(cfg)
