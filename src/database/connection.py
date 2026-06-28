import sqlite3
import os

from config.settings import settings

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

if os.path.isabs(settings.DATABASE_URL):
    DB_PATH = settings.DATABASE_URL
else:
    DB_PATH = os.path.join(ROOT_DIR, 'data', settings.DATABASE_URL)

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
