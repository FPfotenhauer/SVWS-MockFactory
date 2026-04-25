"""
Populate K_Schueler with randomly generated student data.

Creates a gender-mixed set of students based on config['database']['anzahlschueler']
with target distribution 49% male, 49% female, 2% diverse.

Birth dates are generated to fit the assigned jahrgang and school form.
Uses current idSchuljahresabschnitt from schul/stammdaten.
Stores created student metadata in .schueler_cache.json for follow-up PATCH steps.
"""

import json
import random
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings for self-signed certificates
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

RAND = random.Random()


def load_json(path: Path) -> list:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_nachnamen() -> List[str]:
    path = Path(__file__).parent / 'katalogdaten' / 'nachnamen.json'
    return load_json(path)


def load_vornamen(filename: str) -> List[str]:
    path = Path(__file__).parent / 'katalogdaten' / filename
    return load_json(path)


def fetch_stammdaten(config) -> dict:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/schule/stammdaten"
    auth = HTTPBasicAuth(db['username'], db['password'])

    resp = requests.get(url, auth=auth, verify=False, timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_jahrgaenge(config) -> List[dict]:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/jahrgaenge"
    auth = HTTPBasicAuth(db['username'], db['password'])

    resp = requests.get(url, auth=auth, verify=False, timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_classes(config, id_schuljahresabschnitt: Optional[int] = None) -> List[dict]:
    db = config['database']
    if id_schuljahresabschnitt is not None:
        url = (
            f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}"
            f"/klassen/abschnitt/{id_schuljahresabschnitt}"
        )
    else:
        url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/klassen"
    auth = HTTPBasicAuth(db['username'], db['password'])

    resp = requests.get(url, auth=auth, verify=False, timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_religionen(config) -> List[dict]:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/schule/religionen"
    auth = HTTPBasicAuth(db['username'], db['password'])

    resp = requests.get(url, auth=auth, verify=False, timeout=20)
    resp.raise_for_status()
    return resp.json()


def extract_religion_id(entry: dict) -> Optional[int]:
    value = entry.get('id')
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def religion_text(entry: dict) -> str:
    parts = [
        entry.get('kuerzel'),
        entry.get('bezeichnung'),
        entry.get('bezeichnung1'),
        entry.get('bezeichnung2'),
        entry.get('bezeichnung3'),
    ]
    text = ' '.join(str(p) for p in parts if isinstance(p, str) and p.strip())
    return text.lower()


def classify_religion_group(entry: dict) -> str:
    text = religion_text(entry)

    if any(token in text for token in ('evangel', 'ev.', 'ev ')):
        return 'evangelisch'
    if any(token in text for token in ('kathol', 'rk', 'römisch', 'roemisch')):
        return 'katholisch'
    if any(token in text for token in ('islam', 'muslim')):
        return 'islamisch'
    return 'other'


def build_religion_buckets(religionen: List[dict]) -> Dict[str, List[int]]:
    buckets: Dict[str, List[int]] = {
        'evangelisch': [],
        'katholisch': [],
        'islamisch': [],
        'other': [],
    }

    for entry in religionen:
        rid = extract_religion_id(entry)
        if rid is None:
            continue
        group = classify_religion_group(entry)
        buckets[group].append(rid)

    return buckets


def weighted_pick_religion_id(buckets: Dict[str, List[int]]) -> Optional[int]:
    groups = [
        ('evangelisch', 0.30),
        ('katholisch', 0.30),
        ('islamisch', 0.30),
        ('other', 0.10),
    ]

    available = [(name, weight) for name, weight in groups if buckets.get(name)]
    if not available:
        return None

    total_weight = sum(weight for _, weight in available)
    roll = RAND.random() * total_weight
    running = 0.0
    chosen_group = available[-1][0]
    for name, weight in available:
        running += weight
        if roll <= running:
            chosen_group = name
            break

    return RAND.choice(buckets[chosen_group])


def map_yeargroup_ids_by_kuerzel(jahrgaenge: List[dict]) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    for item in jahrgaenge:
        jg_id = item.get('id')
        kuerzel = item.get('kuerzel')
        if isinstance(jg_id, int) and isinstance(kuerzel, str) and kuerzel.strip():
            key = kuerzel.strip().upper()
            mapping[key] = jg_id
            numeric = numeric_from_text(key)
            if numeric is not None:
                mapping[str(numeric)] = jg_id
                mapping[str(numeric).zfill(2)] = jg_id
    return mapping


def infer_jahrgang_kuerzel_from_class_kuerzel(klassen_kuerzel: str) -> Optional[str]:
    upper = (klassen_kuerzel or '').upper()
    if upper in {'EF', 'Q1', 'Q2'}:
        return upper

    if upper.startswith('EF'):
        return 'EF'
    if upper.startswith('Q1'):
        return 'Q1'
    if upper.startswith('Q2'):
        return 'Q2'

    m = re.search(r'(\d{1,2})', upper)
    if not m:
        return None
    return str(int(m.group(1))).zfill(2)


def load_classes_from_cache(cache_file: Path, yeargroup_id_by_kuerzel: Dict[str, int]) -> List[dict]:
    if not cache_file.exists():
        return []

    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cached = json.load(f)
    except Exception:
        return []

    result: List[dict] = []
    for entry in cached:
        class_id = entry.get('id')
        kuerzel = entry.get('kuerzel', str(class_id or ''))
        if not isinstance(class_id, int):
            continue

        jg_kuerzel = infer_jahrgang_kuerzel_from_class_kuerzel(str(kuerzel))
        if not jg_kuerzel:
            continue

        jg_id = yeargroup_id_by_kuerzel.get(jg_kuerzel.upper())
        if not isinstance(jg_id, int):
            continue

        result.append(
            {
                'id': class_id,
                'kuerzel': str(kuerzel),
                'idJahrgang': jg_id,
            }
        )

    return result


def load_classes(config, id_schuljahresabschnitt: int, yeargroup_id_by_kuerzel: Dict[str, int]) -> List[dict]:
    cache_file = Path(__file__).parent / '.klassen_cache.json'
    cached_classes = load_classes_from_cache(cache_file, yeargroup_id_by_kuerzel)
    if cached_classes:
        print(f"ℹ️  Verwende {len(cached_classes)} Klassen aus .klassen_cache.json")
        return cached_classes

    classes: List[dict] = []
    try:
        classes_all = fetch_classes(config, id_schuljahresabschnitt=id_schuljahresabschnitt)
        for k in classes_all:
            k_abschnitt = k.get('idSchuljahresabschnitt')
            if k_abschnitt is None or k_abschnitt == id_schuljahresabschnitt:
                class_id = k.get('id')
                jg_id = extract_class_yeargroup_id(k)
                if class_id and jg_id:
                    classes.append(
                        {
                            'id': class_id,
                            'kuerzel': k.get('kuerzel', str(class_id)),
                            'idJahrgang': jg_id,
                        }
                    )
    except Exception as e:
        print(f"⚠️  Fehler beim Laden der Klassen per Abschnitts-API: {e}")
        print('   Versuche Fallback über /klassen ...')
        try:
            classes_all = fetch_classes(config)
            for k in classes_all:
                k_abschnitt = k.get('idSchuljahresabschnitt')
                if k_abschnitt is None or k_abschnitt == id_schuljahresabschnitt:
                    class_id = k.get('id')
                    jg_id = extract_class_yeargroup_id(k)
                    if class_id and jg_id:
                        classes.append(
                            {
                                'id': class_id,
                                'kuerzel': k.get('kuerzel', str(class_id)),
                                'idJahrgang': jg_id,
                            }
                        )
        except Exception as e2:
            print(f"⚠️  Fehler beim Laden der Klassen per /klassen: {e2}")
        print('   Versuche Fallback über .klassen_cache.json ...')
        classes = load_classes_from_cache(cache_file, yeargroup_id_by_kuerzel)
        if classes:
            print(f"✓ Fallback erfolgreich: {len(classes)} Klassen aus Cache geladen")

    return classes


def numeric_from_text(value: str) -> Optional[int]:
    digits = ''.join(ch for ch in value if ch.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def build_gender_mix(count: int, divers_code: int = 5) -> List[int]:
    diverse = max(1, round(count * 0.02)) if count >= 50 else max(0, round(count * 0.02))
    rest = count - diverse
    male = rest // 2
    female = rest - male
    genders = [3] * male + [4] * female + [divers_code] * diverse
    RAND.shuffle(genders)
    return genders


def build_dates_for_schoolyear() -> Tuple[str, str, date]:
    today = date.today()
    year = today.year
    anmeldedatum = date(year, 2, 1)
    aufnahmedatum = date(year, 8, 1)
    return anmeldedatum.isoformat(), aufnahmedatum.isoformat(), aufnahmedatum


def current_schoolyear_start(today: date) -> date:
    if today.month >= 8:
        return date(today.year, 8, 1)
    return date(today.year - 1, 8, 1)


def yeargroup_level(jahrgang_kuerzel: str) -> Optional[int]:
    numeric = numeric_from_text(jahrgang_kuerzel or '')
    if numeric is not None:
        return numeric
    upper = (jahrgang_kuerzel or '').upper()
    return {'EF': 11, 'Q1': 12, 'Q2': 13}.get(upper)


def start_yeargroup_level_for_form(schulform: str) -> int:
    form = (schulform or '').upper()
    if form in {'G', 'SG', 'FW', 'PS', 'KS', 'V'}:
        return 1
    if form in {'BK', 'SB'}:
        return 1
    return 5


def calculate_entry_dates(
    schulform: str,
    jahrgang_kuerzel: str,
    bk_order_index: Optional[int],
    today: date,
) -> Tuple[str, str]:
    schoolyear_start = current_schoolyear_start(today)
    form = (schulform or '').upper()

    if form in {'BK', 'SB'}:
        years_since_entry = max(0, min(bk_order_index or 0, 2))
    else:
        level = yeargroup_level(jahrgang_kuerzel)
        start_level = start_yeargroup_level_for_form(form)
        if level is None:
            years_since_entry = 0
        else:
            years_since_entry = max(0, level - start_level)

    aufnahme_year = schoolyear_start.year - years_since_entry
    aufnahmedatum = date(aufnahme_year, 8, 1)
    anmeldedatum = date(aufnahme_year, 2, 1)
    return anmeldedatum.isoformat(), aufnahmedatum.isoformat()


def yeargroup_sort_key(kuerzel: str) -> Tuple[int, str]:
    numeric = numeric_from_text(kuerzel)
    if numeric is not None:
        return numeric, kuerzel
    upper = kuerzel.upper()
    special = {'EF': 11, 'Q1': 12, 'Q2': 13}.get(upper)
    if special is not None:
        return special, kuerzel
    return 999, kuerzel


def resolve_age_range(
    schulform: str,
    jahrgang_kuerzel: str,
    bk_order_index: Optional[int],
) -> Tuple[int, int]:
    form = (schulform or '').upper()
    grade_num = numeric_from_text(jahrgang_kuerzel or '')

    if form in {'BK', 'SB'}:
        idx = bk_order_index if bk_order_index is not None else 0
        idx = max(0, min(idx, 2))
        min_age = 16 + idx
        max_age = 19 + idx
        return min_age, max_age

    if grade_num is not None:
        entry_age = grade_num + 5
        return entry_age, entry_age + 1

    upper = (jahrgang_kuerzel or '').upper()
    if upper in {'EF', 'Q1', 'Q2'}:
        mapping = {'EF': (16, 17), 'Q1': (17, 18), 'Q2': (18, 19)}
        return mapping[upper]

    return 10, 11


def random_birthdate_for_age_range(min_age: int, max_age: int, ref_date: date) -> str:
    target_age = RAND.randint(min_age, max_age)
    start = ref_date - timedelta(days=(target_age + 1) * 365) + timedelta(days=1)
    end = ref_date - timedelta(days=target_age * 365)
    span = (end - start).days
    random_day = RAND.randint(0, max(0, span))
    return (start + timedelta(days=random_day)).isoformat()


def extract_class_yeargroup_id(klasse: dict) -> Optional[int]:
    for key in ('idJahrgang', 'jahrgang', 'jahrgangID'):
        value = klasse.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, dict):
            nested = value.get('id')
            if isinstance(nested, int):
                return nested
    return None


def pick_first_names(geschlecht: int, vornamen_m: List[str], vornamen_w: List[str]) -> Tuple[str, str]:
    if geschlecht == 3:
        first = RAND.choice(vornamen_m)
        second_pool = vornamen_m
    elif geschlecht == 4:
        first = RAND.choice(vornamen_w)
        second_pool = vornamen_w
    else:
        combined = vornamen_m + vornamen_w
        first = RAND.choice(combined)
        second_pool = combined

    if RAND.random() < 0.35:
        second = RAND.choice(second_pool)
        alle = f"{first} {second}"
    else:
        alle = first
    return first, alle


def populate_schueler(config, count: Optional[int] = None) -> Tuple[int, int]:
    cache_file = Path(__file__).parent / '.schueler_cache.json'
    if cache_file.exists():
        cache_file.unlink()

    nachnamen = load_nachnamen()
    vornamen_m = load_vornamen('vornamen_m.json')
    vornamen_w = load_vornamen('vornamen_w.json')

    if not nachnamen or not vornamen_m or not vornamen_w:
        print('❌ Namen konnten nicht geladen werden.')
        return 0, 1

    db = config['database']
    total = count if count is not None else db.get('anzahlschueler', 200)

    print(f"\nBefülle K_Schueler mit {total} Einträgen...")

    try:
        stammdaten = fetch_stammdaten(config)
    except Exception as e:
        print(f"❌ Fehler beim Laden der Stammdaten: {e}")
        return 0, 1

    schulform = (stammdaten.get('schulform') or '').upper()
    id_schuljahresabschnitt = stammdaten.get('idSchuljahresabschnitt')
    if not id_schuljahresabschnitt:
        print('❌ Kein idSchuljahresabschnitt in Stammdaten gefunden')
        return 0, 1

    try:
        jahrgaenge = fetch_jahrgaenge(config)
    except Exception as e:
        print(f"❌ Fehler beim Laden der Jahrgänge: {e}")
        return 0, 1

    jahrgang_map: Dict[int, str] = {
        item.get('id'): item.get('kuerzel', '')
        for item in jahrgaenge
        if isinstance(item.get('id'), int)
    }

    yeargroup_id_by_kuerzel = map_yeargroup_ids_by_kuerzel(jahrgaenge)

    try:
        religionen = fetch_religionen(config)
        religion_buckets = build_religion_buckets(religionen)
    except Exception as e:
        print(f"⚠️  Fehler beim Laden der Religionen: {e}")
        religion_buckets = {
            'evangelisch': [],
            'katholisch': [],
            'islamisch': [],
            'other': [],
        }

    classes = load_classes(config, id_schuljahresabschnitt, yeargroup_id_by_kuerzel)

    if not classes:
        print('❌ Keine Klassen gefunden. Bitte zuerst populate_classes.py ausführen.')
        print('   Hinweis: Bei API-Fehlern kann .klassen_cache.json als Fallback genutzt werden.')
        return 0, 1

    # Calculate classes per yeargroup to handle Oberstufe (EF/Q1/Q2) properly
    classes_per_jahrgang = defaultdict(int)
    for c in classes:
        jg_kuerzel = jahrgang_map.get(c['idJahrgang'], '')
        classes_per_jahrgang[jg_kuerzel] += 1
    
    # Identify Oberstufe classes (EF, Q1, Q2) and regular classes
    oberstufe_jahrgaenge = {'EF', 'Q1', 'Q2'}
    oberstufe_classes = []
    regular_classes = []
    
    for c in classes:
        jg_kuerzel = jahrgang_map.get(c['idJahrgang'], '')
        if jg_kuerzel in oberstufe_jahrgaenge:
            oberstufe_classes.append(c)
        else:
            regular_classes.append(c)
    
    # Expand Oberstufe classes to match the number of parallel classes in regular grades
    # This ensures EF/Q1/Q2 get as many students as all parallel classes of e.g. grade 09 combined
    if regular_classes and oberstufe_classes:
        regular_jahrgaenge = [jg for jg in classes_per_jahrgang.keys() if jg not in oberstufe_jahrgaenge]
        if regular_jahrgaenge:
            avg_classes_per_jahrgang = sum(classes_per_jahrgang[jg] for jg in regular_jahrgaenge) / len(regular_jahrgaenge)
            multiplier = max(1, int(round(avg_classes_per_jahrgang)))
            
            # Duplicate each Oberstufe class 'multiplier' times
            expanded_oberstufe = []
            for c in oberstufe_classes:
                for _ in range(multiplier):
                    expanded_oberstufe.append(c)
            
            # Rebuild classes list with expanded Oberstufe
            classes = regular_classes + expanded_oberstufe
            
            print(f"ℹ️  Oberstufe-Klassen (EF/Q1/Q2) je {multiplier}x dupliziert für größere Jahrgänge\n")

    today = date.today()
    aufnahme_ref_date = current_schoolyear_start(today)
    divers_code = db.get('schuelerDiversGeschlechtCode', 5)
    if not isinstance(divers_code, int):
        divers_code = 5
    extra_students_target = max(0, int(total * 0.10))
    extra_batches: List[dict] = []
    extra_class_sequence: List[dict] = []

    primarstufe_schulformen = {'G', 'SG', 'FW', 'PS', 'V'}
    extra_target_jahrgaenge: List[str] = []
    if extra_students_target > 0:
        if schulform in primarstufe_schulformen:
            extra_target_jahrgaenge = ['01']
        elif schulform in {'GY', 'GE'}:
            extra_target_jahrgaenge = ['05', 'EF']
        elif schulform not in {'BK', 'SB'}:
            extra_target_jahrgaenge = ['05']
        else:
            print(
                f"ℹ️  Schulform {schulform}: Keine zusätzliche 10%-Aufnahme-Logik konfiguriert "
                "(nur Primarstufe/Sek I + EF bei GY/GE)."
            )

        for target_jahrgang in extra_target_jahrgaenge:
            target_pool = [
                c for c in classes
                if (jahrgang_map.get(c.get('idJahrgang'), '') or '').upper() == target_jahrgang
            ]
            if not target_pool:
                print(
                    f"⚠️  Keine Klassen für Jahrgang {target_jahrgang} gefunden. "
                    "Zusatz-10%-Aufnahmeschüler für diesen Jahrgang werden übersprungen."
                )
                continue

            extra_batches.append(
                {
                    'jahrgang': target_jahrgang,
                    'count': extra_students_target,
                    'pool': target_pool,
                }
            )

        for batch in extra_batches:
            pool = batch['pool']
            count = batch['count']
            for seq_idx in range(count):
                extra_class_sequence.append(pool[seq_idx % len(pool)])

    total_extra_students = len(extra_class_sequence)
    total_with_extra = total + total_extra_students
    genders = build_gender_mix(total_with_extra, divers_code=divers_code)

    # BK yeargroup ordering for 16-19 start-age logic
    bk_jahrgaenge_sorted = sorted(
        {c['idJahrgang'] for c in classes},
        key=lambda jg_id: yeargroup_sort_key(jahrgang_map.get(jg_id, '')),
    )
    bk_order_index = {jg_id: idx for idx, jg_id in enumerate(bk_jahrgaenge_sorted)}

    RAND.shuffle(classes)

    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/schueler/create"
    auth = HTTPBasicAuth(db['username'], db['password'])

    print(f"Schulform: {schulform}")
    print(f"idSchuljahresabschnitt: {id_schuljahresabschnitt}")
    print(f"Klassen für Aufnahme: {len(classes)}")
    if extra_batches:
        for batch in extra_batches:
            print(
                f"Zusatz-Aufnahmen: {batch['count']} (10%) in Jahrgang {batch['jahrgang']}, "
                "Status 0"
            )
    print(
        "Religionen-Buckets: "
        f"ev={len(religion_buckets['evangelisch'])}, "
        f"kath={len(religion_buckets['katholisch'])}, "
        f"isl={len(religion_buckets['islamisch'])}, "
        f"other={len(religion_buckets['other'])}"
    )
    print(f"URL: {url}\n")

    created = 0
    failed = 0
    cache_data = []
    warned_divers_fallback = False

    for idx in range(1, total_with_extra + 1):
        requested_geschlecht = genders[idx - 1]
        gesendetes_geschlecht = requested_geschlecht
        is_extra_student = idx > total
        status_override = None

        if is_extra_student and extra_class_sequence:
            extra_index = idx - total - 1
            klasse = extra_class_sequence[extra_index]
            status_override = 0
        else:
            klasse = classes[(idx - 1) % len(classes)]

        id_klasse = klasse['id']
        id_jahrgang = klasse['idJahrgang']
        jahrgang_kuerzel = jahrgang_map.get(id_jahrgang, '')

        min_age, max_age = resolve_age_range(
            schulform,
            jahrgang_kuerzel,
            bk_order_index.get(id_jahrgang),
        )
        geburtsdatum = random_birthdate_for_age_range(min_age, max_age, aufnahme_ref_date)
        anmeldedatum, aufnahmedatum = calculate_entry_dates(
            schulform,
            jahrgang_kuerzel,
            bk_order_index.get(id_jahrgang),
            today=today,
        )

        vorname, alle_vornamen = pick_first_names(requested_geschlecht, vornamen_m, vornamen_w)
        nachname = RAND.choice(nachnamen)
        id_religion = weighted_pick_religion_id(religion_buckets)

        if requested_geschlecht not in (3, 4):
            gesendetes_geschlecht = requested_geschlecht

        payload = {
            'nachname': nachname,
            'vorname': vorname,
            'alleVornamen': alle_vornamen,
            'geschlecht': gesendetes_geschlecht,
            'geburtsdatum': geburtsdatum,
            'status': 0,
            'anmeldedatum': anmeldedatum,
            'aufnahmedatum': aufnahmedatum,
            'beginnBildungsgang': None,
            'dauerBildungsgang': None,
            'idReligion': id_religion,
            'idSchuljahresabschnitt': id_schuljahresabschnitt,
            'idJahrgang': id_jahrgang,
            'idKlasse': id_klasse,
            'idGrundschuleEinschulungsart': None,
        }

        try:
            resp = requests.post(
                url,
                json=payload,
                auth=auth,
                verify=False,
                timeout=20,
            )

            # Fallback: Religion-ID optional
            if resp.status_code == 404 and 'Religion' in resp.text:
                payload['idReligion'] = None
                resp = requests.post(
                    url,
                    json=payload,
                    auth=auth,
                    verify=False,
                    timeout=20,
                )

            # Fallback: API akzeptiert gesendeten Divers-Code nicht
            if (
                resp.status_code == 400
                and requested_geschlecht not in (3, 4)
                and 'Geschlecht' in resp.text
            ):
                payload['geschlecht'] = RAND.choice([3, 4])
                gesendetes_geschlecht = payload['geschlecht']
                resp = requests.post(
                    url,
                    json=payload,
                    auth=auth,
                    verify=False,
                    timeout=20,
                )
                if not warned_divers_fallback:
                    print('⚠️  Hinweis: Divers-Geschlecht wurde vom API-Create nicht akzeptiert, verwende Fallback 3/4.')
                    warned_divers_fallback = True

            if resp.status_code in (200, 201):
                created += 1
                print(
                    f"[{idx}/{total_with_extra}] {vorname} {nachname} / Klasse {klasse['kuerzel']}: "
                    f"✓ (HTTP {resp.status_code})"
                )

                try:
                    response_data = resp.json()
                    schueler_id = response_data.get('id')
                    if schueler_id:
                        cache_data.append(
                            {
                                'id': schueler_id,
                                'vorname': vorname,
                                'nachname': nachname,
                                'alleVornamen': alle_vornamen,
                                'geschlecht': gesendetes_geschlecht,
                                'requestedGeschlecht': requested_geschlecht,
                                'geburtsdatum': geburtsdatum,
                                'anmeldedatum': anmeldedatum,
                                'aufnahmedatum': aufnahmedatum,
                                'idReligion': id_religion,
                                'idSchuljahresabschnitt': id_schuljahresabschnitt,
                                'idJahrgang': id_jahrgang,
                                'idKlasse': id_klasse,
                                'jahrgangKuerzel': jahrgang_kuerzel,
                                'klassenKuerzel': klasse['kuerzel'],
                                'statusOverride': status_override,
                            }
                        )
                except Exception:
                    pass
            else:
                try:
                    err = resp.json().get('message', resp.text)
                except Exception:
                    err = resp.text
                failed += 1
                print(f"[{idx}/{total_with_extra}] {vorname} {nachname}: ❌ HTTP {resp.status_code} - {err[:180]}")

        except requests.exceptions.RequestException as exc:  # pragma: no cover
            failed += 1
            print(f"[{idx}/{total_with_extra}] {vorname} {nachname}: ❌ Fehler: {exc}")

    if cache_data:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        print(f"\n💾 {len(cache_data)} Schüler in Cache gespeichert ({cache_file.name})")

    print(f"\nErgebnis: {created} erfolgreich, {failed} fehlgeschlagen")
    if failed == 0:
        print('✓ Alle Schüler erfolgreich erstellt!')
    else:
        print(f"⚠️  {failed} Schüler konnten nicht erstellt werden")

    return created, failed


if __name__ == '__main__':
    from check_server import load_config

    cfg = load_config()
    populate_schueler(cfg)
