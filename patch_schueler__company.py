"""
Assign one random Betrieb (company) to each existing student.

Reads student IDs from .schueler_cache.json (created by populate_schueler.py),
loads available Betriebe via GET /db/{schema}/schule/betriebe (legacy fallback: /betriebe),
and creates one assignment per student via:
POST /db/{schema}/schueler/schueler-betriebe/create
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
DEFAULT_ASSIGNMENT_ENDPOINT_TEMPLATES = [
    '/schueler/schueler-betriebe/create',
    '/betriebe/schuelerbetrieb/new/schueler/{schueler_id}/betrieb/{betrieb_id}',
    '/schule/betriebe/schuelerbetrieb/new/schueler/{schueler_id}/betrieb/{betrieb_id}',
]
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


def load_betriebe_cache() -> List[int]:
    cache_file = Path(__file__).parent / '.betriebe_cache.json'
    if not cache_file.exists():
        return []

    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cached = json.load(f)
    except Exception:
        return []

    if not isinstance(cached, list):
        return []

    ids: List[int] = []
    for entry in cached:
        if isinstance(entry, dict):
            betriebs_id = extract_id(entry)
        else:
            betriebs_id = extract_id({'id': entry})
        if betriebs_id is not None:
            ids.append(betriebs_id)

    return list(dict.fromkeys(ids))


def save_betriebe_cache(ids: List[int]) -> None:
    if not ids:
        return

    cache_file = Path(__file__).parent / '.betriebe_cache.json'
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump([{'id': bid} for bid in ids], f, indent=2, ensure_ascii=False)


def get_assignment_endpoint_templates(db: dict) -> List[str]:
    configured = db.get('company_assignment_endpoint')
    if isinstance(configured, str) and configured.strip():
        template = configured.strip()
        if not template.startswith('/'):
            template = '/' + template
        return [template] + [
            x for x in DEFAULT_ASSIGNMENT_ENDPOINT_TEMPLATES if x != template
        ]

    configured_list = db.get('company_assignment_endpoints')
    if isinstance(configured_list, list):
        cleaned = []
        for item in configured_list:
            if isinstance(item, str) and item.strip():
                template = item.strip()
                if not template.startswith('/'):
                    template = '/' + template
                cleaned.append(template)
        if cleaned:
            merged = list(dict.fromkeys(cleaned + DEFAULT_ASSIGNMENT_ENDPOINT_TEMPLATES))
            return merged

    return list(DEFAULT_ASSIGNMENT_ENDPOINT_TEMPLATES)


def build_assignment_url(base_url: str, endpoint_template: str, schueler_id: int, betrieb_id: int) -> str:
    if '{schueler_id}' in endpoint_template or '{betrieb_id}' in endpoint_template:
        endpoint = endpoint_template.format(schueler_id=schueler_id, betrieb_id=betrieb_id)
    else:
        endpoint = endpoint_template
    return f'{base_url}{endpoint}'


def select_assignment_endpoint(
    base_url: str,
    db: dict,
    session: requests.Session,
    schueler_id: int,
    betrieb_id: int,
    payload: dict,
) -> Tuple[Optional[str], str]:
    templates = get_assignment_endpoint_templates(db)
    probe_messages: List[str] = []

    for template in templates:
        url = build_assignment_url(base_url, template, schueler_id, betrieb_id)
        resp, error = request_with_retry(
            session,
            'POST',
            url,
            payload=payload,
            success_codes=(200, 201, 409),
            retries=1,
        )

        if resp is None:
            probe_messages.append(f'{template}: request error {error or "unbekannt"}')
            continue

        if resp.status_code in (200, 201, 409, 400, 401, 403, 422):
            return template, f'{template}: HTTP {resp.status_code}'

        probe_messages.append(f'{template}: HTTP {resp.status_code}')

    return None, ' | '.join(probe_messages)


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


def is_create_endpoint(endpoint_template: str) -> bool:
    return endpoint_template == '/schueler/schueler-betriebe/create'


def extract_id(entry: dict) -> Optional[int]:
    value = entry.get('id')
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def fetch_betriebe(base_url: str, session: requests.Session) -> List[int]:
    url = f'{base_url}/schule/betriebe'
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    data = resp.json()
    ids: List[int] = []
    for item in data:
        betriebs_id = extract_id(item)
        if betriebs_id is not None:
            ids.append(betriebs_id)

    return list(dict.fromkeys(ids))


def fetch_betriebe_with_fallback(base_url: str, session: requests.Session) -> List[int]:
    urls = [
        f'{base_url}/schule/betriebe',
        f'{base_url}/betriebe',
    ]
    errors: List[str] = []

    for url in urls:
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            ids: List[int] = []
            for item in data:
                betriebs_id = extract_id(item)
                if betriebs_id is not None:
                    ids.append(betriebs_id)
            unique_ids = list(dict.fromkeys(ids))
            if unique_ids:
                if url.endswith('/betriebe'):
                    print('ℹ️  Betriebe über Legacy-Fallback-Endpunkt /betriebe geladen')
                return unique_ids
            errors.append(f'{url}: keine IDs im Payload')
        except requests.exceptions.RequestException as exc:
            errors.append(f'{url}: {exc}')

    raise requests.exceptions.RequestException(' | '.join(errors))


def build_payload(schueler_id: int, betrieb_id: int, vertragsbeginn: str, vertragsende: str) -> dict:
    return {
        'idSchueler': schueler_id,
        'idBetrieb': betrieb_id,
        'idBeschaeftigungsart': 1,
        'vertragsbeginn': vertragsbeginn,
        'vertragsende': vertragsende,
        'nameAusbilder': None,
        'erhaeltAnschreiben': False,
        'istPraktikum': False,
        'sortierung': None,
        'idAnsprechpartner': None,
        'idBetreuungslehrer': None,
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
    betriebe_ids: List[int] = []
    try:
        with create_http_session(auth) as session:
            betriebe_ids = fetch_betriebe_with_fallback(base_url, session)
    except requests.exceptions.RequestException as exc:
        print(f"⚠️  Betriebe konnten nicht per API geladen werden: {exc}")

    if betriebe_ids:
        save_betriebe_cache(betriebe_ids)
    else:
        print('   Versuche Fallback über .betriebe_cache.json ...')
        betriebe_ids = load_betriebe_cache()
        if betriebe_ids:
            print(f"✓ Fallback erfolgreich: {len(betriebe_ids)} Betriebe aus Cache geladen")

    if not betriebe_ids:
        print('❌ Keine Betrieb-IDs gefunden.')
        return 0, 0, len(schueler_list)

    total = len(schueler_list)
    created = 0
    skipped = 0
    failed = 0

    first_student_id = extract_id(schueler_list[0])
    if first_student_id is None:
        print('❌ Erster Schüler im Cache enthält keine gültige ID.')
        return 0, 0, total

    endpoint_template: Optional[str] = None
    probe_company_id = betriebe_ids[0]
    probe_payload = build_payload(first_student_id, probe_company_id, vertragsbeginn_iso, vertragsende_iso)
    with create_http_session(auth) as probe_session:
        endpoint_template, probe_result = select_assignment_endpoint(
            base_url,
            db,
            probe_session,
            first_student_id,
            probe_company_id,
            probe_payload,
        )

    if endpoint_template is None:
        print('⚠️  Kein gültiger API-Endpunkt für Schüler-Betrieb-Zuordnung gefunden.')
        print(f'   Probe-Ergebnis: {probe_result}')
        print('   Schritt wird übersprungen (alle Schüler als skipped).')
        return 0, total, 0

    print(f'ℹ️  Verwende Zuordnungs-Endpunkt: {endpoint_template}')

    print(f'Gefunden: {total} Schüler im Cache')
    print(f'Verfügbare Betriebe: {len(betriebe_ids)}')

    workers_raw = db.get('company_workers', os.getenv('SVWS_COMPANY_WORKERS', DEFAULT_COMPANY_WORKERS))
    try:
        workers = max(1, min(16, int(workers_raw)))
    except Exception:
        workers = 4

    if is_create_endpoint(endpoint_template) and 'company_workers' not in db and 'SVWS_COMPANY_WORKERS' not in os.environ:
        # Default to serial create calls for this endpoint to avoid duplicate key races on some server builds.
        workers = 1

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
        url = build_assignment_url(base_url, endpoint_template, schueler_id, betrieb_id)

        retries = 1 if is_create_endpoint(endpoint_template) else 3
        resp, error = request_with_retry(
            session,
            'POST',
            url,
            payload=payload,
            success_codes=(200, 201, 409),
            retries=retries,
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
