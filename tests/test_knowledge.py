from pathlib import Path

import pytest

from support_intelligence.knowledge import (
    KnowledgeIngestionError,
    ingest_directory,
)


def test_ingests_markdown_and_text_with_source_metadata(tmp_path: Path) -> None:
    (tmp_path / "faq.md").write_text("# FAQ\n\nReturns are accepted.", encoding="utf-8")
    nested = tmp_path / "policies"
    nested.mkdir()
    (nested / "shipping.txt").write_text("Shipping takes five days.", encoding="utf-8")
    (tmp_path / "ignored.csv").write_text("not ingested", encoding="utf-8")

    chunks = ingest_directory(tmp_path)

    assert [chunk.source_path for chunk in chunks] == ["faq.md", "policies/shipping.txt"]
    assert chunks[0].text == "# FAQ\n\nReturns are accepted."
    assert chunks[0].chunk_index == 0
    assert len(chunks[0].source_id) == 64
    assert len(chunks[0].content_hash) == 64
    assert len(chunks[0].chunk_id) == 64


def test_chunks_long_content_with_bounded_overlap(tmp_path: Path) -> None:
    (tmp_path / "long.txt").write_text("alpha beta gamma delta epsilon zeta", encoding="utf-8")

    chunks = ingest_directory(tmp_path, chunk_size=20, overlap=5)

    assert len(chunks) > 1
    assert all(len(chunk.text) <= 20 for chunk in chunks)
    assert all(chunk.chunk_index == index for index, chunk in enumerate(chunks))
    assert "gamma" in chunks[0].text
    assert "gamma" in chunks[1].text


def test_ingestion_is_repeatable_for_unchanged_sources(tmp_path: Path) -> None:
    (tmp_path / "faq.md").write_text("A stable answer.", encoding="utf-8")

    first = ingest_directory(tmp_path)
    second = ingest_directory(tmp_path)

    assert first == second


def test_ignores_empty_documents_and_unsupported_files(tmp_path: Path) -> None:
    (tmp_path / "empty.md").write_text(" \n ", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"not text")

    assert ingest_directory(tmp_path) == []


def test_invalid_utf8_raises_actionable_error(tmp_path: Path) -> None:
    (tmp_path / "broken.txt").write_bytes(b"bad\xfftext")

    with pytest.raises(KnowledgeIngestionError, match="broken.txt"):
        ingest_directory(tmp_path)


def test_missing_directory_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ingest_directory(tmp_path / "missing")


@pytest.mark.parametrize(
    "chunk_size,overlap",
    [(0, 0), (10, -1), (10, 10)],
)
def test_rejects_invalid_chunk_settings(
    tmp_path: Path, chunk_size: int, overlap: int
) -> None:
    with pytest.raises(ValueError):
        ingest_directory(tmp_path, chunk_size=chunk_size, overlap=overlap)