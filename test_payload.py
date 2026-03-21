"""
Test different payload formats for assigning class leaders.
"""

import json
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning
from check_server import load_config

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def test_payload_formats(config):
    """Test different payload formats for class leader assignment."""
    
    db = config['database']
    auth = HTTPBasicAuth(db['username'], db['password'])
    
    # Load from cache instead of API (to avoid 500 errors)
    cache_file = Path(__file__).parent / '.klassen_cache.json'
    with open(cache_file, 'r') as f:
        klassen = json.load(f)
    
    if not klassen:
        print("No classes in cache")
        return
    
    klasse_id = klassen[0]['id']
    klasse_kuerzel = klassen[0]['kuerzel']
    print(f"Test class: {klasse_kuerzel} (ID: {klasse_id})")
    print()
    
    # Use actual teacher IDs from the database
    teacher_id_1 = 19  # ARLT - real ID
    teacher_id_2 = 60  # BEC1 - real ID
    print(f"Test teachers: ID {teacher_id_1} (ARLT), ID {teacher_id_2} (BEC1)")
    print()
    
    # Test payloads - including string and int variants
    test_cases = [
        ("klassenLeitungen as list of ints", {'klassenLeitungen': [teacher_id_1, teacher_id_2]}),
        ("klassenLeitungen as list of strings", {'klassenLeitungen': [str(teacher_id_1), str(teacher_id_2)]}),
        ("klassenLeitungen as objects with id (int)", {'klassenLeitungen': [{'id': teacher_id_1}, {'id': teacher_id_2}]}),
        ("klassenLeitungen as objects with id (string)", {'klassenLeitungen': [{'id': str(teacher_id_1)}, {'id': str(teacher_id_2)}]}),
        ("lehrerIds (int)", {'lehrerIds': [teacher_id_1, teacher_id_2]}),
        ("lehrerIds (string)", {'lehrerIds': [str(teacher_id_1), str(teacher_id_2)]}),
        ("lehrerIDs (int)", {'lehrerIDs': [teacher_id_1, teacher_id_2]}),
        ("lehrerIDs (string)", {'lehrerIDs': [str(teacher_id_1), str(teacher_id_2)]}),
        ("lehrer list of objects", {'lehrer': [{'id': teacher_id_1}, {'id': teacher_id_2}]}),
        ("klassenLeitungenIds (int)", {'klassenLeitungenIds': [teacher_id_1, teacher_id_2]}),
        ("klassenLeitungenIds (string)", {'klassenLeitungenIds': [str(teacher_id_1), str(teacher_id_2)]}),
    ]
    
    url = f"https://{db['server']}:{db['httpsport']}/db/{db['schema']}/klassen/{klasse_id}"
    
    for test_name, payload in test_cases:
        print(f"Testing: {test_name}")
        print(f"  Payload: {json.dumps(payload)}")
        
        try:
            resp = requests.patch(
                url,
                json=payload,
                auth=auth,
                verify=False,
                timeout=10,
            )
            
            print(f"  Status: {resp.status_code}")
            if resp.status_code not in (200, 204):
                try:
                    err = resp.json()
                    print(f"  Full error: {json.dumps(err, indent=4, ensure_ascii=False)}")
                except:
                    print(f"  Error text: {resp.text[:500]}")
            else:
                print(f"  ✓ SUCCESS!")
                return
        except Exception as e:
            print(f"  Exception: {e}")
        
        print()

if __name__ == '__main__':
    cfg = load_config()
    test_payload_formats(cfg)
