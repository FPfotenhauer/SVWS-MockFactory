"""
Populate Schüler Leistungsdaten based on Stundentafeln.json.

Steps:
  1. Schulform aus Stammdaten → passende Stundentafel wählen
  2. Alle Fächer der Stundentafel in der DB sicherstellen (erstellen falls fehlend,
     ungültige Schlüssel werden übersprungen und geloggt)
  3. Pro Klasse: Fach→Lehrer-Zuordnung aufbauen
     - Klassenleitung (aus GET /klassen/{id}) erhält mindestens 2 Fächer
     - Restliche Fächer verteilt auf zufällige Lehrer
  4. Pro Schüler: lernabschnittID ermitteln → Leistungsdaten anlegen
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

# Notenverteilung: glockenförmig um 3
_NOTEN = ['1', '1-', '2+', '2', '2-', '3+', '3', '3-', '4+', '4', '4-', '5+', '5', '6']
_NOTEN_WEIGHTS = [1, 2, 3, 5, 5, 6, 8, 6, 5, 5, 3, 2, 2, 1]


def _random_note() -> str:
    return RAND.choices(_NOTEN, weights=_NOTEN_WEIGHTS, k=1)[0]


# ---------------------------------------------------------------------------
# HTTP session management
# ---------------------------------------------------------------------------

def _create_session(auth: HTTPBasicAuth) -> requests.Session:
    s = requests.Session()
    s.auth = auth
    s.verify = False
    return s


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
# Stundentafel-Hilfsfunktionen
# ---------------------------------------------------------------------------

def _load_stundentafeln() -> dict:
    path = Path(__file__).parent / 'katalogdaten' / 'Stundentafeln.json'
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _get_stundentafel_for_schulform(stundentafeln: dict, schulform: str) -> Optional[dict]:
    """
    Gibt die Stundentafel für die gegebene Schulform zurück.
    Probiert auch Präfixe (z.B. 'GY' aus 'GY8') und Fallbacks.
    """
    sf_map = stundentafeln.get('schulformen', {})

    # Direkte Übereinstimmung
    if schulform in sf_map:
        return sf_map[schulform]

    # Präfix-Suche (z.B. schulform='GY8' → 'GY')
    for key in sf_map:
        if schulform.startswith(key):
            return sf_map[key]

    # Fallback: Gymnasium als Standardschulform
    return sf_map.get('GY')


def _collect_fachschluessel(stundentafel_schulform: dict) -> Dict[str, dict]:
    """
    Sammelt alle eindeutigen Fachschlüssel aus allen Jahrgängen.
    Gibt {schluessel: {'text': ..., 'max_wochenstunden': ...}} zurück.
    """
    result: Dict[str, dict] = {}
    for jahrgang_faecher in stundentafel_schulform.get('jahrgaenge', {}).values():
        for fach in jahrgang_faecher:
            schluessel = fach['schluessel']
            if schluessel not in result:
                result[schluessel] = {'text': fach['text'], 'max_wochenstunden': fach['wochenstunden']}
            else:
                # Höchste Wochenstundenzahl über alle Jahrgänge merken (für Fach-Erstellung)
                if fach['wochenstunden'] > result[schluessel]['max_wochenstunden']:
                    result[schluessel]['max_wochenstunden'] = fach['wochenstunden']
    return result


# ---------------------------------------------------------------------------
# Fächer in der DB sicherstellen
# ---------------------------------------------------------------------------

def _fetch_faecher(base_url: str, session: requests.Session) -> List[dict]:
    resp = session.get(f'{base_url}/faecher', timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _try_create_fach(base_url: str, session: requests.Session, schluessel: str, text: str) -> Optional[int]:
    """
    Versucht ein Fach anzulegen. Gibt die neue ID zurück, oder None bei Fehler.
    Ungültige Schlüssel werden vom Server abgelehnt → dann None.
    """
    payload = {
        'id': 0,
        'kuerzel': schluessel,
        'kuerzelStatistik': schluessel,
        'bezeichnung': text,
        'aufZeugnis': True,
        'istFremdsprache': False,
        'istSichtbar': True,
        'istPruefungsordnungsRelevant': True,
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
    code = resp.status_code if resp else 'n/a'
    detail = (resp.text[:100] if resp else err or '').replace('\n', ' ')
    print(f"  ⚠️  Fach '{schluessel}' ({text}): HTTP {code} {detail} → wird übersprungen")
    return None


def _ensure_faecher(
    base_url: str,
    session: requests.Session,
    alle_schluessel: Dict[str, dict],
) -> Dict[str, int]:
    """
    Stellt sicher, dass alle Fächer in der DB vorhanden sind.
    Gibt {schluessel: fach_id} zurück (nur erfolgreich aufgelöste).
    """
    existing = _fetch_faecher(base_url, session)
    existing_by_kuerzel: Dict[str, int] = {f['kuerzel']: f['id'] for f in existing}

    result: Dict[str, int] = {}
    for schluessel, info in alle_schluessel.items():
        if schluessel in existing_by_kuerzel:
            fach_id = existing_by_kuerzel[schluessel]
            print(f"  ✓ Fach '{schluessel}' ({info['text']}) vorhanden (ID {fach_id})")
            result[schluessel] = fach_id
        else:
            fach_id = _try_create_fach(base_url, session, schluessel, info['text'])
            if fach_id is not None:
                print(f"  ✓ Fach '{schluessel}' ({info['text']}) erstellt (ID {fach_id})")
                result[schluessel] = fach_id

    return result


# ---------------------------------------------------------------------------
# Klassen und Lehrer-Zuweisung
# ---------------------------------------------------------------------------

def _fetch_klasse_detail(base_url: str, session: requests.Session, klasse_id: int) -> Optional[dict]:
    resp, _ = _request(session, 'GET', f'{base_url}/klassen/{klasse_id}', success_codes=(200,))
    if resp is None:
        return None
    try:
        return resp.json()
    except Exception:
        return None


def _fetch_jahrgaenge(base_url: str, session: requests.Session) -> Dict[int, str]:
    """Gibt {jahrgang_id: kuerzel} zurück."""
    resp = session.get(f'{base_url}/jahrgaenge', timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return {j['id']: j['kuerzel'] for j in resp.json() if isinstance(j.get('id'), int)}


def _build_klassen_fach_lehrer(
    base_url: str,
    session: requests.Session,
    klassen_cache: List[dict],
    jahrgang_map: Dict[int, str],
    stundentafel_jahrgaenge: Dict[str, List[dict]],
    faecher_db: Dict[str, int],
    alle_lehrer_ids: List[int],
) -> Dict[int, Dict[str, Tuple[int, int]]]:
    """
    Baut pro Klasse eine Zuordnung: fach_schluessel → (fach_id, lehrer_id)

    - Klassenleitung erhält die ersten 2 Fächer
    - Übrige Fächer werden zufällig auf alle verfügbaren Lehrer verteilt
    """
    klassen_fach_lehrer: Dict[int, Dict[str, Tuple[int, int]]] = {}

    for klasse_entry in klassen_cache:
        klasse_id = klasse_entry['id']

        detail = _fetch_klasse_detail(base_url, session, klasse_id)
        if detail is None:
            print(f"  ⚠️  Klasse {klasse_id}: API-Fehler, nutze Fallback-Lehrer")
            klassen_leiter_ids = []
        else:
            klassen_leiter_ids = detail.get('klassenLeitungen') or []

        jahrgang_kuerzel = jahrgang_map.get(detail.get('idJahrgang') if detail else None)
        if jahrgang_kuerzel is None:
            # Fallback: aus Cache-Kürzel ableiten (z.B. "05a" → "05")
            raw_kuerzel = klasse_entry.get('kuerzel', '')
            jahrgang_kuerzel = raw_kuerzel[:2] if raw_kuerzel[:2].isdigit() else raw_kuerzel

        # Fächer für diesen Jahrgang laut Stundentafel
        stunden_faecher = stundentafel_jahrgaenge.get(jahrgang_kuerzel)
        if not stunden_faecher:
            print(f"  ↷ Klasse {klasse_entry.get('kuerzel')} (Jg {jahrgang_kuerzel}): kein Stundentafel-Eintrag → übersprungen")
            klassen_fach_lehrer[klasse_id] = {}
            continue

        # Nur Fächer nehmen, die erfolgreich in der DB aufgelöst wurden
        gueltige_faecher = [
            f for f in stunden_faecher if f['schluessel'] in faecher_db
        ]
        if not gueltige_faecher:
            klassen_fach_lehrer[klasse_id] = {}
            continue

        # Lehrer-Pool aufbauen
        lehrer_pool = list(alle_lehrer_ids)
        RAND.shuffle(lehrer_pool)

        # Klassenleiter bestimmen (ersten nehmen, falls vorhanden)
        klassenleiter_id = klassen_leiter_ids[0] if klassen_leiter_ids else (lehrer_pool[0] if lehrer_pool else None)

        zuordnung: Dict[str, Tuple[int, int]] = {}
        for idx, fach in enumerate(gueltige_faecher):
            schluessel = fach['schluessel']
            fach_id = faecher_db[schluessel]
            wochenstunden = fach['wochenstunden']

            if klassenleiter_id is not None and idx < 2:
                # Klassenleiter bekommt die ersten 2 Fächer
                lehrer_id = klassenleiter_id
            else:
                # Zufälligen Lehrer aus dem Pool wählen
                lehrer_id = lehrer_pool[idx % len(lehrer_pool)] if lehrer_pool else None

            zuordnung[schluessel] = (fach_id, lehrer_id, wochenstunden)

        klassen_fach_lehrer[klasse_id] = zuordnung
        leiter_kuerzel = f"Lehrer-ID {klassenleiter_id}" if klassenleiter_id else "kein Klassenleiter"
        print(
            f"  Klasse {klasse_entry.get('kuerzel')} (Jg {jahrgang_kuerzel}): "
            f"{len(zuordnung)} Fächer, {leiter_kuerzel} → "
            f"{', '.join(f['schluessel'] for f in gueltige_faecher[:2])} (Klassenleitung)"
        )

    return klassen_fach_lehrer


# ---------------------------------------------------------------------------
# Lernabschnitt
# ---------------------------------------------------------------------------

def _fetch_lernabschnitt_id(
    base_url: str,
    session: requests.Session,
    schueler_id: int,
    id_schuljahresabschnitt: int,
) -> Optional[int]:
    resp, _ = _request(
        session, 'GET',
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


# ---------------------------------------------------------------------------
# Cache-Loader
# ---------------------------------------------------------------------------

def _load_cache(filename: str) -> List[dict]:
    path = Path(__file__).parent / filename
    if not path.exists():
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Hauptfunktion
# ---------------------------------------------------------------------------

def populate_schueler_leistungsdaten(config) -> Tuple[int, int, int]:
    """
    Legt Leistungsdaten für alle Schüler aus .schueler_cache.json an.
    Fächerzuordnung erfolgt laut Stundentafeln.json für die Schulform der Schule.

    Returns:
        (created, skipped, failed)
    """
    print('\nLade Schüler aus Cache...')
    schueler_list = _load_cache('.schueler_cache.json')
    if not schueler_list:
        print('❌ .schueler_cache.json nicht gefunden. Bitte zuerst --populate-schueler ausführen.')
        return 0, 0, 0

    lehrer_list = _load_cache('.lehrer_cache.json')
    if not lehrer_list:
        print('❌ .lehrer_cache.json nicht gefunden. Bitte zuerst --populate-lehrer ausführen.')
        return 0, 0, len(schueler_list)

    klassen_cache = _load_cache('.klassen_cache.json')
    if not klassen_cache:
        print('❌ .klassen_cache.json nicht gefunden. Bitte zuerst --populate-classes ausführen.')
        return 0, 0, len(schueler_list)

    alle_lehrer_ids = [l['id'] for l in lehrer_list if isinstance(l.get('id'), int)]

    db = config['database']
    auth = HTTPBasicAuth(db['username'], db['password'])
    base_url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}"

    # ---------------------------------------------------------------------------
    # Setup-Phase (sequenziell)
    # ---------------------------------------------------------------------------
    print('\nLade Schulstammdaten...')
    try:
        with _create_session(auth) as s:
            stammdaten = s.get(f'{base_url}/schule/stammdaten', timeout=REQUEST_TIMEOUT)
            stammdaten.raise_for_status()
            stammdaten = stammdaten.json()
            id_schuljahresabschnitt = stammdaten['idSchuljahresabschnitt']
            schulform = stammdaten.get('schulform') or stammdaten.get('schulformKuerzel') or 'GY'
            print(f'  Schulform: {schulform}, Schuljahresabschnitt: {id_schuljahresabschnitt}')

            # Stundentafel wählen
            stundentafeln = _load_stundentafeln()
            st_schulform = _get_stundentafel_for_schulform(stundentafeln, schulform)
            if st_schulform is None:
                print(f'❌ Keine Stundentafel für Schulform "{schulform}" gefunden.')
                return 0, 0, len(schueler_list)
            print(f'  Stundentafel: {st_schulform.get("bezeichnung", schulform)}')

            # Alle Fachschlüssel aus der Stundentafel
            alle_schluessel = _collect_fachschluessel(st_schulform)
            print(f'  Fachschlüssel in Stundentafel: {", ".join(sorted(alle_schluessel))}')

            # Fächer in DB sicherstellen
            print('\nStelle Fächer in der Datenbank sicher...')
            faecher_db = _ensure_faecher(base_url, s, alle_schluessel)
            print(f'  {len(faecher_db)}/{len(alle_schluessel)} Fächer verfügbar')

            if not faecher_db:
                print('❌ Keine Fächer verfügbar. Abbruch.')
                return 0, 0, len(schueler_list)

            # Jahrgangsmapping laden
            jahrgang_map = _fetch_jahrgaenge(base_url, s)

            # Klassen-Fach-Lehrer-Zuordnung aufbauen
            print('\nBaue Fach→Lehrer-Zuordnung pro Klasse auf...')
            klassen_fach_lehrer = _build_klassen_fach_lehrer(
                base_url, s,
                klassen_cache, jahrgang_map,
                st_schulform.get('jahrgaenge', {}),
                faecher_db, alle_lehrer_ids,
            )

    except requests.exceptions.RequestException as exc:
        print(f'❌ Server nicht erreichbar: {exc}')
        return 0, 0, len(schueler_list)

    # ---------------------------------------------------------------------------
    # Parallelphase: Leistungsdaten pro Schüler anlegen
    # ---------------------------------------------------------------------------
    workers_raw = db.get('leistung_workers', os.getenv('SVWS_LEISTUNG_WORKERS', DEFAULT_WORKERS))
    try:
        workers = max(1, min(16, int(workers_raw)))
    except Exception:
        workers = 1

    total = len(schueler_list)
    created = 0
    skipped = 0
    failed = 0

    print(f'\nVerarbeite {total} Schüler mit {workers} Worker(n)...')

    def process_student(args: Tuple[int, dict]) -> Tuple[int, int, int, List[str]]:
        idx, schueler = args
        lines: List[str] = []

        schueler_id = schueler.get('id')
        vorname = schueler.get('vorname', '')
        nachname = schueler.get('nachname', '')
        klasse_id = schueler.get('idKlasse')
        jahrgang = schueler.get('jahrgangKuerzel', '')
        label = f'[{idx}/{total}] {vorname} {nachname} ({jahrgang})'

        if not isinstance(schueler_id, int):
            lines.append(f'{label}: ⚠️  Ungültige ID im Cache')
            return 0, 0, 1, lines

        # Klassen-Zuordnung bestimmen
        fach_zuordnung = klassen_fach_lehrer.get(klasse_id, {})
        if not fach_zuordnung:
            lines.append(f'{label}: ↷ Keine Fachzuordnung für Klasse {klasse_id}')
            return 0, 1, 0, lines

        session = _get_thread_session(auth)

        # Lernabschnitt-ID ermitteln
        lernabschnitt_id = _fetch_lernabschnitt_id(
            base_url, session, schueler_id, id_schuljahresabschnitt
        )
        if lernabschnitt_id is None:
            lines.append(f'{label}: ↷ Kein Lernabschnitt für Abschnitt {id_schuljahresabschnitt}')
            return 0, 1, 0, lines

        student_created = 0
        student_skipped = 0
        student_failed = 0

        for schluessel, (fach_id, lehrer_id, wochenstunden) in fach_zuordnung.items():
            fehlstunden_gesamt = RAND.randint(0, 10)
            fehlstunden_un = RAND.randint(0, min(3, fehlstunden_gesamt))

            payload = {
                'lernabschnittID': lernabschnitt_id,
                'fachID': fach_id,
                'lehrerID': lehrer_id,
                'wochenstunden': wochenstunden,
                'aufZeugnis': True,
                'note': _random_note(),
                'istGemahnt': False,
                'istEpochal': False,
                'fehlstundenGesamt': fehlstunden_gesamt,
                'fehlstundenUnentschuldigt': fehlstunden_un,
            }

            resp, err = _request(
                session, 'POST',
                f'{base_url}/schueler/leistungsdaten/create',
                payload=payload,
                success_codes=(200, 201, 409),
                retries=POST_RETRIES,
            )

            if resp is None:
                student_failed += 1
                lines.append(f'{label} - {schluessel}: ✗ Fehler: {err or "unbekannt"}')
            elif resp.status_code == 409:
                student_skipped += 1
            elif resp.status_code in (200, 201):
                student_created += 1
            else:
                student_failed += 1
                detail = resp.text[:120].replace('\n', ' ')
                lines.append(f'{label} - {schluessel}: ✗ HTTP {resp.status_code} {detail}')

        if student_failed == 0:
            lines.append(
                f'{label}: ✓ {student_created} erstellt, {student_skipped} übersprungen'
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
