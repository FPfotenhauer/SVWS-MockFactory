"""
Populate Betriebe catalog with synthetic data.
Creates 150 entries using random names (two surnames joined by ' und '),
random street names from katalogdaten/Strassen.csv, and synthetic contact data.
"""

import csv
import json
import random
import requests
from pathlib import Path
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings for self-signed certificates
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

RAND = random.Random()


def load_nachnamen():
    """Load last names from katalogdaten/nachnamen.json."""
    path = Path(__file__).parent / 'katalogdaten' / 'nachnamen.json'
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_vornamen(filename):
    """Load first names from the given katalogdaten JSON file."""
    path = Path(__file__).parent / 'katalogdaten' / filename
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_strassen():
    """Load street names from katalogdaten/Strassen.csv (column 'Strasse')."""
    path = Path(__file__).parent / 'katalogdaten' / 'Strassen.csv'
    strassen = []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            street = (row.get('Strasse') or '').strip().rstrip(',')
            if street:
                strassen.append(street)
    return strassen


def random_sentence():
    """Return a short German remark sentence."""
    sentences = [
        "Termin nur nach Vereinbarung.",
        "Bitte nur vormittags anrufen.",
        "Lieferung erfolgt wöchentlich am Freitag.",
        "Erwartet Rückmeldung bis Ende des Monats.",
        "Bevorzugt Kommunikation per E-Mail.",
        "Hat Interesse an langfristiger Kooperation.",
        "Praktikumsplätze ab nächstem Quartal verfügbar.",
        "Telefonisch schwer erreichbar, bitte Geduld.",
        "Nur Kontaktaufnahme durch die Schulleitung erwünscht.",
        "Datenschutzunterlagen bereits eingereicht.",
    ]
    return RAND.choice(sentences)


def random_phone():
    """Generate phone number like 012345-XXXXXX."""
    return f"012345-{RAND.randint(100000, 999999)}"


def random_name(nachnamen):
    """Generate company-like name from two random surnames."""
    first, second = RAND.sample(nachnamen, 2)
    return f"{first} und {second}"


def slugify_mail_part(text):
    """Rudimentary slug for email local part."""
    replacements = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
        'Ä': 'ae', 'Ö': 'oe', 'Ü': 'ue',
    }
    lowered = ''.join(replacements.get(ch, ch) for ch in text.lower())
    return ''.join(ch for ch in lowered if ch.isalnum() or ch == '-')


def random_hausnummer():
    number = RAND.randint(1, 200)
    suffix = RAND.choice(['', '', '', '', 'a', 'b', 'c'])  # mostly empty
    return str(number) + suffix


def random_name_zusatz():
    return RAND.choice(['GmbH', 'AG', 'KG', 'OHG', 'UG', 'e.K.'])


def random_branche():
    return RAND.choice([
        'Handwerk', 'IT-Dienstleistungen', 'Gesundheit', 'Bau', 'Lebensmittel',
        'Logistik', 'Automobil', 'Tourismus', 'Bildung', 'Finanzen'
    ])


def populate_betriebe(config, count=150):
    """Populate Betriebe via REST API with synthetic data and two contacts each."""
    nachnamen = load_nachnamen()
    strassen = load_strassen()
    vornamen_m = load_vornamen('vornamen_m.json')
    vornamen_w = load_vornamen('vornamen_w.json')

    if not nachnamen:
        print("❌ Konnte keine Nachnamen laden.")
        return 0, 1
    if not strassen:
        print("❌ Konnte keine Straßennamen laden.")
        return 0, 1
    if not vornamen_m or not vornamen_w:
        print("❌ Konnte keine Vornamen laden.")
        return 0, 1

    server = config['database']['server']
    port = config['database']['httpsport']
    schema = config['database']['schema']
    username = config['database']['username']
    password = config['database']['password']

    # If the config contains an 'anzahlbetriebe' value, use it (overrides
    # the `count` argument). Accept strings or ints; on failure keep `count`.
    try:
        cfg_count = config.get('database', {}).get('anzahlbetriebe')
        if cfg_count is not None:
            count = int(cfg_count)
    except Exception:
        # leave provided/default count unchanged on any error
        pass

    url_betriebe = f"https://{server}:{port}/db/{schema}/schule/betriebe/create"
    url_ap = f"https://{server}:{port}/db/{schema}/schule/betriebe-ansprechpartner/create"

    print(f"\nBefülle Katalog 'Betriebe' mit {count} Einträgen...")
    print(f"URL: {url_betriebe}")
    print(f"Using username: {username}\n")

    created = 0
    failed = 0

    for idx in range(1, count + 1):
        name = random_name(nachnamen)
        payload = {
            'name': name,
            'nameZusatz': random_name_zusatz(),
            'bemerkungen': random_sentence(),
            'branche': random_branche(),
            'idBetriebsart': 1,
            'istAusbildungsbetrieb': RAND.choice([True, False]),
            'istMassnahmentraeger': RAND.choice([True, False]),
            'belehrungNachISGErforderlich': RAND.choice([True, False]),
            'erweitertesFuehrungszeugnisErforderlich': RAND.choice([True, False]),
            'bietetPraktikumsplaetzeAn': RAND.choice([True, False]),
            'strasse': RAND.choice(strassen),
            'hausnummer': random_hausnummer(),
            'hausnummerZusatz': '',
            # idOrt is not available from Strassen.csv; using placeholder 1.
            # Adjust if you have valid Ort-IDs available.
            'idOrt': 1,
            'telefon1': random_phone(),
            'telefon2': random_phone(),
            'fax': random_phone(),
            'eMail': f"kontakt{idx}@betrieb.example.com",
            'istSichtbar': True,
            'sortierung': idx,
        }

        try:
            response = requests.post(
                url_betriebe,
                json=payload,
                auth=HTTPBasicAuth(username, password),
                verify=False,
                timeout=15,
            )

            if response.status_code in (200, 201):
                print(f"[{idx}/{count}] {name}: ✓ (HTTP {response.status_code})")
                created += 1
                try:
                    data = response.json()
                    betriebs_id = data.get('id') or data.get('ID')
                except Exception:
                    betriebs_id = None

                if betriebs_id:
                    contacts = [
                        ('Herr', RAND.choice(vornamen_m)),
                        ('Frau', RAND.choice(vornamen_w)),
                    ]
                    for anrede, rufname in contacts:
                        nachname = RAND.choice(nachnamen)
                        email_local = f"{slugify_mail_part(rufname)}.{slugify_mail_part(nachname)}"
                        ap_payload = {
                            'idBetrieb': betriebs_id,
                            'anrede': anrede,
                            'name': nachname,
                            'rufname': rufname,
                            'telefon': random_phone(),
                            'eMail': f"{email_local}@betrieb.example.com",
                        }
                        try:
                            ap_resp = requests.post(
                                url_ap,
                                json=ap_payload,
                                auth=HTTPBasicAuth(username, password),
                                verify=False,
                                timeout=10,
                            )
                            if ap_resp.status_code in (200, 201):
                                print(f"    -> Ansprechpartner {anrede} {rufname} {nachname}: ✓ (HTTP {ap_resp.status_code})")
                            else:
                                try:
                                    ap_err = ap_resp.json().get('message', ap_resp.text)
                                except Exception:
                                    ap_err = ap_resp.text
                                print(f"    -> Ansprechpartner {anrede} {rufname} {nachname}: ❌ HTTP {ap_resp.status_code} - {ap_err}")
                        except requests.exceptions.RequestException as exc:  # pragma: no cover
                            print(f"    -> Ansprechpartner {anrede} {rufname} {nachname}: ❌ Fehler: {exc}")
                else:
                    print("    -> Keine Ansprechpartner erstellt (konnte ID nicht ermitteln)")
            else:
                try:
                    error_msg = response.json().get('message', response.text)
                except Exception:
                    error_msg = response.text
                print(f"[{idx}/{count}] {name}: ❌ HTTP {response.status_code} - {error_msg}")
                failed += 1
        except requests.exceptions.RequestException as exc:  # pragma: no cover
            print(f"[{idx}/{count}] {name}: ❌ Fehler: {exc}")
            failed += 1

    print(f"\nErgebnis: {created} erfolgreich, {failed} fehlgeschlagen")
    if failed == 0:
        print("✓ Alle Betriebe erfolgreich erstellt!")
    else:
        print(f"⚠️  {failed} Betriebe konnten nicht erstellt werden")

    return created, failed


if __name__ == '__main__':
    from check_server import load_config

    cfg = load_config()
    populate_betriebe(cfg)
