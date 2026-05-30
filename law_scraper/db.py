import yaml
import os
import hashlib
import logging
import datetime
from datetime import date
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from models import Base, Law, Norm

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
        raise FileNotFoundError(f"config file not found: {path}")

    with open(path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    if 'database' not in config:
        raise KeyError("config.yaml is missing 'database' section")

    return config['database']

def init_db():
    db_conf = load_db_config()

    db_url = f"mysql+pymysql://{db_conf['user']}:{db_conf['password']}@{db_conf.get('host', 'localhost')}/{db_conf['db']}?charset=utf8mb4"
    engine = create_engine(db_url, echo=False)

    Base.metadata.create_all(engine)

    session = Session(engine)
    logger.info("connected to database")
    return session

def get_or_create_law(session, law_identifier, law_description):
    law = session.query(Law).filter(Law.name == law_identifier).first()

    if law:
        logger.debug(f"Gesetz gefunden: {law_identifier} (ID: {law.id})")
        return law.id
    else:
        new_law = Law(name=law_identifier, description=law_description)
        session.add(new_law)
        session.commit()
        logger.info(f"Neues Gesetz eingefügt: {law_identifier} (ID: {new_law.id})")
        return new_law.id

def hash_content(content):
    """Hash content using MD5 (consistent with scraper.py)."""
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def save_norm(session, data):
    if 'last_seen' not in data or not data['last_seen']:
        data['last_seen'] = date.today().isoformat()

    if 'content_hash' not in data or not data['content_hash']:
        data['content_hash'] = hash_content(data['content'])

    existing_norm = session.query(Norm).filter(
        Norm.law_id == data['law_id'],
        Norm.number == data['number']
    ).first()

    if existing_norm:
        if existing_norm.content_hash == data['content_hash']:
            existing_norm.last_seen = data['last_seen']
            session.commit()
            logger.debug(f"Unverändert: law_id={data['law_id']}, number={data['number']}")
            return

        existing_norm.number_raw = data['number_raw']
        existing_norm.title = data['title']
        existing_norm.content = data['content']
        existing_norm.url = data['url']
        existing_norm.content_hash = data['content_hash']
        existing_norm.last_seen = data['last_seen']
        session.commit()
        logger.info(f"Aktualisiert: law_id={data['law_id']}, number={data['number']}")
    else:
        new_norm = Norm(
            law_id=data['law_id'],
            number=data['number'],
            number_raw=data['number_raw'],
            title=data['title'],
            content=data['content'],
            url=data['url'],
            content_hash=data['content_hash'],
            last_seen=data['last_seen']
        )
        session.add(new_norm)
        session.commit()
        logger.info(f"Eingefügt: law_id={data['law_id']}, number={data['number']}")

def flag_stale_norms(session, law_id, current_date):
    """Flag norms that were not seen in the current scrape run.

    Sets is_stale = 1 for norms whose last_seen is older than current_date.
    Returns the number of norms flagged.
    """
    stale_norms = session.query(Norm).filter(
        Norm.law_id == law_id,
        (Norm.last_seen < current_date) | (Norm.last_seen == None)
    ).all()

    stale_count = len(stale_norms)
    for norm in stale_norms:
        norm.is_stale = 1
    session.commit()

    unflag_norms = session.query(Norm).filter(
        Norm.law_id == law_id,
        Norm.last_seen == current_date,
        Norm.is_stale == 1
    ).all()

    for norm in unflag_norms:
        norm.is_stale = 0
    session.commit()

    return stale_count

def get_law_last_modified(session, law_id):
    """Return the stored last_modified date for a law, or None."""
    law = session.query(Law).filter(Law.id == law_id).first()
    if not law or law.last_modified is None:
        return None
    lm = law.last_modified
    if isinstance(lm, datetime.datetime):
        return lm.date()
    if isinstance(lm, str):
        return date.fromisoformat(lm)
    return lm


def update_law_last_modified(session, law_id, new_date):
    """Set the last_modified date for a law."""
    law = session.query(Law).filter(Law.id == law_id).first()
    if law:
        law.last_modified = new_date
        session.commit()
        logger.debug(f"Updated last_modified for law_id={law_id}: {new_date}")


def bump_norms_last_seen(session, law_id, current_date):
    """Bump last_seen for all norms of a law without changing content.

    Used when a law is skipped because its last_modified date is unchanged.
    Returns the number of rows updated.
    """
    updated = session.query(Norm).filter(Norm.law_id == law_id).update(
        {Norm.last_seen: current_date}, synchronize_session=False
    )
    session.commit()
    logger.debug(f"Bumped last_seen for {updated} norm(s) of law_id={law_id}")
    return updated

def close_db(session):
    try:
        if session:
            session.close()
            logger.info("Datenbankverbindung geschlossen.")
    except Exception as e:
        logger.error(f"Fehler beim Schließen der Verbindung: {e}")
