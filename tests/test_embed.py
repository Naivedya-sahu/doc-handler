from docsort.embed import embed_text, cosine_similarity


def test_embed_text_is_deterministic():
    v1 = embed_text("Calculus notes linear algebra")
    v2 = embed_text("Calculus notes linear algebra")
    assert v1 == v2


def test_embed_text_similar_text_scores_higher_than_unrelated():
    a = embed_text("BJT bipolar transistor biasing CE CB CC")
    b = embed_text("BJT transistor bias CE amplifier")
    c = embed_text("Fourier transform laplace signals systems")
    assert cosine_similarity(a, b) > cosine_similarity(a, c)


def test_cosine_similarity_identical_vectors_is_one():
    v = embed_text("same text same text")
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-9
