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
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
