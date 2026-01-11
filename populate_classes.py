"""
Populate K_Klassen with dynamically generated classes based on school form and student count.

Classes are created based on:
- anzahlschueler from config.json (divided by 25 students per class)
- schulform from /db/{schema}/schule/stammdaten
- klassenstruktur.json template for grade levels per schulform group
"""

import json
from pathlib import Path
from typing import List, Tuple

import requests
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings for self-signed certificates
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def load_klassenstruktur() -> dict:
    """Load class structure template from JSON file."""
    path = Path(__file__).parent / 'katalogdaten' / 'klassenstruktur.json'
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def fetch_stammdaten(config) -> dict:
    """
    Fetch school master data including schulform and idSchuljahresabschnitt.
    
    Returns:
        dict: stammdaten with schulform, idSchuljahresabschnitt, etc.
    """
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/schule/stammdaten"
    auth = HTTPBasicAuth(db['username'], db['password'])
    
    resp = requests.get(url, auth=auth, verify=False, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_jahrgaenge(config) -> List[dict]:
    """
    Fetch all available Jahrgaenge (grade levels) from the API.
    
    Returns:
        list: List of Jahrgang objects with id, kuerzel, etc.
    """
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/jahrgaenge"
    auth = HTTPBasicAuth(db['username'], db['password'])
    
    resp = requests.get(url, auth=auth, verify=False, timeout=10)
    resp.raise_for_status()
    return resp.json()


def find_schulform_group(schulform: str, struktur: dict) -> dict:
    """
    Find the matching schulform group from klassenstruktur.json.
    
    Args:
        schulform: Schulform kuerzel (e.g., "G", "GY", "BK")
        struktur: Loaded klassenstruktur.json data
        
    Returns:
        dict: Matching group with jahrgaenge, or None if not found
    """
    for group in struktur.get('groups', []):
        if schulform in group.get('schulformen', []):
            return group
    return None


def generate_class_suffix(index: int) -> str:
    """
    Generate class suffix for given index.
    
    0 -> 'a', 1 -> 'b', ..., 25 -> 'z',
    26 -> 'aa', 27 -> 'ab', ..., 51 -> 'az',
    52 -> 'ba', 53 -> 'bb', ..., 77 -> 'bz',
    etc.
    
    Args:
        index: Zero-based index (0 = first class)
        
    Returns:
        str: Class suffix (e.g., 'a', 'b', 'aa', 'ab', etc.)
    """
    if index < 26:
        # Single letter: a-z
        return chr(ord('a') + index)
    else:
        # Double letter: aa-az, ba-bz, etc.
        first = chr(ord('a') + (index // 26) - 1)
        second = chr(ord('a') + (index % 26))
        return first + second


def map_jahrgang_id(kuerzel: str, jahrgaenge: List[dict]) -> int:
    """
    Map Jahrgang kuerzel to its ID from API data.
    
    Args:
        kuerzel: Jahrgang kuerzel (e.g., "01", "05", "EF")
        jahrgaenge: List of Jahrgang objects from API
        
    Returns:
        int: Jahrgang ID, or 0 if not found
    """
    for jg in jahrgaenge:
        if jg.get('kuerzel') == kuerzel:
            return jg.get('id', 0)
    return 0


def populate_classes(config) -> Tuple[int, int]:
    """
    Create classes for the school based on anzahlschueler and schulform.
    
    Args:
        config: Configuration dictionary with database settings
        
    Returns:
        Tuple of (created_count, failed_count)
    """
    print("\n=== Befülle K_Klassen mit dynamisch generierten Klassen ===\n")
    
    # Load class structure template
    struktur = load_klassenstruktur()
    
    # Fetch school master data
    print("Lade Schulstammdaten...")
    try:
        stammdaten = fetch_stammdaten(config)
    except Exception as e:
        print(f"❌ Fehler beim Laden der Stammdaten: {e}")
        return 0, 1
    
    schulform = stammdaten.get('schulform')
    id_schuljahresabschnitt = stammdaten.get('idSchuljahresabschnitt')
    
    if not schulform:
        print("❌ Keine Schulform in Stammdaten gefunden")
        return 0, 1
    
    if not id_schuljahresabschnitt:
        print("❌ Kein idSchuljahresabschnitt in Stammdaten gefunden")
        return 0, 1
    
    print(f"Schulform: {schulform}")
    print(f"idSchuljahresabschnitt: {id_schuljahresabschnitt}")
    
    # Check if BK/SB (requires Fachklassen data)
    if schulform in ['BK', 'SB']:
        print(f"⚠️  Schulform '{schulform}' benötigt Fachklassen-Konfiguration in der Datenbank")
        print("   Klassen-Erstellung für BK/SB wird übersprungen")
        return 0, 0
    
    # Find matching schulform group
    group = find_schulform_group(schulform, struktur)
    if not group:
        print(f"❌ Keine passende Klassenstruktur für Schulform '{schulform}' gefunden")
        return 0, 1
    
    print(f"Gefundene Gruppe: {group['name']}")
    
    # Fetch available Jahrgaenge from API
    print("Lade Jahrgänge...")
    try:
        jahrgaenge = fetch_jahrgaenge(config)
    except Exception as e:
        print(f"❌ Fehler beim Laden der Jahrgänge: {e}")
        return 0, 1
    
    # Calculate number of classes needed
    db = config['database']
    anzahl_schueler = db.get('anzahlschueler', 200)
    classes_per_student = 25
    total_classes = max(1, anzahl_schueler // classes_per_student)
    
    print(f"Anzahl Schüler: {anzahl_schueler}")
    print(f"Benötigte Klassen: {total_classes} (à ~{classes_per_student} Schüler)")
    
    # Get jahrgaenge from template
    template_jahrgaenge = group.get('jahrgaenge', [])
    num_jahrgaenge = len(template_jahrgaenge)
    
    if num_jahrgaenge == 0:
        print(f"❌ Keine Jahrgänge in Template für Gruppe '{group['name']}'")
        return 0, 1
    
    # Check if this is GY/GE/HI (with Oberstufe)
    is_oberstufe_schulform = schulform in ['GY', 'GE', 'HI']
    oberstufe_jahrgaenge = {'EF', 'Q1', 'Q2'}
    
    # Separate regular jahrgaenge from Oberstufe jahrgaenge
    regular_jahrgaenge = []
    oberstufe_jg = []
    
    for jg in template_jahrgaenge:
        if jg.get('kuerzel') in oberstufe_jahrgaenge and is_oberstufe_schulform:
            oberstufe_jg.append(jg)
        else:
            regular_jahrgaenge.append(jg)
    
    # Calculate classes distribution
    # For Oberstufe (EF/Q1/Q2): Always 1 class per grade (containing all students from that year)
    # For regular grades: Distribute classes evenly based on students per grade
    
    # Calculate students per grade (all grades get equal students)
    students_per_grade = anzahl_schueler / num_jahrgaenge
    
    # For regular jahrgaenge: calculate how many parallel classes needed
    num_regular_jahrgaenge = len(regular_jahrgaenge)
    
    if num_regular_jahrgaenge > 0:
        # Each regular grade gets students_per_grade / 25 classes
        classes_per_jahrgang = max(1, int(students_per_grade // classes_per_student))
        # Calculate total regular classes needed
        total_regular_classes = classes_per_jahrgang * num_regular_jahrgaenge
        # Distribute remainder classes to first jahrgaenge
        remainder_students = int(anzahl_schueler - (students_per_grade * num_jahrgaenge))
        remainder = max(0, remainder_students // classes_per_student)
    else:
        classes_per_jahrgang = 0
        remainder = 0
    
    print(f"Jahrgänge: {num_jahrgaenge}")
    print(f"Schüler pro Jahrgang: ~{int(students_per_grade)}")
    if is_oberstufe_schulform and oberstufe_jg:
        print(f"Klassen pro Jahrgang (Sek I): ~{classes_per_jahrgang}")
        print(f"Klassen pro Jahrgang (Oberstufe): 1 (alle ~{int(students_per_grade)} Schüler des Jahrgangs)")
    else:
        print(f"Klassen pro Jahrgang: ~{classes_per_jahrgang}")
    print()
    
    # Prepare API request
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/klassen/create"
    auth = HTTPBasicAuth(db['username'], db['password'])
    
    print(f"URL: {url}\n")
    
    # For certain Schulformen (H, SK, R, SR, S), the API may reject a fixed idSchulgliederung.
    # In those cases, omit the field to let the server pick a valid default.
    omit_schulgliederung = schulform in ['H', 'SK', 'R', 'SR', 'S']
    
    created = 0
    failed = 0
    created_classes = []  # Track created class IDs and kuerzels
    sortierung = 1  # Global sorting counter for all classes
    
    # Create classes for regular jahrgaenge (non-Oberstufe)
    for jg_idx, jg_template in enumerate(regular_jahrgaenge):
        jg_kuerzel = jg_template.get('kuerzel')
        jg_beschreibung = jg_template.get('beschreibung', f"Jahrgang {jg_kuerzel}")
        jg_prefix = jg_template.get('prefix', '')  # For BK classes
        
        # Map to API Jahrgang ID
        jg_id = map_jahrgang_id(jg_kuerzel, jahrgaenge)
        if jg_id == 0:
            print(f"⚠️  Jahrgang '{jg_kuerzel}' nicht in API gefunden, überspringe")
            continue
        
        # Distribute extra classes to first jahrgaenge
        num_classes_this_jg = classes_per_jahrgang
        if jg_idx < remainder:
            num_classes_this_jg += 1
        
        print(f"Jahrgang {jg_kuerzel} (ID {jg_id}): {num_classes_this_jg} Klassen")
        
        # Create classes for this jahrgang
        for class_idx in range(num_classes_this_jg):
            suffix = generate_class_suffix(class_idx)
            parallelitaet = suffix[0].upper()  # First letter uppercase
            
            if jg_prefix:
                kuerzel = f"{jg_prefix}{jg_kuerzel}{suffix}"
            else:
                kuerzel = f"{jg_kuerzel}{suffix}"
            
            beschreibung = f"Klasse {kuerzel}"
            
            # Set fields based on Schulform
            # BK/SB (vocational schools) use different organizational form and klassenart
            if schulform in ['BK', 'SB']:
                payload = {
                    'idSchuljahresabschnitt': id_schuljahresabschnitt,
                    'kuerzel': kuerzel,
                    'idJahrgang': jg_id,
                    'parallelitaet': parallelitaet,
                    'sortierung': sortierung,
                    'beschreibung': beschreibung,
                    'idBerufsbildendOrganisationsform': 1005000,  # Vocational organization form
                    'idKlassenart': 7001,  # Vocational class type
                    'idSchulgliederung': 1001000,  # BK Schulgliederung
                }
            else:
                # General education schools
                payload = {
                    'idSchuljahresabschnitt': id_schuljahresabschnitt,
                    'kuerzel': kuerzel,
                    'idJahrgang': jg_id,
                    'parallelitaet': parallelitaet,
                    'sortierung': sortierung,
                    'beschreibung': beschreibung,
                    'idAllgemeinbildendOrganisationsform': 3001001,  # Standard value
                    'idKlassenart': 7002,  # Standard Klassenart
                }
                if not omit_schulgliederung:
                    payload['idSchulgliederung'] = 0
            
            sortierung += 1  # Increment for next class
            
            try:
                resp = requests.post(
                    url,
                    json=payload,
                    auth=auth,
                    verify=False,
                    timeout=20,
                )
                
                if resp.status_code in (200, 201):
                    created += 1
                    # Save created class info
                    try:
                        response_data = resp.json()
                        class_id = response_data.get('id')
                        if class_id:
                            created_classes.append({'id': class_id, 'kuerzel': kuerzel})
                    except Exception:
                        pass
                    print(f"  [{created}/{total_classes}] {kuerzel}: ✓ (HTTP {resp.status_code})")
                else:
                    try:
                        err = resp.json().get('message', resp.text)
                    except Exception:
                        err = resp.text
                    failed += 1
                    print(f"  [{created + failed}/{total_classes}] {kuerzel}: ❌ HTTP {resp.status_code} - {err[:120]}")
            
            except requests.exceptions.RequestException as exc:
                failed += 1
                print(f"  [{created + failed}/{total_classes}] {kuerzel}: ❌ Fehler: {exc}")
        
        print()  # Blank line between jahrgaenge
    
    # Create Oberstufe classes (EF, Q1, Q2) - always 1 class per jahrgang, no suffix
    for jg_template in oberstufe_jg:
        jg_kuerzel = jg_template.get('kuerzel')
        jg_beschreibung = jg_template.get('beschreibung', f"Jahrgang {jg_kuerzel}")
        
        # Map to API Jahrgang ID
        jg_id = map_jahrgang_id(jg_kuerzel, jahrgaenge)
        if jg_id == 0:
            print(f"⚠️  Jahrgang '{jg_kuerzel}' nicht in API gefunden, überspringe")
            continue
        
        print(f"Jahrgang {jg_kuerzel} (ID {jg_id}): 1 Klasse (Oberstufe, alle Schüler)")
        
        # Create single class without suffix (or just use the kuerzel as-is)
        kuerzel = jg_kuerzel
        parallelitaet = 'A'  # Standard for single Oberstufe class
        beschreibung = f"Jahrgang {jg_kuerzel}"
        
        # Set fields based on Schulform
        if schulform in ['BK', 'SB']:
            payload = {
                'idSchuljahresabschnitt': id_schuljahresabschnitt,
                'kuerzel': kuerzel,
                'idJahrgang': jg_id,
                'parallelitaet': parallelitaet,
                'sortierung': sortierung,
                'beschreibung': beschreibung,
                'idBerufsbildendOrganisationsform': 1005000,
                'idKlassenart': 7001,
                'idSchulgliederung': 1001000,
            }
        else:
            payload = {
                'idSchuljahresabschnitt': id_schuljahresabschnitt,
                'kuerzel': kuerzel,
                'idJahrgang': jg_id,
                'parallelitaet': parallelitaet,
                'sortierung': sortierung,
                'beschreibung': beschreibung,
                'idAllgemeinbildendOrganisationsform': 3001001,
                'idKlassenart': 7002,
            }
            if not omit_schulgliederung:
                payload['idSchulgliederung'] = 0
        
        sortierung += 1  # Increment for next class
        
        try:
            resp = requests.post(
                url,
                json=payload,
                auth=auth,
                verify=False,
                timeout=20,
            )
            
            if resp.status_code in (200, 201):
                created += 1
                # Save created class info
                try:
                    response_data = resp.json()
                    class_id = response_data.get('id')
                    if class_id:
                        created_classes.append({'id': class_id, 'kuerzel': kuerzel})
                except Exception:
                    pass
                print(f"  [{created}/{total_classes}] {kuerzel}: ✓ (HTTP {resp.status_code})")
            else:
                try:
                    err = resp.json().get('message', resp.text)
                except Exception:
                    err = resp.text
                failed += 1
                print(f"  [{created + failed}/{total_classes}] {kuerzel}: ❌ HTTP {resp.status_code} - {err[:120]}")
        
        except requests.exceptions.RequestException as exc:
            failed += 1
            print(f"  [{created + failed}/{total_classes}] {kuerzel}: ❌ Fehler: {exc}")
        
        print()  # Blank line between jahrgaenge
    
    print(f"\nErgebnis: {created} erfolgreich, {failed} fehlgeschlagen")
    if failed == 0:
        print("✓ Alle Klassen erfolgreich erstellt!")
    else:
        print(f"⚠️  {failed} Klassen konnten nicht erstellt werden")
    
    # Save created classes to cache file for assign_class_leaders
    if created_classes:
        cache_file = Path(__file__).parent / '.klassen_cache.json'
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(created_classes, f, indent=2, ensure_ascii=False)
        print(f"\n💾 {len(created_classes)} Klassen-IDs in Cache gespeichert")
    
    return created, failed


def fetch_all_classes(config) -> List[dict]:
    """
    Fetch all classes from the database.
    
    Returns:
        list: List of class objects with id, kuerzel, etc.
    """
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/klassen"
    auth = HTTPBasicAuth(db['username'], db['password'])
    
    resp = requests.get(url, auth=auth, verify=False, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_all_teachers(config) -> List[dict]:
    """
    Fetch all teachers from the database.
    
    Returns:
        list: List of teacher objects with id, kuerzel, etc.
    """
    db = config['database']
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/lehrer"
    auth = HTTPBasicAuth(db['username'], db['password'])
    
    resp = requests.get(url, auth=auth, verify=False, timeout=10)
    resp.raise_for_status()
    return resp.json()


def assign_class_leaders(config) -> Tuple[int, int]:
    """
    Assign 2 random teachers (Klassenleitungen) to each class.
    Ensures each teacher has max 2 class assignments.
    Uses .klassen_cache.json from populate_classes().
    
    Args:
        config: Configuration dictionary with database settings
        
    Returns:
        Tuple of (assigned_count, failed_count)
    """
    import random
    
    print("\n=== Weise Klassenleitungen zu (2 Lehrer pro Klasse) ===\n")
    
    # Load classes from cache
    cache_file = Path(__file__).parent / '.klassen_cache.json'
    if not cache_file.exists():
        print(f"❌ Cache-Datei nicht gefunden: {cache_file}")
        print("   Bitte zuerst populate_classes() ausführen!")
        return 0, 1
    
    with open(cache_file, 'r', encoding='utf-8') as f:
        classes = json.load(f)
    
    print(f"Lade {len(classes)} Klassen aus Cache...")
    
    # Fetch all teachers
    print("Lade alle Lehrkräfte...")
    try:
        teachers = fetch_all_teachers(config)
    except Exception as e:
        print(f"❌ Fehler beim Laden der Lehrkräfte: {e}")
        return 0, 1
    
    if not classes:
        print("⚠️  Keine Klassen gefunden")
        return 0, 0
    
    if not teachers:
        print("❌ Keine Lehrkräfte gefunden")
        return 0, 1
    
    num_classes = len(classes)
    num_teachers = len(teachers)
    
    print(f"Gefunden: {num_classes} Klassen, {num_teachers} Lehrkräfte")
    
    # Check if we have enough teachers (need 2 per class, max 2 classes per teacher)
    min_teachers_needed = num_classes  # At minimum 1 per class if doubled
    if num_teachers < min_teachers_needed:
        print(f"⚠️  Warnung: Nur {num_teachers} Lehrkräfte für {num_classes} Klassen")
        print(f"   (Optimal wären mindestens {min_teachers_needed} Lehrkräfte)")
    
    print()
    
    # Track teacher assignments (teacher_id -> count)
    teacher_assignments = {t['id']: 0 for t in teachers}
    teacher_ids = [t['id'] for t in teachers]
    
    db = config['database']
    url_base = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/klassen"
    auth = HTTPBasicAuth(db['username'], db['password'])
    
    assigned = 0
    failed = 0
    
    for idx, klasse in enumerate(classes, start=1):
        klasse_id = klasse.get('id')
        klasse_kuerzel = klasse.get('kuerzel', '?')
        
        if not klasse_id:
            print(f"[{idx}/{num_classes}] {klasse_kuerzel}: ⚠️  Keine ID, übersprungen")
            failed += 1
            continue
        
        # Find available teachers (those with < 2 assignments)
        available = [tid for tid in teacher_ids if teacher_assignments[tid] < 2]
        
        if len(available) < 2:
            # Not enough available teachers, use any teachers
            print(f"[{idx}/{num_classes}] {klasse_kuerzel}: ⚠️  Nicht genug verfügbare Lehrkräfte (verwende beliebige)")
            available = teacher_ids
        
        # Pick 2 random teachers
        if len(available) >= 2:
            selected = random.sample(available, 2)
        else:
            # Fallback: pick what we have and maybe duplicate
            selected = available + random.sample(teacher_ids, 2 - len(available))
        
        # Update assignment counts
        for tid in selected:
            teacher_assignments[tid] += 1
        
        # PATCH the class with klassenLeitungen
        payload = {
            'klassenLeitungen': selected
        }
        
        url = f"{url_base}/{klasse_id}"
        try:
            resp = requests.patch(
                url,
                json=payload,
                auth=auth,
                verify=False,
                timeout=20,
            )
            
            if resp.status_code in (200, 204):
                assigned += 1
                print(f"[{idx}/{num_classes}] {klasse_kuerzel}: ✓ Lehrer {selected}")
            else:
                try:
                    err = resp.json().get('message', resp.text)
                except Exception:
                    err = resp.text
                failed += 1
                print(f"[{idx}/{num_classes}] {klasse_kuerzel}: ❌ HTTP {resp.status_code} - {err[:120]}")
        
        except requests.exceptions.RequestException as exc:
            failed += 1
            print(f"[{idx}/{num_classes}] {klasse_kuerzel}: ❌ Fehler: {exc}")
    
    # Statistics
    print(f"\nErgebnis: {assigned} erfolgreich, {failed} fehlgeschlagen")
    
    # Show teacher assignment distribution
    assignments_dist = {}
    for count in teacher_assignments.values():
        assignments_dist[count] = assignments_dist.get(count, 0) + 1
    
    print("\nLehrer-Verteilung:")
    for count in sorted(assignments_dist.keys()):
        print(f"  {assignments_dist[count]} Lehrkräfte mit {count} Klassen")
    
    if failed == 0:
        print("\n✓ Alle Klassenleitungen erfolgreich zugewiesen!")
    else:
        print(f"\n⚠️  {failed} Zuweisungen fehlgeschlagen")
    
    return assigned, failed


if __name__ == '__main__':
    from check_server import load_config
    
    cfg = load_config()
    populate_classes(cfg)
    assign_class_leaders(cfg)
