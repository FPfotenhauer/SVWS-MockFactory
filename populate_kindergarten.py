"""
Modul zum Befüllen des Katalogs 'Kindergarten' im SVWS-Server.
Nur für Schulformen G, PS, S, V oder WF.
"""

import requests
import json
import urllib3
import random
import csv
from pathlib import Path

# SSL-Warnungen deaktivieren (für selbstsignierte Zertifikate)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def load_config(config_file='config.json'):
    """Lädt die Konfiguration aus der JSON-Datei."""
    config_path = Path(__file__).parent / config_file
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_school_data(config):
    """
    Ruft die Schuldaten vom Server ab, um die Schulform zu ermitteln.
    
    Args:
        config: Konfigurationsdictionary mit Verbindungsdaten
        
    Returns:
        dict: Schuldaten mit Schulform (schulform), oder None bei Fehler
    """
    db_config = config['database']
    server = db_config['server']
    port = db_config['httpsport']
    schema = db_config['schema']
    username = db_config['username']
    password = db_config['password']
    
    url = f"https://{server}:{port}/db/{schema}/schule/stammdaten"
    
    try:
        response = requests.get(
            url,
            auth=(username, password),
            headers={
                'Accept': 'application/json'
            },
            verify=False,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Fehler beim Abrufen der Schuldaten: HTTP {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Fehler beim Abrufen der Schuldaten: {e}")
        return None


def load_street_names():
    """Lädt Straßennamen aus der CSV-Datei."""
    streets = []
    csv_path = Path(__file__).parent / 'katalogdaten' / 'Strassen.csv'
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if 'Strasse' in row and row['Strasse']:
                streets.append(row['Strasse'])
    
    return streets


# Deutsche Kindergartennamen-Komponenten
KITA_NAMES = [
    "Sonnenschein", "Regenbogen", "Pusteblume", "Abenteuerland", "Sterntaler",
    "Wirbelwind", "Traumland", "Zauberbaum", "Glücksklee", "Sonnenblume",
    "Wichtelwald", "Rappelkiste", "Spatzennest", "Bärenhöhle", "Entdeckerland",
    "Farbklecks", "Märchenwald", "Pipi-Langstrumpf", "Tausendfüßler", "Wolkenschaf",
    "Löwenzahn", "Kunterbunt", "Sternschnuppe", "Waldgeister", "Fliegenpilz",
    "Schatzinsel", "Elfenreich", "Zauberflöte", "Blumenwiese", "Kinderparadies",
    "Himmelsstürmer", "Pfiffikus", "Weltentdecker", "Schatzkiste", "Tausendsassa",
    "Regenwurm", "Känguru", "Marienkäfer", "Feenland", "Koboldmühle",
    "Purzelbaum", "Wirbelwelt", "Lummerland", "Nimmerland", "Bullerbü",
    "Hoppetosse", "Rotkäppchen", "Schneeweißchen", "Rosenrot", "Sternenhimmel"
]

KITA_PREFIXES = ["Kita", "Kindergarten", "KiTa"]

KITA_SUFFIXES = ["", " I", " II", " Mitte", " Nord", " Süd", " Ost", " West"]

BEMERKUNGEN = [
    "Tolles Außengelände!",
    "Sehr freundliches Personal.",
    "Moderne Ausstattung vorhanden.",
    "Großer Garten zum Spielen.",
    "Zentrale Lage in der Innenstadt.",
    "Naturnahe Umgebung mit Wald.",
    "Kleine Gruppen, individuelle Betreuung.",
    "Musikalische Früherziehung im Programm.",
    "Gesunde Ernährung wird großgeschrieben.",
    "Barrierefreier Zugang vorhanden.",
    "Familiäre Atmosphäre.",
    "Kreatives Angebot für alle Altersgruppen.",
    "Bilinguale Betreuung möglich.",
    "Viele Ausflüge und Projekte.",
    "Erfahrenes und liebevolles Team.",
    "Flexible Öffnungszeiten.",
    "Intensive Elternzusammenarbeit.",
    "Schwerpunkt auf Bewegung und Sport.",
    "Regelmäßige Vorschulangebote.",
    "Enge Kooperation mit Grundschulen."
]

PLZ_WUPPERTAL = [
    "42103", "42105", "42107", "42109", "42111", "42113", "42115", "42117",
    "42119", "42275", "42277", "42279", "42281", "42283", "42285", "42287",
    "42289", "42327", "42329", "42349", "42389", "42399"
]


def generate_kindergarten_name(existing_names=None):
    """
    Generiert einen zufälligen Kindergartennamen.
    
    Args:
        existing_names: Set bereits verwendeter Namen zur Vermeidung von Duplikaten
        
    Returns:
        str: Eindeutiger Kindergartenname
    """
    if existing_names is None:
        existing_names = set()
    
    # Versuche bis zu 100 mal einen eindeutigen Namen zu generieren
    for attempt in range(100):
        prefix = random.choice(KITA_PREFIXES)
        name = random.choice(KITA_NAMES)
        suffix = random.choice(KITA_SUFFIXES)
        full_name = f"{prefix} {name}{suffix}"
        
        if full_name not in existing_names:
            return full_name
    
    # Fallback: Füge eine Nummer hinzu
    base_name = f"{random.choice(KITA_PREFIXES)} {random.choice(KITA_NAMES)}"
    counter = 1
    while f"{base_name} {counter}" in existing_names:
        counter += 1
    return f"{base_name} {counter}"


def generate_phone_number():
    """Generiert eine zufällige Telefonnummer im Format 012345-######."""
    prefix = "0202"
    suffix = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    return f"{prefix}-{suffix}"


def generate_email(index):
    """Generiert eine E-Mail-Adresse."""
    return f"kita{index}@kita.example.com"


def generate_house_number():
    """Generiert eine zufällige Hausnummer."""
    return str(random.randint(1, 200))


def generate_kindergarten_entries(streets, count=20):
    """
    Generiert Kindergarten-Einträge mit Zufallsdaten.
    
    Args:
        streets: Liste der Straßennamen
        count: Anzahl der zu generierenden Einträge
        
    Returns:
        list: Liste der Kindergarten-Einträge
    """
    entries = []
    used_names = set()
    
    for i in range(1, count + 1):
        # Generiere eindeutigen Namen
        name = generate_kindergarten_name(used_names)
        used_names.add(name)
        
        entry = {
            "bezeichnung": name,
            "bemerkung": random.choice(BEMERKUNGEN),
            "tel": generate_phone_number(),
            "email": generate_email(i),
            "strassenname": random.choice(streets),
            "hausNr": generate_house_number(),
            "hausNrZusatz": "",
            "plz": random.choice(PLZ_WUPPERTAL),
            "ort": "Wuppertal",
            "sortierung": i,
            "istSichtbar": True
        }
        entries.append(entry)
    
    return entries


def populate_kindergarten(config):
    """
    Befüllt den Katalog 'Kindergarten' mit 20 Einträgen.
    Nur für Schulformen G, PS, S, V oder WF.
    
    Args:
        config: Konfigurationsdictionary mit Verbindungsdaten
        
    Returns:
        tuple: (created_count, failed_count)
    """
    db_config = config['database']
    
    server = db_config['server']
    port = db_config['httpsport']
    schema = db_config['schema']
    username = db_config['username']
    password = db_config['password']
    
    # Abrufen der Schuldaten
    print("Rufe Schuldaten ab...")
    school_data = get_school_data(config)
    
    if not school_data:
        print("Fehler: Schuldaten konnten nicht abgerufen werden.")
        return 0, 1
    
    schulform = school_data.get('schulform')
    print(f"Schulform: {schulform}")
    
    # Prüfen ob Kindergarten für diese Schulform relevant ist
    relevant_schulformen = ['G', 'PS', 'S', 'V', 'WF']
    if schulform not in relevant_schulformen:
        print(f"⚠ Kindergarten-Katalog nicht relevant für Schulform '{schulform}'")
        print(f"  (Nur für Schulformen: {', '.join(relevant_schulformen)})")
        return 0, 0
    
    print()
    
    # Laden der Straßennamen
    try:
        streets = load_street_names()
        print(f"✓ {len(streets)} Straßennamen geladen")
    except Exception as e:
        print(f"Fehler beim Laden der Straßennamen: {e}")
        return 0, 1
    
    # Generieren der Kindergarten-Einträge
    kindergarten_entries = generate_kindergarten_entries(streets, count=20)
    
    url = f"https://{server}:{port}/db/{schema}/kindergarten/create"
    
    print()
    print(f"Befülle Katalog 'Kindergarten' mit {len(kindergarten_entries)} Einträgen...")
    print(f"URL: {url}")
    print(f"Using username: {username}")
    print()
    
    created_count = 0
    failed_count = 0
    retry_pool = []  # Namen die wir bei Duplikaten erneut versuchen können
    
    for i, entry in enumerate(kindergarten_entries, 1):
        max_retries = 3
        success = False
        
        for retry_attempt in range(max_retries):
            try:
                # Bei Retry: Generiere einen neuen Namen
                if retry_attempt > 0:
                    used_names = {e['bezeichnung'] for e in kindergarten_entries}
                    entry['bezeichnung'] = generate_kindergarten_name(used_names)
                
                response = requests.post(
                    url,
                    auth=(username, password),
                    json=entry,
                    headers={
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    verify=False,
                    timeout=30
                )
                
                if retry_attempt == 0:
                    print(f"[{i}/{len(kindergarten_entries)}] {entry['bezeichnung']}: ", end="")
                else:
                    print(f"  Retry {retry_attempt} mit '{entry['bezeichnung']}': ", end="")
                
                if response.status_code == 200 or response.status_code == 201:
                    print(f"✓ (HTTP {response.status_code})")
                    created_count += 1
                    success = True
                    break
                elif response.status_code == 400 and 'bereits vorhanden' in response.text:
                    # Duplikat - versuche erneut mit neuem Namen
                    if retry_attempt < max_retries - 1:
                        print(f"✗ Duplikat")
                    else:
                        print(f"✗ (HTTP {response.status_code}) - Alle Retries erschöpft")
                        failed_count += 1
                else:
                    print(f"✗ (HTTP {response.status_code})")
                    print(f"  Response: {response.text[:200]}")
                    failed_count += 1
                    break
                    
            except requests.exceptions.RequestException as e:
                print(f"✗ Fehler: {e}")
                failed_count += 1
                break
        
        if not success and retry_attempt == max_retries - 1:
            # Alle Retries fehlgeschlagen
            pass
    
    print()
    print(f"Ergebnis: {created_count} erfolgreich, {failed_count} fehlgeschlagen")
    
    if failed_count == 0:
        print("✓ Alle Kindergarten-Einträge erfolgreich erstellt!")
    else:
        print(f"⚠ {failed_count} Einträge konnten nicht erstellt werden.")
    
    return created_count, failed_count


if __name__ == '__main__':
    config = load_config()
    populate_kindergarten(config)
