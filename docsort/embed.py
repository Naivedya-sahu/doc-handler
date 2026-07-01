import hashlib
import math
import re

DIMS = 128
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _bucket(token):
    return int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % DIMS


def embed_text(text):
    """Deterministic fixed-size vector via the hashing trick (stdlib-only bag-of-words)."""
    vec = [0.0] * DIMS
    for token in _TOKEN_RE.findall(text.lower()):
        vec[_bucket(token)] += 1.0
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return tuple(vec)


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def centroid(vectors):
    if not vectors:
        return tuple([0.0] * DIMS)
    n = len(vectors)
    dims = len(vectors[0])
    return tuple(sum(v[i] for v in vectors) / n for i in range(dims))


def classify_by_centroid(vector, centroids):
    """Return (best_label, best_score) — nearest centroid by cosine similarity."""
    best_label, best_score = None, -1.0
    for label, c in centroids.items():
        score = cosine_similarity(vector, c)
        if score > best_score:
            best_label, best_score = label, score
    return best_label, best_score
