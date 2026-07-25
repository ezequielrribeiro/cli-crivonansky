import os
import json
import numpy as np
from commands.complements.crivo_llm_plugin.config import KnowledgeBaseConfig
from commands.complements.crivo_llm_plugin.embedder import embed_query

CHUNKS_FILE = "chunks.json"
EMBEDDINGS_FILE = "embeddings.npy"


def search(
    query: str, kb: KnowledgeBaseConfig, top_k: int = None
) -> list[dict]:
    if top_k is None:
        top_k = kb.default_top_k

    chunks_path = os.path.join(kb.index_dir, CHUNKS_FILE)
    embeddings_path = os.path.join(kb.index_dir, EMBEDDINGS_FILE)

    if not os.path.exists(chunks_path) or not os.path.exists(embeddings_path):
        print(
            "[red]Indice nao encontrado para a base "
            f"'{kb.name}'. Adicione documentos primeiro.[/red]"
        )
        return []

    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    embeddings = np.load(embeddings_path)

    if len(chunks) == 0:
        print("[yellow]Indice vazio.[/yellow]")
        return []

    query_vec = embed_query(query, kb.model_name)

    scores = _cosine_similarity(query_vec, embeddings)
    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for idx in top_indices:
        results.append({
            "id": chunks[idx]["id"],
            "text": chunks[idx]["text"],
            "source": chunks[idx]["source"],
            "score": float(scores[idx]),
        })

    return results


def _cosine_similarity(
    query_vec: np.ndarray, embeddings: np.ndarray
) -> np.ndarray:
    query_norm = query_vec / np.linalg.norm(query_vec)
    embeddings_norm = embeddings / np.linalg.norm(
        embeddings, axis=1, keepdims=True
    )
    scores = np.dot(embeddings_norm, query_norm)
    return scores
