#!/usr/bin/env python3
"""
Schema management module for SVWS Mock Factory
Handles schema listing and deletion
"""

import requests
import urllib3


# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def list_schemas(config):
    """
    List all existing schemas
    
    Args:
        config: Configuration dictionary containing server details
        
    Returns:
        list: List of schema names, or None if request failed
    """
    server = config['database']['server']
    port = config['database']['httpsport']
    username = config['database']['mariadbroot']
    password = config['database']['mariadbdbrootpassword']
    
    url = f"https://{server}:{port}/api/schema/liste/svws"
    
    auth = (username, password)
    
    try:
        print(f"Fetching list of schemas...")
        
        response = requests.get(
            url,
            auth=auth,
            verify=False,
            timeout=30
        )
        
        print(f"Response Status Code: {response.status_code}")
        
        if response.status_code == 200:
            schemas_data = response.json()
            schema_names = []
            
            if schemas_data:
                print(f"Found {len(schemas_data)} schema(s):")
                for schema_obj in schemas_data:
                    schema_name = schema_obj.get('name') if isinstance(schema_obj, dict) else schema_obj
                    schema_names.append(schema_name)
                    print(f"  - {schema_name}")
            else:
                print("No schemas found.")
            return schema_names
        else:
            print(f"✗ Failed to list schemas with status code: {response.status_code}")
            if response.text:
                print(f"Response: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
        return None


def delete_schema(config, schema=None):
    """
    Delete a database schema
    
    Args:
        config: Configuration dictionary containing server details
        schema: Schema name to delete (uses config schema if not provided)
        
    Returns:
        bool: True if deletion successful, False otherwise
    """
    server = config['database']['server']
    port = config['database']['httpsport']
    username = config['database']['mariadbroot']
    password = config['database']['mariadbdbrootpassword']
    
    if schema is None:
        schema = config['database']['schema']
    
    url = f"https://{server}:{port}/api/schema/root/destroy/{schema}"
    
    auth = (username, password)
    
    try:
        print(f"Deleting schema: {schema}")
        print(f"URL: {url}")
        
        # Try POST method first (some APIs use POST for destructive operations)
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
            print(f"✓ Schema '{schema}' deleted successfully!")
            return True
        else:
            print(f"✗ Schema deletion failed with status code: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
        return False


def delete_schema_if_exists(config, schema=None):
    """
    Delete a schema only if it exists
    
    Args:
        config: Configuration dictionary containing server details
        schema: Schema name to delete (uses config schema if not provided)
        
    Returns:
        bool: True if schema was deleted or didn't exist, False if deletion failed
    """
    if schema is None:
        schema = config['database']['schema']
    
    schemas = list_schemas(config)
    
    if schemas is None:
        print("Could not retrieve schema list.")
        return False
    
    if schema in schemas:
        print(f"\nSchema '{schema}' exists. Deleting...")
        return delete_schema(config, schema)
    else:
        print(f"Schema '{schema}' does not exist. No deletion needed.")
        return True


def main():
    """Main entry point for testing"""
    from check_server import load_config
    
    print("SVWS Mock Factory - Schema Management")
    print("=" * 50)
    
    try:
        config = load_config()
        
        print("\n1. Listing schemas:")
        print("-" * 50)
        list_schemas(config)
        
        return 0
            
    except FileNotFoundError:
        print("Error: config.json not found!")
        return 1
    except KeyError as e:
        print(f"Error: Missing configuration key: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
