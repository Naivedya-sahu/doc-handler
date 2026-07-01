import os

from docsort.index import open_index, scan_directory
from docsort.tree import DirectoryTree


def test_from_index_scopes_to_root_not_filesystem_ancestors(tmp_path):
    data_root = tmp_path / "data"
    (data_root / "sub").mkdir(parents=True)
    (data_root / "a.txt").write_bytes(b"1")
    (data_root / "sub" / "b.txt").write_bytes(b"2")

    db_path = tmp_path / "index.db"   # sibling of data_root, not inside it
    conn = open_index(str(db_path))
    scan_directory(conn, str(data_root))

    tree = DirectoryTree.from_index(conn, str(data_root))
    dirs = tree.all_dirs()
    assert str(data_root) in dirs
    assert str(data_root / "sub") in dirs
    assert str(tmp_path) not in dirs          # ancestor above root must not leak in
    conn.close()


def test_child_dirs_returns_direct_subdirectories(tmp_path):
    root = tmp_path / "data"
    (root / "A").mkdir(parents=True)
    (root / "B").mkdir(parents=True)
    (root / "A" / "x.txt").write_bytes(b"1")
    (root / "B" / "y.txt").write_bytes(b"2")   # empty dirs are invisible to a files-only index

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(root))

    tree = DirectoryTree.from_index(conn, str(root))
    assert set(tree.child_dirs(str(root))) == {str(root / "A"), str(root / "B")}
    conn.close()


def test_child_count_counts_files_and_dirs_together(tmp_path):
    """A folder with 1 subdir AND some files of its own is NOT a pass-through wrapper —
    collapsing it would lose real content. Child count must include files, not just
    subdirectory children (a real bug in the pre-DirectoryTree reorg.py logic)."""
    root = tmp_path / "data"
    (root / "Wrapper" / "Inner").mkdir(parents=True)
    (root / "Wrapper" / "loose.txt").write_bytes(b"real content, not just a wrapper")
    (root / "Wrapper" / "Inner" / "deep.txt").write_bytes(b"deep")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(root))

    tree = DirectoryTree.from_index(conn, str(root))
    # Wrapper has 1 subdir (Inner) AND 1 loose file -> child_count is 2, not 1.
    assert tree.child_count(str(root / "Wrapper")) == 2
    conn.close()


def test_descendant_files_is_recursive(tmp_path):
    root = tmp_path / "data"
    (root / "A" / "B").mkdir(parents=True)
    (root / "A" / "x.txt").write_bytes(b"1")
    (root / "A" / "B" / "y.txt").write_bytes(b"2")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(root))

    tree = DirectoryTree.from_index(conn, str(root))
    paths = {p for p, _h in tree.descendant_files(str(root / "A"))}
    assert paths == {str(root / "A" / "x.txt"), str(root / "A" / "B" / "y.txt")}
    conn.close()
