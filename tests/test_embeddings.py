import pytest

from app.rag.embeddings import EMBED_DIM, embed_texts


@pytest.mark.slow
def test_embed_texts_shape():
    vecs = embed_texts(["python backend engineer", "data scientist"])
    assert len(vecs) == 2
    assert len(vecs[0]) == EMBED_DIM == 384
