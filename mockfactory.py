#!/usr/bin/env python3
"""
SVWS Mock Factory
Main application for creating demonstration and testing databases
for the school server system
"""

import argparse
import sys
from check_server import load_config, check_server_alive
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
        '--init-db',
        action='store_true',
        help='Initialize the database with school number'
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
    elif args.init_db:
        success = init_database(config)
        return 0 if success else 1
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
