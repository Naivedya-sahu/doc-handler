def find_exact_duplicates(conn):
    """Group indexed files by content hash; return {hash: [paths]} for hashes with 2+ files."""
    rows = conn.execute(
        "SELECT hash, path FROM files WHERE hash IS NOT NULL"
    ).fetchall()
    by_hash = {}
    for filehash, path in rows:
        by_hash.setdefault(filehash, []).append(path)
    return {h: paths for h, paths in by_hash.items() if len(paths) >= 2}
