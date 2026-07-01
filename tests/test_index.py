import sqlite3
from docsort.index import open_index, SCHEMA, hash_file, scan_directory


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


def test_hash_file_is_stable(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"hello world")
    h1 = hash_file(str(f))
    h2 = hash_file(str(f))
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex digest


def test_scan_directory_indexes_all_files(tmp_path):
    data_root = tmp_path / "data"
    (data_root / "sub").mkdir(parents=True)
    (data_root / "a.txt").write_bytes(b"one")
    (data_root / "sub" / "b.txt").write_bytes(b"two")

    db_path = tmp_path / "index.db"  # deliberately outside data_root
    conn = open_index(str(db_path))
    scan_directory(conn, str(data_root))

    rows = conn.execute("SELECT path, size, archive_depth FROM files ORDER BY path").fetchall()
    assert len(rows) == 2
    assert all(r[2] == 0 for r in rows)  # archive_depth 0 for plain files
    conn.close()
