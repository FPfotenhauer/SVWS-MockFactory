#!/usr/bin/env python3
"""
Database initialization module for SVWS Mock Factory
Handles schema creation and school initialization
"""

import requests
import urllib3


# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def init_database(config):
    """
    Initialize the database with a school number
    
    Args:
        config: Configuration dictionary containing server details
        
    Returns:
        bool: True if initialization successful, False otherwise
    """
    server = config['database']['server']
    port = config['database']['httpsport']
    username = config['database']['username']
    password = config['database']['password']
    schema = config['database']['schema']
    schulnummer = config['database']['schulnummer']
    
    url = f"https://{server}:{port}/db/{schema}/schule/init/{schulnummer}"
    
    # Create authorization header
    auth = (username, password)
    
    try:
        print(f"Initializing database schema: {schema}")
        print(f"School number: {schulnummer}")
        print(f"URL: {url}")
        print(f"Using username: {username}")
        
        # Make POST request with basic auth
        response = requests.post(
            url,
            auth=auth,
            verify=False,
            timeout=30
        )
        
        print(f"Response Status Code: {response.status_code}")
        
        if response.text:
            print(f"Response Content: {response.text}")
        
        if response.status_code in [200, 201, 204]:
            print("✓ Database initialized successfully!")
            return True
        else:
            print(f"✗ Database initialization failed with status code: {response.status_code}")
            try:
                print(f"Error details: {response.json()}")
            except:
                pass
            return False
            
    except requests.exceptions.ConnectionError as e:
        print(f"✗ Connection error: {e}")
        return False
    except requests.exceptions.Timeout as e:
        print(f"✗ Request timeout: {e}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
        return False


def main():
    """Main entry point for testing"""
    from check_server import load_config
    
    print("SVWS Mock Factory - Database Initialization")
    print("=" * 50)
    
    try:
        config = load_config()
        success = init_database(config)
        
        if success:
            print("\nDatabase initialization completed.")
            return 0
        else:
            print("\nDatabase initialization failed.")
            return 1
            
    except FileNotFoundError:
        print("Error: config.json not found!")
        return 1
    except KeyError as e:
        print(f"Error: Missing configuration key: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
