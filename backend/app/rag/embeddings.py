
from functools import lru_cache

MODEL_NAME = "BAAI/bge-small-en-v1.5"


@lru_cache(maxsize=1)
def get_embedding_model():
    # Load PyTorch only when embeddings are actually needed.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    return model.encode(
        texts,
        normalize_embeddings=True
    ).tolist()


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
