import json
import os


CONFIG_FILE = "crivo_llm_conf.json"

DEFAULT_EXCLUDE_PATTERNS = [
    "*/vendor/*", "*/node_modules/*", "*/.git/*",
    "*/cache/*", "*/logs/*", "*/tmp/*", "*/backup/*",
    "*/dist/*", "*/build/*", "*/tests/*", "*/test/*",
    "__pycache__",
]

DEFAULT_CONFIG = {
    "index_base_dir": "./crivo_llm_index",
    "model_name": "all-MiniLM-L6-v2",
    "chunk_size": 500,
    "chunk_overlap": 50,
    "default_top_k": 5,
    "default_kb": "default",
    "exclude_patterns": DEFAULT_EXCLUDE_PATTERNS,
}


class KnowledgeBaseConfig:
    def __init__(self, name: str, data: dict, global_config: "Config"):
        self.name = name
        self.document_dirs: list[str] = data.get(
            "document_dirs", global_config.document_dirs
        )
        self.exclude_patterns: list[str] = data.get(
            "exclude_patterns", global_config.exclude_patterns
        )
        self.index_dir: str = os.path.join(
            global_config.index_base_dir, name
        )
        self.model_name: str = data.get(
            "model_name", global_config.model_name
        )
        self.chunk_size: int = data.get(
            "chunk_size", global_config.chunk_size
        )
        self.chunk_overlap: int = data.get(
            "chunk_overlap", global_config.chunk_overlap
        )
        self.default_top_k: int = data.get(
            "default_top_k", global_config.default_top_k
        )


class Config:
    def __init__(self, data: dict):
        self.index_base_dir: str = data.get(
            "index_base_dir", DEFAULT_CONFIG["index_base_dir"]
        )
        self.model_name: str = data.get(
            "model_name", DEFAULT_CONFIG["model_name"]
        )
        self.chunk_size: int = data.get(
            "chunk_size", DEFAULT_CONFIG["chunk_size"]
        )
        self.chunk_overlap: int = data.get(
            "chunk_overlap", DEFAULT_CONFIG["chunk_overlap"]
        )
        self.default_top_k: int = data.get(
            "default_top_k", DEFAULT_CONFIG["default_top_k"]
        )
        self.default_kb: str = data.get(
            "default_kb", DEFAULT_CONFIG["default_kb"]
        )
        self.exclude_patterns: list[str] = data.get(
            "exclude_patterns", DEFAULT_CONFIG["exclude_patterns"]
        )
        self.document_dirs: list[str] = data.get(
            "document_dirs", ["./rag_docs"]
        )

        kbs_data = data.get("knowledge_bases", {})
        self.knowledge_bases: dict[str, KnowledgeBaseConfig] = {}

        if not kbs_data:
            self.knowledge_bases["default"] = KnowledgeBaseConfig(
                "default",
                {"document_dirs": self.document_dirs},
                self,
            )
        else:
            for name, kb_data in kbs_data.items():
                self.knowledge_bases[name] = KnowledgeBaseConfig(
                    name, kb_data, self
                )

    def get_kb(self, name: str = None) -> KnowledgeBaseConfig | None:
        if name is None:
            name = self.default_kb
        kb = self.knowledge_bases.get(name)
        if kb is None:
            print(
                f"[red]Base de conhecimento '{name}' nao encontrada.[/red]"
            )
            return None
        return kb

    def list_kbs(self) -> list[str]:
        return list(self.knowledge_bases.keys())


def load_config() -> Config:
    if not os.path.exists(CONFIG_FILE):
        print(
            f"[yellow]Arquivo {CONFIG_FILE} nao encontrado. "
            "Usando configuracao padrao.[/yellow]"
        )
        return Config(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Config(data)
    except (json.JSONDecodeError, IOError) as e:
        print(
            f"[red]Erro ao ler {CONFIG_FILE}: {e}. "
            "Usando padrao.[/red]"
        )
        return Config(DEFAULT_CONFIG)
