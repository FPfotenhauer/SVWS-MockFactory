"""
Populate K_Lehrer with randomly generated teacher data.
Creates a gender-balanced set of teachers based on config['database']['anzahllehrer'].
"""

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, List, Set, Tuple

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


def load_strassen() -> List[str]:
    path = Path(__file__).parent / 'katalogdaten' / 'Strassen.csv'
    streets: List[str] = []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            street = (row.get('Strasse') or '').strip().rstrip(',')
            if street:
                streets.append(street)
    return streets


def random_phone() -> str:
    return f"012345-{RAND.randint(100000, 999999)}"


def random_birthdate() -> str:
    # Age between 30 and 60 years
    today = date.today()
    min_days = 30 * 365
    max_days = 60 * 365
    delta_days = RAND.randint(min_days, max_days)
    birth = today - timedelta(days=delta_days)
    return birth.isoformat()


def pick_staatsangehoerigkeit() -> str:
    roll = RAND.random()
    if roll < 0.90:
        return 'DEU'
    if roll < 0.95:
        return 'TUR'
    return 'ITA'


def slugify_mail_part(text: str) -> str:
    replacements = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
        'Ä': 'ae', 'Ö': 'oe', 'Ü': 'ue',
    }
    lowered = ''.join(replacements.get(ch, ch) for ch in text.lower())
    return ''.join(ch for ch in lowered if ch.isalnum() or ch == '-')


def hausnummer() -> str:
    base = RAND.randint(1, 199)
    suffix = RAND.choice(['', '', '', 'a', 'b'])
    return f"{base}{suffix}"


def make_kuerzel(nachname: str, existing: Set[str]) -> str:
    cleaned = ''.join(ch for ch in nachname if ch.isalpha())
    base = (cleaned[:4] or cleaned).upper()
    if len(base) < 3:
        base = (base + 'XXXX')[:3]
    if base not in existing:
        existing.add(base)
        return base
    short = (cleaned[:3] or cleaned).upper()
    if len(short) < 3:
        short = (short + 'XXX')[:3]
    counter = 1
    while True:
        candidate = f"{short}{counter}"
        if candidate not in existing:
            existing.add(candidate)
            return candidate
        counter += 1


def fetch_wuppertal_ort_ids(config) -> List[int]:
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/orte"
    resp = requests.get(
        url,
        auth=HTTPBasicAuth(db['username'], db['password']),
        verify=False,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    ort_ids: List[int] = []
    for item in data:
        ort = item.get('ortsname') or item.get('Ort') or item.get('ort') or ''
        if isinstance(ort, str) and ort.lower() == 'wuppertal':
            if 'id' in item:
                try:
                    ort_ids.append(int(item['id']))
                except (TypeError, ValueError):
                    continue
    return ort_ids


def balanced_genders(count: int) -> List[int]:
    males = count // 2
    females = count - males
    genders = [3] * males + [4] * females
    RAND.shuffle(genders)
    return genders


def populate_lehrer(config, count: int | None = None) -> Tuple[int, int]:
    nachnamen = load_nachnamen()
    vornamen_m = load_vornamen('vornamen_m.json')
    vornamen_w = load_vornamen('vornamen_w.json')
    strassen = load_strassen()

    if not nachnamen or not vornamen_m or not vornamen_w or not strassen:
        print('❌ Namen oder Straßen konnten nicht geladen werden.')
        return 0, 1

    db = config['database']
    total = count if count is not None else db.get('anzahllehrer', 50)

    ort_ids = fetch_wuppertal_ort_ids(config)
    if not ort_ids:
        print('❌ Keine Ort-IDs für Wuppertal gefunden. Abbruch.')
        return 0, 1

    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/lehrer/create"
    auth = HTTPBasicAuth(db['username'], db['password'])

    print(f"\nBefülle K_Lehrer mit {total} Einträgen...")
    print(f"URL: {url}")
    print(f"Using username: {db['username']}\n")

    genders = balanced_genders(total)
    existing_kuerzel: Set[str] = set()
    created = 0
    failed = 0

    for idx in range(1, total + 1):
        geschlecht = genders[idx - 1]
        is_male = geschlecht == 3
        vorname = RAND.choice(vornamen_m if is_male else vornamen_w)
        nachname = RAND.choice(nachnamen)
        kuerzel = make_kuerzel(nachname, existing_kuerzel)

        email_local = f"{slugify_mail_part(vorname)}.{slugify_mail_part(nachname)}"

        titel = 'Dr.' if RAND.random() < 0.10 else ''

        roll_amts = RAND.random()
        if roll_amts < 0.60:
            amts = 'StR'
        elif roll_amts < 0.80:
            amts = 'Lehrer'
        elif roll_amts < 0.90:
            amts = 'OStR'
        else:
            amts = 'LiA'

        payload = {
            'kuerzel': kuerzel,
            'personalTyp': 'LEHRKRAFT',
            'anrede': 'Herr' if is_male else 'Frau',
            'titel': titel,
            'amtsbezeichnung': amts,
            'nachname': nachname,
            'vorname': vorname,
            'geschlecht': geschlecht,
            'geburtsdatum': random_birthdate(),
            'staatsangehoerigkeitID': pick_staatsangehoerigkeit(),
            'strassenname': RAND.choice(strassen),
            'hausnummer': hausnummer(),
            'hausnummerZusatz': '',
            'wohnortID': RAND.choice(ort_ids),
            'ortsteilID': None,
            'telefon': random_phone(),
            'telefonMobil': random_phone(),
            'emailPrivat': f"{email_local}@privat.l.example.com",
            'emailDienstlich': f"{email_local}@dienstlich.l.example.com",
            'foto': '',
            'istSichtbar': True,
            'istRelevantFuerStatistik': True,
            'leitungsfunktionen': [],
        }

        try:
            resp = requests.post(
                url,
                json=payload,
                auth=auth,
                verify=False,
                timeout=20,
            )

            # Fallback: fehlende Nationalität -> einmal ohne ID erneut senden
            if resp.status_code == 404 and 'Nationalität' in resp.text:
                payload['staatsangehoerigkeitID'] = None
                resp = requests.post(
                    url,
                    json=payload,
                    auth=auth,
                    verify=False,
                    timeout=20,
                )

            if resp.status_code in (200, 201):
                created += 1
                print(f"[{idx}/{total}] {kuerzel} {vorname} {nachname}: ✓ (HTTP {resp.status_code})")
            else:
                try:
                    err = resp.json().get('message', resp.text)
                except Exception:
                    err = resp.text
                failed += 1
                print(f"[{idx}/{total}] {kuerzel} {vorname} {nachname}: ❌ HTTP {resp.status_code} - {err[:180]}")
        except requests.exceptions.RequestException as exc:  # pragma: no cover
            failed += 1
            print(f"[{idx}/{total}] {kuerzel} {vorname} {nachname}: ❌ Fehler: {exc}")

    print(f"\nErgebnis: {created} erfolgreich, {failed} fehlgeschlagen")
    if failed == 0:
        print('✓ Alle Lehrer erfolgreich erstellt!')
    else:
        print(f"⚠️  {failed} Lehrer konnten nicht erstellt werden")

    return created, failed


if __name__ == '__main__':
    from check_server import load_config

    cfg = load_config()
    populate_lehrer(cfg)
