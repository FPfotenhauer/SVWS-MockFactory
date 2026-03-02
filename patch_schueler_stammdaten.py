"""
Patch K_Schueler stammdaten for already created students.

Reads student base data from .schueler_cache.json (created by populate_schueler.py)
and sends PATCH batches to /db/{schema}/schueler/stammdaten.

Distribution rules:
- Wohnort: 80% school city, 20% other cities from /orte
- Staatsangehoerigkeit: 80% DEU, 20% other from nationalitaeten catalog
- Status: 95% status=2, 5% status=0
"""

import csv
import json
import random
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings for self-signed certificates
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

RAND = random.Random()


def slugify_mail_part(text: str) -> str:
    replacements = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
        'Ä': 'ae', 'Ö': 'oe', 'Ü': 'ue',
    }
    lowered = ''.join(replacements.get(ch, ch) for ch in (text or '').lower())
    cleaned = ''.join(ch for ch in lowered if ch.isalnum() or ch == '-')
    return cleaned or 'x'


def load_cache() -> List[dict]:
    cache_file = Path(__file__).parent / '.schueler_cache.json'
    if not cache_file.exists():
        print(f"❌ Cache-Datei nicht gefunden: {cache_file}")
        print('   Bitte zuerst --populate-schueler ausführen!')
        return []

    with open(cache_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_streets_by_city() -> Dict[str, List[str]]:
    path = Path(__file__).parent / 'katalogdaten' / 'Strassen.csv'
    result: Dict[str, List[str]] = {}
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            city = (row.get('Ort') or '').strip()
            street = (row.get('Strasse') or '').strip().rstrip(',')
            if not city or not street:
                continue
            result.setdefault(city.casefold(), []).append(street)
    return result


def load_streets_by_locality_postal(required_pairs: Optional[set] = None) -> Dict[Tuple[str, str], List[str]]:
    path = Path(__file__).parent / 'katalogdaten' / 'streets.csv'
    if not path.exists():
        return {}

    result: Dict[Tuple[str, str], List[str]] = {}
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            locality = (row.get('Locality') or '').strip()
            postal_raw = (row.get('PostalCode') or '').strip()
            street = (row.get('Name') or '').strip().strip('"')
            if not locality or not postal_raw or not street:
                continue

            digits = ''.join(ch for ch in postal_raw if ch.isdigit())
            if not digits:
                continue
            postal = digits.zfill(5)

            key = (locality.casefold(), postal)
            if required_pairs is not None and key not in required_pairs:
                continue

            result.setdefault(key, []).append(street)

    # De-duplicate while preserving order
    for key, streets in result.items():
        seen = set()
        unique = []
        for street in streets:
            marker = street.casefold()
            if marker in seen:
                continue
            seen.add(marker)
            unique.append(street)
        result[key] = unique

    return result


def load_streets_by_postal(required_postals: Optional[set] = None) -> Dict[str, List[str]]:
    path = Path(__file__).parent / 'katalogdaten' / 'streets.csv'
    if not path.exists():
        return {}

    result: Dict[str, List[str]] = {}
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            postal_raw = (row.get('PostalCode') or '').strip()
            street = (row.get('Name') or '').strip().strip('"')
            if not postal_raw or not street:
                continue

            digits = ''.join(ch for ch in postal_raw if ch.isdigit())
            if not digits:
                continue
            postal = digits.zfill(5)
            if required_postals is not None and postal not in required_postals:
                continue

            result.setdefault(postal, []).append(street)

    for postal, streets in result.items():
        seen = set()
        unique = []
        for street in streets:
            marker = street.casefold()
            if marker in seen:
                continue
            seen.add(marker)
            unique.append(street)
        result[postal] = unique

    return result


def fetch_stammdaten(config) -> dict:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/schule/stammdaten"
    resp = requests.get(
        url,
        auth=HTTPBasicAuth(db['username'], db['password']),
        verify=False,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_orte(config) -> List[dict]:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/orte"
    resp = requests.get(
        url,
        auth=HTTPBasicAuth(db['username'], db['password']),
        verify=False,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_nationalitaeten(config) -> List[dict]:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/schule/allgemein/nationalitaeten"
    resp = requests.get(
        url,
        auth=HTTPBasicAuth(db['username'], db['password']),
        verify=False,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_haltestellen(config) -> List[dict]:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/haltestellen"
    resp = requests.get(
        url,
        auth=HTTPBasicAuth(db['username'], db['password']),
        verify=False,
        timeout=20,
    )
    if resp.status_code >= 400:
        return []
    try:
        return resp.json()
    except Exception:
        return []


def fetch_fahrschuelerarten(config) -> List[dict]:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/schueler/fahrschuelerarten"
    resp = requests.get(
        url,
        auth=HTTPBasicAuth(db['username'], db['password']),
        verify=False,
        timeout=20,
    )
    if resp.status_code >= 400:
        return []
    try:
        return resp.json()
    except Exception:
        return []


def extract_id(entry: dict) -> Optional[int]:
    value = entry.get('id')
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def ort_id(entry: dict) -> Optional[int]:
    value = entry.get('id')
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def ort_name(entry: dict) -> str:
    for key in ('ortsname', 'Ort', 'ort', 'bezeichnung'):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ''


def ort_postal_code(entry: dict) -> Optional[str]:
    for key in ('plz', 'PLZ', 'postleitzahl', 'postalCode'):
        value = entry.get(key)
        if isinstance(value, int):
            return str(value).zfill(5)
        if isinstance(value, str):
            digits = ''.join(ch for ch in value if ch.isdigit())
            if digits:
                return digits.zfill(5)
    return None


def _extract_street_names_from_openplz_payload(payload) -> List[str]:
    entries = []
    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        for key in ('items', 'content', 'results', 'data'):
            value = payload.get(key)
            if isinstance(value, list):
                entries = value
                break

    streets: List[str] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        for key in ('name', 'street', 'strasse', 'streetName'):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                streets.append(value.strip())
                break

    # de-duplicate while preserving order
    seen = set()
    unique: List[str] = []
    for street in streets:
        marker = street.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(street)
    return unique


def fetch_openplz_streets(
    locality: str,
    postal_code: str,
    cache: Dict[Tuple[str, str], Tuple[List[str], str]],
    budget_state: Dict[str, int],
    timeout: int = 3,
) -> Tuple[List[str], str]:
    key = (locality.casefold(), postal_code)
    if key in cache:
        streets, mode = cache[key]
        return streets, f'cache:{mode}'

    # Global request budget to avoid long-running hangs when many different PLZ/Orte are sampled
    if budget_state['used'] >= budget_state['limit']:
        cache[key] = ([], 'budget_exceeded')
        return [], 'budget_exceeded'

    url = 'https://openplzapi.org/de/Streets'
    params = {
        'locality': locality,
        'postalCode': postal_code,
        'page': 1,
        'pageSize': 50,
    }

    try:
        budget_state['used'] += 1
        resp = requests.get(url, params=params, timeout=(2, timeout))
        if resp.status_code >= 400:
            cache[key] = ([], 'http_error')
            return [], 'http_error'
        streets = _extract_street_names_from_openplz_payload(resp.json())
        mode = 'locality'

        # Fallback query: postal code only (locality can be too strict in some datasets)
        if not streets:
            params_postal_only = {
                'postalCode': postal_code,
                'page': 1,
                'pageSize': 50,
            }
            if budget_state['used'] >= budget_state['limit']:
                cache[key] = ([], 'budget_exceeded')
                return [], 'budget_exceeded'
            budget_state['used'] += 1
            resp2 = requests.get(url, params=params_postal_only, timeout=(2, timeout))
            if resp2.status_code < 400:
                streets = _extract_street_names_from_openplz_payload(resp2.json())
                mode = 'postal_only' if streets else 'none'
            else:
                mode = 'none'

        cache[key] = (streets, mode)
        return streets, mode
    except Exception:
        cache[key] = ([], 'exception')
        return [], 'exception'


def get_school_ort_id(stammdaten: dict, orte: List[dict]) -> Optional[int]:
    # Prefer direct ID if present
    for key in ('ortID', 'wohnortID', 'idOrt', 'idOrtSchule'):
        value = stammdaten.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)

    # Fallback by name matching
    school_ort_name = ''
    for key in ('ort', 'ortsname', 'schulort', 'bezeichnungOrt'):
        value = stammdaten.get(key)
        if isinstance(value, str) and value.strip():
            school_ort_name = value.strip()
            break

    if not school_ort_name:
        return None

    target = school_ort_name.casefold()
    for entry in orte:
        if ort_name(entry).casefold() == target:
            return ort_id(entry)

    return None


def extract_nat_code(entry: dict) -> Optional[str]:
    for key in ('kuerzel', 'iso3', 'code', 'id', 'staat'):
        value = entry.get(key)
        if isinstance(value, str) and len(value.strip()) == 3 and value.strip().isalpha():
            return value.strip().upper()
    return None


def split_nationalitaeten(nationalitaeten: List[dict]) -> Tuple[Optional[str], List[str]]:
    codes = []
    for item in nationalitaeten:
        code = extract_nat_code(item)
        if code:
            codes.append(code)

    unique_codes = sorted(set(codes))
    deu = 'DEU' if 'DEU' in unique_codes else None
    others = [c for c in unique_codes if c != 'DEU']
    return deu, others


def random_house_number() -> str:
    return str(RAND.randint(1, 220))


def random_phone() -> str:
    return f"012345-{RAND.randint(100000, 999999)}"


def random_mobile() -> str:
    return f"0177-555-{RAND.randint(1000, 9999)}"


def unique_email_local(vorname: str, nachname: str, used_locals: set) -> str:
    first = slugify_mail_part(vorname)
    last = slugify_mail_part(nachname)

    base = f"{first}.{last}"
    if base not in used_locals:
        used_locals.add(base)
        return base

    counter = 1
    while True:
        candidate = f"{first}{counter}.{last}"
        if candidate not in used_locals:
            used_locals.add(candidate)
            return candidate
        counter += 1


def format_schuelerausweis_id(running_number: int) -> str:
    return f"AS-{running_number:010d}"


def random_language_code() -> str:
    # ISO 639-3 examples
    return RAND.choice(['deu', 'tur', 'ara', 'eng', 'rus', 'pol', 'sqi', 'ita', 'fra', 'oji'])


def parse_birth_year(geburtsdatum: Optional[str]) -> int:
    if isinstance(geburtsdatum, str) and len(geburtsdatum) >= 4 and geburtsdatum[:4].isdigit():
        return int(geburtsdatum[:4])
    return date.today().year - 10


def bool_with_probability(prob_true: float) -> bool:
    return RAND.random() < prob_true


def pick_wohnort(
    school_ort_id: Optional[int],
    all_ort_ids: List[int],
) -> Optional[int]:
    if not all_ort_ids:
        return school_ort_id

    if school_ort_id is None:
        return RAND.choice(all_ort_ids)

    other_ids = [oid for oid in all_ort_ids if oid != school_ort_id]
    if other_ids and RAND.random() >= 0.80:
        return RAND.choice(other_ids)
    return school_ort_id


def pick_staatsangehoerigkeit(deu_code: Optional[str], other_codes: List[str]) -> Optional[str]:
    if deu_code and RAND.random() < 0.80:
        return deu_code

    if other_codes:
        return RAND.choice(other_codes)

    return deu_code


def pick_status() -> int:
    return 2 if RAND.random() < 0.95 else 0


def is_full_age(geburtsdatum: Optional[str]) -> bool:
    if not isinstance(geburtsdatum, str) or len(geburtsdatum) < 10:
        return False
    try:
        year = int(geburtsdatum[0:4])
        month = int(geburtsdatum[5:7])
        day = int(geburtsdatum[8:10])
        birth = date(year, month, day)
        today = date.today()
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        return age >= 18
    except Exception:
        return False


def build_payload_entry(
    schueler: dict,
    schuelerausweis_number: int,
    ort_id_to_name: Dict[int, str],
    ort_id_to_postal: Dict[int, str],
    ort_name_to_ids: Dict[str, List[int]],
    school_ort_id: Optional[int],
    all_ort_ids: List[int],
    streets_by_locality_postal: Dict[Tuple[str, str], List[str]],
    streets_by_postal: Dict[str, List[str]],
    streets_by_city: Dict[str, List[str]],
    deu_code: Optional[str],
    other_nat_codes: List[str],
    haltestellen_ids: List[int],
    fahrschuelerarten_ids: List[int],
    use_openplz_streets: bool,
    openplz_cache: Dict[Tuple[str, str], Tuple[List[str], str]],
    openplz_budget_state: Dict[str, int],
    street_source_stats: Dict[str, int],
    openplz_mode_stats: Dict[str, int],
    postal_miss_stats: Dict[str, int],
    switched_postal_stats: Dict[str, int],
    used_email_locals: set,
) -> Optional[dict]:
    schueler_id = schueler.get('id')
    if not isinstance(schueler_id, int):
        return None

    wohnort_id = pick_wohnort(school_ort_id, all_ort_ids)
    wohnort_name = ort_id_to_name.get(wohnort_id or -1, '')
    wohnort_postal = ort_id_to_postal.get(wohnort_id or -1)

    # Primary source: exact locality + postal code mapping from streets.csv
    if wohnort_name and wohnort_postal:
        key = (wohnort_name.casefold(), wohnort_postal)
        mapped_streets = streets_by_locality_postal.get(key, [])
        if mapped_streets:
            selected_street = RAND.choice(mapped_streets)
            street_source_stats['csv_postal_locality'] = street_source_stats.get('csv_postal_locality', 0) + 1
            city_streets = mapped_streets
        else:
            city_streets = []
    else:
        city_streets = []

    # Secondary source: PLZ-only mapping from local streets.csv
    # (preferred over external OpenPLZ lookup)
    if not city_streets and wohnort_postal:
        postal_only_streets = streets_by_postal.get(wohnort_postal)
        if postal_only_streets:
            city_streets = postal_only_streets
            street_source_stats['csv_postal_only'] = street_source_stats.get('csv_postal_only', 0) + 1

    # External fallback: OpenPLZ only when local CSV mappings have no match
    openplz_mode = 'not_used'
    if use_openplz_streets and wohnort_name and wohnort_postal and not city_streets:
        city_streets, openplz_mode = fetch_openplz_streets(
            locality=wohnort_name,
            postal_code=wohnort_postal,
            cache=openplz_cache,
            budget_state=openplz_budget_state,
        )
        openplz_mode_stats[openplz_mode] = openplz_mode_stats.get(openplz_mode, 0) + 1

        # If initial postal code has no street matches, try alternative postals of same locality.
        if not city_streets:
            locality_key = wohnort_name.casefold()
            candidate_ids = ort_name_to_ids.get(locality_key, [])
            for candidate_id in candidate_ids:
                if candidate_id == wohnort_id:
                    continue
                candidate_postal = ort_id_to_postal.get(candidate_id)
                if not candidate_postal or candidate_postal == wohnort_postal:
                    continue

                candidate_streets, candidate_mode = fetch_openplz_streets(
                    locality=wohnort_name,
                    postal_code=candidate_postal,
                    cache=openplz_cache,
                    budget_state=openplz_budget_state,
                )
                openplz_mode_stats[candidate_mode] = openplz_mode_stats.get(candidate_mode, 0) + 1

                if candidate_streets:
                    previous_postal = wohnort_postal
                    wohnort_id = candidate_id
                    wohnort_postal = candidate_postal
                    city_streets = candidate_streets
                    switched_postal_stats[previous_postal] = switched_postal_stats.get(previous_postal, 0) + 1
                    street_source_stats['openplz_postal_switch'] = street_source_stats.get('openplz_postal_switch', 0) + 1
                    break

            wohnort_name = ort_id_to_name.get(wohnort_id or -1, wohnort_name)

    # If we know a postal code, enforce postal-compatible street selection
    # and avoid broad city-only fallback from Strassen.csv.
    if woonort_postal_and_has_street := bool(wohnort_postal and city_streets):
        selected_street = RAND.choice(city_streets)
        if openplz_mode != 'not_used':
            street_source_stats['openplz'] = street_source_stats.get('openplz', 0) + 1
    elif wohnort_postal and not city_streets:
        # Last fallback: city-based street list to avoid "Unbekannt"
        city_key = wohnort_name.casefold()
        city_fallback_streets = streets_by_city.get(city_key)
        if not city_fallback_streets:
            city_key_alt = city_key.replace('ß', 'ss')
            city_fallback_streets = streets_by_city.get(city_key_alt)

        if city_fallback_streets:
            selected_street = RAND.choice(city_fallback_streets)
            street_source_stats['csv_city_fallback_with_plz'] = street_source_stats.get('csv_city_fallback_with_plz', 0) + 1
            postal_miss_stats[wohnort_postal] = postal_miss_stats.get(wohnort_postal, 0) + 1
        else:
            selected_street = 'Unbekannt'
            street_source_stats['unknown_with_plz'] = street_source_stats.get('unknown_with_plz', 0) + 1
            postal_miss_stats[wohnort_postal] = postal_miss_stats.get(wohnort_postal, 0) + 1
    else:
        city_key = wohnort_name.casefold()
        if not city_streets:
            city_streets = streets_by_city.get(city_key)
        if not city_streets:
            # Try simple replacements for common spelling differences
            city_key_alt = city_key.replace('ß', 'ss')
            city_streets = streets_by_city.get(city_key_alt)

        if not city_streets:
            # fallback: any city streets
            all_streets = [s for streets in streets_by_city.values() for s in streets]
            city_streets = all_streets if all_streets else ['Hauptstraße']

        selected_street = RAND.choice(city_streets)
        street_source_stats['csv_fallback'] = street_source_stats.get('csv_fallback', 0) + 1

    geburtsdatum = schueler.get('geburtsdatum')
    birth_year = parse_birth_year(geburtsdatum)

    hat_migrationshintergrund = bool_with_probability(0.25)
    zuzugsjahr = None
    if hat_migrationshintergrund:
        start = min(date.today().year, birth_year + 1)
        end = date.today().year
        zuzugsjahr = RAND.randint(start, end) if start <= end else end

    staatsangehoerigkeit = pick_staatsangehoerigkeit(deu_code, other_nat_codes)
    geburtsland = pick_staatsangehoerigkeit(deu_code, other_nat_codes) or 'DEU'
    geburtsland_vater = pick_staatsangehoerigkeit(deu_code, other_nat_codes) or geburtsland
    geburtsland_mutter = pick_staatsangehoerigkeit(deu_code, other_nat_codes) or geburtsland

    status = pick_status()
    haltestelle_id = RAND.choice(haltestellen_ids) if haltestellen_ids else None
    fahrschuelerart_id = RAND.choice(fahrschuelerarten_ids) if fahrschuelerarten_ids else None

    religion_id = schueler.get('idReligion')
    if not isinstance(religion_id, int):
        religion_id = None

    vorname = schueler.get('vorname') or ''
    nachname = schueler.get('nachname') or ''
    email_local = unique_email_local(vorname, nachname, used_email_locals)

    entry = {
        'id': schueler_id,
        'foto': '',
        'nachname': nachname,
        'vorname': vorname,
        'alleVornamen': schueler.get('alleVornamen'),
        'geschlecht': schueler.get('geschlecht'),
        'geburtsdatum': geburtsdatum,
        'geburtsort': wohnort_name or 'Unbekannt',
        'geburtsname': nachname,
        'strassenname': selected_street,
        'hausnummer': random_house_number(),
        'hausnummerZusatz': '',
        'wohnortID': wohnort_id,
        'ortsteilID': None,
        'telefon': random_phone(),
        'telefonMobil': random_mobile(),
        'emailPrivat': f"{email_local}@privat.schueler.example.com",
        'emailSchule': f"{email_local}@schulisch.schueler.example.com",
        'staatsangehoerigkeitID': staatsangehoerigkeit,
        'staatsangehoerigkeit2ID': None,
        'religionID': religion_id,
        'druckeKonfessionAufZeugnisse': False,
        'religionabmeldung': None,
        'religionanmeldung': None,
        'hatMigrationshintergrund': hat_migrationshintergrund,
        'zuzugsjahr': zuzugsjahr,
        'geburtsland': geburtsland,
        'verkehrspracheFamilie': random_language_code(),
        'geburtslandVater': geburtsland_vater,
        'geburtslandMutter': geburtsland_mutter,
        'status': status,
        'istDuplikat': False,
        'externeSchulNr': None,
        'idSchuelerausweis': format_schuelerausweis_id(schuelerausweis_number),
        'fahrschuelerArtID': fahrschuelerart_id,
        'haltestelleID': haltestelle_id,
        'anmeldedatum': schueler.get('anmeldedatum'),
        'aufnahmedatum': schueler.get('aufnahmedatum'),
        'istVolljaehrig': is_full_age(geburtsdatum),
        'istSchulpflichtErfuellt': False,
        'istBerufsschulpflichtErfuellt': False,
        'hatMasernimpfnachweis': bool_with_probability(0.85),
        'keineAuskunftAnDritte': False,
        'erhaeltSchuelerBAFOEG': False,
        'erhaeltMeisterBAFOEG': False,
        'beginnBildungsgang': None,
        'dauerBildungsgang': None,
        'beruf': None,
    }

    return entry


def chunked(items: List[dict], size: int) -> List[List[dict]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def patch_schueler_stammdaten(config, batch_size: int = 200) -> Tuple[int, int]:
    print('\nLade Schüler aus Cache...')
    schueler_list = load_cache()
    if not schueler_list:
        print('⚠️  Keine Schüler im Cache gefunden.')
        return 0, 0

    db = config['database']
    auth = HTTPBasicAuth(db['username'], db['password'])

    try:
        stammdaten = fetch_stammdaten(config)
        orte = fetch_orte(config)
        nationalitaeten = fetch_nationalitaeten(config)
    except Exception as e:
        print(f'❌ Fehler beim Laden von Stammdaten/Katalogen: {e}')
        return 0, 1

    haltestellen = fetch_haltestellen(config)
    haltestellen_ids = [hid for h in haltestellen for hid in [extract_id(h)] if hid is not None]
    fahrschuelerarten = fetch_fahrschuelerarten(config)
    fahrschuelerarten_ids = [fid for f in fahrschuelerarten for fid in [extract_id(f)] if fid is not None]

    ort_id_to_name = {
        oid: ort_name(entry)
        for entry in orte
        for oid in [ort_id(entry)]
        if oid is not None
    }
    ort_id_to_postal = {
        oid: postal
        for entry in orte
        for oid in [ort_id(entry)]
        for postal in [ort_postal_code(entry)]
        if oid is not None and postal is not None
    }
    all_ort_ids = list(ort_id_to_name.keys())
    ort_name_to_ids: Dict[str, List[int]] = {}
    for oid, oname in ort_id_to_name.items():
        if oname:
            ort_name_to_ids.setdefault(oname.casefold(), []).append(oid)

    school_ort_id = get_school_ort_id(stammdaten, orte)

    # To keep runtime bounded, sample a limited pool of non-school locations
    # instead of drawing from all available Orte.
    sampled_ort_ids = all_ort_ids
    if school_ort_id is not None and len(all_ort_ids) > 120:
        others = [oid for oid in all_ort_ids if oid != school_ort_id]
        sampled_others = RAND.sample(others, min(80, len(others)))
        sampled_ort_ids = [school_ort_id] + sampled_others

    required_pairs = {
        (ort_id_to_name[oid].casefold(), ort_id_to_postal[oid])
        for oid in sampled_ort_ids
        if oid in ort_id_to_name and oid in ort_id_to_postal and ort_id_to_name[oid]
    }
    required_postals = {
        ort_id_to_postal[oid]
        for oid in sampled_ort_ids
        if oid in ort_id_to_postal
    }

    streets_by_locality_postal = load_streets_by_locality_postal(required_pairs=required_pairs)
    streets_by_postal = load_streets_by_postal(required_postals=required_postals)
    streets_by_city = load_streets_by_city()
    deu_code, other_nat_codes = split_nationalitaeten(nationalitaeten)
    use_openplz_streets = bool(db.get('useOpenPlzStreetLookup', True))
    openplz_cache: Dict[Tuple[str, str], Tuple[List[str], str]] = {}
    openplz_budget_state = {
        'used': 0,
        'limit': int(db.get('openPlzRequestLimit', 150)),
    }
    street_source_stats: Dict[str, int] = {}
    openplz_mode_stats: Dict[str, int] = {}
    postal_miss_stats: Dict[str, int] = {}
    switched_postal_stats: Dict[str, int] = {}
    used_email_locals: set = set()

    print(f'Gefunden: {len(schueler_list)} Schüler im Cache')
    print(f'Orte: {len(all_ort_ids)}, Nationalitäten: {len(other_nat_codes) + (1 if deu_code else 0)}')
    print(f'Orte mit PLZ: {len(ort_id_to_postal)}')
    print(f'Haltestellen: {len(haltestellen_ids)}, Fahrschülerarten: {len(fahrschuelerarten_ids)}')
    print(f'Locality+PLZ Straßen-Mappinge: {len(streets_by_locality_postal)}')
    print(f'PLZ-only Straßen-Mappinge: {len(streets_by_postal)}')
    print(f'Schul-Ort-ID: {school_ort_id}')
    print(f'OpenPLZ Straßenabgleich: {"aktiv" if use_openplz_streets else "deaktiviert"}')
    print(f"OpenPLZ Request-Limit: {openplz_budget_state['limit']}")
    if sampled_ort_ids is not all_ort_ids:
        print(f"Orts-Pool für Zufallsauswahl begrenzt: {len(sampled_ort_ids)} von {len(all_ort_ids)}")
    print('Verteilung: 80% Schulort / 20% andere Orte, 80% DEU, 95% Status=2, 5% Status=0')

    payload_all = []
    total = len(schueler_list)
    for index, schueler in enumerate(schueler_list, start=1):
        entry = build_payload_entry(
            schueler,
            index,
            ort_id_to_name,
            ort_id_to_postal,
            ort_name_to_ids,
            school_ort_id,
            sampled_ort_ids,
            streets_by_locality_postal,
            streets_by_postal,
            streets_by_city,
            deu_code,
            other_nat_codes,
            haltestellen_ids,
            fahrschuelerarten_ids,
            use_openplz_streets,
            openplz_cache,
            openplz_budget_state,
            street_source_stats,
            openplz_mode_stats,
            postal_miss_stats,
            switched_postal_stats,
            used_email_locals,
        )
        if entry is not None:
            payload_all.append(entry)
        if index % 100 == 0:
            print(f"  Payload-Fortschritt: {index}/{total} (OpenPLZ Requests: {openplz_budget_state['used']})")

    print('\nStraßen-Quellen:')
    print(f"  csv_postal_locality: {street_source_stats.get('csv_postal_locality', 0)}")
    print(f"  csv_postal_only: {street_source_stats.get('csv_postal_only', 0)}")
    print(f"  csv_city_fallback_with_plz: {street_source_stats.get('csv_city_fallback_with_plz', 0)}")
    print(f"  openplz: {street_source_stats.get('openplz', 0)}")
    print(f"  openplz_postal_switch: {street_source_stats.get('openplz_postal_switch', 0)}")
    print(f"  csv_fallback (ohne PLZ): {street_source_stats.get('csv_fallback', 0)}")
    print(f"  unbekannt trotz PLZ: {street_source_stats.get('unknown_with_plz', 0)}")

    if switched_postal_stats:
        top_switched = sorted(switched_postal_stats.items(), key=lambda item: item[1], reverse=True)[:10]
        print('PLZ-Wechsel innerhalb desselben Orts (Top 10):')
        for plz, count in top_switched:
            print(f"  {plz}: {count}")

    if use_openplz_streets:
        print('OpenPLZ Modi:')
        for mode, count in sorted(openplz_mode_stats.items(), key=lambda item: item[0]):
            print(f"  {mode}: {count}")
        print(f"OpenPLZ Requests verwendet: {openplz_budget_state['used']} / {openplz_budget_state['limit']}")

    if postal_miss_stats:
        top_missing = sorted(postal_miss_stats.items(), key=lambda item: item[1], reverse=True)[:10]
        print('PLZ ohne OpenPLZ-Straßentreffer (Top 10):')
        for plz, count in top_missing:
            print(f"  {plz}: {count}")
        if '42001' in postal_miss_stats:
            print(f"⚠️  Speziell PLZ 42001 ohne Treffer: {postal_miss_stats['42001']}")

    if not payload_all:
        print('❌ Keine gültigen Schülerdaten zum Patchen gefunden.')
        return 0, 1

    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/schueler/stammdaten"

    patched = 0
    failed = 0

    batches = chunked(payload_all, max(1, batch_size))
    print(f'\nPatche {len(payload_all)} Schüler in {len(batches)} Batch(es)...')
    print(f'URL: {url}\n')

    for idx, batch in enumerate(batches, start=1):
        try:
            resp = requests.patch(
                url,
                json=batch,
                auth=auth,
                verify=False,
                timeout=60,
            )
            if resp.status_code in (200, 201, 204):
                patched += len(batch)
                print(f"[{idx}/{len(batches)}] ✓ Batch mit {len(batch)} Einträgen (HTTP {resp.status_code})")
            else:
                failed += len(batch)
                try:
                    err = resp.json().get('message', resp.text)
                except Exception:
                    err = resp.text
                print(f"[{idx}/{len(batches)}] ❌ Batch fehlgeschlagen (HTTP {resp.status_code}) - {err[:180]}")
        except requests.exceptions.RequestException as exc:
            failed += len(batch)
            print(f"[{idx}/{len(batches)}] ❌ Fehler beim Batch-Patch: {exc}")

    print(f"\nErgebnis: {patched} erfolgreich, {failed} fehlgeschlagen")
    if failed == 0:
        print('✓ Alle Schüler-Stammdaten erfolgreich gepatcht!')
    else:
        print(f'⚠️  {failed} Schüler konnten nicht gepatcht werden')

    return patched, failed


if __name__ == '__main__':
    from check_server import load_config

    cfg = load_config()
    patch_schueler_stammdaten(cfg)
