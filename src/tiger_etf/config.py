from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql://user:password@localhost:5432/mirae_etf"
    base_url: str = "https://investments.miraeasset.com/tigeretf"
    request_delay: float = 1.0
    max_retries: int = 3
    log_level: str = "INFO"
    data_dir: Path = Path("./data")

    # GraphRAG
    graph_store: str = "bolt://neo4j:password@localhost:7689"
    vector_store: str = "postgresql://graphrag:graphragpass@localhost:5433/graphrag_db"
    graphrag_extraction_llm: str = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    graphrag_response_llm: str = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    graphrag_embedding_model: str = "cohere.embed-multilingual-v3"

    @property
    def pdfs_dir(self) -> Path:
        d = self.data_dir / "pdfs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def excel_dir(self) -> Path:
        d = self.data_dir / "excel"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def logs_dir(self) -> Path:
        d = self.data_dir / "logs"
        d.mkdir(parents=True, exist_ok=True)
        return d


settings = Settings()
