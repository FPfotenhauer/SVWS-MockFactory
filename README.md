# SVWS-MockFactory

Eine Factory um im SVWS-Server Demonstrationsdatenbanken zu erstellen über die API.

Dieses Python-Programm erstellt realistische Testdatenbanken für den SVWS-Server über dessen REST-API. Die Verbindungsdaten und Konfiguration sind in der `config.json` hinterlegt.

## Features

- ✓ **Server-Status prüfen**: Verbindung zum SVWS-Server testen
- ✓ **Datenbank initialisieren**: Schema mit Schulnummer initialisieren
- 🚧 **Kataloge füllen**: Schuldatenbank-Kataloge befüllen (in Entwicklung)
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

### Komplettes Setup (empfohlen)

Führt alle Schritte aus: Schema löschen (falls vorhanden) → Schema erstellen → Datenbank initialisieren:

```bash
python mockfactory.py --setup
```

Dies ist die einfachste Methode für ein komplettes Setup und wird empfohlen.

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

## Datendateien

Das Programm nutzt folgende JSON-Dateien zur Generierung realistischer Testdaten:

- `vornamen_m.json`: Männliche Vornamen
- `vornamen_w.json`: Weibliche Vornamen
- `nachnamen.json`: Nachnamen
- `Strassen.csv`: Straßennamen für Adressdaten

## Entwicklungsstatus

### Implementiert ✓
- Server-Erreichbarkeit prüfen
- Datenbank-Schema initialisieren
- Grundlegende Konfigurationsverwaltung
- Fehlerbehandlung und Logging

### In Planung 🚧
- Katalogdaten befüllen
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

