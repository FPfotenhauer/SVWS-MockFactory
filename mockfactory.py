#!/usr/bin/env python3
"""
SVWS Mock Factory
Main application for creating demonstration and testing databases
for the school server system
"""

import argparse
import sys
import time
from check_server import load_config, check_server_alive
from schema_manager import list_schemas, delete_schema
from create_schema import create_schema
from init_database import init_database
from init_schooldata import patch_schulstammdaten
from populate_fahrschuelerarten import populate_fahrschuelerarten
from populate_einwilligungsarten import populate_einwilligungsarten
from populate_foerderschwerpunkte import populate_foerderschwerpunkte
from populate_floskelgruppen import populate_floskelgruppen
from populate_floskeln import populate_floskeln
from populate_haltestellen import populate_haltestellen
from populate_lernplattformen import populate_lernplattformen
from populate_schulen import populate_schulen
from populate_vermerkarten import populate_vermerkarten
from populate_betriebe import populate_betriebe
from populate_kindergarten import populate_kindergarten
from populate_lehrer import populate_lehrer
from patch_lehrer_personaldaten import patch_lehrer_personaldaten
from populate_classes import populate_classes, assign_class_leaders
from populate_schueler import populate_schueler
from patch_schueler_stammdaten import patch_schueler_stammdaten
from patch_schueler_schulbesuch import patch_schueler_schulbesuch
from patch_schueler_language import patch_schuler_language
from patch_schueler_telefon import patch_schuler_telefon
from patch_schueler_misc import patch_schueler_misc
from patch_schueler_parents import patch_schuler_parents
from patch_schueler__company import patch_schueler_company
from populate_schueler_leistungsdaten import populate_schueler_leistungsdaten


def main():
    """Main application entry point"""
    parser = argparse.ArgumentParser(
        description='SVWS Mock Factory - Create test databases for school server'
    )
    parser.add_argument(
        '--check-server',
        action='store_true',
        help='Check if the server is alive'
    )
    parser.add_argument(
        '--list-schemas',
        action='store_true',
        help='List all existing schemas'
    )
    parser.add_argument(
        '--delete-schema',
        action='store_true',
        help='Delete the configured schema'
    )
    parser.add_argument(
        '--create-schema',
        action='store_true',
        help='Create a new database schema'
    )
    parser.add_argument(
        '--init-db',
        action='store_true',
        help='Initialize the database with school number'
    )
    parser.add_argument(
        '--setup',
        action='store_true',
        help='Complete setup: create schema and initialize database'
    )
    parser.add_argument(
        '--populate-fahrschuelerarten',
        action='store_true',
        help='Populate Fahrschuelerarten catalog with 15 entries'
    )
    parser.add_argument(
        '--populate-einwilligungsarten',
        action='store_true',
        help='Populate Einwilligungsarten catalog from katalogdaten/einwilligungen.json'
    )
    parser.add_argument(
        '--populate-foerderschwerpunkte',
        action='store_true',
        help='Populate Foerderschwerpunkte catalog based on school form'
    )
    parser.add_argument(
        '--populate-floskelgruppen',
        action='store_true',
        help='Populate Floskelgruppen catalog from katalogdaten/Floskelgruppenart.json'
    )
    parser.add_argument(
        '--populate-floskeln',
        action='store_true',
        help='Populate Floskeln (snippets) from katalogdaten/Floskeln.csv'
    )
    parser.add_argument(
        '--populate-haltestellen',
        action='store_true',
        help='Populate Haltestellen (bus stops) from katalogdaten/haltestellen.txt'
    )
    parser.add_argument(
        '--populate-lernplattformen',
        action='store_true',
        help='Populate Lernplattformen from katalogdaten/lernplattformen.txt'
    )
    parser.add_argument(
        '--populate-schulen',
        action='store_true',
        help='Populate Schulen (schools) from katalogdaten/schulen.json'
    )
    parser.add_argument(
        '--populate-vermerkarten',
        action='store_true',
        help='Populate Vermerkarten catalog from katalogdaten/vermerkarten.txt'
    )
    parser.add_argument(
        '--populate-betriebe',
        action='store_true',
        help='Populate Betriebe catalog with synthetic data'
    )
    parser.add_argument(
        '--populate-kindergarten',
        action='store_true',
        help='Populate Kindergarten catalog with synthetic data (only for G, PS, S, V, WF)'
    )
    parser.add_argument(
        '--populate-lehrer',
        action='store_true',
        help='Populate Lehrer (teachers) catalog with synthetic data'
    )
    parser.add_argument(
        '--patch-lehrer-personaldaten',
        action='store_true',
        help='Patch existing Lehrer records with Personaldaten'
    )
    parser.add_argument(
        '--populate-classes',
        action='store_true',
        help='Populate K_Klassen (classes) with dynamic generation and assign teachers'
    )
    parser.add_argument(
        '--populate-schueler',
        action='store_true',
        help='Populate K_Schueler (students) with synthetic data by school form and grade'
    )
    parser.add_argument(
        '--patch-schueler-stammdaten',
        action='store_true',
        help='Patch existing Schueler records with additional Stammdaten'
    )
    parser.add_argument(
        '--patch-schueler-schulbesuch',
        action='store_true',
        help='Patch Schulbesuch for selected Schueler year groups with a Grundschule'
    )
    parser.add_argument(
        '--patch-schueler-language',
        action='store_true',
        help='Create language belegungen for selected Schueler year groups (POST)'
    )
    parser.add_argument(
        '--patch-schueler-telefon',
        action='store_true',
        help='Create two phone entries for each existing Schueler record (POST)'
    )
    parser.add_argument(
        '--patch-schueler-misc',
        action='store_true',
        help='Create three random Vermerke per existing Schueler record (POST)'
    )
    parser.add_argument(
        '--patch-schueler-parents',
        action='store_true',
        help='Create one parent entry per Schueler (first parent, female)'
    )
    parser.add_argument(
        '--patch-schueler-company',
        action='store_true',
        help='Assign one random Betrieb to each existing Schueler record'
    )
    parser.add_argument(
        '--populate-schueler-leistungsdaten',
        action='store_true',
        help='Create Leistungsdaten (Fächer) for each Schueler in current Lernabschnitt'
    )
    parser.add_argument(
        '--full-setup',
        action='store_true',
        help='Complete setup with all catalogs: create schema, initialize database, and populate all catalogs'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = load_config()
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return 1
    
    # Execute requested action
    if args.check_server:
        is_alive = check_server_alive(config)
        return 0 if is_alive else 1
    elif args.list_schemas:
        list_schemas(config)
        return 0
    elif args.delete_schema:
        success = delete_schema(config)
        return 0 if success else 1
    elif args.create_schema:
        success = create_schema(config)
        return 0 if success else 1
    elif args.init_db:
        success = init_database(config)
        return 0 if success else 1
    elif args.setup:
        print("Running complete setup...")
        print("\n1. Creating schema...")
        if not create_schema(config):
            print("Schema creation failed. Aborting setup.")
            return 1
        print("\n2. Initializing database...")
        if not init_database(config):
            print("Database initialization failed.")
            return 1
        print("\n✓ Complete setup finished successfully!")
        return 0
    elif args.populate_fahrschuelerarten:
        created, failed = populate_fahrschuelerarten(config)
        return 0 if failed == 0 else 1
    elif args.populate_einwilligungsarten:
        created, failed = populate_einwilligungsarten(config)
        return 0 if failed == 0 else 1
    elif args.populate_foerderschwerpunkte:
        created, failed = populate_foerderschwerpunkte(config)
        return 0 if failed == 0 else 1
    elif args.populate_floskelgruppen:
        created, failed = populate_floskelgruppen(config)
        return 0 if failed == 0 else 1
    elif args.populate_floskeln:
        created, failed = populate_floskeln(config)
        return 0 if failed == 0 else 1
    elif args.populate_haltestellen:
        created, failed = populate_haltestellen(config)
        return 0 if failed == 0 else 1
    elif args.populate_lernplattformen:
        created, failed = populate_lernplattformen(config)
        return 0 if failed == 0 else 1
    elif args.populate_schulen:
        created, failed = populate_schulen(config)
        return 0 if failed == 0 else 1
    elif args.populate_vermerkarten:
        created, failed = populate_vermerkarten(config)
        return 0 if failed == 0 else 1
    elif args.populate_betriebe:
        created, failed = populate_betriebe(config)
        return 0 if failed == 0 else 1
    elif args.populate_kindergarten:
        created, failed = populate_kindergarten(config)
        return 0 if failed == 0 else 1
    elif args.populate_lehrer:
        created, failed = populate_lehrer(config)
        return 0 if failed == 0 else 1
    elif args.patch_lehrer_personaldaten:
        patched, failed = patch_lehrer_personaldaten(config)
        return 0 if failed == 0 else 1
    elif args.populate_classes:
        created, failed = populate_classes(config)
        if failed > 0:
            return 1
        assigned, failed = assign_class_leaders(config)
        return 0 if failed == 0 else 1
    elif args.populate_schueler:
        created, failed = populate_schueler(config)
        return 0 if failed == 0 else 1
    elif args.patch_schueler_stammdaten:
        patched, failed = patch_schueler_stammdaten(config)
        return 0 if failed == 0 else 1
    elif args.patch_schueler_schulbesuch:
        patched, skipped, failed = patch_schueler_schulbesuch(config)
        return 0 if failed == 0 else 1
    elif args.patch_schueler_language:
        created, skipped, failed = patch_schuler_language(config)
        return 0 if failed == 0 else 1
    elif args.patch_schueler_telefon:
        patched, failed = patch_schuler_telefon(config)
        return 0 if failed == 0 else 1
    elif args.patch_schueler_misc:
        created, failed = patch_schueler_misc(config)
        return 0 if failed == 0 else 1
    elif args.patch_schueler_parents:
        created, skipped, failed = patch_schuler_parents(config)
        return 0 if failed == 0 else 1
    elif args.patch_schueler_company:
        created, skipped, failed = patch_schueler_company(config)
        return 0 if failed == 0 else 1
    elif args.populate_schueler_leistungsdaten:
        created, skipped, failed = populate_schueler_leistungsdaten(config)
        return 0 if failed == 0 else 1
    elif args.full_setup:
        full_setup_start = time.perf_counter()

        def print_full_setup_duration():
            elapsed_seconds = time.perf_counter() - full_setup_start
            minutes, seconds = divmod(elapsed_seconds, 60)
            print(f"\n⏱️ Gesamtzeit (--full-setup): {int(minutes):02d}:{seconds:05.2f} (mm:ss)")

        print("=" * 70)
        print("SVWS Mock Factory - Complete Setup with All Catalogs")
        print("=" * 70)
        
        # Step 1: Check server
        print("\n[1/26] Checking server connectivity...")
        if not check_server_alive(config):
            print("Server is not accessible. Aborting setup.")
            print_full_setup_duration()
            return 1
        print("✓ Server is alive")
        
        # Step 2: Create schema
        print("\n[2/26] Creating schema...")
        if not create_schema(config):
            print("Schema creation failed. Aborting setup.")
            print_full_setup_duration()
            return 1
        print("✓ Schema created successfully")
        
        # Step 3: Initialize database
        print("\n[3/26] Initializing database...")
        if not init_database(config):
            print("Database initialization failed. Aborting setup.")
            print_full_setup_duration()
            return 1
        
        # Patch Schulstammdaten with test values
        if patch_schulstammdaten(config):
            print("✓ Database initialized and Schulstammdaten patched successfully")
        else:
            print("✓ Database initialized (Schulstammdaten patch failed but continuing)")
        
        # Step 4: Populate Fahrschuelerarten
        print("\n[4/26] Populating Fahrschuelerarten catalog...")
        created, failed = populate_fahrschuelerarten(config)
        if failed > 0:
            print(f"Warning: {failed} entries failed to create")
        else:
            print(f"✓ Created {created} Fahrschuelerarten entries")
        
        # Step 5: Populate Einwilligungsarten
        print("\n[5/26] Populating Einwilligungsarten catalog...")
        created, failed = populate_einwilligungsarten(config)
        if failed > 0:
            print(f"Warning: {failed} entries failed to create")
        else:
            print(f"✓ Created {created} Einwilligungsarten entries")
        
        # Step 6: Populate Foerderschwerpunkte
        print("\n[6/26] Populating Foerderschwerpunkte catalog...")
        created, failed = populate_foerderschwerpunkte(config)
        if failed > 0:
            print(f"Warning: {failed} entries failed to create")
        else:
            print(f"✓ Created {created} Foerderschwerpunkte entries")
        
        # Step 7: Populate Floskelgruppen
        print("\n[7/26] Populating Floskelgruppen catalog...")
        created, failed = populate_floskelgruppen(config)
        if failed > 0:
            print(f"Warning: {failed} entries failed to create")
        else:
            print(f"✓ Created {created} Floskelgruppen entries")
        
        # Step 8: Populate Floskeln
        print("\n[8/26] Populating Floskeln (snippets) catalog...")
        created, failed = populate_floskeln(config)
        if failed > 0:
            print(f"Warning: {failed} entries failed to create")
        else:
            print(f"✓ Created {created} Floskeln entries")
        
        # Step 9: Populate Haltestellen
        print("\n[9/26] Populating Haltestellen (bus stops) catalog...")
        created, failed = populate_haltestellen(config)
        if failed > 0:
            print(f"Warning: {failed} entries failed to create")
        else:
            print(f"✓ Created {created} Haltestellen entries")

        # Step 10: Populate Lernplattformen
        print("\n[10/26] Populating Lernplattformen catalog...")
        created, failed = populate_lernplattformen(config)
        if failed > 0:
            print(f"Warning: {failed} entries failed to create")
        else:
            print(f"✓ Created {created} Lernplattformen entries")

        # Step 11: Populate Vermerkarten
        print("\n[11/26] Populating Vermerkarten catalog...")
        created, failed = populate_vermerkarten(config)
        if failed > 0:
            print(f"Warning: {failed} entries failed to create")
        else:
            print(f"✓ Created {created} Vermerkarten entries")

        # Step 12: Populate Betriebe
        print("\n[12/26] Populating Betriebe catalog...")
        created, failed = populate_betriebe(config)
        if failed > 0:
            print(f"Warning: {failed} entries failed to create")
        else:
            print(f"✓ Created {created} Betriebe entries")

        # Step 13: Populate Kindergarten
        print("\n[13/26] Populating Kindergarten catalog...")
        created, failed = populate_kindergarten(config)
        if failed > 0:
            print(f"Warning: {failed} entries failed to create")
        else:
            print(f"✓ Created {created} Kindergarten entries")

        # Step 14: Populate Schulen
        print("\n[14/26] Populating Schulen (schools) catalog...")
        created, failed = populate_schulen(config)
        if failed > 0:
            print(f"Warning: {failed} entries failed to create")
        else:
            print(f"✓ Created {created} Schulen entries")

        # Step 15: Populate Lehrer
        print("\n[15/26] Populating Lehrer (teachers) catalog...")
        created, failed = populate_lehrer(config)
        if failed > 0:
            print(f"Warning: {failed} entries failed to create")
        else:
            print(f"✓ Created {created} Lehrer entries")
        
        # Step 16: Patch Lehrer Personaldaten
        print("\n[16/26] Patching Lehrer Personaldaten...")
        patched, failed = patch_lehrer_personaldaten(config)
        if failed > 0:
            print(f"Warning: {failed} entries failed to patch")
        else:
            print(f"✓ Patched {patched} Lehrer Personaldaten entries")
        
        # Step 17: Populate Classes and Assign Teachers
        print("\n[17/26] Populating K_Klassen (classes) and assigning teachers...")
        created, failed = populate_classes(config)
        if failed > 0:
            print(f"Warning: {failed} classes failed to create")
        else:
            print(f"✓ Created {created} classes")
        
        assigned, failed = assign_class_leaders(config)
        if failed > 0:
            print(f"Warning: {failed} class teacher assignments failed")
        else:
            print(f"✓ Assigned teachers to {assigned} classes")

        # Step 18: Populate Schueler
        print("\n[18/26] Populating K_Schueler (students) catalog...")
        created, failed = populate_schueler(config)
        if failed > 0:
            print(f"Warning: {failed} students failed to create")
        else:
            print(f"✓ Created {created} Schueler entries")

        # Step 19: Patch Schueler Stammdaten
        print("\n[19/26] Patching Schueler Stammdaten...")
        patched, failed = patch_schueler_stammdaten(config)
        if failed > 0:
            print(f"Warning: {failed} student stammdaten entries failed to patch")
        else:
            print(f"✓ Patched {patched} Schueler Stammdaten entries")

        # Step 20: Patch Schueler Schulbesuch
        print("\n[20/26] Patching Schueler Schulbesuch entries...")
        patched, skipped, failed = patch_schueler_schulbesuch(config)
        if failed > 0:
            print(f"Warning: {failed} student schulbesuch entries failed to patch")
        else:
            print(f"✓ Patched {patched} Schueler Schulbesuch entries ({skipped} skipped)")

        # Step 21: Create Schueler Language Belegungen
        print("\n[21/26] Creating Schueler language belegungen...")
        created, skipped, failed = patch_schuler_language(config)
        if failed > 0:
            print(f"Warning: {failed} student language belegungen failed to create")
        else:
            print(f"✓ Created {created} language belegungen ({skipped} skipped)")

        # Step 22: Create Schueler Telefon
        print("\n[22/26] Creating Schueler Telefon entries...")
        patched, failed = patch_schuler_telefon(config)
        if failed > 0:
            print(f"Warning: {failed} student telefon entries failed to create")
        else:
            print(f"✓ Created {patched} Schueler Telefon entries")

        # Step 23: Create Schueler Misc (Vermerke)
        print("\n[23/26] Creating Schueler Vermerke entries...")
        created, failed = patch_schueler_misc(config)
        if failed > 0:
            print(f"Warning: {failed} student vermerke entries failed to create")
        else:
            print(f"✓ Created {created} Schueler Vermerke entries")

        # Step 24: Create Schueler Parents
        print("\n[24/26] Creating Schueler Parents entries...")
        created, skipped, failed = patch_schuler_parents(config)
        if failed > 0:
            print(f"Warning: {failed} student parent entries failed to create")
        else:
            print(f"✓ Created {created} Schueler Parent entries ({skipped} skipped)")

        # Step 25: Assign Schueler to random Betrieb
        print("\n[25/26] Assigning Schueler to random Betriebe...")
        created, skipped, failed = patch_schueler_company(config)
        if failed > 0:
            print(f"Warning: {failed} student company assignments failed")
        else:
            print(f"✓ Created {created} Schueler company assignments ({skipped} skipped)")

        # Step 26: Populate Schueler Leistungsdaten
        print("\n[26/26] Populating Schueler Leistungsdaten...")
        created, skipped, failed = populate_schueler_leistungsdaten(config)
        if failed > 0:
            print(f"Warning: {failed} Leistungsdaten entries failed to create")
        else:
            print(f"✓ Created {created} Leistungsdaten entries ({skipped} skipped)")

        print("\n" + "=" * 70)
        print("✓ Complete setup finished successfully!")
        print("=" * 70)
        print_full_setup_duration()
        return 0
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
