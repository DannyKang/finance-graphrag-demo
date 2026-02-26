"""Configuration loader: env vars > .env file > config.yaml > defaults."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Tuple, Type

import yaml
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


def _find_config_yaml() -> Path:
    """Walk up from this file to find config.yaml in the project root."""
    current = Path(__file__).resolve().parent
    for _ in range(5):
        candidate = current / "config.yaml"
        if candidate.exists():
            return candidate
        current = current.parent
    return Path("config.yaml")


class YamlSettingsSource(PydanticBaseSettingsSource):
    """Custom pydantic-settings source that reads from config.yaml.

    Loaded with lower priority than env vars and .env file.
    """

    def __init__(self, settings_cls: Type[BaseSettings]):
        super().__init__(settings_cls)
        self._yaml_data = self._load()

    def _load(self) -> dict[str, Any]:
        path = _find_config_yaml()
        if not path.exists():
            return {}
        with open(path) as f:
            raw = yaml.safe_load(f) or {}

        flat: dict[str, Any] = {}
        # Top-level scalars
        for key in ("graph_store", "graph_store_reader", "vector_store", "database_url", "database_url_reader", "log_level", "data_dir"):
            if key in raw:
                flat[key] = raw[key]

        # graphrag section → flat keys
        graphrag = raw.get("graphrag", {})
        if graphrag:
            mapping = {
                "extraction_llm": "graphrag_extraction_llm",
                "response_llm": "graphrag_response_llm",
                "embedding_model": "graphrag_embedding_model",
                "aws_region": "graphrag_aws_region",
                "extraction_num_workers": "graphrag_extraction_num_workers",
                "extraction_num_threads_per_worker": "graphrag_extraction_num_threads_per_worker",
                "build_num_workers": "graphrag_build_num_workers",
                "batch_writes_enabled": "graphrag_batch_writes_enabled",
                "enable_cache": "graphrag_enable_cache",
            }
            for yaml_key, flat_key in mapping.items():
                if yaml_key in graphrag:
                    flat[flat_key] = graphrag[yaml_key]

        # scraper section → flat keys
        scraper = raw.get("scraper", {})
        if scraper:
            if "base_url" in scraper:
                flat["base_url"] = scraper["base_url"]
            if "request_delay" in scraper:
                flat["request_delay"] = scraper["request_delay"]
            if "max_retries" in scraper:
                flat["max_retries"] = scraper["max_retries"]

        return flat

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> Tuple[Any, str, bool]:
        value = self._yaml_data.get(field_name)
        return value, field_name, False

    def __call__(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        for field_name, field_info in self.settings_cls.model_fields.items():
            value, _, _ = self.get_field_value(field_info, field_name)
            if value is not None:
                d[field_name] = value
        return d


class Settings(BaseSettings):
    """Project settings.

    Priority (highest to lowest):
      1. Environment variables
      2. .env file
      3. config.yaml
      4. Field defaults
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql://user:password@localhost:5432/mirae_etf"
    database_url_reader: str = ""
    base_url: str = "https://investments.miraeasset.com/tigeretf"
    request_delay: float = 1.0
    max_retries: int = 3
    log_level: str = "INFO"
    data_dir: Path = Path("./data")

    # GraphRAG stores (write endpoint for indexing, read endpoint for queries)
    # 실제 값은 .env 파일에서 설정
    graph_store: str = ""
    graph_store_reader: str = ""
    vector_store: str = ""

    # GraphRAG LLM (AWS Bedrock model IDs)
    graphrag_extraction_llm: str = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    graphrag_response_llm: str = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    graphrag_embedding_model: str = "amazon.titan-embed-text-v2:0"

    # GraphRAG runtime
    graphrag_aws_region: str = "ap-northeast-2"
    graphrag_extraction_num_workers: int = 1
    graphrag_extraction_num_threads_per_worker: int = 8
    graphrag_build_num_workers: int = 1
    graphrag_batch_writes_enabled: bool = False
    graphrag_enable_cache: bool = True

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ):
        """Insert YamlSettingsSource between dotenv and defaults."""
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlSettingsSource(settings_cls),
            file_secret_settings,
        )

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
