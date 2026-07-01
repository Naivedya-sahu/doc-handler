import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    size INTEGER,
    hash TEXT,
    mtime REAL,
    archive_depth INTEGER DEFAULT 0,
    source_archive TEXT
);
"""


def open_index(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.commit()
    return conn
