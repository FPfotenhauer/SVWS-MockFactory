"""
Assign one random Betrieb (company) to each existing student.

Reads student IDs from .schueler_cache.json (created by populate_schueler.py),
loads available Betriebe via GET /db/{schema}/betriebe,
and creates one assignment per student via:
POST /db/{schema}/betriebe/schuelerbetrieb/new/schueler/{idSchueler}/betrieb/{idBetrieb}
"""

import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

import requests
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

RAND = random.Random()
REQUEST_TIMEOUT = 20
RETRY_BACKOFF_SECONDS = 0.2
DEFAULT_COMPANY_WORKERS = '4'
_THREAD_LOCAL = threading.local()
_THREAD_SESSIONS: List[requests.Session] = []
_THREAD_SESSIONS_LOCK = threading.Lock()


def load_cache() -> List[dict]:
    cache_file = Path(__file__).parent / '.schueler_cache.json'
    if not cache_file.exists():
        print(f"❌ Cache-Datei nicht gefunden: {cache_file}")
        print('   Bitte zuerst --populate-schueler ausführen!')
        return []

    with open(cache_file, 'r', encoding='utf-8') as f:
        return json.load(f)


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
) -> Tuple[Optional[requests.Response], Optional[str]]:
    last_error: Optional[str] = None
    for attempt in range(1, retries + 1):
        try:
            resp = session.request(method=method, url=url, json=payload, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            resp = None
            last_error = str(exc)

        if resp is not None and resp.status_code in success_codes:
            return resp, None

        should_retry = resp is None or resp.status_code >= 500
        if attempt < retries and should_retry:
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)
            continue

        return resp, last_error

    return None, last_error


def extract_id(entry: dict) -> Optional[int]:
    value = entry.get('id')
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def fetch_betriebe(base_url: str, session: requests.Session) -> List[int]:
    url = f'{base_url}/betriebe'
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    data = resp.json()
    ids: List[int] = []
    for item in data:
        betriebs_id = extract_id(item)
        if betriebs_id is not None:
            ids.append(betriebs_id)

    return list(dict.fromkeys(ids))


def build_payload(schueler_id: int, betrieb_id: int, vertragsbeginn: str, vertragsende: str) -> dict:
    return {
        'id': 0,
        'schueler_id': schueler_id,
        'betrieb_id': betrieb_id,
        'beschaeftigungsart_id': 1,
        'vertragsbeginn': vertragsbeginn,
        'vertragsende': vertragsende,
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
    base_url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}"
    vertragsbeginn_iso = date.today().isoformat()
    vertragsende_iso = (date.today() + timedelta(days=1)).isoformat()

    print('Lade Betriebe...')
    try:
        with create_http_session(auth) as session:
            betriebe_ids = fetch_betriebe(base_url, session)
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

    workers_raw = db.get('company_workers', os.getenv('SVWS_COMPANY_WORKERS', DEFAULT_COMPANY_WORKERS))
    try:
        workers = max(1, min(16, int(workers_raw)))
    except Exception:
        workers = 4
    print(f'Parallelität: {workers} Worker')

    def process_student(args: Tuple[int, dict]) -> Tuple[int, int, int, str]:
        idx, schueler = args
        schueler_id = extract_id(schueler)
        vorname = schueler.get('vorname', '')
        nachname = schueler.get('nachname', '')

        if schueler_id is None:
            return 0, 0, 1, f"[{idx}/{total}] {vorname} {nachname}: ⚠️  Keine ID im Cache"

        session, rng = get_thread_state(auth)
        betrieb_id = rng.choice(betriebe_ids)
        payload = build_payload(schueler_id, betrieb_id, vertragsbeginn_iso, vertragsende_iso)
        url = f'{base_url}/betriebe/schuelerbetrieb/new/schueler/{schueler_id}/betrieb/{betrieb_id}'

        resp, error = request_with_retry(
            session,
            'POST',
            url,
            payload=payload,
            success_codes=(200, 201, 409),
        )

        if resp is None:
            return 0, 0, 1, f"[{idx}/{total}] {vorname} {nachname}: ✗ Request-Fehler: {error or 'unbekannt'}"

        if resp.status_code in (200, 201):
            return 1, 0, 0, f"[{idx}/{total}] {vorname} {nachname}: ✓ Betrieb {betrieb_id} zugeordnet"
        if resp.status_code == 409:
            return 0, 1, 0, f"[{idx}/{total}] {vorname} {nachname}: ↷ bereits zugeordnet"

        return 0, 0, 1, f"[{idx}/{total}] {vorname} {nachname}: ✗ {resp.status_code} {resp.text[:180]}"

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for local_created, local_skipped, local_failed, line in executor.map(
                process_student,
                enumerate(schueler_list, start=1),
            ):
                created += local_created
                skipped += local_skipped
                failed += local_failed
                print(line)
    finally:
        close_thread_sessions()

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
