import pymysql
import yaml
import os
import hashlib
import logging
from datetime import date

logger = logging.getLogger("law_scraper.db")
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)  # Du kannst INFO oder DEBUG setzen

# logging formatting
formatter = logging.Formatter("[%(levelname)s] %(asctime)s | %(name)s | %(message)s")
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)

def load_db_config(path="config.yml"):
    base_dir = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(base_dir, 'config.yml')
    
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config-Datei nicht gefunden: {path}")

    with open(path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    if 'database' not in config:
        raise KeyError("In der config.yaml fehlt der Abschnitt 'database'")

    return config['database']

def init_db():
    db_conf = load_db_config()

    conn = pymysql.connect(
        host=db_conf.get('host', 'localhost'),
        user=db_conf['user'],
        password=db_conf['password'],
        database=db_conf['db'],
        charset='utf8mb4',
        autocommit=False
    )
    logger.info("Datenbankverbindung hergestellt.")
    return conn

def get_or_create_law(conn, law_identifier, law_description):
    with conn.cursor() as cursor:
        cursor.execute("SELECT id FROM laws WHERE name = %s", (law_identifier,))
        result = cursor.fetchone()
        if result:
            logger.debug(f"Gesetz gefunden: {law_identifier} (ID: {result[0]})")
            return result[0]
        else:
            cursor.execute(
                "INSERT INTO laws (name, description) VALUES (%s, %s)",
                (law_identifier, law_description)
            )
            conn.commit()
            law_id = cursor.lastrowid
            logger.info(f"Neues Gesetz eingefügt: {law_identifier} (ID: {law_id})")
            return law_id

def hash_content(content):
    """Hash content using MD5 (consistent with scraper.py)."""
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def save_norm(conn, data):
    cursor = conn.cursor()

    # Default last_seen to today if not provided
    if 'last_seen' not in data or not data['last_seen']:
        data['last_seen'] = date.today().isoformat()

    if 'content_hash' not in data or not data['content_hash']:
        data['content_hash'] = hash_content(data['content'])

    sql_select = """
    SELECT content_hash FROM norms WHERE law_id = %s AND number = %s
    """
    cursor.execute(sql_select, (data['law_id'], data['number']))
    result = cursor.fetchone()

    if result:
        existing_hash = result[0]
        if existing_hash == data['content_hash']:
            # Content unchanged, but still update last_seen to mark as active
            cursor.execute(
                "UPDATE norms SET last_seen = %s WHERE law_id = %s AND number = %s",
                (data['last_seen'], data['law_id'], data['number'])
            )
            conn.commit()
            logger.debug(f"Unverändert: law_id={data['law_id']}, number={data['number']}")
            return 

        sql_update = """
            UPDATE norms
            SET number_raw = %s, title = %s, content = %s, url = %s, content_hash = %s, last_seen = %s
            WHERE law_id = %s AND number = %s
        """

        cursor.execute(sql_update, (
            data['number_raw'],
            data['title'],
            data['content'],
            data['url'],
            data['content_hash'],
            data['last_seen'],
            data['law_id'],
            data['number'],
        ))
        logger.info(f"Aktualisiert: law_id={data['law_id']}, number={data['number']}")

    else:
        sql_insert = """
        INSERT INTO norms (law_id, number, number_raw, title, content, url, content_hash, last_seen)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        cursor.execute(sql_insert, (
            data['law_id'],
            data['number'],
            data['number_raw'],
            data['title'],
            data['content'],
            data['url'],
            data['content_hash'],
            data['last_seen']
        ))
        logger.info(f"Eingefügt: law_id={data['law_id']}, number={data['number']}")

    conn.commit()

def flag_stale_norms(conn, law_id, current_date):
    """Flag norms that were not seen in the current scrape run.
    
    Sets is_stale = 1 for norms whose last_seen is older than current_date.
    Returns the number of norms flagged.
    """
    with conn.cursor() as cursor:
        sql = """
            UPDATE norms
            SET is_stale = 1
            WHERE law_id = %s AND (last_seen < %s OR last_seen IS NULL)
        """
        cursor.execute(sql, (law_id, current_date))
        stale_count = cursor.rowcount

        # Unflag norms that were seen today (in case they were previously stale)
        sql_unflag = """
            UPDATE norms
            SET is_stale = 0
            WHERE law_id = %s AND last_seen = %s AND is_stale = 1
        """
        cursor.execute(sql_unflag, (law_id, current_date))

        conn.commit()
        return stale_count

def close_db(conn):
    try:
        if conn:
            conn.close()
            logger.info("Datenbankverbindung geschlossen.")
    except Exception as e:
        logger.error(f"Fehler beim Schließen der Verbindung: {e}")