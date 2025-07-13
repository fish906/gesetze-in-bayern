import yaml
import time
import requests
from datetime import datetime

from parser import parse_norm, parse_overview
from db import init_db, get_or_create_law, save_norm, update_law_date, get_law_by_id

with open('laws.yml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

def fetch_and_parse_norm(url):
    print(f"Lade Norm: {url}")
    response = requests.get(url)
    response.raise_for_status()
    data = parse_norm(response.text)
    data['url'] = url
    return data

def fetch_overview_date(url):
    print(f"Lade Übersichtsseite: {url}")
    response = requests.get(url)
    response.raise_for_status()
    return parse_overview(response.text)

def main():
    conn = init_db()

    base_url = config['base_url']
    global_conf = config.get('global', {})
    retries = global_conf.get('retries', 3)
    delay = global_conf.get('delay_between_requests', 0.5)

    for law in config['laws']:
        law_id = get_or_create_law(conn, law['id'], law['name'])

        prefix = law['numbering']['prefix']
        overview_url = f"{base_url}/{prefix}"
        
        if not overview_url:
            print(f"Keine Übersicht definiert für {law['name']}, überspringe.")
            continue

        new_date = None
        for attempt in range(retries):
            try:
                new_date = fetch_overview_date(overview_url)
                break
            except Exception as e:
                print(f"Fehler beim Laden der Übersichtsseite: {e}, Versuch {attempt+1}/{retries}")
                time.sleep(delay)

        if not new_date:
            print(f"Kein Datum gefunden, überspringe {law['name']}.")
            continue

        current_law = get_law_by_id(conn, law_id)
        old_date = current_law.get('last_modified')

        if old_date == new_date:
            print(f"Keine Änderung ({new_date}), überspringe {law['name']}.")
            continue

        print(f"Änderung gefunden! Alt: {old_date} → Neu: {new_date}")

        start = law['numbering']['start']
        end = law['numbering']['end']

        for num in range(start, end + 1):
            url = f"{base_url}/{prefix}-{num}"
            for attempt in range(retries):
                try:
                    norm_data = fetch_and_parse_norm(url)
                    norm_data['law_id'] = law_id
                    norm_data['number'] = f"{prefix}-{num}"
                    norm_data['number_raw'] = f"{num}"
                    norm_data['last_seen'] = datetime.now().isoformat()
                    norm_data.setdefault('references', [])

                    save_norm(conn, norm_data)
                    print(f"Gespeichert: {norm_data['number']} - {norm_data['title']}")
                    break
                except Exception as e:
                    print(f"Fehler beim Laden {url}: {e}, Versuch {attempt+1}/{retries}")
                    time.sleep(delay)
            time.sleep(delay)

        update_law_date(conn, law_id, new_date)
        print(f"Datum aktualisiert auf {new_date}")

    conn.close()

if __name__ == "__main__":
    main()
