import hashlib
import os
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


def hash_file(path, chunk_size=65536):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _upsert(conn, path, size, filehash, mtime, archive_depth=0, source_archive=None):
    conn.execute(
        "INSERT OR REPLACE INTO files(path,size,hash,mtime,archive_depth,source_archive) "
        "VALUES (?,?,?,?,?,?)",
        (path, size, filehash, mtime, archive_depth, source_archive),
    )


def scan_directory(conn, root):
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            try:
                size = os.path.getsize(full)
                mtime = os.path.getmtime(full)
                filehash = hash_file(full)
            except OSError:
                continue
            _upsert(conn, full, size, filehash, mtime)
    conn.commit()
