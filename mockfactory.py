#!/usr/bin/env python3
"""
SVWS Mock Factory
Main application for creating demonstration and testing databases
for the school server system
"""

import argparse
import sys
from check_server import load_config, check_server_alive
from schema_manager import list_schemas, delete_schema
from create_schema import create_schema
from init_database import init_database
from populate_fahrschuelerarten import populate_fahrschuelerarten
from populate_einwilligungsarten import populate_einwilligungsarten
from populate_foerderschwerpunkte import populate_foerderschwerpunkte
from populate_floskelgruppen import populate_floskelgruppen


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
    elif args.full_setup:
        print("=" * 70)
        print("SVWS Mock Factory - Complete Setup with All Catalogs")
        print("=" * 70)
        
        # Step 1: Check server
        print("\n[1/5] Checking server connectivity...")
        if not check_server_alive(config):
            print("Server is not accessible. Aborting setup.")
            return 1
        print("✓ Server is alive")
        
        # Step 2: Create schema
        print("\n[2/5] Creating schema...")
        if not create_schema(config):
            print("Schema creation failed. Aborting setup.")
            return 1
        print("✓ Schema created successfully")
        
        # Step 3: Initialize database
        print("\n[3/5] Initializing database...")
        if not init_database(config):
            print("Database initialization failed. Aborting setup.")
            return 1
        print("✓ Database initialized successfully")
        
        # Step 4: Populate Fahrschuelerarten
        print("\n[4/5] Populating Fahrschuelerarten catalog...")
        created, failed = populate_fahrschuelerarten(config)
        if failed > 0:
            print(f"Warning: {failed} entries failed to create")
        else:
            print(f"✓ Created {created} Fahrschuelerarten entries")
        
        # Step 5: Populate Einwilligungsarten
        print("\n[5/6] Populating Einwilligungsarten catalog...")
        created, failed = populate_einwilligungsarten(config)
        if failed > 0:
            print(f"Warning: {failed} entries failed to create")
        else:
            print(f"✓ Created {created} Einwilligungsarten entries")
        
        # Step 6: Populate Foerderschwerpunkte
        print("\n[6/7] Populating Foerderschwerpunkte catalog...")
        created, failed = populate_foerderschwerpunkte(config)
        if failed > 0:
            print(f"Warning: {failed} entries failed to create")
        else:
            print(f"✓ Created {created} Foerderschwerpunkte entries")
        
        # Step 7: Populate Floskelgruppen
        print("\n[7/7] Populating Floskelgruppen catalog...")
        created, failed = populate_floskelgruppen(config)
        if failed > 0:
            print(f"Warning: {failed} entries failed to create")
        else:
            print(f"✓ Created {created} Floskelgruppen entries")
        
        print("\n" + "=" * 70)
        print("✓ Complete setup finished successfully!")
        print("=" * 70)
        return 0
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
