import pymysql
import yaml
import os

def load_db_config(path="config.yml"):
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
    return conn

def get_or_create_law(conn, law_identifier, law_description):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM laws WHERE name = %s", (law_identifier,))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        cursor.execute(
            "INSERT INTO laws (name, description) VALUES (%s, %s)",
            (law_identifier, law_description)
        )
        conn.commit()
        return cursor.lastrowid


def save_law(conn, name, description=None):
    with conn.cursor() as cursor:
        # Prüfen, ob es schon existiert
        sql = "SELECT id FROM laws WHERE name = %s"
        cursor.execute(sql, (name,))
        result = cursor.fetchone()

        if result:
            law_id = result[0]
        else:
            sql = "INSERT INTO laws (name, description) VALUES (%s, %s)"
            cursor.execute(sql, (name, description))
            law_id = cursor.lastrowid

        conn.commit()
        return law_id

def save_norm(conn, data):
    cursor = conn.cursor()

    sql_select = """
    SELECT content_hash FROM norms WHERE law_id = %s AND number = %s
    """
    cursor.execute(sql_select, (data['law_id'], data['number']))
    result = cursor.fetchone()

    if result:
        existing_hash = result[0]
        if existing_hash == data['content_hash']:
            print(f"No changes for law_id={data['law_id']}, number={data['number']}")
            return  # Keine Änderung, nichts tun

        sql_update = """
        UPDATE norms
        SET number_raw = %s, title = %s, content = %s, url = %s, content_hash = %s
        WHERE law_id = %s AND number = %s
        """
        cursor.execute(sql_update, (
            data['number_raw'],
            data['title'],
            data['content'],
            data['url'],
            data['content_hash'],
            data['law_id'],
            data['number']
        ))
        print(f"Updated law_id={data['law_id']}, number={data['number']}")

    else:
        # Norm existiert nicht → Insert
        sql_insert = """
        INSERT INTO norms (law_id, number, number_raw, title, content, url, content_hash)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql_insert, (
            data['law_id'],
            data['number'],
            data['number_raw'],
            data['title'],
            data['content'],
            data['url'],
            data['content_hash']
        ))
        print(f"Inserted law_id={data['law_id']}, number={data['number']}")

    conn.commit()

def close_db(conn):
    try:
        if conn:
            conn.close()
            print("DB-Verbindung geschlossen.")
    except Exception as e:
        print(f"Fehler beim Schließen der DB-Verbindung: {e}")
