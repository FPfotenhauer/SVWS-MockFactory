#!/usr/bin/env python3
"""
SVWS Mock Factory - Server Status Checker
Checks if the school server is alive and responding
"""

import json
import requests
import urllib3
from pathlib import Path


# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def load_config(config_file='config.json'):
    """Load configuration from JSON file"""
    config_path = Path(__file__).parent / config_file
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def check_server_alive(config):
    """
    Check if the server is alive using the REST API
    
    Args:
        config: Configuration dictionary containing server details
        
    Returns:
        bool: True if server is alive, False otherwise
    """
    server = config['database']['server']
    port = config['database']['httpsport']
    username = config['database']['dbusername']
    password = config['database']['dbpassword']
    
    url = f"https://{server}:{port}/status/alive"
    
    # Create authorization header
    auth = (username, password)
    
    try:
        print(f"Checking server status at: {url}")
        print(f"Using username: {username}")
        
        # Make GET request with basic auth
        # verify=False to allow self-signed certificates
        response = requests.get(
            url,
            auth=auth,
            verify=False,
            timeout=10
        )
        
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Content: {response.text}")
        
        if response.status_code == 200:
            print("✓ Server is alive!")
            return True
        else:
            print(f"✗ Server returned status code: {response.status_code}")
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
    """Main entry point"""
    print("SVWS Mock Factory - Server Status Check")
    print("=" * 50)
    
    try:
        config = load_config()
        is_alive = check_server_alive(config)
        
        if is_alive:
            print("\nServer is operational.")
            return 0
        else:
            print("\nServer is not responding properly.")
            return 1
            
    except FileNotFoundError:
        print("Error: config.json not found!")
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in config file: {e}")
        return 1
    except KeyError as e:
        print(f"Error: Missing configuration key: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
