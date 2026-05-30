import time
import yaml
import os
import requests
import hashlib
import logging
from datetime import date
from models import Law, Norm

from .parser import parse_norm, parse_overview, ParseError
from .db import (
    save_norm, init_db, get_or_create_law, close_db, flag_stale_norms,
    get_law_last_modified, update_law_last_modified, bump_norms_last_seen,
)

logger = logging.getLogger("scraper")
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

def fetch_with_retries(http_session, url, retries):
    tries = 0
    while tries < retries:
        try:
            response = http_session.get(url, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.Timeout:
            tries += 1
            logger.warning(f"Timeout for {url}, retry {tries}/{retries}")
            time.sleep(min(2 ** tries, 30))
            continue
        except requests.exceptions.ConnectionError as e:
            tries += 1
            logger.warning(f"Connection error for {url}: {e}, retry {tries}/{retries}")
            time.sleep(min(2 ** tries, 30))
            continue
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return "failed"

        if response.status_code == 200:
            return response
        elif response.status_code == 404:
            return None
        else:
            tries += 1
            logger.warning(f"HTTP {response.status_code} for {url}, retry {tries}/{retries}")
            time.sleep(min(2 ** tries, 30))

    logger.error(f"Max retries reached for {url}")
    return "failed"

def scrape_norm(http_session, url, prefix, number, db_law_id, session, retries):
    response = fetch_with_retries(http_session, url, retries)

    if response == "failed":
        return "failed"
    if response is None:
        logger.debug(f"Not found: {prefix}-{number}")
        return "not_found"

    try:
        data = parse_norm(response.text)
    except ParseError as e:
        logger.debug(f"Skipping {url}: {e}")
        return "not_found"
    except Exception as e:
        logger.error(f"Parsing failed for {url}: {e}")
        return "failed"

    data['law_id'] = db_law_id
    data['number'] = number
    data['number_raw'] = f"{prefix}-{number}"
    data['url'] = url
    data['last_seen'] = date.today().isoformat()

    combined_content = f"{data.get('number_raw', '')}{data.get('title', '')}{data.get('content', '')}"
    data['content_hash'] = hashlib.md5(combined_content.encode('utf-8')).hexdigest()

    if 'references' not in data:
        data['references'] = []

    try:
        save_norm(session, data)
    except Exception as e:
        logger.error(f"DB save failed for {url}: {e}")
        session.rollback()
        return "failed"

    logger.info(f"Found: {prefix}-{number}")
    return "found"

def main():
    session = None
    total_found = 0
    total_failed = 0
    total_stale = 0
    try:
        config = load_config()
        base_url = config['base_url']
        retries = config.get('global', {}).get('retries', 3)
        delay = config.get('global', {}).get('delay_between_requests', 0.3)

        session = init_db()
        http_session = requests.Session()

        for law in config['laws']:
            law_identifier = law['id']
            law_name = law['name']

            try:
                db_law_id = get_or_create_law(session, law_identifier, law_name)
            except Exception as e:
                logger.error(f"Failed to get/create law '{law_identifier}': {e}")
                continue

            prefix = law['numbering']['prefix']
            start = law['numbering']['start']
            end = law['numbering']['end']
            today = date.today()
            today_iso = today.isoformat()

            # Check the law overview page for the "Text gilt ab" date
            overview_url = f"{base_url}/{prefix}"
            logger.debug(f"Requesting overview: {overview_url}")
            overview_response = fetch_with_retries(http_session, overview_url, retries)

            site_date = None
            if overview_response not in (None, "failed"):
                site_date = parse_overview(overview_response.text)
                if site_date is None:
                    logger.warning(f"Could not parse 'Text gilt ab' date from {overview_url}")
            else:
                logger.warning(f"Could not fetch overview for {law_identifier}; scraping anyway")

            if site_date is not None:
                stored_date = get_law_last_modified(session, db_law_id)
                logger.debug(f"{law_identifier}: site_date={site_date!r} stored_date={stored_date!r}")
                if stored_date == site_date:
                    bumped = bump_norms_last_seen(session, db_law_id, today_iso)
                    logger.info(
                        f"{law_identifier} unchanged (Text gilt ab: {site_date}), "
                        f"skipping — bumped last_seen on {bumped} norm(s)"
                    )
                    time.sleep(delay)
                    continue

            logger.info(f"Scraping {law_identifier} ({start}-{end}) ...")

            law_found = 0
            law_failed = 0

            for number in range(start, end + 1):
                url = f"{base_url}/{prefix}-{number}"
                logger.debug(f"Requesting: {url}")
                result = scrape_norm(http_session, url, prefix, str(number), db_law_id, session, retries)
                if result == "found":
                    law_found += 1
                elif result == "failed":
                    law_failed += 1
                time.sleep(delay)

                if result != "found":
                    continue

                for suffix in "abcdefghijklmnopqrstuvwxyz":
                    sub_number = f"{number}{suffix}"
                    sub_url = f"{base_url}/{prefix}-{sub_number}"
                    logger.debug(f"Requesting: {sub_url}")
                    sub_result = scrape_norm(http_session, sub_url, prefix, sub_number, db_law_id, session, retries)
                    if sub_result == "found":
                        law_found += 1
                    elif sub_result == "failed":
                        law_failed += 1
                    time.sleep(delay)
                    if sub_result != "found":
                        break

            total_found += law_found
            total_failed += law_failed
            logger.info(
                f"{law_identifier}: {law_found} found, {law_failed} failed"
                f" ({end - start + 1 - law_found - law_failed} not found)"
            )

            if site_date is not None:
                try:
                    update_law_last_modified(session, db_law_id, site_date)
                except Exception as e:
                    logger.error(f"Failed to update last_modified for '{law_identifier}': {e}")

            try:
                stale_count = flag_stale_norms(session, db_law_id, today_iso)
                total_stale += stale_count
                if stale_count > 0:
                    logger.warning(f"{stale_count} stale norm(s) flagged for {law_identifier}")
            except Exception as e:
                logger.error(f"Failed to flag stale norms for '{law_identifier}': {e}")

    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
    finally:
        if session:
            close_db(session)
        logger.info(
            f"Done — {total_found} norms saved/updated, "
            f"{total_failed} failed, {total_stale} marked stale"
        )


if __name__ == "__main__":
    main()