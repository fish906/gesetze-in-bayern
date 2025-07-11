import time
import yaml
import requests
from parser import parse_norm
from db import save_norm, init_db, get_or_create_law  
import hashlib

with open('laws.yml', 'r') as f:
    config = yaml.safe_load(f)

BASE_URL = config['base_url']
GLOBAL_RETRIES = config.get('global', {}).get('retries', 3)
DELAY = config.get('global', {}).get('delay_between_requests', 0.3)

conn = init_db()

for law in config['laws']:
    law_identifier = law['id']
    law_name = law['name']
    db_law_id = get_or_create_law(conn, law_identifier, law_name)


    prefix = law['numbering']['prefix']
    start = law['numbering']['start']
    end = law['numbering']['end']

    print(f"Scraping {law_identifier} ...")

    for number in range(start, end + 1):
        url = f"{BASE_URL}/{prefix}{number}"
        print(f"Requesting: {url}")

        tries = 0
        while tries < GLOBAL_RETRIES:
            response = requests.get(url)
            if response.status_code == 200:
                print(f"Found: {prefix}{number}")
                data = parse_norm(response.text)

                data['law_id'] = db_law_id
                data['number'] = number
                data['number_raw'] = f"{prefix}{number}"
                data['url'] = url

                combined_content = f"{data.get('title', '')}{data.get('content', '')}"
                data['content_hash'] = hashlib.md5(combined_content.encode('utf-8')).hexdigest()

                if 'references' not in data:
                    data['references'] = []

                save_norm(conn, data)
                break
            elif response.status_code == 404:
                print(f"Not found: {prefix}{number}")
                break
            else:
                tries += 1
                print(f"Error {response.status_code}, retry {tries}/{GLOBAL_RETRIES}")
                time.sleep(2)
        time.sleep(DELAY)

conn.close()
