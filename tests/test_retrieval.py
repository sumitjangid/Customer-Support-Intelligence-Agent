import json
from pathlib import Path
from typing import List

import pytest

from support_intelligence.retrieval import (
    EMBEDDING_MODEL,
    GeminiEmbeddingProvider,
    LocalVectorIndex,
    RetrievalError,
    index_knowledge_directory,
    search_knowledge,
)


class FakeEmbedder:
    model = "fake-embedding-model"

    def embed_document(self, title: str, text: str) -> List[float]:
        lowered = (title + " " + text).lower()
        if "shipping" in lowered or "delivery" in lowered:
            return [0.0, 1.0, 0.0]
        if "return" in lowered or "refund" in lowered:
            return [1.0, 0.0, 0.0]
        return [0.0, 0.0, 1.0]

    def embed_query(self, text: str) -> List[float]:
        return self.embed_document("", text)


def test_indexes_locally_and_returns_ranked_source_citations(tmp_path: Path) -> None:
    docs = tmp_path / "knowledge"
    docs.mkdir()
    (docs / "returns.md").write_text("Return and refund policy.", encoding="utf-8")
    (docs / "shipping.txt").write_text("Shipping and delivery policy.", encoding="utf-8")
    index_path = tmp_path / "private" / "vectors.json"

    index = index_knowledge_directory(
        docs, index_path=index_path, embedder=FakeEmbedder()
    )
    results = search_knowledge(
        "How long does delivery take?",
        index_path=index_path,
        embedder=FakeEmbedder(),
        top_k=2,
    )

    assert len(index.records) == 2
    assert results[0].source_path == "shipping.txt"
    assert results[0].score == pytest.approx(1.0)
    assert results[0].text == "Shipping and delivery policy."
    assert results[1].source_path == "returns.md"
    assert index_path.exists()
    assert index_path.stat().st_mode & 0o777 == 0o600
    persisted = json.loads(index_path.read_text(encoding="utf-8"))
    assert persisted["records"][0]["text"]


def test_index_can_be_reloaded(tmp_path: Path) -> None:
    docs = tmp_path / "knowledge"
    docs.mkdir()
    (docs / "returns.md").write_text("Refund policy.", encoding="utf-8")
    index_path = tmp_path / "index.json"
    index_knowledge_directory(docs, index_path=index_path, embedder=FakeEmbedder())

    loaded = LocalVectorIndex.load(index_path)

    assert loaded.model == FakeEmbedder.model
    assert len(loaded.records) == 1


def test_search_refuses_different_embedding_model(tmp_path: Path) -> None:
    docs = tmp_path / "knowledge"
    docs.mkdir()
    (docs / "returns.md").write_text("Refund policy.", encoding="utf-8")
    index_path = tmp_path / "index.json"
    index_knowledge_directory(docs, index_path=index_path, embedder=FakeEmbedder())

    class OtherEmbedder(FakeEmbedder):
        model = "different-model"

    with pytest.raises(RetrievalError, match="Rebuild the index"):
        search_knowledge("refund", index_path=index_path, embedder=OtherEmbedder())


def test_search_rejects_blank_query(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="blank"):
        search_knowledge("  ", index_path=tmp_path / "index.json", embedder=FakeEmbedder())


def test_search_rejects_non_positive_top_k(tmp_path: Path) -> None:
    index = LocalVectorIndex(tmp_path / "index.json", "fake", [])

    with pytest.raises(ValueError, match="top_k"):
        index.search([1.0], top_k=0)


def test_invalid_index_is_reported(tmp_path: Path) -> None:
    bad_index = tmp_path / "bad.json"
    bad_index.write_text("not json", encoding="utf-8")

    with pytest.raises(RetrievalError, match="Could not read"):
        LocalVectorIndex.load(bad_index)


def test_gemini_provider_formats_query_and_document_for_retrieval() -> None:
    from google.genai import types

    captured = {}

    class FakeModels:
        def embed_content(self, **kwargs):
            captured.update(kwargs)
            return types.EmbedContentResponse(
                embeddings=[types.ContentEmbedding(values=[0.1] * 768)]
            )

    class FakeClient:
        models = FakeModels()

    provider = GeminiEmbeddingProvider(client=FakeClient())
    document_embedding = provider.embed_document("Returns", "Refunds take time.")
    assert len(document_embedding) == 768
    assert provider.model == EMBEDDING_MODEL
    assert captured["contents"] == "title: Returns | text: Refunds take time."

    query_embedding = provider.embed_query("When will I get a refund?")
    assert len(query_embedding) == 768
    assert captured["contents"] == "task: search result | query: When will I get a refund?"
