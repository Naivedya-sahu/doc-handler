import os


class DirectoryTree:
    """Tree structure derived once from the ground-truth index, scoped to `root`.

    Owns all parent/child path derivation so callers (dedup's subtree-duplicate
    detection, reorg's thin-chain detection, vendor's dump detection) stop
    reconstructing it independently from flat path strings via os.path.dirname()/
    startswith() — the source of two real scoping bugs found doing that by hand.
    """

    def __init__(self, root, dirs, dir_children, dir_files):
        self.root = root
        self._dirs = dirs
        self._dir_children = dir_children
        self._dir_files = dir_files

    @classmethod
    def from_index(cls, conn, root):
        root_prefix = root + os.sep
        rows = conn.execute("SELECT path, hash FROM files").fetchall()
        dirs = set()
        dir_files = {}
        for path, filehash in rows:
            if not (path == root or path.startswith(root_prefix)):
                continue
            d = os.path.dirname(path)
            dir_files.setdefault(d, []).append((path, filehash))
            cur = d
            while cur == root or cur.startswith(root_prefix):
                if cur in dirs:
                    break
                dirs.add(cur)
                parent = os.path.dirname(cur)
                if parent == cur:
                    break
                cur = parent
        dir_children = {}
        for d in dirs:
            parent = os.path.dirname(d)
            dir_children.setdefault(parent, set()).add(d)
        return cls(root, dirs, dir_children, dir_files)

    def all_dirs(self):
        return set(self._dirs)

    def child_dirs(self, path):
        return sorted(self._dir_children.get(path, []))

    def files(self, path):
        """Direct files in `path` (not recursive), as (path, hash) pairs."""
        return list(self._dir_files.get(path, []))

    def child_count(self, path):
        """Total direct children — subdirectories AND files — for thin-chain
        detection. A folder with a subdir and its own loose files is not a
        pure pass-through wrapper even though it has only one subdirectory."""
        return len(self._dir_children.get(path, [])) + len(self._dir_files.get(path, []))

    def descendant_files(self, path):
        """All files anywhere under `path`, recursive, as (path, hash) pairs."""
        prefix = path + os.sep
        out = []
        for d, files in self._dir_files.items():
            if d == path or d.startswith(prefix):
                out.extend(files)
        return out
