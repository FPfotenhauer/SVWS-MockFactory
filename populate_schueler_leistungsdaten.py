"""
Populate Schüler Leistungsdaten with generated performance records.

Steps:
  1. Fetch school Fächer from API; create any missing ones
  2. For each Schüler from .schueler_cache.json find their current Lernabschnitt
  3. Create a SchuelerLeistungsdaten entry per Fach via
     POST /db/{schema}/schueler/leistungsdaten/create
"""

import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

REQUEST_TIMEOUT = 20
RETRY_BACKOFF_SECONDS = 0.2
DEFAULT_WORKERS = '4'
POST_RETRIES = 2

_THREAD_LOCAL = threading.local()
_THREAD_SESSIONS: List[requests.Session] = []
_THREAD_SESSIONS_LOCK = threading.Lock()

RAND = random.Random()

# ---------------------------------------------------------------------------
# Fächer-Definition
# Erweitern um weitere Fächer nach Bedarf.
# ab_jahrgang: None = alle Jahrgänge, sonst Mindestsjahrgang-Kürzel (z.B. '07')
# ---------------------------------------------------------------------------
FAECHER_DEFINITION = [
    {
        'kuerzel': 'D',
        'kuerzelStatistik': 'D',
        'bezeichnung': 'Deutsch',
        'wochenstunden': 4,
        'ab_jahrgang': None,
        'istFremdsprache': False,
        'aufZeugnis': True,
        'istSichtbar': True,
        'istPruefungsordnungsRelevant': True,
    },
    # Weitere Fächer können hier ergänzt werden, z.B.:
    # {
    #     'kuerzel': 'M',
    #     'kuerzelStatistik': 'M',
    #     'bezeichnung': 'Mathematik',
    #     'wochenstunden': 4,
    #     'ab_jahrgang': None,
    #     'istFremdsprache': False,
    #     'aufZeugnis': True,
    #     'istSichtbar': True,
    #     'istPruefungsordnungsRelevant': True,
    # },
    # {
    #     'kuerzel': 'E',
    #     'kuerzelStatistik': 'E',
    #     'bezeichnung': 'Englisch',
    #     'wochenstunden': 4,
    #     'ab_jahrgang': '05',
    #     'istFremdsprache': True,
    #     'aufZeugnis': True,
    #     'istSichtbar': True,
    #     'istPruefungsordnungsRelevant': True,
    # },
]

# Notenverteilung: leicht glockenförmig um 3
_NOTEN = ['1', '1-', '2+', '2', '2-', '3+', '3', '3-', '4+', '4', '4-', '5+', '5', '6']
_NOTEN_WEIGHTS = [1, 2, 3, 5, 5, 6, 8, 6, 5, 5, 3, 2, 2, 1]


def _random_note() -> str:
    return RAND.choices(_NOTEN, weights=_NOTEN_WEIGHTS, k=1)[0]


def _jahrgang_order(kuerzel: str) -> int:
    mapping = {'EF': 11, 'Q1': 12, 'Q2': 13}
    if kuerzel in mapping:
        return mapping[kuerzel]
    try:
        return int(kuerzel)
    except (ValueError, TypeError):
        return 0


def _fach_gilt_fuer_jahrgang(fach_def: dict, jahrgang_kuerzel: str) -> bool:
    ab = fach_def.get('ab_jahrgang')
    if ab is None:
        return True
    return _jahrgang_order(jahrgang_kuerzel) >= _jahrgang_order(ab)


# ---------------------------------------------------------------------------
# HTTP session management (thread-safe)
# ---------------------------------------------------------------------------

def _create_session(auth: HTTPBasicAuth) -> requests.Session:
    session = requests.Session()
    session.auth = auth
    session.verify = False
    return session


def _get_thread_session(auth: HTTPBasicAuth) -> requests.Session:
    session = getattr(_THREAD_LOCAL, 'session', None)
    if session is None:
        session = _create_session(auth)
        _THREAD_LOCAL.session = session
        with _THREAD_SESSIONS_LOCK:
            _THREAD_SESSIONS.append(session)
    return session


def _close_all_sessions() -> None:
    with _THREAD_SESSIONS_LOCK:
        sessions = list(_THREAD_SESSIONS)
        _THREAD_SESSIONS.clear()
    for s in sessions:
        try:
            s.close()
        except Exception:
            pass


def _request(
    session: requests.Session,
    method: str,
    url: str,
    payload: Optional[dict] = None,
    success_codes: Tuple[int, ...] = (200, 201),
    retries: int = POST_RETRIES,
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


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _fetch_stammdaten(base_url: str, session: requests.Session) -> dict:
    resp = session.get(f'{base_url}/schule/stammdaten', timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _fetch_faecher(base_url: str, session: requests.Session) -> List[dict]:
    resp = session.get(f'{base_url}/faecher', timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _create_fach(base_url: str, session: requests.Session, fach_def: dict) -> Optional[int]:
    payload = {
        'id': 0,
        'kuerzel': fach_def['kuerzel'],
        'kuerzelStatistik': fach_def['kuerzelStatistik'],
        'bezeichnung': fach_def['bezeichnung'],
        'aufZeugnis': fach_def.get('aufZeugnis', True),
        'istFremdsprache': fach_def.get('istFremdsprache', False),
        'istSichtbar': fach_def.get('istSichtbar', True),
        'istPruefungsordnungsRelevant': fach_def.get('istPruefungsordnungsRelevant', True),
        'istNachpruefungErlaubt': False,
        'istSchriftlichZK': False,
        'istSchriftlichBA': False,
        'istFHRFach': False,
        'holeAusAltenLernabschnitten': False,
        'istOberstufenFach': False,
        'istMoeglichAlsNeueFremdspracheInSekII': False,
        'sortierung': 32000,
        'referenziertInAnderenTabellen': False,
    }
    resp, err = _request(session, 'POST', f'{base_url}/faecher/create', payload=payload)
    if resp is not None and resp.status_code in (200, 201):
        try:
            return resp.json().get('id')
        except Exception:
            pass
    kuerzel = fach_def['kuerzel']
    code = resp.status_code if resp else 'n/a'
    detail = (resp.text[:120] if resp else err or '') .replace('\n', ' ')
    print(f"  ⚠️  Fach '{kuerzel}' konnte nicht erstellt werden: HTTP {code} {detail}")
    return None


def _ensure_faecher(base_url: str, session: requests.Session) -> Dict[str, dict]:
    """Ensure all defined Fächer exist. Returns mapping kuerzel -> {id, wochenstunden, ...}."""
    existing = _fetch_faecher(base_url, session)
    existing_by_kuerzel = {f['kuerzel']: f for f in existing}

    result: Dict[str, dict] = {}
    for fach_def in FAECHER_DEFINITION:
        kuerzel = fach_def['kuerzel']
        if kuerzel in existing_by_kuerzel:
            fach_id = existing_by_kuerzel[kuerzel]['id']
            print(f"  ✓ Fach '{kuerzel}' bereits vorhanden (ID {fach_id})")
        else:
            fach_id = _create_fach(base_url, session, fach_def)
            if fach_id is None:
                continue
            print(f"  ✓ Fach '{kuerzel}' erstellt (ID {fach_id})")

        result[kuerzel] = {**fach_def, 'id': fach_id}

    return result


def _fetch_lernabschnitt_id(
    base_url: str,
    session: requests.Session,
    schueler_id: int,
    id_schuljahresabschnitt: int,
) -> Optional[int]:
    resp, err = _request(
        session,
        'GET',
        f'{base_url}/schueler/{schueler_id}/lernabschnitte',
        success_codes=(200,),
    )
    if resp is None:
        return None
    try:
        abschnitte = resp.json()
    except Exception:
        return None

    for eintrag in abschnitte:
        if eintrag.get('schuljahresabschnitt') == id_schuljahresabschnitt:
            return eintrag.get('id')
    return None


def _load_schueler_cache() -> List[dict]:
    cache_file = Path(__file__).parent / '.schueler_cache.json'
    if not cache_file.exists():
        print(f"❌ Cache-Datei nicht gefunden: {cache_file}")
        print('   Bitte zuerst --populate-schueler ausführen!')
        return []
    with open(cache_file, 'r', encoding='utf-8') as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def populate_schueler_leistungsdaten(config) -> Tuple[int, int, int]:
    """
    Create Leistungsdaten for all students in .schueler_cache.json.

    Returns:
        (created, skipped, failed)
    """
    print('\nLade Schüler aus Cache...')
    schueler_list = _load_schueler_cache()
    if not schueler_list:
        print('⚠️  Keine Schüler im Cache gefunden.')
        return 0, 0, 0

    db = config['database']
    auth = HTTPBasicAuth(db['username'], db['password'])
    base_url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}"

    # Fetch current Schuljahresabschnitt
    print('Lade Schulstammdaten...')
    try:
        with _create_session(auth) as setup_session:
            stammdaten = _fetch_stammdaten(base_url, setup_session)
            id_schuljahresabschnitt = stammdaten['idSchuljahresabschnitt']
            print(f'  Aktueller Schuljahresabschnitt: ID {id_schuljahresabschnitt}')

            # Ensure Fächer exist
            print('Stelle Fächer sicher...')
            faecher_map = _ensure_faecher(base_url, setup_session)
    except requests.exceptions.RequestException as exc:
        print(f'❌ Server nicht erreichbar: {exc}')
        return 0, 0, len(schueler_list)

    if not faecher_map:
        print('❌ Keine Fächer verfügbar. Abbruch.')
        return 0, 0, len(schueler_list)

    workers_raw = db.get('leistung_workers', os.getenv('SVWS_LEISTUNG_WORKERS', DEFAULT_WORKERS))
    try:
        workers = max(1, min(16, int(workers_raw)))
    except Exception:
        workers = 1

    total = len(schueler_list)
    created = 0
    skipped = 0
    failed = 0

    print(f'\nGefunden: {total} Schüler')
    print(f'Fächer: {", ".join(faecher_map.keys())}')
    print(f'Parallelität: {workers} Worker')

    def process_student(args: Tuple[int, dict]) -> Tuple[int, int, int, List[str]]:
        idx, schueler = args
        lines: List[str] = []

        schueler_id = schueler.get('id')
        vorname = schueler.get('vorname', '')
        nachname = schueler.get('nachname', '')
        jahrgang_kuerzel = schueler.get('jahrgangKuerzel') or ''
        label = f'[{idx}/{total}] {vorname} {nachname} ({jahrgang_kuerzel})'

        if not isinstance(schueler_id, int):
            lines.append(f'{label}: ⚠️  Keine gültige ID im Cache')
            return 0, 0, 1, lines

        session = _get_thread_session(auth)

        # Fetch lernabschnittID for the current Schuljahresabschnitt
        lernabschnitt_id = _fetch_lernabschnitt_id(
            base_url, session, schueler_id, id_schuljahresabschnitt
        )
        if lernabschnitt_id is None:
            lines.append(f'{label}: ↷ Kein Lernabschnitt für Abschnitt {id_schuljahresabschnitt} gefunden')
            return 0, 1, 0, lines

        student_created = 0
        student_skipped = 0
        student_failed = 0

        for kuerzel, fach in faecher_map.items():
            if not _fach_gilt_fuer_jahrgang(fach, jahrgang_kuerzel):
                student_skipped += 1
                continue

            fehlstunden_gesamt = RAND.randint(0, 10)
            fehlstunden_un = RAND.randint(0, min(3, fehlstunden_gesamt))

            payload = {
                'lernabschnittID': lernabschnitt_id,
                'fachID': fach['id'],
                'lehrerID': None,
                'wochenstunden': fach.get('wochenstunden', 2),
                'aufZeugnis': fach.get('aufZeugnis', True),
                'note': _random_note(),
                'istGemahnt': False,
                'istEpochal': False,
                'fehlstundenGesamt': fehlstunden_gesamt,
                'fehlstundenUnentschuldigt': fehlstunden_un,
            }

            resp, err = _request(
                session,
                'POST',
                f'{base_url}/schueler/leistungsdaten/create',
                payload=payload,
                success_codes=(200, 201, 409),
                retries=POST_RETRIES,
            )

            if resp is None:
                student_failed += 1
                lines.append(f'{label} - {kuerzel}: ✗ Request-Fehler: {err or "unbekannt"}')
            elif resp.status_code == 409:
                student_skipped += 1
            elif resp.status_code in (200, 201):
                student_created += 1
            else:
                student_failed += 1
                detail = resp.text[:120].replace('\n', ' ')
                lines.append(f'{label} - {kuerzel}: ✗ HTTP {resp.status_code} {detail}')

        if student_failed == 0:
            lines.append(
                f'{label}: ✓ erstellt={student_created}, übersprungen={student_skipped}'
            )

        return student_created, student_skipped, student_failed, lines

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for loc_created, loc_skipped, loc_failed, lines in executor.map(
                process_student,
                enumerate(schueler_list, start=1),
            ):
                created += loc_created
                skipped += loc_skipped
                failed += loc_failed
                for line in lines:
                    print(line)
    finally:
        _close_all_sessions()

    print(f'\nErgebnis: {created} erstellt, {skipped} übersprungen, {failed} fehlgeschlagen')
    if failed == 0:
        print('✓ Leistungsdaten erfolgreich angelegt!')
    else:
        print(f'⚠️  {failed} Leistungsdaten konnten nicht angelegt werden')

    return created, skipped, failed


if __name__ == '__main__':
    from check_server import load_config
    cfg = load_config()
    populate_schueler_leistungsdaten(cfg)
