from docsort.embed import embed_text, cosine_similarity, centroid, classify_by_centroid


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


def test_centroid_averages_vectors():
    a = embed_text("bjt transistor")
    b = embed_text("bjt bias")
    c = centroid([a, b])
    assert len(c) == len(a)
    unrelated = embed_text("fourier laplace signals")
    assert cosine_similarity(c, a) > cosine_similarity(unrelated, a)


def test_classify_by_centroid_picks_nearest_label():
    centroids = {
        "04BJT": centroid([embed_text("bjt transistor biasing ce cb cc")]),
        "09SNS": centroid([embed_text("fourier laplace transform signals systems")]),
    }
    label, score = classify_by_centroid(embed_text("bjt bias amplifier ce"), centroids)
    assert label == "04BJT"
    assert 0.0 <= score <= 1.0
