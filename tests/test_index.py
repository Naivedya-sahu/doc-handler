import sqlite3
from docsort.index import open_index, SCHEMA


def test_open_index_creates_files_table(tmp_path):
    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='files'")
    assert cur.fetchone() is not None
    cols = {row[1] for row in conn.execute("PRAGMA table_info(files)")}
    assert cols == {
        "path", "size", "hash", "mtime", "archive_depth", "source_archive"
    }
    conn.close()
