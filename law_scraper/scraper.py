import time
import yaml
import os
import requests
import hashlib
import logging
from datetime import date
from .parser import parse_norm, ParseError
from .db import save_norm, init_db, get_or_create_law, close_db, flag_stale_norms

logger = logging.getLogger("law_scraper.scraper")
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("[%(levelname)s] %(asctime)s | %(name)s | %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

REQUEST_TIMEOUT = 15  # seconds
_dir = os.path.dirname(os.path.abspath(__file__))


def load_config():
    """Load laws.yml from the package directory."""
    path = os.path.join(_dir, 'laws.yml')
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def scrape_norm(session, url, prefix, number, db_law_id, conn, retries):
    """Fetch and store a single norm. Returns True on success, False on skip/not found."""
    tries = 0
    while tries < retries:
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.Timeout:
            tries += 1
            logger.warning(f"Timeout for {url}, retry {tries}/{retries}")
            time.sleep(2)
            continue
        except requests.exceptions.ConnectionError as e:
            tries += 1
            logger.warning(f"Connection error for {url}: {e}, retry {tries}/{retries}")
            time.sleep(2)
            continue
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return False

        if response.status_code == 200:
            try:
                data = parse_norm(response.text)
            except ParseError as e:
                logger.debug(f"Skipping {url}: {e}")
                return False
            except Exception as e:
                logger.error(f"Parsing failed for {url}: {e}")
                return False

            data['law_id'] = db_law_id
            data['number'] = number
            data['number_raw'] = f"{prefix}{number}"
            data['url'] = url
            data['last_seen'] = date.today().isoformat()

            combined_content = f"{data.get('number_raw', '')}{data.get('title', '')}{data.get('content', '')}"
            data['content_hash'] = hashlib.md5(combined_content.encode('utf-8')).hexdigest()

            if 'references' not in data:
                data['references'] = []

            try:
                save_norm(conn, data)
            except Exception as e:
                logger.error(f"DB save failed for {url}: {e}")
                return False

            logger.info(f"Found: {prefix}{number}")
            return True

        elif response.status_code == 404:
            logger.debug(f"Not found: {prefix}{number}")
            return False
        else:
            tries += 1
            logger.warning(f"HTTP {response.status_code} for {url}, retry {tries}/{retries}")
            time.sleep(2)

    logger.error(f"Max retries reached for {url}")
    return False


def main():
    conn = None
    try:
        config = load_config()
        base_url = config['base_url']
        retries = config.get('global', {}).get('retrie4', 3)
        delay = config.get('global', {}).get('delay_between_requests', 0.3)

        conn = init_db()
        session = requests.Session()

        for law in config['laws']:
            law_identifier = law['id']
            law_name = law['name']

            try:
                db_law_id = get_or_create_law(conn, law_identifier, law_name)
            except Exception as e:
                logger.error(f"Failed to get/create law '{law_identifier}': {e}")
                continue

            prefix = law['numbering']['prefix']
            start = law['numbering']['start']
            end = law['numbering']['end']

            logger.info(f"Scraping {law_identifier} ({start}-{end}) ...")

            today = date.today().isoformat()

            for number in range(start, end + 1):
                url = f"{base_url}/{prefix}{number}"
                logger.debug(f"Requesting: {url}")
                scrape_norm(session, url, prefix, number, db_law_id, conn, retries)
                time.sleep(delay)

            try:
                stale_count = flag_stale_norms(conn, db_law_id, today)
                if stale_count > 0:
                    logger.warning(f"{stale_count} stale norm(s) flagged for {law_identifier}")
            except Exception as e:
                logger.error(f"Failed to flag stale norms for '{law_identifier}': {e}")

    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
    finally:
        if conn:
            close_db(conn)


if __name__ == "__main__":
    main()