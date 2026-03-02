"""
Create one parent (Erzieher) entry for each existing student.

Reads student IDs from .schueler_cache.json (created by populate_schueler.py),
checks existing parent entries via GET /db/{schema}/schueler/{id}/erzieher,
and creates one parent via POST /db/{schema}/schueler/erzieher/new/{idSchueler}/{idErzieherArt}.
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
    'Kontakt tagsüber bevorzugt',
    'Erreichbarkeit am Nachmittag gut',
    'Rückruf bei Bedarf',
    'Anschreiben per E-Mail bevorzugt',
]


def load_json(path: Path) -> list:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_nachnamen() -> List[str]:
    return load_json(Path(__file__).parent / 'katalogdaten' / 'nachnamen.json')


def load_vornamen_w() -> List[str]:
    return load_json(Path(__file__).parent / 'katalogdaten' / 'vornamen_w.json')


def load_vornamen_m() -> List[str]:
    return load_json(Path(__file__).parent / 'katalogdaten' / 'vornamen_m.json')


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


def slugify_mail_part(text: str) -> str:
    replacements = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
        'Ä': 'ae', 'Ö': 'oe', 'Ü': 'ue',
    }
    lowered = ''.join(replacements.get(ch, ch) for ch in (text or '').lower())
    cleaned = ''.join(ch for ch in lowered if ch.isalnum() or ch in ('-', '.'))
    return cleaned or 'eltern'


def fetch_existing_erzieher(config, auth: HTTPBasicAuth, schueler_id: int) -> List[dict]:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/schueler/{schueler_id}/erzieher"
    resp = requests.get(url, auth=auth, verify=False, timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_student_stammdaten(config, auth: HTTPBasicAuth, schueler_id: int) -> dict:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/schueler/{schueler_id}/stammdaten"
    resp = requests.get(url, auth=auth, verify=False, timeout=20)
    resp.raise_for_status()
    return resp.json()


def has_erzieherart(existing: List[dict], erzieherart_id: int) -> bool:
    for item in existing:
        value = item.get('idErzieherArt')
        if isinstance(value, int) and value == erzieherart_id:
            return True
        if isinstance(value, str) and value.isdigit() and int(value) == erzieherart_id:
            return True
    return False


def first_erzieher_for_art(existing: List[dict], erzieherart_id: int) -> Optional[dict]:
    for item in existing:
        value = item.get('idErzieherArt')
        if isinstance(value, int) and value == erzieherart_id:
            return item
        if isinstance(value, str) and value.isdigit() and int(value) == erzieherart_id:
            return item
    return None


def has_male_second(existing: List[dict], erzieherart_id: int) -> bool:
    for item in existing:
        value = item.get('idErzieherArt')
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        if value != erzieherart_id:
            continue
        anrede = (item.get('anrede') or '').strip().casefold()
        if anrede == 'herr':
            return True
    return False


def build_payload(vorname: str, nachname: str, erzieherart_id: int, student_stammdaten: dict) -> dict:
    mail_part = slugify_mail_part(nachname)
    return {
        'idErzieherArt': erzieherart_id,
        'titel': None,
        'anrede': 'Frau',
        'nachname': nachname,
        'vorname': vorname,
        'strassenname': student_stammdaten.get('strassenname'),
        'hausnummer': student_stammdaten.get('hausnummer'),
        'hausnummerZusatz': student_stammdaten.get('hausnummerZusatz'),
        'wohnortID': student_stammdaten.get('wohnortID'),
        'ortsteilID': student_stammdaten.get('ortsteilID'),
        'erhaeltAnschreiben': True,
        'eMail': f'eltern.{mail_part}@example.com',
        'staatsangehoerigkeitID': 'DEU',
        'bemerkungen': RAND.choice(BEMERKUNGEN),
    }


def build_second_payload(vorname: str, nachname: str, erzieherart_id: int, student_stammdaten: dict) -> dict:
    mail_part = slugify_mail_part(nachname)
    return {
        'idErzieherArt': erzieherart_id,
        'titel': 'Dr.' if RAND.random() < 0.1 else None,
        'anrede': 'Herr',
        'nachname': nachname,
        'vorname': vorname,
        'strassenname': student_stammdaten.get('strassenname'),
        'hausnummer': student_stammdaten.get('hausnummer'),
        'hausnummerZusatz': student_stammdaten.get('hausnummerZusatz'),
        'wohnortID': student_stammdaten.get('wohnortID'),
        'ortsteilID': student_stammdaten.get('ortsteilID'),
        'eMail': f'eltern2.{mail_part}@example.com',
        'staatsangehoerigkeitID': 'TUR',
        'bemerkungen': RAND.choice(BEMERKUNGEN),
    }


def patch_schuler_parents(config):
    print('\nLade Schüler aus Cache...')
    schueler_list = load_cache()
    if not schueler_list:
        print('⚠️  Keine Schüler im Cache gefunden.')
        return 0, 0, 0

    nachnamen = load_nachnamen()
    vornamen_w = load_vornamen_w()
    vornamen_m = load_vornamen_m()

    db = config['database']
    auth = HTTPBasicAuth(db['username'], db['password'])
    erzieherart_id = 5
    endpoint_erzieherart_id = 1
    total = len(schueler_list)

    print(f'Gefunden: {total} Schüler im Cache')
    print(
        f'Erzeuge je Schüler einen Erzieher mit idErzieherArt={erzieherart_id} '
        f'(Endpoint-Slot={endpoint_erzieherart_id}) und ergänze eine zweite männliche Person'
    )

    created_first = 0
    skipped_first = 0
    created_second = 0
    skipped_second = 0
    failed = 0

    for idx, schueler in enumerate(schueler_list, start=1):
        schueler_id = extract_id(schueler)
        s_vorname = schueler.get('vorname', '')
        s_nachname = schueler.get('nachname', '')

        if schueler_id is None:
            failed += 1
            print(f"[{idx}/{total}] {s_vorname} {s_nachname}: ⚠️  Keine ID im Cache")
            continue

        try:
            existing = fetch_existing_erzieher(config, auth, schueler_id)
        except requests.exceptions.RequestException as exc:
            failed += 1
            print(f"[{idx}/{total}] {s_vorname} {s_nachname}: ❌ Fehler beim Laden vorhandener Erzieher: {exc}")
            continue

        try:
            student_stammdaten = fetch_student_stammdaten(config, auth, schueler_id)
        except requests.exceptions.RequestException as exc:
            failed += 1
            print(f"[{idx}/{total}] {s_vorname} {s_nachname}: ❌ Fehler beim Laden der Schüler-Stammdaten: {exc}")
            continue

        primary = first_erzieher_for_art(existing, erzieherart_id)
        primary_id = extract_id(primary) if primary else None

        first_status = '↷'
        primary_nachname: Optional[str] = None
        if primary_id is None:
            vorname = RAND.choice(vornamen_w)
            nachname = RAND.choice(nachnamen)
            primary_nachname = nachname
            payload = build_payload(vorname, nachname, erzieherart_id, student_stammdaten)
            url = (
                f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}"
                f"/schueler/erzieher/new/{schueler_id}/{endpoint_erzieherart_id}"
            )

            try:
                resp = requests.post(
                    url,
                    json=payload,
                    auth=auth,
                    verify=False,
                    timeout=20,
                )

                if resp.status_code in (200, 201):
                    created_first += 1
                    first_status = '✓'
                    try:
                        created_primary = resp.json()
                        primary_id = extract_id(created_primary)
                        if isinstance(created_primary, dict):
                            value = created_primary.get('nachname')
                            if isinstance(value, str) and value.strip():
                                primary_nachname = value.strip()
                    except Exception:
                        primary_id = None
                else:
                    failed += 1
                    first_status = '✗'
            except requests.exceptions.RequestException:
                failed += 1
                first_status = '✗'
        else:
            skipped_first += 1
            value = primary.get('nachname') if isinstance(primary, dict) else None
            if isinstance(value, str) and value.strip():
                primary_nachname = value.strip()

        second_status = '↷'
        if has_male_second(existing, erzieherart_id):
            skipped_second += 1
        elif primary_id is None:
            failed += 1
            second_status = '✗'
        else:
            vorname2 = RAND.choice(vornamen_m)
            nachname2 = primary_nachname or RAND.choice(nachnamen)
            payload2 = build_second_payload(vorname2, nachname2, erzieherart_id, student_stammdaten)
            url2 = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/erzieher/{primary_id}/stammdaten/2"
            try:
                resp2 = requests.patch(
                    url2,
                    json=payload2,
                    auth=auth,
                    verify=False,
                    timeout=20,
                )
                if resp2.status_code in (200, 204):
                    created_second += 1
                    second_status = '✓'
                else:
                    failed += 1
                    second_status = '✗'
            except requests.exceptions.RequestException:
                failed += 1
                second_status = '✗'

        print(f"[{idx}/{total}] {s_vorname} {s_nachname}: 1.Person {first_status}, 2.Person {second_status}")

    created = created_first + created_second
    skipped = skipped_first + skipped_second

    print(f"\nErgebnis: {created} erstellt, {skipped} übersprungen, {failed} fehlgeschlagen")
    print(f"  - 1.Person: {created_first} erstellt, {skipped_first} übersprungen")
    print(f"  - 2.Person: {created_second} erstellt, {skipped_second} übersprungen")
    if failed == 0:
        print('✓ Eltern-Einträge erfolgreich verarbeitet!')
    else:
        print(f"⚠️  {failed} Eltern-Einträge konnten nicht verarbeitet werden")

    return created, skipped, failed


if __name__ == '__main__':
    from check_server import load_config

    cfg = load_config()
    patch_schuler_parents(cfg)
