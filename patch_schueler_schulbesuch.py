"""
Patch Schulbesuch for selected students.

For students in year groups 05, 06, 07, 08, 09, 10, EF, Q1, Q2,
load current Schulbesuch via GET /db/{schema}/schueler/{id}/schulbesuch
and PATCH a randomly selected Grundschule from
GET /db/{schema}/schule/schulen.
"""

import json
import random
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import requests
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

RAND = random.Random()
TARGET_JAHRGAENGE = {'05', '06', '07', '08', '09', '10', 'EF', 'Q1', 'Q2'}
KINDERGARTEN_JAHRGAENGE = {'01', '02', '03', '04'}
SCHULBESUCH_PATCH_KEY = 'idVorherigeSchule'
VORIGE_ENTLASSGRUND_ID = 4
VORIGE_ART_LETZTE_VERSETZUNG = '11101'
GRUNDSCHULE_EINSCHULUNGSART_ID = 51
ID_GRUNDSCHULE_JAHRE_EINGANGSPHASE = 2
KUERZEL_GRUNDSCHULE_UEBERGANGSEMPFEHLUNG = 'R/GY'
ALLOWED_SEK1_SCHULFORMEN = {'H', 'R', 'GY', 'GE', 'FW', 'S', 'SK', 'PS'}


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


def fetch_stammdaten(config, auth: HTTPBasicAuth) -> dict:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/schule/stammdaten"
    resp = requests.get(url, auth=auth, verify=False, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, dict) else {}


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


def _entry_text(entry: dict) -> str:
    parts = []
    for key in ('name', 'bezeichnung', 'bezeichnung1', 'bezeichnung2', 'kurzbezeichnung', 'kuerzel'):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return ' '.join(parts).casefold()


def _extract_schulform_hints(entry: dict) -> Set[str]:
    hints: Set[str] = set()
    for key in ('schulform', 'schulformKrz', 'kuerzelSchulform', 'schulformkuerzel'):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            hints.add(value.strip().upper())
    return hints


def is_grundschule(entry: dict) -> bool:
    id_schulform = entry.get('idSchulform')
    if isinstance(id_schulform, int) and id_schulform == 3000:
        return True
    if isinstance(id_schulform, str) and id_schulform.isdigit() and int(id_schulform) == 3000:
        return True

    schulform_hints = _extract_schulform_hints(entry)
    if schulform_hints.intersection({'G', 'GG', 'EG', 'KG', 'GS'}):
        return True

    return 'grundschule' in _entry_text(entry)


def fetch_grundschulen(config, auth: HTTPBasicAuth) -> List[int]:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/schule/schulen"
    resp = requests.get(url, auth=auth, verify=False, timeout=20)
    resp.raise_for_status()

    ids: List[int] = []
    for entry in resp.json():
        if not isinstance(entry, dict):
            continue
        if not is_grundschule(entry):
            continue
        sid = extract_id(entry)
        if sid is not None:
            ids.append(sid)

    unique_ids: List[int] = []
    seen = set()
    for sid in ids:
        if sid in seen:
            continue
        seen.add(sid)
        unique_ids.append(sid)

    return unique_ids


def fetch_kindergaerten(config, auth: HTTPBasicAuth) -> List[int]:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/kindergaerten"
    try:
        resp = requests.get(url, auth=auth, verify=False, timeout=20)
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        print(f"⚠️  Kindergärten konnten nicht geladen werden: {exc}")
        return []

    ids: List[int] = []
    for entry in resp.json():
        if not isinstance(entry, dict):
            continue
        kid = extract_id(entry)
        if kid is not None:
            ids.append(kid)

    unique_ids: List[int] = []
    seen = set()
    for kid in ids:
        if kid in seen:
            continue
        seen.add(kid)
        unique_ids.append(kid)

    return unique_ids


def fetch_schulbesuch(config, auth: HTTPBasicAuth, schueler_id: int) -> dict:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/schueler/{schueler_id}/schulbesuch"
    resp = requests.get(url, auth=auth, verify=False, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, dict) else {}


def resolve_vorige_entlassdatum(aufnahmedatum: Optional[str]) -> str:
    if isinstance(aufnahmedatum, str) and len(aufnahmedatum) >= 4 and aufnahmedatum[:4].isdigit():
        year = int(aufnahmedatum[:4])
    else:
        year = 2023
    return f'{year:04d}-07-31'


def resolve_year_from_aufnahmedatum(aufnahmedatum: Optional[str]) -> int:
    if isinstance(aufnahmedatum, str) and len(aufnahmedatum) >= 4 and aufnahmedatum[:4].isdigit():
        return int(aufnahmedatum[:4])
    return date.today().year


def resolve_sek1_erste_schulform(stammdaten: dict) -> str:
    schulform = stammdaten.get('schulform')
    if isinstance(schulform, str):
        normalized = schulform.strip().upper()
        if normalized in ALLOWED_SEK1_SCHULFORMEN:
            return normalized
    return 'R'


def resolve_grundschule_einschulungsjahr(
    geburtsdatum: Optional[str],
    schulbesuch: dict,
) -> int:
    if isinstance(geburtsdatum, str) and len(geburtsdatum) >= 4 and geburtsdatum[:4].isdigit():
        return int(geburtsdatum[:4]) + 6

    existing = schulbesuch.get('grundschuleEinschulungsjahr')
    if isinstance(existing, int):
        return existing
    if isinstance(existing, str) and existing.isdigit():
        return int(existing)

    return date.today().year - 4


def patch_schulbesuch(
    config,
    auth: HTTPBasicAuth,
    schueler_id: int,
    grundschule_id: int,
    vorige_entlassdatum: str,
    grundschule_einschulungsjahr: int,
    sek1_wechsel: int,
    sek1_erste_schulform: str,
) -> requests.Response:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/schueler/{schueler_id}/schulbesuch"
    payload = {
        SCHULBESUCH_PATCH_KEY: grundschule_id,
        'vorigeEntlassgrundID': VORIGE_ENTLASSGRUND_ID,
        'vorigeArtLetzteVersetzung': VORIGE_ART_LETZTE_VERSETZUNG,
        'vorigeEntlassdatum': vorige_entlassdatum,
        'grundschuleEinschulungsjahr': grundschule_einschulungsjahr,
        'grundschuleEinschulungsartID': GRUNDSCHULE_EINSCHULUNGSART_ID,
        'idGrundschuleJahreEingangsphase': ID_GRUNDSCHULE_JAHRE_EINGANGSPHASE,
        'kuerzelGrundschuleUebergangsempfehlung': KUERZEL_GRUNDSCHULE_UEBERGANGSEMPFEHLUNG,
        'sekIWechsel': sek1_wechsel,
        'sekIErsteSchulform': sek1_erste_schulform,
    }

    return requests.patch(url, json=payload, auth=auth, verify=False, timeout=20)


def patch_kindergarten(
    config,
    auth: HTTPBasicAuth,
    schueler_id: int,
    kindergarten_id: int,
    dauerbesuch_id: int,
) -> requests.Response:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/schueler/{schueler_id}/schulbesuch"
    payload = {
        'idKindergarten': kindergarten_id,
        'idDauerKindergartenbesuch': dauerbesuch_id,
    }
    return requests.patch(url, json=payload, auth=auth, verify=False, timeout=20)


def patch_schueler_schulbesuch(config) -> Tuple[int, int, int]:
    print('\nLade Schüler aus Cache...')
    schueler_list = load_cache()
    if not schueler_list:
        print('⚠️  Keine Schüler im Cache gefunden.')
        return 0, 0, 0

    db = config['database']
    auth = HTTPBasicAuth(db['username'], db['password'])

    print('Lade Schulstammdaten...')
    try:
        stammdaten = fetch_stammdaten(config, auth)
    except requests.exceptions.RequestException as exc:
        print(f"❌ Schulstammdaten konnten nicht geladen werden: {exc}")
        return 0, 0, len(schueler_list)

    sek1_erste_schulform = resolve_sek1_erste_schulform(stammdaten)

    print('Lade Jahrgänge...')
    try:
        jahrgang_id_to_kuerzel = fetch_jahrgaenge(config, auth)
    except requests.exceptions.RequestException as exc:
        print(f"❌ Jahrgänge konnten nicht geladen werden: {exc}")
        return 0, 0, len(schueler_list)

    print('Lade Grundschulen...')
    try:
        grundschulen_ids = fetch_grundschulen(config, auth)
    except requests.exceptions.RequestException as exc:
        print(f"❌ Schulen konnten nicht geladen werden: {exc}")
        return 0, 0, len(schueler_list)

    if not grundschulen_ids:
        print('❌ Keine Grundschulen im Katalog gefunden.')
        return 0, 0, len(schueler_list)

    print('Lade Kindergärten...')
    try:
        kindergaerten_ids = fetch_kindergaerten(config, auth)
    except requests.exceptions.RequestException as exc:
        print(f"⚠️  Kindergärten-API-Fehler: {exc}")
        kindergaerten_ids = []

    total = len(schueler_list)
    print(f'Gefunden: {total} Schüler im Cache')
    print(f'Verfügbare Grundschulen: {len(grundschulen_ids)}')
    print(f'Verfügbare Kindergärten: {len(kindergaerten_ids)}')
    print('Zieljahrgänge (Grundschule): 05, 06, 07, 08, 09, 10, EF, Q1, Q2')
    print('Zieljahrgänge (Kindergarten): 01, 02, 03, 04')

    patched = 0
    skipped = 0
    failed = 0

    for idx, schueler in enumerate(schueler_list, start=1):
        schueler_id = extract_id(schueler)
        vorname = schueler.get('vorname', '')
        nachname = schueler.get('nachname', '')

        if schueler_id is None:
            failed += 1
            print(f"[{idx}/{total}] {vorname} {nachname}: ⚠️  Keine ID im Cache")
            continue

        jahrgang_kuerzel = resolve_jahrgang_kuerzel(schueler, jahrgang_id_to_kuerzel)

        # Handle Kindergarten for grades 01-04
        if jahrgang_kuerzel in KINDERGARTEN_JAHRGAENGE:
            if not kindergaerten_ids:
                skipped += 1
                print(f"[{idx}/{total}] {vorname} {nachname}: ↷ Keine Kindergärten verfügbar")
                continue

            try:
                kindergarten_id = RAND.choice(kindergaerten_ids)
                dauerbesuch_id = RAND.choice([4, 5])

                patch_resp = patch_kindergarten(
                    config,
                    auth,
                    schueler_id,
                    kindergarten_id,
                    dauerbesuch_id,
                )

                if patch_resp.status_code in (200, 201, 204):
                    patched += 1
                    print(
                        f"[{idx}/{total}] {vorname} {nachname} ({jahrgang_kuerzel}): "
                        f"✓ Kindergarten {kindergarten_id}, Besuchsdauer {dauerbesuch_id}"
                    )
                else:
                    failed += 1
                    error_text = patch_resp.text[:180].replace('\n', ' ')
                    print(
                        f"[{idx}/{total}] {vorname} {nachname} ({jahrgang_kuerzel}): "
                        f"✗ PATCH fehlgeschlagen (HTTP {patch_resp.status_code}) - {error_text}"
                    )
            except requests.exceptions.RequestException as exc:
                failed += 1
                print(f"[{idx}/{total}] {vorname} {nachname} ({jahrgang_kuerzel}): ✗ Request-Fehler: {exc}")
            continue

        # Handle Grundschule for grades 05-Q2
        if jahrgang_kuerzel not in TARGET_JAHRGAENGE:
            skipped += 1
            print(f"[{idx}/{total}] {vorname} {nachname}: ↷ Jahrgang {jahrgang_kuerzel or '-'} nicht im Zielbereich")
            continue

        try:
            schulbesuch = fetch_schulbesuch(config, auth, schueler_id)
            grundschule_id = RAND.choice(grundschulen_ids)
            vorige_entlassdatum = resolve_vorige_entlassdatum(schueler.get('aufnahmedatum'))
            sek1_wechsel = resolve_year_from_aufnahmedatum(schueler.get('aufnahmedatum'))
            grundschule_einschulungsjahr = resolve_grundschule_einschulungsjahr(
                schueler.get('geburtsdatum'),
                schulbesuch,
            )

            patch_resp = patch_schulbesuch(
                config,
                auth,
                schueler_id,
                grundschule_id,
                vorige_entlassdatum,
                grundschule_einschulungsjahr,
                sek1_wechsel,
                sek1_erste_schulform,
            )
            if patch_resp.status_code in (200, 201, 204):
                patched += 1
                print(
                    f"[{idx}/{total}] {vorname} {nachname} ({jahrgang_kuerzel}): "
                    f"✓ {SCHULBESUCH_PATCH_KEY}={grundschule_id}, "
                    f"vorigeEntlassdatum={vorige_entlassdatum}, "
                    f"grundschuleEinschulungsjahr={grundschule_einschulungsjahr}, "
                    f"sekIWechsel={sek1_wechsel}, sekIErsteSchulform={sek1_erste_schulform}"
                )
            else:
                failed += 1
                error_text = patch_resp.text[:220].replace('\n', ' ')
                print(
                    f"[{idx}/{total}] {vorname} {nachname} ({jahrgang_kuerzel}): "
                    f"✗ PATCH fehlgeschlagen (HTTP {patch_resp.status_code}) - {error_text}"
                )
        except requests.exceptions.RequestException as exc:
            failed += 1
            print(f"[{idx}/{total}] {vorname} {nachname} ({jahrgang_kuerzel}): ✗ Request-Fehler: {exc}")

    print(f"\nErgebnis: {patched} gepatcht, {skipped} übersprungen, {failed} fehlgeschlagen")
    if failed == 0:
        print('✓ Schüler-Schulbesuch erfolgreich aktualisiert!')
    else:
        print(f'⚠️  {failed} Schüler konnten nicht gepatcht werden')

    return patched, skipped, failed


if __name__ == '__main__':
    from check_server import load_config

    cfg = load_config()
    patch_schueler_schulbesuch(cfg)
