import numpy as np
from sentence_transformers import SentenceTransformer


_model_instance = None


def get_model(model_name: str) -> SentenceTransformer:
    global _model_instance
    if _model_instance is None:
        _model_instance = SentenceTransformer(model_name)
    return _model_instance


def embed_texts(texts: list[str], model_name: str) -> np.ndarray:
    model = get_model(model_name)
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    return embeddings


def embed_query(query: str, model_name: str) -> np.ndarray:
    model = get_model(model_name)
    embedding = model.encode([query], convert_to_numpy=True)
    return embedding[0]
