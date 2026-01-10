# SVWS-MockFactory

Eine Factory um im SVWS-Server Demonstrationsdatenbanken zu erstellen über die API.

Dieses Python-Programm erstellt realistische Testdatenbanken für den SVWS-Server über dessen REST-API. Die Verbindungsdaten und Konfiguration sind in der `config.json` hinterlegt.

## Features

- ✓ **Server-Status prüfen**: Verbindung zum SVWS-Server testen
- ✓ **Datenbank-Schema verwalten**: Erstellen, löschen, auflisten
- ✓ **Datenbank initialisieren**: Schema mit Schulnummer und Schulinformationen initialisieren
- ✓ **Kataloge füllen**: Automatische Befüllung der Schuldatenbank-Kataloge
  - Fahrschülerarten (15 Einträge)
  - Einwilligungsarten (7 Einträge aus katalogdaten/einwilligungen.json)
  - Förderschwerpunkte (10+ Einträge, schulformabhängig)
  - Floskelgruppen (11 Einträge aus katalogdaten/Floskelgruppenart.json)
- 🚧 **Lehrkräfte generieren**: Realistische Lehrkräftedaten erstellen (in Entwicklung)
- 🚧 **Schülerdaten generieren**: Realistische Schülerdaten erstellen (in Entwicklung)

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
    "dbusername": "your-db-username",
    "dbpassword": "your-db-password",
    "username": "your-admin-username",
    "password": "your-admin-password",
    "schulnummer": 123456,
    "anzahllehrer": 100,
    "anzahlschueler": 1200
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
- **anzahllehrer**: Anzahl zu generierender Lehrkräfte
- **anzahlschueler**: Anzahl zu generierender Schüler

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

**Workflow** (7 Schritte):
1. Server-Erreichbarkeit prüfen
2. Datenbank-Schema erstellen
3. Datenbank initialisieren
4. Fahrschülerarten befüllen (15 Einträge)
5. Einwilligungsarten befüllen (7 Einträge)
6. Förderschwerpunkte befüllen (schulformabhängig)
7. Floskelgruppen befüllen (11 Einträge)

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
## Datendateien

Das Programm nutzt folgende Dateien zur Generierung realistischer Testdaten und Kataloge:

### Namensdaten
- `vornamen_m.json`: Männliche Vornamen
- `vornamen_w.json`: Weibliche Vornamen
- `nachnamen.json`: Nachnamen
- `Strassen.csv`: Straßennamen für Adressdaten

### Katalogdaten
- `katalogdaten/einwilligungen.json`: Einwilligungsarten-Katalog (7 Einträge)
- `katalogdaten/Floskelgruppenart.json`: Floskelgruppen-Katalog (11 Einträge)
- `statistikdaten/Foerderschwerpunkt.json`: Förderschwerpunkt-Katalog (schulformabhängig)

## Entwicklungsstatus

### Implementiert ✓
- Server-Erreichbarkeit prüfen
- Datenbank-Schema erstellen, löschen, auflisten
- Datenbank-Schema initialisieren
- Katalog-Befüllung:
  - Fahrschülerarten (15 Einträge)
  - Einwilligungsarten (7 Einträge aus JSON-Datei)
  - Förderschwerpunkte (10+ Einträge, schulformabhängig)
  - Floskelgruppen (11 Einträge aus JSON-Datei)
- Grundlegende Konfigurationsverwaltung
- Fehlerbehandlung und Logging
- Complete Setup Workflow mit allen Katalogen (7 Schritte)
- Basis-Setup Workflow (Schema + Initialisierung)

### In Planung 🚧
- Weitere Kataloge (Adressarten, Berufsfelder, etc.)
- Lehrkräfte mit realistischen Daten generieren
- Schülerdaten mit realistischen Daten generieren
- Klassen und Kurse erstellen
- Stundenplan-Generierung

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

