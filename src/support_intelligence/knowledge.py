"""Load and chunk local Markdown and plain-text knowledge documents."""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Union

SUPPORTED_EXTENSIONS = {".md", ".txt"}


@dataclass(frozen=True)
class KnowledgeChunk:
    """A normalized piece of a source document with traceable metadata."""

    chunk_id: str
    source_id: str
    source_path: str
    content_hash: str
    chunk_index: int
    text: str


class KnowledgeIngestionError(ValueError):
    """Raised when a supported knowledge document cannot be decoded."""


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _normalize_text(text: str) -> str:
    """Normalize line endings and trailing whitespace without rewriting content."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).strip()


def _split_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Split text near paragraph or word boundaries, with bounded overlap."""
    chunks = []
    start = 0

    while start < len(text):
        limit = min(start + chunk_size, len(text))
        end = limit

        if limit < len(text):
            boundary_start = start + max(1, chunk_size // 2)
            paragraph_break = text.rfind("\n\n", boundary_start, limit)
            word_break = text.rfind(" ", boundary_start, limit)
            boundary = max(paragraph_break, word_break)
            if boundary > start:
                end = boundary

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        next_start = max(start + 1, end - overlap)
        while next_start < len(text) and text[next_start].isspace():
            next_start += 1
        start = next_start

    return chunks


def ingest_directory(
    directory: Union[str, Path], chunk_size: int = 1000, overlap: int = 100
) -> List[KnowledgeChunk]:
    """Read supported documents recursively and return deterministic text chunks.

    Supported inputs are UTF-8 Markdown (``.md``) and plain text (``.txt``).
    Empty documents are ignored. Symbolic links are excluded. This function
    does not persist content, create embeddings, or send data to a provider.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    root = Path(directory)
    if not root.exists():
        raise FileNotFoundError("Knowledge directory does not exist: {}".format(root))
    if not root.is_dir():
        raise NotADirectoryError("Knowledge path is not a directory: {}".format(root))

    chunks = []
    paths = sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )

    for path in paths:
        relative_path = path.relative_to(root).as_posix()
        raw_content = path.read_bytes()
        try:
            source_text = raw_content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise KnowledgeIngestionError(
                "Knowledge document is not valid UTF-8: {}".format(relative_path)
            ) from exc

        normalized_text = _normalize_text(source_text)
        if not normalized_text:
            continue

        source_id = _sha256(relative_path.encode("utf-8"))
        content_hash = _sha256(raw_content)
        source_chunks = _split_text(normalized_text, chunk_size, overlap)

        for index, chunk_text in enumerate(source_chunks):
            chunk_identity = "{}:{}:{}:{}".format(
                source_id, content_hash, index, chunk_text
            ).encode("utf-8")
            chunks.append(
                KnowledgeChunk(
                    chunk_id=_sha256(chunk_identity),
                    source_id=source_id,
                    source_path=relative_path,
                    content_hash=content_hash,
                    chunk_index=index,
                    text=chunk_text,
                )
            )

    return chunks
