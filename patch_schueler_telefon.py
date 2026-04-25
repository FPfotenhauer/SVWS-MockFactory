"""
Create two phone entries for each existing student record.

Reads student IDs from .schueler_cache.json (created by populate_schueler.py),
loads available phone type IDs via /db/{schema}/schule/telefonarten,
and creates entries via POST /db/{schema}/schueler/{id}/telefon.
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

REQUEST_TIMEOUT = 20
DEFAULT_TELEFON_WORKERS = '4'
POST_RETRIES = 1
RETRY_BACKOFF_SECONDS = 0.2
_THREAD_LOCAL = threading.local()
_THREAD_SESSIONS: List[requests.Session] = []
_THREAD_SESSIONS_LOCK = threading.Lock()
BEMERKUNGEN = [
    'Ist noch aktiv',
    'Nur tagsüber erreichbar',
    'Rückruf am Nachmittag',
    'Bei Notfällen bevorzugen',
    'Kontakt über Erziehungsberechtigte',
]


def create_http_session(auth: HTTPBasicAuth) -> requests.Session:
    session = requests.Session()
    session.auth = auth
    session.verify = False
    return session


def get_thread_state(auth: HTTPBasicAuth) -> Tuple[requests.Session, random.Random]:
    state = getattr(_THREAD_LOCAL, 'state', None)
    if state is None:
        session = requests.Session()
        session.auth = auth
        session.verify = False
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


def _extract_error_text(resp: requests.Response) -> str:
    try:
        message = resp.json().get('message')
        if isinstance(message, str) and message.strip():
            return message.strip()
    except Exception:
        pass
    return (resp.text or '').strip()


def post_phone_entry(
    session: requests.Session,
    url: str,
    entry: dict,
) -> Tuple[bool, int, str]:
    payload_candidates = [entry]
    if bool(entry.get('istGesperrt')):
        fallback_entry = dict(entry)
        fallback_entry['istGesperrt'] = False
        payload_candidates.append(fallback_entry)

    last_status = 0
    last_error = ''

    for payload in payload_candidates:
        for attempt in range(1, POST_RETRIES + 1):
            try:
                resp = session.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            except requests.exceptions.RequestException as exc:
                last_status = 0
                last_error = str(exc)
                if attempt < POST_RETRIES:
                    time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                    continue
                break

            last_status = resp.status_code
            if resp.status_code in (200, 201, 204):
                return True, resp.status_code, ''

            last_error = _extract_error_text(resp)
            retryable = resp.status_code >= 500
            if retryable and attempt < POST_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                continue
            break

    return False, last_status, last_error


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


def fetch_telefonarten_ids(base_url: str, session: requests.Session) -> List[int]:
    url = f'{base_url}/schule/telefonarten'

    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    data = resp.json()
    ids: List[int] = []
    for item in data:
        item_id = extract_id(item)
        if item_id is not None:
            ids.append(item_id)

    return list(dict.fromkeys(ids))


def random_phone(rng: random.Random) -> str:
    area = rng.randint(1000, 99999)
    number = rng.randint(100000, 999999)
    return f"0{area}-{number}"


def build_phone_entries(telefonarten_ids: List[int], rng: random.Random) -> List[dict]:
    if len(telefonarten_ids) >= 2:
        chosen = rng.sample(telefonarten_ids, 2)
    else:
        chosen = [telefonarten_ids[0], telefonarten_ids[0]]

    return [
        {
            'idTelefonArt': chosen[0],
            'telefonnummer': random_phone(rng),
            'bemerkung': rng.choice(BEMERKUNGEN),
            'sortierung': 1,
            'istGesperrt': rng.random() < 0.1,
        },
        {
            'idTelefonArt': chosen[1],
            'telefonnummer': random_phone(rng),
            'bemerkung': rng.choice(BEMERKUNGEN),
            'sortierung': 2,
            'istGesperrt': rng.random() < 0.1,
        },
    ]


def patch_schuler_telefon(config):
    print('\nLade Schüler aus Cache...')
    schueler_list = load_cache()

    if not schueler_list:
        print('⚠️  Keine Schüler im Cache gefunden.')
        return 0, 0

    db = config['database']
    base_url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}"
    auth = HTTPBasicAuth(db['username'], db['password'])

    print('Lade Telefonarten...')
    try:
        with create_http_session(auth) as session:
            telefonarten_ids = fetch_telefonarten_ids(base_url, session)
    except requests.exceptions.RequestException as exc:
        print(f"❌ Telefonarten konnten nicht geladen werden: {exc}")
        return 0, len(schueler_list)

    if not telefonarten_ids:
        print('❌ Keine Telefonarten-IDs gefunden.')
        return 0, len(schueler_list)

    total = len(schueler_list)
    print(f'Gefunden: {total} Schüler im Cache')
    print(f'Verfügbare Telefonarten: {len(telefonarten_ids)}')

    url_base = f'{base_url}/schueler'
    workers_raw = db.get('telefon_workers', os.getenv('SVWS_TELEFON_WORKERS', DEFAULT_TELEFON_WORKERS))
    try:
        workers = max(1, min(16, int(workers_raw)))
    except Exception:
        workers = 6

    if 'telefon_workers' not in db and 'SVWS_TELEFON_WORKERS' not in os.environ:
        # Default to serial create calls to reduce duplicate key races on some server builds.
        workers = 1

    print(f"\nErzeuge Telefon-Daten für {total} Schüler...")
    print(f"Parallelität: {workers} Worker")
    print(f"URL: {url_base}/{{id}}/telefon\n")

    created = 0
    failed = 0

    def process_student(args: Tuple[int, dict]) -> Tuple[int, int, str]:
        idx, schueler = args
        schueler_id = extract_id(schueler)
        vorname = schueler.get('vorname', '')
        nachname = schueler.get('nachname', '')

        if schueler_id is None:
            return 0, 1, f"[{idx}/{total}] {vorname} {nachname}: ⚠️  Keine ID im Cache"

        session, rng = get_thread_state(auth)

        entries = build_phone_entries(telefonarten_ids, rng)
        url = f"{url_base}/{schueler_id}/telefon"

        last_status = 200

        for entry in entries:
            success, status_code, error_text = post_phone_entry(session, url, entry)
            last_status = status_code or last_status
            if not success:
                if status_code > 0:
                    return 0, 1, f"[{idx}/{total}] {vorname} {nachname}: ❌ HTTP {status_code} - {error_text[:180]}"
                return 0, 1, f"[{idx}/{total}] {vorname} {nachname}: ❌ Fehler: {error_text}"

        return 1, 0, f"[{idx}/{total}] {vorname} {nachname}: ✓ (HTTP {last_status})"

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for local_created, local_failed, line in executor.map(
                process_student,
                enumerate(schueler_list, start=1),
            ):
                created += local_created
                failed += local_failed
                print(line)
    finally:
        close_thread_sessions()

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
