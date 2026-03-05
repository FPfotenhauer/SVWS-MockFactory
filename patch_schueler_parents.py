"""
Create one parent (Erzieher) entry for each existing student.

Reads student IDs from .schueler_cache.json (created by populate_schueler.py),
checks existing parent entries via GET /db/{schema}/schueler/{id}/erzieher,
and creates one parent via POST /db/{schema}/schueler/erzieher/new/{idSchueler}/{idErzieherArt}.
"""

import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional, Tuple

import requests
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

RAND = random.Random()
REQUEST_TIMEOUT = 20
RETRY_BACKOFF_SECONDS = 0.2
DEFAULT_PARENTS_WORKERS = '4'
_THREAD_LOCAL = threading.local()
_THREAD_SESSIONS: List[requests.Session] = []
_THREAD_SESSIONS_LOCK = threading.Lock()
BEMERKUNGEN = [
    'Kontakt tagsüber bevorzugt',
    'Erreichbarkeit am Nachmittag gut',
    'Rückruf bei Bedarf',
    'Anschreiben per E-Mail bevorzugt',
]


def create_http_session(auth: HTTPBasicAuth) -> requests.Session:
    session = requests.Session()
    session.auth = auth
    session.verify = False
    return session


def get_thread_state(auth: HTTPBasicAuth) -> Tuple[requests.Session, random.Random]:
    state = getattr(_THREAD_LOCAL, 'state', None)
    if state is None:
        session = create_http_session(auth)
        rng = random.Random()
        state = (session, rng)
        _THREAD_LOCAL.state = state
        with _THREAD_SESSIONS_LOCK:
            _THREAD_SESSIONS.append(session)
    return state


def close_thread_sessions() -> None:
    with _THREAD_SESSIONS_LOCK:
        sessions = list(_THREAD_SESSIONS)
        _THREAD_SESSIONS.clear()

    for session in sessions:
        try:
            session.close()
        except Exception:
            pass


def request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    payload: Optional[dict] = None,
    success_codes: Tuple[int, ...] = (200, 201, 204),
    retries: int = 3,
) -> Optional[requests.Response]:
    for attempt in range(1, retries + 1):
        try:
            resp = session.request(method=method, url=url, json=payload, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.RequestException:
            resp = None

        if resp is not None and resp.status_code in success_codes:
            return resp

        should_retry = resp is None or resp.status_code >= 500
        if attempt < retries and should_retry:
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)
            continue

        return resp

    return None


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


def fetch_existing_erzieher(base_url: str, session: requests.Session, schueler_id: int) -> List[dict]:
    url = f'{base_url}/schueler/{schueler_id}/erzieher'
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def fetch_student_stammdaten(base_url: str, session: requests.Session, schueler_id: int) -> dict:
    url = f'{base_url}/schueler/{schueler_id}/stammdaten'
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
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


def build_payload(
    vorname: str,
    nachname: str,
    erzieherart_id: int,
    student_stammdaten: dict,
    rng: random.Random,
) -> dict:
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
        'bemerkungen': rng.choice(BEMERKUNGEN),
    }


def build_second_payload(
    vorname: str,
    nachname: str,
    erzieherart_id: int,
    student_stammdaten: dict,
    rng: random.Random,
) -> dict:
    mail_part = slugify_mail_part(nachname)
    return {
        'idErzieherArt': erzieherart_id,
        'titel': 'Dr.' if rng.random() < 0.1 else None,
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
        'bemerkungen': rng.choice(BEMERKUNGEN),
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
    base_url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}"
    erzieherart_id = 5
    endpoint_erzieherart_id = 1
    total = len(schueler_list)

    print(f'Gefunden: {total} Schüler im Cache')
    print(
        f'Erzeuge je Schüler einen Erzieher mit idErzieherArt={erzieherart_id} '
        f'(Endpoint-Slot={endpoint_erzieherart_id}) und ergänze eine zweite männliche Person'
    )
    workers_raw = db.get('parents_workers', os.getenv('SVWS_PARENTS_WORKERS', DEFAULT_PARENTS_WORKERS))
    try:
        workers = max(1, min(16, int(workers_raw)))
    except Exception:
        workers = 4
    print(f'Parallelität: {workers} Worker')

    created_first = 0
    skipped_first = 0
    created_second = 0
    skipped_second = 0
    failed = 0

    def process_student(args: Tuple[int, dict]) -> Tuple[int, int, int, int, int, str]:
        idx, schueler = args
        local_created_first = 0
        local_skipped_first = 0
        local_created_second = 0
        local_skipped_second = 0
        local_failed = 0

        schueler_id = extract_id(schueler)
        s_vorname = schueler.get('vorname', '')
        s_nachname = schueler.get('nachname', '')

        if schueler_id is None:
            return 0, 0, 0, 0, 1, f"[{idx}/{total}] {s_vorname} {s_nachname}: ⚠️  Keine ID im Cache"

        session, rng = get_thread_state(auth)

        try:
            existing = fetch_existing_erzieher(base_url, session, schueler_id)
        except requests.exceptions.RequestException as exc:
            return 0, 0, 0, 0, 1, (
                f"[{idx}/{total}] {s_vorname} {s_nachname}: "
                f"❌ Fehler beim Laden vorhandener Erzieher: {exc}"
            )

        primary = first_erzieher_for_art(existing, erzieherart_id)
        primary_id = extract_id(primary) if primary else None
        male_second_exists = has_male_second(existing, erzieherart_id)

        student_stammdaten: Optional[dict] = None
        needs_stammdaten = (primary_id is None) or (not male_second_exists)
        if needs_stammdaten:
            try:
                student_stammdaten = fetch_student_stammdaten(base_url, session, schueler_id)
            except requests.exceptions.RequestException as exc:
                return 0, 0, 0, 0, 1, (
                    f"[{idx}/{total}] {s_vorname} {s_nachname}: "
                    f"❌ Fehler beim Laden der Schüler-Stammdaten: {exc}"
                )

        first_status = '↷'
        primary_nachname: Optional[str] = None
        if primary_id is None:
            vorname = rng.choice(vornamen_w)
            nachname = rng.choice(nachnamen)
            primary_nachname = nachname
            payload = build_payload(vorname, nachname, erzieherart_id, student_stammdaten or {}, rng)
            url = f'{base_url}/schueler/erzieher/new/{schueler_id}/{endpoint_erzieherart_id}'

            resp = request_with_retry(session, 'POST', url, payload=payload, success_codes=(200, 201))
            if resp is not None and resp.status_code in (200, 201):
                local_created_first += 1
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
                local_failed += 1
                first_status = '✗'
        else:
            local_skipped_first += 1
            value = primary.get('nachname') if isinstance(primary, dict) else None
            if isinstance(value, str) and value.strip():
                primary_nachname = value.strip()

        second_status = '↷'
        if male_second_exists:
            local_skipped_second += 1
        elif primary_id is None:
            local_failed += 1
            second_status = '✗'
        else:
            vorname2 = rng.choice(vornamen_m)
            nachname2 = primary_nachname or rng.choice(nachnamen)
            payload2 = build_second_payload(vorname2, nachname2, erzieherart_id, student_stammdaten or {}, rng)
            url2 = f'{base_url}/erzieher/{primary_id}/stammdaten/2'

            resp2 = request_with_retry(session, 'PATCH', url2, payload=payload2, success_codes=(200, 204))
            if resp2 is not None and resp2.status_code in (200, 204):
                local_created_second += 1
                second_status = '✓'
            else:
                local_failed += 1
                second_status = '✗'

        line = f"[{idx}/{total}] {s_vorname} {s_nachname}: 1.Person {first_status}, 2.Person {second_status}"
        return local_created_first, local_skipped_first, local_created_second, local_skipped_second, local_failed, line

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for (
                local_created_first,
                local_skipped_first,
                local_created_second,
                local_skipped_second,
                local_failed,
                line,
            ) in executor.map(process_student, enumerate(schueler_list, start=1)):
                created_first += local_created_first
                skipped_first += local_skipped_first
                created_second += local_created_second
                skipped_second += local_skipped_second
                failed += local_failed
                print(line)
    finally:
        close_thread_sessions()

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
