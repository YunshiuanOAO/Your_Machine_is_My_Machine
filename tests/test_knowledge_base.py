from pathlib import Path
import sqlite3

import pytest

from pentestagent.config import Settings


def test_configured_knowledge_base_path_points_to_chroma_store():
    settings = Settings.from_env()
    knowledge_base_path = Path(settings.resolved_knowledge_base_path())

    assert knowledge_base_path.name == "my_knowledge_base"
    assert knowledge_base_path.exists()
    assert (knowledge_base_path / "chroma.sqlite3").exists()


def test_configured_knowledge_base_sqlite_contains_collection():
    settings = Settings.from_env()
    sqlite_path = Path(settings.resolved_knowledge_base_path()) / "chroma.sqlite3"

    with sqlite3.connect(sqlite_path) as connection:
        collection_names = {
            row[0]
            for row in connection.execute("select name from collections").fetchall()
        }

    assert settings.collection_name in collection_names


def test_chroma_collection_can_open_when_optional_dependency_is_installed():
    chromadb = pytest.importorskip("chromadb")

    settings = Settings.from_env()
    knowledge_base_path = Path(settings.resolved_knowledge_base_path())
    if not knowledge_base_path.exists():
        pytest.skip(f"Knowledge base path does not exist: {knowledge_base_path}")

    client = chromadb.PersistentClient(path=str(knowledge_base_path))
    collection = client.get_collection(name=settings.collection_name)

    assert collection.name == settings.collection_name
    assert collection.count() >= 0
