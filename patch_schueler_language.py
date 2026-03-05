"""
Create language belegungen for selected students.

For students in year groups 05, 06, 07, 08, 09, 10, EF, Q1, Q2,
creates two language entries via:
POST /db/{schema}/schueler/{id}/sprachen/belegungen
"""

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import requests
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

REQUEST_TIMEOUT = 20
RETRY_BACKOFF_SECONDS = 0.2
DEFAULT_LANGUAGE_WORKERS = '4'
_THREAD_LOCAL = threading.local()
_THREAD_SESSIONS: List[requests.Session] = []
_THREAD_SESSIONS_LOCK = threading.Lock()

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


def create_http_session(auth: HTTPBasicAuth) -> requests.Session:
    session = requests.Session()
    session.auth = auth
    session.verify = False
    return session


def get_thread_session(auth: HTTPBasicAuth) -> requests.Session:
    session = getattr(_THREAD_LOCAL, 'session', None)
    if session is None:
        session = create_http_session(auth)
        _THREAD_LOCAL.session = session
        with _THREAD_SESSIONS_LOCK:
            _THREAD_SESSIONS.append(session)
    return session


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


def normalize_sprache_kuerzel(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    return normalized or None


def extract_existing_sprachen(data: object) -> Set[str]:
    result: Set[str] = set()
    if not isinstance(data, list):
        return result

    for item in data:
        if not isinstance(item, dict):
            continue

        kuerzel = normalize_sprache_kuerzel(item.get('sprache'))
        if kuerzel is None:
            kuerzel = normalize_sprache_kuerzel(item.get('kuerzel'))
        if kuerzel is None:
            kuerzel = normalize_sprache_kuerzel(item.get('spracheKuerzel'))

        if kuerzel is not None:
            result.add(kuerzel)

    return result


def fetch_jahrgaenge(base_url: str, session: requests.Session) -> Dict[int, str]:
    url = f'{base_url}/jahrgaenge'
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
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
    base_url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}"

    print('Lade Jahrgänge...')
    try:
        with create_http_session(auth) as session:
            jahrgang_id_to_kuerzel = fetch_jahrgaenge(base_url, session)
    except requests.exceptions.RequestException as exc:
        print(f"❌ Jahrgänge konnten nicht geladen werden: {exc}")
        return 0, 0, len(schueler_list)

    workers_raw = db.get('language_workers', os.getenv('SVWS_LANGUAGE_WORKERS', DEFAULT_LANGUAGE_WORKERS))
    try:
        workers = max(1, min(16, int(workers_raw)))
    except Exception:
        workers = 4

    total = len(schueler_list)
    created = 0
    skipped = 0
    failed = 0

    print(f'Gefunden: {total} Schüler im Cache')
    print('Zieljahrgänge: 05, 06, 07, 08, 09, 10, EF, Q1, Q2')
    print(f'Parallelität: {workers} Worker')

    def process_student(args: Tuple[int, dict]) -> Tuple[int, int, int, List[str]]:
        idx, schueler = args
        lines: List[str] = []

        schueler_id = extract_id(schueler)
        vorname = schueler.get('vorname', '')
        nachname = schueler.get('nachname', '')

        if schueler_id is None:
            lines.append(f"[{idx}/{total}] {vorname} {nachname}: ⚠️  Keine ID im Cache")
            return 0, 0, 1, lines

        jahrgang_kuerzel = resolve_jahrgang_kuerzel(schueler, jahrgang_id_to_kuerzel)
        if jahrgang_kuerzel not in TARGET_JAHRGAENGE:
            lines.append(f"[{idx}/{total}] {vorname} {nachname}: ↷ Jahrgang {jahrgang_kuerzel or '-'} nicht im Zielbereich")
            return 0, 1, 0, lines

        student_created = 0
        student_skipped = 0
        student_failed = 0

        session = get_thread_session(auth)
        url = f'{base_url}/schueler/{schueler_id}/sprachen/belegungen'
        existing_sprachen: Set[str] = set()

        existing_resp, existing_err = request_with_retry(
            session,
            'GET',
            url,
            success_codes=(200,),
        )
        if existing_resp is not None:
            try:
                existing_sprachen = extract_existing_sprachen(existing_resp.json())
            except Exception:
                existing_sprachen = set()
        elif existing_err:
            lines.append(
                f"[{idx}/{total}] {vorname} {nachname} ({jahrgang_kuerzel}): "
                f"⚠️  Belegungen konnten nicht vorab geladen werden ({existing_err})"
            )

        for payload in LANGUAGE_BELEGUNGEN:
            payload_sprache = normalize_sprache_kuerzel(payload.get('sprache'))
            if payload_sprache is not None and payload_sprache in existing_sprachen:
                student_skipped += 1
                continue

            resp, error = request_with_retry(
                session,
                'POST',
                url,
                payload=payload,
                success_codes=(200, 201, 409),
            )

            if resp is None:
                student_failed += 1
                lines.append(
                    f"[{idx}/{total}] {vorname} {nachname} ({jahrgang_kuerzel}) - {payload['sprache']}: "
                    f"✗ Request-Fehler: {error or 'unbekannt'}"
                )
                continue

            if resp.status_code in (200, 201):
                student_created += 1
                if payload_sprache is not None:
                    existing_sprachen.add(payload_sprache)
            elif resp.status_code == 409:
                student_skipped += 1
                if payload_sprache is not None:
                    existing_sprachen.add(payload_sprache)
            else:
                # Some backends may return HTTP 500 instead of 409 on duplicates.
                if resp.status_code >= 500 and payload_sprache is not None:
                    verify_resp, _ = request_with_retry(
                        session,
                        'GET',
                        url,
                        success_codes=(200,),
                        retries=1,
                    )
                    if verify_resp is not None:
                        try:
                            verify_existing = extract_existing_sprachen(verify_resp.json())
                        except Exception:
                            verify_existing = set()
                        if payload_sprache in verify_existing:
                            student_skipped += 1
                            existing_sprachen.add(payload_sprache)
                            continue

                student_failed += 1
                error_text = resp.text[:180].replace('\n', ' ')
                lines.append(
                    f"[{idx}/{total}] {vorname} {nachname} ({jahrgang_kuerzel}) - {payload['sprache']}: "
                    f"✗ HTTP {resp.status_code} {error_text}"
                )

        if student_failed == 0:
            lines.append(
                f"[{idx}/{total}] {vorname} {nachname} ({jahrgang_kuerzel}): "
                f"✓ erstellt={student_created}, übersprungen={student_skipped}"
            )

        return student_created, student_skipped, student_failed, lines

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for local_created, local_skipped, local_failed, lines in executor.map(
                process_student,
                enumerate(schueler_list, start=1),
            ):
                created += local_created
                skipped += local_skipped
                failed += local_failed
                for line in lines:
                    print(line)
    finally:
        close_thread_sessions()

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
