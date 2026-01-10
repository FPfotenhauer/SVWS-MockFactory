#!/usr/bin/env python3
"""
Schema creation module for SVWS Mock Factory
Handles database schema creation and cleanup
"""

import requests
import urllib3
from schema_manager import delete_schema_if_exists


# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def create_schema(config):
    """
    Create a new database schema
    
    Args:
        config: Configuration dictionary containing server details
        
    Returns:
        bool: True if schema creation successful, False otherwise
    """
    server = config['database']['server']
    port = config['database']['httpsport']
    username = config['database']['mariadbroot']
    password = config['database']['mariadbdbrootpassword']
    schema = config['database']['schema']
    
    # Admin credentials for schema creation
    admin_user = config['database']['username']
    admin_password = config['database']['password']
    
    # Delete schema if it already exists
    print(f"Checking for existing schema '{schema}'...")
    if not delete_schema_if_exists(config, schema):
        print("Failed to clean up existing schema.")
        return False
    
    url = f"https://{server}:{port}/api/schema/root/create/{schema}"
    
    # Create authorization header using root credentials
    auth = (username, password)
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    # Body with admin credentials for schema creation
    body = {
        "user": admin_user,
        "password": admin_password
    }
    
    try:
        print(f"Creating database schema: {schema}")
        print(f"URL: {url}")
        print(f"Using root username: {username}")
        print(f"Schema user: {admin_user}")
        
        # Make POST request with basic auth and proper headers
        response = requests.post(
            url,
            auth=auth,
            headers=headers,
            json=body,
            verify=False,
            timeout=30
        )
        
        print(f"Response Status Code: {response.status_code}")
        
        if response.text:
            print(f"Response Content: {response.text}")
        
        if response.status_code in [200, 201, 204]:
            print("✓ Schema created successfully!")
            return True
        else:
            print(f"✗ Schema creation failed with status code: {response.status_code}")
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
    
    print("SVWS Mock Factory - Schema Creation")
    print("=" * 50)
    
    try:
        config = load_config()
        success = create_schema(config)
        
        if success:
            print("\nSchema creation completed.")
            return 0
        else:
            print("\nSchema creation failed.")
            return 1
            
    except FileNotFoundError:
        print("Error: config.json not found!")
        return 1
    except KeyError as e:
        print(f"Error: Missing configuration key: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
