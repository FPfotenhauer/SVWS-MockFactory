# SVWS-MockFactory

Eine Factory um im SVWS-Server Demonstrationsdatenbanken zu erstellen über die API.

Dieses Python-Programm erstellt realistische Testdatenbanken für den SVWS-Server über dessen REST-API. Die Verbindungsdaten und Konfiguration sind in der `config.json` hinterlegt.

## Features

- ✓ **Server-Status prüfen**: Verbindung zum SVWS-Server testen
- ✓ **Datenbank-Schema verwalten**: Erstellen, löschen, auflisten
- ✓ **Datenbank initialisieren**: Schema mit Schulnummer und Schulinformationen initialisieren
- ✓ **Kataloge füllen**: Automatische Befüllung der Schuldatenbank-Kataloge
  - Schulen (190 NRW Schulen aus katalogdaten/Schulen.csv mit idSchulform-Mapping)
  - Fahrschülerarten (15 Einträge)
  - Einwilligungsarten (7 Einträge aus katalogdaten/einwilligungen.json)
  - Förderschwerpunkte (10+ Einträge, schulformabhängig)
  - Floskelgruppen (11 Einträge aus katalogdaten/Floskelgruppenart.json)
  - Floskeln (47 Einträge aus katalogdaten/Floskeln.csv)
  - Haltestellen (10 Einträge aus katalogdaten/haltestellen.txt mit Zufallsdistanzen)
  - Lernplattformen (Einträge aus katalogdaten/lernplattformen.txt)
  - Vermerkarten (7 Einträge aus katalogdaten/vermerkarten.txt)
  - Betriebe (konfigurierbare Anzahl synthetischer Einträge mit je 2 Ansprechpartnern)
  - Kindergarten (20 synthetische Einträge, nur für Schulformen G, PS, S, V, WF)
  - Lehrkräfte (konfigurierbare Anzahl, standardmäßig 100 aus config.json)
  - Klassen (dynamisch basierend auf Schülerzahl und Schulform)
- ✓ **Schulstammdaten patchen**: Aktualisiert Schulinformationen nach der Initialisierung mit Test-Werten
- ✓ **Lehrkräfte generieren**: Realistische Lehrkräftedaten mit Geschlecht, Titel, Amtsbezeichnung, Adressen und Kontaktdaten
- ✓ **Klassen erstellen**: Dynamische Klassengenerierung basierend auf Schülerzahl (~25 Schüler/Klasse) mit schulformspezifischen Jahrgängen und automatischer Klassenleiterzuweisung
- ✓ **Schülerdaten generieren**: Realistische Schülerdaten erstellen (schulform-/jahrgangsbasiert)
- ✓ **Schüler-Telefonnummern anlegen**: Legt pro Schüler zwei Telefonnummern über Telefonarten an
- ✓ **Schüler-Schulbesuch patchen**: Setzt für Zieljahrgänge eine Grundschule aus dem Schulenkatalog
- ✓ **Schüler-Sprachbelegungen anlegen**: Legt für Zieljahrgänge zwei Sprachbelegungen (E/S) an
- ✓ **Schüler-Misc-Daten anlegen**: Legt pro Schüler drei zufällige Vermerke an und setzt Einwilligungen/Lernplattformen auf aktiv
- ✓ **Schüler-Erzieherdaten anlegen**: Legt pro Schüler zwei Erzieher-Personen an (1. Person weiblich, 2. Person männlich)
- ✓ **Schüler-Betrieb zuordnen**: Ordnet jedem Schüler einen zufälligen Betrieb zu

## Installation

### Voraussetzungen
- Python 3.8 oder höher
- Zugriff auf einen SVWS-Server

### Setup

1. Repository klonen und in das Verzeichnis wechseln:
```bash
cd SVWS-MockFactory
```

2. Virtuelle Umgebung erstellen und aktivieren:
```bash
python3 -m venv venv
source venv/bin/activate  # Unter Windows: venv\Scripts\activate
```

3. Abhängigkeiten installieren:
```bash
pip install -r requirements.txt
```

4. Konfiguration anpassen:
```bash
cp config.example.json config.json
# Dann config.json mit eigenen Werten bearbeiten
```

## Konfiguration

Die `config.json` enthält alle notwendigen Verbindungsdaten:

```json
{
  "database": {
    "server": "your-server-hostname",
    "httpsport": 8443,
    "schema": "your-schema-name",
    "mariadbroot": "your-mariadb-root-user",
    "mariadbdbrootpassword": "your-mariadb-root-password",
    "dbusername": "your-db-username",
    "dbpassword": "your-db-password",
    "username": "your-admin-username",
    "password": "your-admin-password",
    "schulnummer": 123456,
    "test": false,
    "anzahllehrer": 100,
    "anzahlschueler": 1200,
    "anzahlbetriebe": 150,

  "language_workers": 1,
    "telefon_workers": 1,
    "misc_workers": 1,
    "parents_workers": 1,
    "company_workers": 1,

    "company_assignment_endpoint": "/schueler/schueler-betriebe/create",
    "company_assignment_endpoints": [
      "/schueler/schueler-betriebe/create",
      "/betriebe/schuelerbetrieb/new/schueler/{schueler_id}/betrieb/{betrieb_id}"
    ]
  }
}
```

### Konfigurationsparameter

- **server**: Hostname oder IP-Adresse des SVWS-Servers
- **httpsport**: HTTPS-Port des Servers (Standard: 8443)
- **schema**: Name des Datenbankschemas
- **mariadbroot/mariadbdbrootpassword**: Root-Zugangsdaten für Admin-Operationen (Schema erstellen/löschen)
- **dbusername/dbpassword**: Zugangsdaten für Datenbankoperationen (Server-Status)
- **username/password**: Zugangsdaten für API-Operationen (Schema-Initialisierung)
- **schulnummer**: Schulnummer für die Initialisierung
- **test**: Flag für Testmodus bei Schulen-Befüllung (false: Schulen.csv, true: SchulenTest.csv)
- **anzahllehrer**: Anzahl zu generierender Lehrkräfte (Standard: 100)
- **anzahlschueler**: Anzahl zu generierender Schüler (für Klassenberechnung)
- **anzahlbetriebe**: Anzahl zu generierender Betriebe (Standard: 150)

Zusätzliche optionale Tuning-Parameter:
- **language_workers**: Parallelität für `--patch-schueler-language` (Default intern: 1 bei fehlender Konfiguration)
- **telefon_workers**: Parallelität für `--patch-schueler-telefon` (Default intern: 1 bei fehlender Konfiguration)
- **misc_workers**: Parallelität für `--patch-schueler-misc` (Default intern: 1 bei fehlender Konfiguration)
- **parents_workers**: Parallelität für `--patch-schueler-parents` (Default intern: 1 bei fehlender Konfiguration)
- **company_workers**: Parallelität für `--patch-schueler-company` (Default intern: 1 für den Create-Endpunkt bei fehlender Konfiguration)
- **company_assignment_endpoint**: Erzwingt einen einzelnen Endpoint-Template-Pfad für Schüler-Betriebszuordnung
- **company_assignment_endpoints**: Priorisierte Liste von Endpoint-Template-Pfaden für den Endpunkt-Preflight

## Sicherheit

⚠️ **Wichtig**: Die `config.json` enthält sensitive Anmeldedaten und sollte **niemals** in die Versionskontrolle committed werden.

- `.gitignore` ist bereits konfiguriert, um `config.json` zu ignorieren
- Verwende `config.example.json` als Vorlage
- Alle Credentials im Repository sind Platzhalter und keine echten Zugangsdaten
- Schütze deine `config.json` vor unauthorisiertem Zugriff

## Verwendung

### Hauptanwendung

```bash
python mockfactory.py --help
```

### Komplettes Setup mit allen Katalogen (empfohlen)

Führt alle Schritte aus: Schema löschen → Schema erstellen → Datenbank initialisieren → alle Kataloge befüllen:

```bash
python mockfactory.py --full-setup
```

Dies ist die einfachste Methode für ein komplettes Setup mit allen Katalogen und wird empfohlen.

**Workflow** (25 Schritte):
1. Server-Erreichbarkeit prüfen
2. Datenbank-Schema erstellen
3. Datenbank initialisieren + Schulstammdaten mit Testwerten patchen
4. Fahrschülerarten befüllen (15 Einträge)
5. Einwilligungsarten befüllen (7 Einträge)
6. Förderschwerpunkte befüllen (schulformabhängig)
7. Floskelgruppen befüllen (11 Einträge)
8. Floskeln befüllen (47 Einträge)
9. Haltestellen befüllen (10 Einträge)
10. Lernplattformen befüllen (aus Textdatei)
11. Vermerkarten befüllen (7 Einträge aus Textdatei)
12. Betriebe befüllen (konfigurierbare Anzahl synthetischer Einträge mit je 2 Ansprechpartnern)
13. Kindergarten befüllen (20 Einträge, nur bei Schulformen G, PS, S, V, WF)
14. Schulen befüllen (190 NRW Schulen)
15. Lehrkräfte befüllen (konfigurierbare Anzahl, standardmäßig 100)
16. Lehrkräfte Personaldaten patchen
17. Klassen erstellen und Klassenleitungen zuweisen (dynamisch basierend auf Schülerzahl und Schulform)
18. Schülerdaten generieren (schulform-/jahrgangsgerechte Altersverteilung)
19. Schüler-Stammdaten patchen
20. Schüler-Schulbesuch patchen (Jahrgänge 05-10, EF, Q1, Q2)
21. Schüler-Sprachbelegungen anlegen (E/S für Jahrgänge 05-10, EF, Q1, Q2)
22. Schüler-Telefonnummern anlegen (2 Einträge pro Schüler)
23. Schüler-Misc-Daten anlegen (3 Vermerke + Einwilligungen + Lernplattformen)
24. Schüler-Erzieherdaten anlegen (2 Personen pro Schüler)
25. Schüler-Betrieb zuordnen (1 zufälliger Betrieb pro Schüler)

Einzeln ausführbar:

```bash
python mockfactory.py --patch-schueler-schulbesuch
```

API-Endpunkte dafür:
- `GET /db/{schema}/schule/schulen` (Katalog der Schulen, Filter auf Grundschulen)
- `GET /db/{schema}/schueler/{id}/schulbesuch`
- `PATCH /db/{schema}/schueler/{id}/schulbesuch`

Zieljahrgänge: `05`, `06`, `07`, `08`, `09`, `10`, `EF`, `Q1`, `Q2`

Einzeln ausführbar:

```bash
python mockfactory.py --patch-schueler-language
```

API-Endpunkt dafür:
- `POST /db/{schema}/schueler/{id}/sprachen/belegungen` (2 Einträge pro Schüler in Zieljahrgängen)

Hinweis zur Stabilität:
- Die Sprachbelegungs-Erzeugung läuft standardmäßig seriell (1 Worker) und ohne Retry beim `POST /schueler/{id}/sprachen/belegungen`, um Duplicate-Key-Races auf einigen Serverständen zu vermeiden.
- Optional kann die Parallelität explizit über `database.language_workers` oder `SVWS_LANGUAGE_WORKERS` erhöht werden.

Einzeln ausführbar:

```bash
python mockfactory.py --patch-schueler-telefon
```

API-Endpunkt dafür: `POST /db/{schema}/schueler/{id}/telefon` (zweimal pro Schüler, je Telefonnummer ein Request).

Hinweis zur Stabilität:
- Die Telefon-Erzeugung läuft standardmäßig seriell (1 Worker) und ohne Retry beim `POST /schueler/{id}/telefon`, um Duplicate-Key-Races auf einigen Serverständen zu vermeiden.
- Optional kann die Parallelität explizit über `database.telefon_workers` oder `SVWS_TELEFON_WORKERS` erhöht werden.

Einzeln ausführbar:

```bash
python mockfactory.py --patch-schueler-misc
```

API-Endpunkte dafür:
- `POST /db/{schema}/schueler/vermerke` (3 Einträge pro Schüler)
- `PATCH /db/{schema}/schueler/{id}/einwilligungen/{idEinwilligungsart}`
- `PATCH /db/{schema}/schueler/{id}/lernplattformen/{idLernplattform}`

Hinweis zur Stabilität:
- Die Vermerk-Erzeugung läuft standardmäßig seriell (1 Worker) und ohne Retry beim `POST /schueler/vermerke`, um Duplicate-Key-Races auf einigen Serverständen zu vermeiden.
- Optional kann die Parallelität explizit über `database.misc_workers` oder `SVWS_MISC_WORKERS` erhöht werden.

Einzeln ausführbar:

```bash
python mockfactory.py --patch-schueler-parents
```

API-Endpunkte dafür:
- `POST /db/{schema}/schueler/erzieher/new/{idSchueler}/1` (1. Person anlegen)
- `PATCH /db/{schema}/erzieher/{idErzieher}/stammdaten/2` (2. Person ergänzen)

Hinweis zur Stabilität:
- Die Erzieher-Erzeugung läuft standardmäßig seriell (1 Worker) und ohne Retry beim `POST /schueler/erzieher/new/...`, um Duplicate-Key-Races auf einigen Serverständen zu vermeiden.
- Optional kann die Parallelität explizit über `database.parents_workers` oder `SVWS_PARENTS_WORKERS` erhöht werden.

Einzeln ausführbar:

```bash
python mockfactory.py --patch-schueler-company
```

API-Endpunkte dafür:
- `GET /db/{schema}/schule/betriebe` (primär, Liste verfügbarer Betriebe)
- `GET /db/{schema}/betriebe` (Fallback für ältere Serverstände)
- `POST /db/{schema}/schueler/schueler-betriebe/create` (primär laut OpenAPI)
- `POST /db/{schema}/betriebe/schuelerbetrieb/new/schueler/{idSchueler}/betrieb/{idBetrieb}` (historisch)
- `POST /db/{schema}/schule/betriebe/schuelerbetrieb/new/schueler/{idSchueler}/betrieb/{idBetrieb}` (historischer Fallback-Kandidat)

Hinweis zu unterschiedlichen Serverständen:
- Der Zuordnungs-Schritt führt einen Endpunkt-Preflight aus und überspringt den Schritt sauber, wenn kein passender POST-Endpunkt gefunden wird.
- Optional kann der Endpunkt in `config.json` erzwungen werden:
  - `database.company_assignment_endpoint`: ein einzelnes Template, z. B. `/schule/betriebe/schuelerbetrieb/new/schueler/{schueler_id}/betrieb/{betrieb_id}`
  - `database.company_assignment_endpoints`: Liste von Templates in Prioritätsreihenfolge
- Für den Create-Endpunkt `/schueler/schueler-betriebe/create` läuft die Zuordnung standardmäßig seriell (1 Worker) und ohne Retry, um Duplicate-Key-Races auf einigen Serverständen zu vermeiden.
- Optional kann die Parallelität explizit gesetzt werden über `database.company_workers` oder die Umgebungsvariable `SVWS_COMPANY_WORKERS`.

### Schulstammdaten patchen

Aktualisiert die Schulstammdaten mit Testwerten nach der Datenbankinitialisierung:

```bash
python init_schooldata.py
```

**API-Endpunkt**: `PATCH /db/{schema}/schule/stammdaten`  
**Authentifizierung**: Basic Auth mit `username` und `password`  
**Test-Werte**:
- Bezeichnung 1: "Testschule aus gernerierten Daten"
- Bezeichnung 2: "MockFactory Schule"
- Bezeichnung 3: "Generierte Daten"
- Straße: "Hauptstraße 76"
- PLZ/Ort: "42287 Wuppertal"
- Telefon: "012345-6876876"
- Fax: "012345-6876877"
- E-Mail: "mockschule@schule.example.com"
- Web: "https://meineschule.de"

Dieses Modul wird automatisch während des `--full-setup` Workflows nach der Datenbankinitialisierung aufgerufen, kann aber auch standalone ausgeführt werden.

### Kindergarten befüllen (synthetisch)

Erzeugt konfigurierbare Anzahl Betriebe mit Zufallsdaten (Namen aus Nachnamen kombiniert, Straßen aus katalogdaten/Strassen.csv, zufällige Kontaktdaten) **inklusive je zwei Ansprechpartnern** (Herr aus vornamen_m.json, Frau aus vornamen_w.json, zufällige Telefonnummern, E-Mail: rufname.nachname@betrieb.example.com). Die Anzahl wird aus `config.json` (`anzahlbetriebe`) gelesen (Standardwert: 150):

```bash
python mockfactory.py --populate-betriebe
```

### Kindergarten befüllen (synthetisch)

Erzeugt 20 Kindergarten-Einträge mit Zufallsdaten. **Nur für Schulformen G, PS, S, V oder WF** - bei anderen Schulformen wird die Befüllung übersprungen.

```bash
python mockfactory.py --populate-kindergarten
```

### Lehrkräfte befüllen (synthetisch)

Erzeugt realistische Lehrkräfte-Datensätze mit zufällig generierten Daten. Die Anzahl wird aus `config.json` (`anzahllehrer`) gelesen (Standardwert: 100):

```bash
# Schritt 2: Lehrkräfte erstellen (mit Cache-Datei)
python mockfactory.py --populate-lehrer

# Schritt 3: Personaldaten hinzufügen (optional, verwendet Cache)
python mockfactory.py --patch-lehrer-personaldaten
```

Oder kombiniert im `--full-setup` (Schritte 15 & 16).

**API-Endpunkte**:
- CREATE: `POST /db/{schema}/lehrer/create`
- PATCH: `PATCH /db/{schema}/lehrer/{id}/personaldaten`

**Authentifizierung**: Basic Auth mit `username` und `password`  
**Quellen**: katalogdaten/nachnamen.json, vornamen_m.json, vornamen_w.json, Strassen.csv, /orte API

Das Programm generiert für jede Lehrkraft:

**Persönliche Daten**:
- Kürzel: 4 Buchstaben des Nachnamens (uppercase), bei Duplikaten: 3 Buchstaben + Ziffer
- Vorname: Zufällig aus vornamen_m.json (Männer) oder vornamen_w.json (Frauen)
- Nachname: Zufällig aus nachnamen.json
- Geschlecht: Balanciert 50% männlich (3) / 50% weiblich (4)
- Titel: 10% erhalten Dr.

**Amtsbezeichnung** (gewichtet):
- 60% StR (Studienrat/Studienrätin)
- 20% Lehrer
- 10% OStR (Oberstudienrat)
- 10% LiA (Lehramt in Ausbildung)

**Geburtsdatum**: Zufällig generiert (Alter: 30-60 Jahre)

**Staatsangehörigkeit**:
- 90% DEU (Deutschland)
- 5% TUR (Türkei)
- 5% ITA (Italien)

**Adresse**:
- Straße: Zufällig aus katalogdaten/Strassen.csv
- Hausnummer: Zufällig (1-199, ggf. mit Zusatz a, b, c)
- Wohnort: Zufällig aus Wuppertal (via `/orte` API)

**Kontaktdaten**:
- Telefon: Format `012345-XXXXXX` (6-stellige Zufallszahl)
- Telefon mobil: Format `012345-XXXXXX` (6-stellige Zufallszahl)
- Email privat: `vorname.nachname@privat.l.example.com`
- Email dienstlich: `vorname.nachname@dienstlich.l.example.com`

**Sichtbarkeit**:
- Alle Lehrkräfte sind sichtbar (`istSichtbar: true`)
- Alle Lehrkräfte sind relevant für Statistik (`istRelevantFuerStatistik: true`)

**Personaldaten** (via PATCH nach Erstellung):
- **identNrTeil1**: TTMMJJG (Tag + Monat + Jahr + Geschlecht)
- **identNrTeil2SerNr**: 3-stellige Zahl + 'X' (eindeutig pro Lehrkraft)
- **personalaktennummer**: PA + 8-stellige Zufallszahl
- **lbvPersonalnummer**: LB + 8-stellige Zufallszahl
- **lbvVerguetungsschluessel**: 'A' (fest)
- **zugangsdatum**: Heute - 2 Jahre
- **zugangsgrund**: 'NEU' (fest)

**Workflow**: `populate_lehrer.py` speichert bei der Erstellung Lehrkräfte-Daten in `.lehrer_cache.json`. `patch_lehrer_personaldaten.py` liest diese Cache-Datei und ergänzt die Personaldaten via PATCH. Die Cache-Datei wird ignoriert (`.gitignore`).

### Klassen erstellen (dynamisch)

Erstellt Klassen basierend auf der Schülerzahl und Schulform der Schule, mit automatischer Zuweisung von zwei Klassenleitungen pro Klasse:

```bash
python mockfactory.py --populate-classes
```

**API-Endpunkte**:
- CREATE: `POST /db/{schema}/klassen/create`
- PATCH: `PATCH /db/{schema}/klassen/{id}` (für Klassenleitungen)
- GET: `GET /db/{schema}/schule/stammdaten` (für Schulform)
- GET: `GET /db/{schema}/jahrgaenge` (für Jahrgangs-IDs)
- GET: `GET /db/{schema}/lehrer` (für Lehrerliste)

**Authentifizierung**: Basic Auth mit `username` und `password`  
**Quellen**: katalogdaten/klassenstruktur.json, config.json (anzahlschueler)

Das Programm generiert Klassen dynamisch:

**Berechnung**:
- Klassengröße: ~25 Schüler pro Klasse
- Anzahl Klassen = anzahlschueler / 25
- Verteilung auf Jahrgänge: gleichmäßig basierend auf Schulform

**Schulformspezifische Jahrgänge** (aus klassenstruktur.json):
- **Grundschule & Förderschulen Primarstufe** (G, SG, FW): 01-04
- **Gymnasium, Gesamtschule, Hibernia** (GY, GE, HI): 05-10, EF, Q1, Q2
  - Jahrgänge 05-10: Mehrere Parallelklassen (05a, 05b, 06a, ...)
  - **EF, Q1, Q2**: Jeweils **eine Klasse** ohne Suffix (EF, Q1, Q2) mit allen Schülern des Jahrgangs
- **Haupt-, Real-, Sekundarschulen** (H, SK, R, SR, S, WF): 05-10
- **PRIMUS, Klinikschule, Volksschule** (PS, KS, V): 01-10
- **Berufskolleg** (BK, SB): ⚠️ Übersprungen (erfordert Fachklassen-Konfiguration in der Datenbank)

**Klassennamen**:
- Format: `{Prefix}{Jahrgang}{Suffix}` (z.B. "05a", "Fachklasse 01a")
- Suffix: a-z, dann aa-az, ba-bz, ... (unterstützt bis zu 676 Parallelklassen)
- Oberstufe (EF/Q1/Q2): Kein Suffix, nur Jahrgangsbezeichnung

**Klassenleitungen**:
- 2 Lehrer pro Klasse (automatisch zugewiesen)
- Tracking: Max. 2 Klassen pro Lehrer bevorzugt
- Fallback: Bei Lehrermangel werden Lehrer auch für mehr Klassen eingeteilt (mit Warnung)

**Spezielle API-Anforderungen**:
- Schulformen H/SK/R/SR/S: `idSchulgliederung` wird weggelassen (API-Validierung)
- Schulformen BK/SB: Benötigen `idBerufsbildendOrganisationsform` und `idFachklasse` (derzeit übersprungen)

**Cache**: Speichert erstellte Klassen-IDs in `.klassen_cache.json` für Klassenleiterzuweisung. Die Cache-Datei wird ignoriert (`.gitignore`).


3. Verwendet deutsche Kindergartennamen (z.B. "Kita Sonnenschein", "Kindergarten Regenbogen")
4. Generiert Zufallsadressen (Straßen aus Strassen.csv, Wuppertaler PLZ)
5. Erstellt realistische Telefonnummern (0202-######) und E-Mail-Adressen (kita1@kita.example.com)
6. Verhindert Duplikate durch erweiterten Namenspool (50 Namen × 3 Präfixe × 8 Suffixe = 1.200 Kombinationen)
7. Automatisches Retry bei Duplikaten (bis zu 3 Versuche mit neuen Namen)

### Basis-Setup (Schema + Initialisierung)

Führt nur die ersten 3 Schritte aus:

```bash
python mockfactory.py --setup
```

### Server-Status prüfen

Prüft ob der SVWS-Server erreichbar ist:

```bash
python mockfactory.py --check-server
```

oder direkt:

```bash
python check_server.py
```

**API-Endpunkt**: `GET /status/alive`  
**Authentifizierung**: Basic Auth mit `dbusername` und `dbpassword`

### Datenbank-Schema auflisten

Zeigt alle vorhandenen Schemas:

```bash
python mockfactory.py --list-schemas
```

### Datenbank-Schema löschen

Löscht das in `config.json` konfigurierte Schema:

```bash
python mockfactory.py --delete-schema
```

**API-Endpunkt**: `POST /api/schema/root/destroy/{schema}`  
**Authentifizierung**: Basic Auth mit `mariadbroot` und `mariadbdbrootpassword`

### Datenbank-Schema erstellen

Erstellt ein neues Datenbank-Schema mit allen Tabellen, Indizes und Triggern:

```bash
python mockfactory.py --create-schema
```

**API-Endpunkt**: `POST /api/schema/root/create/{schema}`  
**Authentifizierung**: Basic Auth mit `mariadbroot` und `mariadbdbrootpassword`

### Datenbank initialisieren

Initialisiert das Schema mit einer Schulnummer:

```bash
python mockfactory.py --init-db
```

oder direkt:

```bash
python init_database.py
```

**API-Endpunkt**: `POST /db/{schema}/schule/init/{schulnummer}`  
**Authentifizierung**: Basic Auth mit `username` und `password`

Die Initialisierung erstellt die Schulstruktur mit:
- Schulform und Bezeichnung
- Adressdaten
- Kontaktinformationen
- Schuljahresabschnitte
- Grundeinstellungen

### Schulen befüllen

Befüllt den Schulen-Katalog mit NRW Schulen aus CSV-Dateien. Abhängig vom `test`-Flag in `config.json` wird entweder `katalogdaten/Schulen.csv` (190 Einträge, `test: false`) oder `katalogdaten/SchulenTest.csv` (2 Einträge, `test: true`) verwendet:

```bash
python mockfactory.py --populate-schulen
```

**API-Endpunkt**: `POST /db/{schema}/schule/schulen/create`  
**Authentifizierung**: Basic Auth mit `username` und `password`  
**Quelle**: katalogdaten/Schulen.csv oder SchulenTest.csv, statistikdaten/Schulform.json

Das Programm:
1. Prüft das `test`-Flag in `config.json` zur Dateiauswahl
2. Konvertiert CSV-Daten zu SVWS-kompatiblem JSON-Format
3. Mappt die Schulform-Abkürzung (z.B. "BK", "GG", "GY") zur idSchulform
   - Liest statistikdaten/Schulform.json für die Schulform-ID-Zuordnung
   - Verwendet die ID aus dem ersten History-Eintrag (z.B. "BK" → 1000, "GG" → 3000)
4. Generiert Email-Adressen im Format `{schulnummer}@schule.nrw.de`
5. Bereinigt Telefon-/Fax-Nummern (entfernt Bindestriche)
6. Erstellt alle Schulen mit korrekten Schulform-IDs

Schulen (190 Einträge bei `test: false`, 2 Einträge bei `test: true`):
- 16 Schulformtypen (BK, GG, GY, H, R, GE, SK, V, FÖ, PS, WB, etc.)
- NRW-weite Abdeckung mit Adressdaten
- Schulnummern, Kürzel und Kurzbezeichnungen
- Telefon-, Fax- und Email-Kontakte

### Katalogdaten befüllen

#### Fahrschülerarten

Erstellt 15 Standard-Fahrschülerarteneinträge (Busunternehmen 1-15):

```bash
python mockfactory.py --populate-fahrschuelerarten
```

**API-Endpunkt**: `POST /db/{schema}/schueler/fahrschuelerarten/create`  
**Authentifizierung**: Basic Auth mit `username` und `password`  
**Quelle**: Statische Daten (15 Einträge)

#### Einwilligungsarten

Befüllt den Einwilligungskatalog aus der JSON-Datei `katalogdaten/einwilligungen.json`:

```bash
python mockfactory.py --populate-einwilligungsarten
```

**API-Endpunkt**: `POST /db/{schema}/schule/einwilligungsarten/new`  
**Authentifizierung**: Basic Auth mit `username` und `password`  
**Quelle**: katalogdaten/einwilligungen.json

Einträge:
- Einwilligung Homepage
- Einwilligung Social Media
- Einwilligung Presse
- Einwilligung Werbung
- Einwilligung Externe Partner
- Einwilligung Forschung
- Einwilligung Newsletter

#### Förderschwerpunkte

Befüllt den Förderschwerpunkt-Katalog basierend auf der Schulform der Schule:

```bash
python mockfactory.py --populate-foerderschwerpunkte
```

**API-Endpunkt**: `POST /db/{schema}/foerderschwerpunkte/create`  
**Authentifizierung**: Basic Auth mit `username` und `password`  
**Quelle**: statistikdaten/Foerderschwerpunkt.json (schulformabhängig)

Das Programm:
1. Ruft die Schulstammdaten ab, um die Schulform zu ermitteln
2. Lädt die Förderschwerpunkt-Katalogdaten
3. Filtert Einträge für die Schulform
4. Erstellt nur gültige Einträge für diese Schulform
5. Berücksichtigt zeitliche Gültigkeiten basierend auf dem aktuellen Jahr

Beispiel für Gesamtschule (GE): 10 Förderschwerpunkte
- kein Förderschwerpunkt (**)
- Sehen (BL)
- Emotionale und soziale Entwicklung (EZ)
- Geistige Entwicklung (GB)
- Hören und Kommunikation (GH)
- Körperliche und motorische Entwicklung (KB)
- Sprache (LB, SG)
- und weitere
#### Floskelgruppen

Befüllt den Floskelgruppen-Katalog aus der JSON-Datei `katalogdaten/Floskelgruppenart.json`:

```bash
python mockfactory.py --populate-floskelgruppen
```

**API-Endpunkt**: `POST /db/{schema}/schule/floskelgruppen/create`  
**Authentifizierung**: Basic Auth mit `username` und `password`  
**Quelle**: katalogdaten/Floskelgruppenart.json

Das Programm:
1. Lädt die Floskelgruppen-Katalogdaten
2. Extrahiert den neuesten History-Eintrag für jede Floskelgruppe
3. Generiert automatisch Farben für die Benutzeroberfläche
4. Trunckt Bezeichnungen auf maximal 50 Zeichen (API-Beschränkung)
5. Erstellt alle 11 Einträge mit ihren Konfigurationen

Floskelgruppen (11 Einträge):
- ALLG: Allgemeine Floskeln
- ASV: Floskeln für Arbeits- und Sozialverhalten
- AUE: Floskeln für außerunterrichtliche Aktivitäten
- FACH: Fachbezogene Floskeln
- FSP: Bemerkungen zum Förderschwerpunkt
- FOERD: Floskeln für Fördermaßnahmen
- VERM: Floskeln für Vermerke
- VERS: Bemerkung zur Versetzung
- ZB: Floskeln für Zeugnisbemerkungen
- LELS: Floskeln für Lernentwicklung und Leistungsstand
- ÜG45: Floskeln für Übergangsempfehlungen

#### Floskeln

Befüllt den Floskeln-Katalog (Zeugnisbemerkungen und Bewertungstext-Snippets) aus der CSV-Datei `katalogdaten/Floskeln.csv`:

```bash
python mockfactory.py --populate-floskeln
```

**API-Endpunkt**: `POST /db/{schema}/schule/floskeln/create`  
**Authentifizierung**: Basic Auth mit `username` und `password`  
**Quelle**: katalogdaten/Floskeln.csv

Das Programm:
1. Lädt die Floskeln-Katalogdaten aus CSV
2. Ordnet die Einträge zu ihren Floskelgruppen
3. Parst Jahrgänge aus komma-separierten Werten (leer wenn nicht spezifiziert)
4. Erstellt alle Einträge mit Nummer, Text, Fach, Niveau und Jahrgänge-Zuordnung

Floskeln (47 Einträge):
- 24 Bemerkungen zum Förderschwerpunkt (#2359-#2382)
- 23 Floskeln für Arbeits- und Sozialverhalten (#ASV001-#ASV023)

Die Floskeln enthalten Vorlagen mit Variablen wie:
- `$Vorname$`: wird durch den Vornamen des Schülers ersetzt
- `&Er%Sie&`: wird durch Pronomen ersetzt
- `**text**`: markiert editierbare Felder im Zeugnis

#### Haltestellen

Befüllt den Haltestellen-Katalog (Bus- und Bahnhaltestellen) aus der Textdatei `katalogdaten/haltestellen.txt`:

```bash
python mockfactory.py --populate-haltestellen
```

**API-Endpunkt**: `POST /db/{schema}/haltestellen/create`  
**Authentifizierung**: Basic Auth mit `username` und `password`  
**Quelle**: katalogdaten/haltestellen.txt

Das Programm:
1. Lädt die Haltestellen-Katalogdaten aus Textdatei (eine pro Zeile)
2. Generiert für jede Haltestelle eine zufällige Entfernung (1-10 km zur Schule)
3. Erstellt automatische Sortierungsnummern (1-10)
4. Markiert alle Einträge als sichtbar in der Benutzeroberfläche

Haltestellen (10 Einträge):
1. Meckelstraße
2. Fingscheid
3. Hauptbahnhof
4. Opernstraße
5. Schwebebahnhof Alter Markt
6. S-Bahn Unterbarmen
7. Barmer Bahnhof
8. Nordbahntrasse
9. Haltestelle Skulpturenpark
10. Schwebebahnstation Zoo

Die Entfernung ist eine Zufallszahl zwischen 1 und 10 und wird zur Laufzeit generiert, so dass bei mehrfachem Ausführen unterschiedliche Daten entstehen.

#### Lernplattformen

Befüllt den Lernplattformen-Katalog aus der Textdatei `katalogdaten/lernplattformen.txt`:

```bash
python mockfactory.py --populate-lernplattformen
```

**API-Endpunkt**: `POST /db/{schema}/schule/lernplattformen/create`  
**Authentifizierung**: Basic Auth mit `username` und `password`  
**Quelle**: katalogdaten/lernplattformen.txt

Das Programm:
1. Lädt die Lernplattformen aus der Textdatei (eine Plattform pro Zeile)
2. Erstellt einen Eintrag mit der Bezeichnung

## Datendateien

Das Programm nutzt folgende Dateien zur Generierung realistischer Testdaten und Kataloge:

### Namensdaten
- `katalogdaten/vornamen_m.json`: Männliche Vornamen
- `katalogdaten/vornamen_w.json`: Weibliche Vornamen
- `katalogdaten/nachnamen.json`: Nachnamen
- `katalogdaten/Strassen.csv`: Straßennamen für Adressdaten

### Katalogdaten
- `katalogdaten/einwilligungen.json`: Einwilligungsarten-Katalog (7 Einträge)
- `katalogdaten/Schulen.csv`: Schulen-Katalog (190 NRW Schulen)
- `katalogdaten/Floskelgruppenart.json`: Floskelgruppen-Katalog (11 Einträge)
- `katalogdaten/Floskeln.csv`: Floskeln-Katalog (47 Einträge)
- `katalogdaten/haltestellen.txt`: Haltestellen-Katalog (10 Einträge)
- `katalogdaten/lernplattformen.txt`: Lernplattformen-Katalog (Einträge pro Zeile)
- `katalogdaten/klassenstruktur.json`: Klassenstruktur-Template (Jahrgänge pro Schulform)
- `statistikdaten/Foerderschwerpunkt.json`: Förderschwerpunkt-Katalog (schulformabhängig)
- `statistikdaten/Schulform.json`: Schulform-Katalog mit IDs für Schulform-Mapping

## Entwicklungsstatus

### Implementiert ✓
- Server-Erreichbarkeit prüfen
- Datenbank-Schema erstellen, löschen, auflisten
- Datenbank-Schema initialisieren
- Katalog-Befüllung:
  - Schulen (190 NRW Schulen mit idSchulform-Mapping aus Schulform.json)
  - Fahrschülerarten (15 Einträge)
  - Einwilligungsarten (7 Einträge aus JSON-Datei)
  - Förderschwerpunkte (10+ Einträge, schulformabhängig)
  - Floskelgruppen (11 Einträge aus JSON-Datei)
  - Floskeln (47 Einträge aus CSV-Datei)
  - Haltestellen (10 Einträge aus Text-Datei mit Zufallsdistanzen)
  - Lernplattformen (Einträge aus Text-Datei)
  - Betriebe (konfigurierbare Anzahl synthetische Einträge mit je 2 Ansprechpartnern)
  - Kindergarten (20 synthetische Einträge, nur für Schulformen G, PS, S, V, WF)
  - Lehrkräfte (Zahl aus config.json, standardmäßig 100 mit Geschlechtsmix, Titel, Amtsbezeichnung)
  - Klassen (dynamisch basierend auf anzahlschueler/25, schulformspezifische Jahrgänge, automatische Klassenleiterzuweisung)
- Grundlegende Konfigurationsverwaltung
- Fehlerbehandlung und Logging
- Schüler-Schulbesuch patchen (Zieljahrgänge 05-10, EF, Q1, Q2)
- Schüler-Sprachbelegungen (E/S für Zieljahrgänge 05-10, EF, Q1, Q2)
- Schüler-Telefonnummern (2 Einträge pro Schüler)
- Schüler-Misc-Daten (3 Vermerke + Einwilligungen + Lernplattformen)
- Schüler-Erzieherdaten (2 Personen pro Schüler)
- Schüler-Betrieb-Zuordnung (1 zufälliger Betrieb pro Schüler)
- Complete Setup Workflow mit allen Katalogen (25 Schritte)
- Basis-Setup Workflow (Schema + Initialisierung)

### In Planung 🚧
- Weitere Kataloge (Adressarten, Berufsfelder, etc.)
- Klassen und Kurse erweitern (Schülerzuweisungen)
- Stundenplan-Generierung
- BK/SB Fachklassen-Unterstützung (erfordert Fachklassen-Konfiguration)

## Technische Details

- **Framework**: Python 3
- **HTTP-Client**: requests
- **API-Format**: REST (JSON)
- **Authentifizierung**: HTTP Basic Auth
- **SSL**: Unterstützt selbstsignierte Zertifikate

## Fehlerbehandlung

Die Anwendung behandelt folgende Fehlerszenarien:
- Verbindungsfehler zum Server
- Timeouts
- Authentifizierungsfehler (401)
- Fehlende oder ungültige Konfiguration
- SSL-Zertifikatsprobleme

## Lizenz

Siehe LICENSE-Datei für Details.

