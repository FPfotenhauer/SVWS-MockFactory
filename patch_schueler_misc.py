"""
Create miscellaneous student notes (Vermerke) for existing students.

Reads student IDs from .schueler_cache.json (created by populate_schueler.py),
loads available Vermerkarten IDs via /db/{schema}/schule/vermerkarten,
and creates one note per student via POST /db/{schema}/schueler/vermerke.
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
DEFAULT_MISC_WORKERS = '6'
LP_EINWILLIGUNG_KEYS = (
    'einwilligungAbgefragt',
    'einwilligungNutzung',
    'einwilligungAudiokonferenz',
    'einwilligungVideokonferenz',
)
_THREAD_LOCAL = threading.local()

BEMERKUNGEN = [
    'Eltern haben nicht zugestimmt',
    'Rückmeldung der Erziehungsberechtigten steht aus',
    'Gespräch mit Klassenleitung erforderlich',
    'Entschuldigung wurde nachgereicht',
    'Teilnahme an AG dokumentiert',
    'Hinweis im Beratungsgespräch aufgenommen',
]


def get_session(auth: HTTPBasicAuth) -> requests.Session:
    session = getattr(_THREAD_LOCAL, 'session', None)
    if session is None:
        session = requests.Session()
        session.auth = auth
        session.verify = False
        _THREAD_LOCAL.session = session
    return session


def parse_optional_int(value) -> Optional[int]:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


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

        should_retry = resp is None or (resp.status_code >= 500)
        if attempt < retries and should_retry:
            time.sleep(0.15 * attempt)
            continue

        return resp

    return None


def is_vermerk_create_endpoint(url: str) -> bool:
    return url.endswith('/schueler/vermerke')


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


def fetch_vermerkarten_ids(base_url: str, session: requests.Session) -> List[int]:
    url = f'{base_url}/schule/vermerkarten'
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
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


def fetch_student_einwilligungen(base_url: str, session: requests.Session, schueler_id: int) -> List[dict]:
    url = f'{base_url}/schueler/{schueler_id}/einwilligungen'
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def patch_student_einwilligung(base_url: str, session: requests.Session, schueler_id: int, id_einwilligungsart: int) -> bool:
    url = f'{base_url}/schueler/{schueler_id}/einwilligungen/{id_einwilligungsart}'
    payload = {
        'abgefragt': True,
        'status': True,
    }
    resp = request_with_retry(session, 'PATCH', url, payload=payload, success_codes=(200, 204))
    return resp is not None and resp.status_code in (200, 204)


def fetch_student_lernplattformen(base_url: str, session: requests.Session, schueler_id: int) -> List[dict]:
    url = f'{base_url}/schueler/{schueler_id}/lernplattformen'
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def patch_student_lernplattform(base_url: str, session: requests.Session, schueler_id: int, id_lernplattform: int) -> bool:
    url = f'{base_url}/schueler/{schueler_id}/lernplattformen/{id_lernplattform}'
    payload = {
        'einwilligungAbgefragt': True,
        'einwilligungNutzung': True,
        'einwilligungAudiokonferenz': True,
        'einwilligungVideokonferenz': True,
    }
    resp = request_with_retry(session, 'PATCH', url, payload=payload, success_codes=(200, 204))
    return resp is not None and resp.status_code in (200, 204)


def needs_einwilligung_update(einwilligung: dict) -> bool:
    return not (bool(einwilligung.get('abgefragt')) and bool(einwilligung.get('status')))


def needs_lernplattform_update(lernplattform: dict) -> bool:
    return not all(bool(lernplattform.get(key)) for key in LP_EINWILLIGUNG_KEYS)


def patch_schueler_misc(config):
    print('\nLade Schüler aus Cache...')
    schueler_list = load_cache()

    if not schueler_list:
        print('⚠️  Keine Schüler im Cache gefunden.')
        return 0, 0

    db = config['database']
    base_url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}"
    auth = HTTPBasicAuth(db['username'], db['password'])
    session = get_session(auth)

    print('Lade Vermerkarten...')
    try:
        vermerkarten_ids = fetch_vermerkarten_ids(base_url, session)
    except requests.exceptions.RequestException as exc:
        print(f"❌ Vermerkarten konnten nicht geladen werden: {exc}")
        return 0, len(schueler_list)

    if not vermerkarten_ids:
        print('❌ Keine Vermerkarten-IDs gefunden.')
        return 0, len(schueler_list)

    total = len(schueler_list)
    print(f'Gefunden: {total} Schüler im Cache')
    print(f'Verfügbare Vermerkarten: {len(vermerkarten_ids)}')

    url = f'{base_url}/schueler/vermerke'
    workers_raw = db.get('misc_workers', os.getenv('SVWS_MISC_WORKERS', DEFAULT_MISC_WORKERS))
    try:
        workers = max(1, min(16, int(workers_raw)))
    except Exception:
        workers = 6

    if is_vermerk_create_endpoint(url) and 'misc_workers' not in db and 'SVWS_MISC_WORKERS' not in os.environ:
        # Default to serial create calls to reduce duplicate key races on some server builds.
        workers = 1

    print(f"\nErzeuge Vermerke für {total} Schüler...")
    print(f"Parallelität: {workers} Worker")
    print(f"URL: {url}\n")

    created = 0
    failed = 0
    einwilligungen_updated = 0
    lernplattformen_updated = 0
    entries_per_student = 3

    def process_student(args: Tuple[int, dict]) -> Tuple[int, int, int, int, str]:
        idx, schueler = args
        schueler_id = extract_id(schueler)
        vorname = schueler.get('vorname', '')
        nachname = schueler.get('nachname', '')

        local_created = 0
        local_failed = 0
        student_einwilligungen_ok = 0
        student_lernplattformen_ok = 0
        student_failed = 0

        if schueler_id is None:
            return 0, 1, 0, 0, f"[{idx}/{total}] {vorname} {nachname}: ⚠️  Keine ID im Cache"

        session = get_session(auth)

        for _ in range(entries_per_student):
            payload = build_vermerk_payload(schueler_id, vermerkarten_ids)

            resp = request_with_retry(
                session,
                'POST',
                url,
                payload=payload,
                success_codes=(200, 201),
                retries=1,
            )
            if resp is not None and resp.status_code in (200, 201):
                local_created += 1
            else:
                local_failed += 1
                student_failed += 1

        student_einwilligungen_ok = 0
        student_lernplattformen_ok = 0

        try:
            einwilligungen = fetch_student_einwilligungen(base_url, session, schueler_id)
            for einwilligung in einwilligungen:
                id_einwilligungsart = parse_optional_int(einwilligung.get('idEinwilligungsart'))
                if id_einwilligungsart is None:
                    continue
                if not needs_einwilligung_update(einwilligung):
                    continue
                try:
                    if patch_student_einwilligung(base_url, session, schueler_id, id_einwilligungsart):
                        student_einwilligungen_ok += 1
                    else:
                        local_failed += 1
                        student_failed += 1
                except requests.exceptions.RequestException:
                    local_failed += 1
                    student_failed += 1
        except requests.exceptions.RequestException:
            local_failed += 1
            student_failed += 1

        try:
            lernplattformen = fetch_student_lernplattformen(base_url, session, schueler_id)
            for lernplattform in lernplattformen:
                id_lernplattform = parse_optional_int(lernplattform.get('idLernplattform'))
                if id_lernplattform is None:
                    continue
                if not needs_lernplattform_update(lernplattform):
                    continue
                try:
                    if patch_student_lernplattform(base_url, session, schueler_id, id_lernplattform):
                        student_lernplattformen_ok += 1
                    else:
                        local_failed += 1
                        student_failed += 1
                except requests.exceptions.RequestException:
                    local_failed += 1
                    student_failed += 1
        except requests.exceptions.RequestException:
            local_failed += 1
            student_failed += 1

        if student_failed == 0:
            line = (
                f"[{idx}/{total}] {vorname} {nachname}: ✓ "
                f"({entries_per_student} Vermerke, {student_einwilligungen_ok} Einwilligungen, "
                f"{student_lernplattformen_ok} Lernplattformen)"
            )
        else:
            line = (
                f"[{idx}/{total}] {vorname} {nachname}: ⚠️ "
                f"({entries_per_student} Vermerke, {student_einwilligungen_ok} Einwilligungen, "
                f"{student_lernplattformen_ok} Lernplattformen; Fehler: {student_failed})"
            )

        return local_created, local_failed, student_einwilligungen_ok, student_lernplattformen_ok, line

    with ThreadPoolExecutor(max_workers=workers) as executor:
        for local_created, local_failed, local_einwilligungen, local_lernplattformen, line in executor.map(
            process_student,
            enumerate(schueler_list, start=1),
        ):
            created += local_created
            failed += local_failed
            einwilligungen_updated += local_einwilligungen
            lernplattformen_updated += local_lernplattformen
            print(line)

    print(f"\nErgebnis: {created} Vermerke erfolgreich, {failed} fehlgeschlagen")
    print(f"Zusätzlich gesetzt: {einwilligungen_updated} Einwilligungen, {lernplattformen_updated} Lernplattformen")
    if failed == 0:
        print('✓ Alle Schüler-Vermerke erfolgreich angelegt!')
    else:
        print(f"⚠️  {failed} Schüler-Vermerke konnten nicht angelegt werden")

    return created, failed


if __name__ == '__main__':
    from check_server import load_config

    cfg = load_config()
    patch_schueler_misc(cfg)
