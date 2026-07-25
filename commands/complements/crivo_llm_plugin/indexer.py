import json
import os
import fnmatch
import numpy as np
from commands.complements.crivo_llm_plugin.config import KnowledgeBaseConfig
from commands.complements.crivo_llm_plugin.embedder import embed_texts

CHUNKS_FILE = "chunks.json"
EMBEDDINGS_FILE = "embeddings.npy"

SUPPORTED_EXTENSIONS = {
    ".md", ".txt", ".py", ".json", ".yaml", ".yml", ".toml",
    ".ini", ".cfg", ".csv", ".html", ".js", ".ts", ".css",
    ".sql", ".sh", ".bat", ".ps1", ".php", ".xml",
}

PDF_EXTENSIONS = {".pdf"}


def _ensure_index_dir(kb: KnowledgeBaseConfig):
    os.makedirs(kb.index_dir, exist_ok=True)


def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _read_pdf(path: str) -> str:
    try:
        import fitz
    except ImportError:
        print(
            "[red]PyMuPDF (fitz) nao instalado. "
            "Instale com: pip install PyMuPDF[/red]"
        )
        return ""
    doc = fitz.open(path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end >= len(words):
            break
        start += chunk_size - overlap
    return chunks


def _is_supported_file(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in SUPPORTED_EXTENSIONS or ext in PDF_EXTENSIONS


def _is_pdf(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in PDF_EXTENSIONS


def _should_exclude(file_path: str, exclude_patterns: list[str]) -> bool:
    if not exclude_patterns:
        return False
    abs_path = os.path.abspath(file_path).replace("\\", "/")
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(abs_path, pattern):
            return True
    return False


def _load_existing_index(index_dir: str):
    chunks_path = os.path.join(index_dir, CHUNKS_FILE)
    embeddings_path = os.path.join(index_dir, EMBEDDINGS_FILE)
    chunks = []
    embeddings = None
    if os.path.exists(chunks_path):
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
    if os.path.exists(embeddings_path):
        embeddings = np.load(embeddings_path)
    return chunks, embeddings


def _save_index(index_dir: str, chunks: list[dict], embeddings: np.ndarray):
    chunks_path = os.path.join(index_dir, CHUNKS_FILE)
    embeddings_path = os.path.join(index_dir, EMBEDDINGS_FILE)
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    np.save(embeddings_path, embeddings)


def _get_known_sources(kb: KnowledgeBaseConfig) -> set[str]:
    if not os.path.exists(kb.index_dir):
        return set()
    chunks_path = os.path.join(kb.index_dir, CHUNKS_FILE)
    if not os.path.exists(chunks_path):
        return set()
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    return {c["source"] for c in chunks}


def _read_document(path: str) -> str:
    if _is_pdf(path):
        return _read_pdf(path)
    return _read_text_file(path)


def index_files(file_paths: list[str], kb: KnowledgeBaseConfig):
    _ensure_index_dir(kb)

    existing_chunks, existing_embeddings = _load_existing_index(kb.index_dir)

    if existing_chunks and existing_embeddings is not None:
        next_id = max(c["id"] for c in existing_chunks) + 1
    else:
        existing_chunks = []
        existing_embeddings = np.empty((0, 0), dtype=np.float32)
        next_id = 0

    new_chunks = []
    all_texts = []

    for file_path in file_paths:
        if not os.path.exists(file_path):
            print(f"[red]Arquivo nao encontrado: {file_path}[/red]")
            continue
        if _should_exclude(file_path, kb.exclude_patterns):
            print(f"  [yellow]Excluido por padrao: {file_path}[/yellow]")
            continue
        if not _is_supported_file(file_path):
            print(
                f"[yellow]Formato nao suportado, ignorando: "
                f"{file_path}[/yellow]"
            )
            continue

        text = _read_document(file_path)
        if not text.strip():
            print(f"  [yellow]Documento vazio: {file_path}[/yellow]")
            continue

        chunk_texts = _chunk_text(
            text, kb.chunk_size, kb.chunk_overlap
        )

        for chunk_text in chunk_texts:
            new_chunks.append({
                "id": next_id,
                "text": chunk_text,
                "source": os.path.abspath(file_path),
            })
            all_texts.append(chunk_text)
            next_id += 1

        print(f"  {len(chunk_texts)} chunks de {file_path}")

    if not all_texts:
        print("[yellow]Nenhum chunk novo para indexar.[/yellow]")
        return

    print(
        f"Gerando embeddings para {len(all_texts)} chunks "
        f"(modelo: {kb.model_name})..."
    )
    new_embeddings = embed_texts(all_texts, kb.model_name)

    if existing_embeddings.shape[0] == 0:
        combined_embeddings = new_embeddings
    else:
        combined_embeddings = np.vstack(
            [existing_embeddings, new_embeddings]
        )

    combined_chunks = existing_chunks + new_chunks

    _save_index(kb.index_dir, combined_chunks, combined_embeddings)

    print(
        f"[green]Indexados {len(new_chunks)} novos chunks. "
        f"Total: {len(combined_chunks)} chunks.[/green]"
    )


def index_directory(dir_path: str, kb: KnowledgeBaseConfig):
    if not os.path.isdir(dir_path):
        print(f"[red]Diretorio nao encontrado: {dir_path}[/red]")
        return

    known_sources = _get_known_sources(kb)

    files_to_index = []
    for root, _, files in os.walk(dir_path):
        for file in files:
            full_path = os.path.join(root, file)
            abs_path = os.path.abspath(full_path)
            if abs_path in known_sources:
                continue
            if _should_exclude(full_path, kb.exclude_patterns):
                continue
            if _is_supported_file(full_path):
                files_to_index.append(full_path)

    if not files_to_index:
        print(
            "[yellow]Nenhum arquivo novo para indexar "
            "no diretorio.[/yellow]"
        )
        return

    print(
        f"Encontrados {len(files_to_index)} arquivos novos "
        f"para indexar..."
    )
    index_files(files_to_index, kb)


def list_indexed(kb: KnowledgeBaseConfig) -> list[dict]:
    chunks_path = os.path.join(kb.index_dir, CHUNKS_FILE)
    if not os.path.exists(chunks_path):
        return []
    with open(chunks_path, "r", encoding="utf-8") as f:
        return json.load(f)
