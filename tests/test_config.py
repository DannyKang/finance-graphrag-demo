"""Tests for config.yaml loading and Settings construction."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


def _write_yaml(tmp_path: Path, content: dict) -> Path:
    p = tmp_path / "config.yaml"
    with open(p, "w") as f:
        yaml.dump(content, f)
    return p


class TestYamlSettingsSource:
    def test_loads_graph_store(self, tmp_path):
        from tiger_etf.config import YamlSettingsSource, Settings

        config_path = _write_yaml(tmp_path, {
            "graph_store": "neptune-graph://test-graph-id",
            "vector_store": "aoss://test-endpoint",
        })

        with patch("tiger_etf.config._find_config_yaml", return_value=config_path):
            source = YamlSettingsSource(Settings)
            data = source()

        assert data["graph_store"] == "neptune-graph://test-graph-id"
        assert data["vector_store"] == "aoss://test-endpoint"

    def test_flattens_graphrag_section(self, tmp_path):
        from tiger_etf.config import YamlSettingsSource, Settings

        config_path = _write_yaml(tmp_path, {
            "graphrag": {
                "extraction_llm": "us.anthropic.claude-sonnet-4-20250514-v1:0",
                "response_llm": "us.anthropic.claude-sonnet-4-20250514-v1:0",
                "embedding_model": "amazon.titan-embed-text-v2:0",
                "aws_region": "us-west-2",
                "extraction_num_workers": 2,
                "extraction_num_threads_per_worker": 4,
                "enable_cache": False,
            }
        })

        with patch("tiger_etf.config._find_config_yaml", return_value=config_path):
            source = YamlSettingsSource(Settings)
            data = source()

        assert data["graphrag_extraction_llm"] == "us.anthropic.claude-sonnet-4-20250514-v1:0"
        assert data["graphrag_aws_region"] == "us-west-2"
        assert data["graphrag_extraction_num_workers"] == 2
        assert data["graphrag_extraction_num_threads_per_worker"] == 4
        assert data["graphrag_enable_cache"] is False

    def test_flattens_scraper_section(self, tmp_path):
        from tiger_etf.config import YamlSettingsSource, Settings

        config_path = _write_yaml(tmp_path, {
            "scraper": {
                "base_url": "https://example.com",
                "request_delay": 2.5,
                "max_retries": 5,
            }
        })

        with patch("tiger_etf.config._find_config_yaml", return_value=config_path):
            source = YamlSettingsSource(Settings)
            data = source()

        assert data["base_url"] == "https://example.com"
        assert data["request_delay"] == 2.5
        assert data["max_retries"] == 5

    def test_missing_yaml_returns_empty(self, tmp_path):
        from tiger_etf.config import YamlSettingsSource, Settings

        missing_path = tmp_path / "nonexistent.yaml"
        with patch("tiger_etf.config._find_config_yaml", return_value=missing_path):
            source = YamlSettingsSource(Settings)
            data = source()

        assert data == {}


class TestSettingsPriority:
    def test_env_var_overrides_yaml(self, tmp_path):
        """Environment variables should take precedence over config.yaml."""
        from tiger_etf.config import Settings

        config_path = _write_yaml(tmp_path, {
            "graph_store": "neptune-graph://yaml-graph-id",
        })

        env_override = "neptune-graph://env-override-id"
        with patch("tiger_etf.config._find_config_yaml", return_value=config_path):
            with patch.dict(os.environ, {"GRAPH_STORE": env_override}):
                s = Settings(_env_file=None)

        assert s.graph_store == env_override

    def test_yaml_overrides_default(self, tmp_path):
        """config.yaml should take precedence over field defaults."""
        from tiger_etf.config import Settings

        config_path = _write_yaml(tmp_path, {
            "graph_store": "neptune-graph://from-yaml",
        })

        with patch("tiger_etf.config._find_config_yaml", return_value=config_path):
            # Clear env vars that could interfere
            env_clear = {k: "" for k in ["GRAPH_STORE", "VECTOR_STORE"]}
            with patch.dict(os.environ, env_clear, clear=False):
                # Remove the env vars entirely
                for k in env_clear:
                    os.environ.pop(k, None)
                s = Settings(_env_file=None)

        assert s.graph_store == "neptune-graph://from-yaml"


class TestSettingsWithDotEnv:
    def test_current_env_has_neptune(self):
        """The current .env file should have Neptune/OpenSearch values."""
        from tiger_etf.config import Settings

        # Use a dummy yaml to avoid config.yaml interference
        with patch("tiger_etf.config._find_config_yaml", return_value=Path("/nonexistent")):
            s = Settings()

        assert s.graph_store.startswith("neptune-db://") or s.graph_store.startswith("neptune-graph://")
        assert "aoss.amazonaws.com" in s.vector_store

    def test_current_env_has_new_llm(self):
        """The current .env should have updated LLM model names."""
        from tiger_etf.config import Settings

        with patch("tiger_etf.config._find_config_yaml", return_value=Path("/nonexistent")):
            s = Settings()

        assert "anthropic" in s.graphrag_extraction_llm
        assert "titan" in s.graphrag_embedding_model


class TestParseGraphStoreUri:
    def test_neptune_analytics(self):
        from tiger_etf.graphrag.query import _parse_graph_store_uri

        store_type, identifier = _parse_graph_store_uri("neptune-graph://g-abc123")
        assert store_type == "analytics"
        assert identifier == "g-abc123"

    def test_neptune_database(self):
        from tiger_etf.graphrag.query import _parse_graph_store_uri

        store_type, identifier = _parse_graph_store_uri(
            "neptune-db://my-cluster.cluster-xxx.us-east-1.neptune.amazonaws.com"
        )
        assert store_type == "database"
        assert "neptune.amazonaws.com" in identifier

    def test_neptune_database_https(self):
        from tiger_etf.graphrag.query import _parse_graph_store_uri

        store_type, identifier = _parse_graph_store_uri(
            "https://my-cluster.cluster-xxx.us-east-1.neptune.amazonaws.com:8182"
        )
        assert store_type == "database"
        assert identifier == "my-cluster.cluster-xxx.us-east-1.neptune.amazonaws.com"

    def test_unsupported_uri_raises(self):
        from tiger_etf.graphrag.query import _parse_graph_store_uri

        with pytest.raises(ValueError, match="Unsupported"):
            _parse_graph_store_uri("bolt://localhost:7687")
