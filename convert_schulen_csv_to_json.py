#!/usr/bin/env python3
"""
Converts Schulen.csv to schulen.json for the SVWS API.

This script reads the school data from CSV format and converts it to the JSON
schema required by the POST /db/{schema}/schule/schulen/create endpoint.

Schulform IDs are loaded from statistikdaten/Schulform.json using the 
SchulformKrz (e.g., "BK" -> idSchulform from Schulform.json).
"""

import csv
import json
from pathlib import Path


def load_schulform_mapping(schulform_path: str) -> dict:
    """Load Schulform.json and create mapping from Kuerzel to id from historie"""
    schulform_map = {}
    
    with open(schulform_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        for entry in data.get('daten', []):
            kuerzel = entry.get('bezeichner')
            # Get id from the first historie entry
            if entry.get('historie') and len(entry['historie']) > 0:
                id_schulform = entry['historie'][0].get('id')
                if kuerzel and id_schulform:
                    schulform_map[kuerzel] = id_schulform
    
    return schulform_map


def convert_csv_to_json(csv_path: str, json_path: str):
    """
    Convert Schulen CSV to JSON format matching the SVWS API schema.
    
    CSV columns:
        ID, SchulNr, Name, SchulformNr, SchulformKrz, SchulformBez, 
        Strassenname, HausNr, HausNrZusatz, PLZ, Ort, Telefon, Fax, 
        Email, Schulleiter, Sortierung, Sichtbar, Aenderbar, SchulNr_SIM, 
        Kuerzel, KurzBez
    
    JSON schema:
        kuerzel, kurzbezeichnung, schulnummerStatistik, name, idSchulform,
        strassenname, hausnummer, zusatzHausnummer, plz, ort, telefon, fax,
        email, schulleiter, sortierung, istSichtbar
    """
    # Load Schulform mapping
    schulform_path = Path(csv_path).parent.parent / 'statistikdaten' / 'Schulform.json'
    schulform_map = load_schulform_mapping(str(schulform_path))
    
    schulen = []
    
    with open(csv_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        for row in reader:
            # Map CSV columns to JSON schema
            # Generate email from schulnummerStatistik
            email = f"{row['SchulNr']}@schule.nrw.de" if row['SchulNr'] else None
            
            # Get idSchulform from Schulform.json mapping using SchulformKrz
            schulform_krz = row['SchulformKrz'].strip() if row['SchulformKrz'] else None
            id_schulform = schulform_map.get(schulform_krz) if schulform_krz else None
            
            schule = {
                "kuerzel": row['Kuerzel'] if row['Kuerzel'] else None,
                "kurzbezeichnung": row['KurzBez'] if row['KurzBez'] else None,
                "schulnummerStatistik": row['SchulNr'],
                "name": row['Name'],
                "idSchulform": id_schulform,  # From Schulform.json historie[0].id
                "strassenname": row['Strassenname'] if row['Strassenname'] else None,
                "hausnummer": row['HausNr'] if row['HausNr'] else None,
                "zusatzHausnummer": row['HausNrZusatz'] if row['HausNrZusatz'] else "",
                "plz": row['PLZ'] if row['PLZ'] else None,
                "ort": row['Ort'] if row['Ort'] else None,
                "telefon": row['Telefon'].replace('-', '') if row['Telefon'] else None,  # Remove dashes
                "fax": row['Fax'].replace('-', '') if row['Fax'] and row['Fax'] != '-' else None,
                "email": email,
                "schulleiter": row['Schulleiter'] if row['Schulleiter'] else None,
                "sortierung": int(row['Sortierung']) if row['Sortierung'] else 32000,
                "istSichtbar": row['Sichtbar'] == '+'
            }
            
            schulen.append(schule)
    
    # Write JSON file
    with open(json_path, 'w', encoding='utf-8') as jsonfile:
        json.dump(schulen, jsonfile, ensure_ascii=False, indent=2)
    
    return len(schulen)
    
    # Write JSON file
    with open(json_path, 'w', encoding='utf-8') as jsonfile:
        json.dump(schulen, jsonfile, ensure_ascii=False, indent=2)
    
    return len(schulen)


if __name__ == "__main__":
    csv_path = "katalogdaten/Schulen.csv"
    json_path = "katalogdaten/schulen.json"
    
    print(f"Converting {csv_path} to {json_path}...")
    count = convert_csv_to_json(csv_path, json_path)
    print(f"✓ Successfully converted {count} schools to JSON format")
    print(f"✓ Output written to {json_path}")
