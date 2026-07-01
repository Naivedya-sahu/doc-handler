from docsort.index import open_index, scan_directory
from docsort.dedup import find_exact_duplicates


def test_find_exact_duplicates_groups_identical_content(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "a.txt").write_bytes(b"same content")
    (data_root / "b.txt").write_bytes(b"same content")
    (data_root / "c.txt").write_bytes(b"different")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(data_root))

    groups = find_exact_duplicates(conn)
    assert len(groups) == 1
    group = list(groups.values())[0]
    assert len(group) == 2
    assert all(p.endswith(("a.txt", "b.txt")) for p in group)
    conn.close()
