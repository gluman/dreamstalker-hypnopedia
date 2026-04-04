import requests
import sys

try:
    resp = requests.get('http://127.0.0.1:8000/api/sessions', timeout=10)
    if resp.status_code == 200:
        print('OK: DreamStalker server is healthy')
        sys.exit(0)
    else:
        print(f'ERROR: Status {resp.status_code}')
        sys.exit(1)
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
