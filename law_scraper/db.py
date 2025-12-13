import pymysql
import yaml
import os
import hashlib
import logging

logger = logging.getLogger("law_scraper.db")
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO) 

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
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def save_norm(conn, data):
    cursor = conn.cursor()

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
            data['law_id'],
            data['number'],
            data['last_seen']
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

def get_law_by_id(conn, law_id):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, last_modified FROM laws WHERE id = %s",
        (law_id,)
    )
    row = cursor.fetchone()
    if row:
        return {
            'id': row[0],
            'name': row[1],
            'last_modified': row[2]
        }
    return None

def update_law_date(conn, law_id, new_date):
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE laws SET last_modified = %s WHERE id = %s",
        (new_date, law_id)
    )
    conn.commit()

def close_db(conn):
    try:
        if conn:
            conn.close()
            logger.info("Datenbankverbindung geschlossen.")
    except Exception as e:
        logger.error(f"Fehler beim Schließen der Verbindung: {e}")
