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
    if id_schuljahresabschnitt is None:
        stammdaten_url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/schule/stammdaten"
        auth = HTTPBasicAuth(db['username'], db['password'])
        sr = requests.get(stammdaten_url, auth=auth, verify=False, timeout=10)
        sr.raise_for_status()
        id_schuljahresabschnitt = sr.json().get('idSchuljahresabschnitt', 1)
    url = (
        f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}"
        f"/klassen/minimal/abschnitt/{id_schuljahresabschnitt}"
    )
    auth = HTTPBasicAuth(db['username'], db['password'])
    resp = requests.get(url, auth=auth, verify=False, timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_classes_via_auswahlliste(config, id_schuljahresabschnitt: int) -> List[dict]:
    """Fallback-Quelle für Klassen, falls die /klassen-Endpunkte nicht verfügbar sind.

    Die Schüler-Auswahlliste enthält die vollständigen Klassen-Objekte für den
    angegebenen Schuljahresabschnitt und bleibt auch dann erreichbar, wenn
    /klassen bzw. /klassen/abschnitt/{id} mit HTTP 500 antwortet.
    """
    db = config['database']
    url = (
        f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}"
        f"/schueler/abschnitt/{id_schuljahresabschnitt}/auswahlliste"
    )
    auth = HTTPBasicAuth(db['username'], db['password'])

    resp = requests.get(url, auth=auth, verify=False, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and isinstance(data.get('klassen'), list):
        return data['klassen']
    return []


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


def normalize_jahrgang(value: str) -> str:
    """Vereinheitlicht Jahrgangs-Kürzel für Vergleiche ('09'/'9' -> '9', 'ef' -> 'EF')."""
    text = (value or '').strip().upper()
    if not text:
        return ''
    if text.isdigit():
        return str(int(text))
    return text


def _write_classes_cache(cache_file: Path, classes: List[dict]) -> None:
    try:
        payload = [
            {
                'id': c['id'],
                'kuerzel': c.get('kuerzel', str(c['id'])),
                'idJahrgang': c.get('idJahrgang'),
            }
            for c in classes
            if isinstance(c.get('id'), int)
        ]
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️  Konnte .klassen_cache.json nicht aktualisieren: {e}")


def _classes_from_api_list(classes_all: List[dict], id_schuljahresabschnitt: int) -> List[dict]:
    result: List[dict] = []
    for k in classes_all:
        k_abschnitt = k.get('idSchuljahresabschnitt')
        if k_abschnitt is not None and k_abschnitt != id_schuljahresabschnitt:
            continue
        class_id = k.get('id')
        jg_id = extract_class_yeargroup_id(k)
        if class_id and jg_id:
            result.append(
                {
                    'id': class_id,
                    'kuerzel': k.get('kuerzel', str(class_id)),
                    'idJahrgang': jg_id,
                }
            )
    return result


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

        explicit_jg = entry.get('idJahrgang')
        if isinstance(explicit_jg, int):
            result.append(
                {
                    'id': class_id,
                    'kuerzel': str(kuerzel),
                    'idJahrgang': explicit_jg,
                }
            )
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

    # Live-Quellen der Reihe nach probieren. Die Abschnitts-API ist die
    # bevorzugte Quelle; die Schüler-Auswahlliste dient als Fallback, falls
    # /klassen* mit HTTP 500 antwortet.
    live_sources = (
        (
            'Abschnitts-API (/klassen/minimal/abschnitt)',
            lambda: fetch_classes(config, id_schuljahresabschnitt=id_schuljahresabschnitt),
        ),
        (
            'Schüler-Auswahlliste',
            lambda: fetch_classes_via_auswahlliste(config, id_schuljahresabschnitt),
        ),
    )

    for label, loader in live_sources:
        try:
            classes = _classes_from_api_list(loader(), id_schuljahresabschnitt)
        except Exception as e:
            print(f"⚠️  Klassen über {label} nicht ladbar: {e}")
            continue
        if classes:
            print(f"ℹ️  {len(classes)} Klassen über {label} geladen")
            _write_classes_cache(cache_file, classes)
            return classes

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


def populate_schueler(
    config,
    count: Optional[int] = None,
    jahrgang: Optional[str] = None,
    status: Optional[int] = None,
    append: bool = False,
) -> Tuple[int, int]:
    """Erzeugt Schülerdatensätze.

    count    -- Anzahl (Default: config['database']['anzahlschueler'])
    jahrgang -- Nur Klassen dieses Jahrgangs bestücken (z.B. '10', '09', 'EF').
                Ist ein Jahrgang gesetzt, entfällt die zusätzliche 10%-Aufnahme-Logik.
    status   -- Status der erzeugten Schüler (z.B. 2 = aktiv). Default: 0.
    append   -- .schueler_cache.json nicht löschen, neue Einträge anhängen.
    """
    cache_file = Path(__file__).parent / '.schueler_cache.json'
    existing_cache: List[dict] = []
    if append and cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                existing_cache = json.load(f)
            if not isinstance(existing_cache, list):
                existing_cache = []
            print(f"ℹ️  Append-Modus: {len(existing_cache)} vorhandene Cache-Einträge bleiben erhalten")
        except Exception:
            existing_cache = []
    elif cache_file.exists():
        cache_file.unlink()

    status_value = status if isinstance(status, int) else 0

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

    target_jahrgang = normalize_jahrgang(jahrgang) if jahrgang else None
    if target_jahrgang:
        filtered = [
            c for c in classes
            if normalize_jahrgang(jahrgang_map.get(c.get('idJahrgang'), '')) == target_jahrgang
        ]
        if not filtered:
            verfuegbar = sorted({
                jahrgang_map.get(c.get('idJahrgang'), '?') for c in classes
            })
            print(f"❌ Keine Klassen für Jahrgang '{jahrgang}' gefunden.")
            print(f"   Verfügbare Jahrgänge mit Klassen: {', '.join(verfuegbar)}")
            return 0, 1
        classes = filtered
        print(
            f"ℹ️  Jahrgangsfilter '{jahrgang}': {len(classes)} Klasse(n) "
            f"({', '.join(c['kuerzel'] for c in classes)})"
        )

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
    # Bei aktivem Jahrgangsfilter keine zusätzlichen 10%-Aufnahmeschüler erzeugen.
    extra_students_target = 0 if target_jahrgang else max(0, int(total * 0.10))
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

        valid_targets: List[Tuple[str, List[dict]]] = []
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
            valid_targets.append((target_jahrgang, target_pool))

        # extra_students_target ist bereits die GESAMTE 10%-Menge. Auf mehrere Ziel-
        # Jahrgänge (z.B. 05 + EF bei GY/GE) aufteilen, statt sie je Jahrgang zu wiederholen.
        n_targets = len(valid_targets)
        for i, (target_jahrgang, target_pool) in enumerate(valid_targets):
            batch_count = extra_students_target // n_targets
            if i < extra_students_target % n_targets:
                batch_count += 1
            if batch_count <= 0:
                continue

            extra_batches.append(
                {
                    'jahrgang': target_jahrgang,
                    'count': batch_count,
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
    print(f"Status der erzeugten Schüler: {status_value}")
    if target_jahrgang:
        print(f"Jahrgangsfilter: {jahrgang}")
    if extra_batches:
        total_extra_batches = sum(b['count'] for b in extra_batches)
        print(f"Zusatz-Aufnahmen gesamt: {total_extra_batches} (10% von {total}), Status 0")
        for batch in extra_batches:
            print(f"  davon {batch['count']} in Jahrgang {batch['jahrgang']}")
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

        effective_status = status_override if isinstance(status_override, int) else status_value

        payload = {
            'nachname': nachname,
            'vorname': vorname,
            'alleVornamen': alle_vornamen,
            'geschlecht': gesendetes_geschlecht,
            'geburtsdatum': geburtsdatum,
            'status': effective_status,
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
                                'statusOverride': (
                                    status_value if status is not None else status_override
                                ),
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

    all_cache = existing_cache + cache_data
    if all_cache:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(all_cache, f, indent=2, ensure_ascii=False)
        if existing_cache:
            print(
                f"\n💾 {len(cache_data)} neue Schüler in Cache angehängt "
                f"({cache_file.name}), gesamt {len(all_cache)}"
            )
        else:
            print(f"\n💾 {len(cache_data)} Schüler in Cache gespeichert ({cache_file.name})")

    print(f"\nErgebnis: {created} erfolgreich, {failed} fehlgeschlagen")
    if failed == 0:
        print('✓ Alle Schüler erfolgreich erstellt!')
    else:
        print(f"⚠️  {failed} Schüler konnten nicht erstellt werden")

    return created, failed


if __name__ == '__main__':
    import argparse

    from check_server import load_config

    parser = argparse.ArgumentParser(
        description='Erzeugt Schülerdatensätze (optional gefiltert nach Jahrgang/Status).'
    )
    parser.add_argument('--count', type=int, default=None,
                        help='Anzahl zu erzeugender Schüler (Default: config anzahlschueler)')
    parser.add_argument('--jahrgang', type=str, default=None,
                        help="Nur Klassen dieses Jahrgangs bestücken, z.B. 10, 09, EF")
    parser.add_argument('--status', type=int, default=None,
                        help='Status der erzeugten Schüler (z.B. 2 = aktiv). Default: 0')
    parser.add_argument('--append', action='store_true',
                        help='.schueler_cache.json nicht löschen, neue Schüler anhängen')
    args = parser.parse_args()

    cfg = load_config()
    populate_schueler(
        cfg,
        count=args.count,
        jahrgang=args.jahrgang,
        status=args.status,
        append=args.append,
    )
