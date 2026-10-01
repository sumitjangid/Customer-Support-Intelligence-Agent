"""Semantic retrieval with remote embeddings and a local JSON vector index."""

import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence

from support_intelligence.knowledge import KnowledgeChunk, ingest_directory

EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIMENSIONS = 768
INDEX_SCHEMA_VERSION = 1
DEFAULT_INDEX_PATH = Path(".local/knowledge-index.json")


class EmbeddingProvider(Protocol):
    """Interface implemented by embedding services and test doubles."""

    model: str

    def embed_document(self, title: str, text: str) -> List[float]:
        """Create an embedding for a source document chunk."""

    def embed_query(self, text: str) -> List[float]:
        """Create an embedding for a retrieval query."""


class RetrievalError(RuntimeError):
    """Raised for invalid indexes, embedding responses, or provider setup."""


class GeminiEmbeddingProvider:
    """Call Gemini Embedding 2 for dummy/prototype text only.

    The embedding request sends its text to Google's Gemini API. Do not use this
    free-tier prototype with confidential or real customer content.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        client: Optional[Any] = None,
        model: str = EMBEDDING_MODEL,
        dimensions: int = EMBEDDING_DIMENSIONS,
    ) -> None:
        self.model = model
        self.dimensions = dimensions
        self._client = client
        if self._client is None:
            key = api_key or os.environ.get("GEMINI_API_KEY")
            if not key:
                raise RetrievalError(
                    "GEMINI_API_KEY is required. Set it in your local .env file."
                )
            try:
                from google import genai
            except ImportError as exc:
                raise RetrievalError(
                    "Gemini SDK is missing. Install the optional gemini dependencies."
                ) from exc
            self._client = genai.Client(api_key=key)

    def _embed(self, prompt: str) -> List[float]:
        try:
            from google.genai import types
        except ImportError as exc:
            raise RetrievalError(
                "Gemini SDK is missing. Install the optional gemini dependencies."
            ) from exc

        response = self._client.models.embed_content(
            model=self.model,
            contents=prompt,
            config=types.EmbedContentConfig(
                output_dimensionality=self.dimensions
            ),
        )
        embeddings = getattr(response, "embeddings", None)
        if not embeddings or not getattr(embeddings[0], "values", None):
            raise RetrievalError("Gemini returned no embedding values.")
        return [float(value) for value in embeddings[0].values]

    def embed_document(self, title: str, text: str) -> List[float]:
        """Embed a chunk using Gemini's recommended search-result format."""
        return self._embed("title: {} | text: {}".format(title or "none", text))

    def embed_query(self, text: str) -> List[float]:
        """Embed a query using Gemini's recommended search-query format."""
        return self._embed("task: search result | query: {}".format(text))


@dataclass(frozen=True)
class IndexedChunk:
    """A local source chunk and its embedding vector."""

    chunk_id: str
    source_id: str
    source_path: str
    content_hash: str
    chunk_index: int
    text: str
    embedding: List[float]

    @classmethod
    def from_chunk(cls, chunk: KnowledgeChunk, embedding: Sequence[float]) -> "IndexedChunk":
        return cls(
            chunk_id=chunk.chunk_id,
            source_id=chunk.source_id,
            source_path=chunk.source_path,
            content_hash=chunk.content_hash,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            embedding=[float(value) for value in embedding],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "source_id": self.source_id,
            "source_path": self.source_path,
            "content_hash": self.content_hash,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "embedding": self.embedding,
        }


@dataclass(frozen=True)
class SearchResult:
    """A matched chunk with its cosine-similarity score and provenance."""

    chunk_id: str
    source_id: str
    source_path: str
    content_hash: str
    chunk_index: int
    text: str
    score: float


class LocalVectorIndex:
    """Persist vectors and their source text to a local JSON file."""

    def __init__(self, path: Path, model: str, records: List[IndexedChunk]) -> None:
        self.path = Path(path)
        self.model = model
        self.records = records

    @classmethod
    def load(cls, path: Path) -> "LocalVectorIndex":
        """Load a local index or fail with a clear error if it is malformed."""
        path = Path(path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != INDEX_SCHEMA_VERSION:
                raise RetrievalError("Unsupported local vector index schema version.")
            records = [IndexedChunk(**record) for record in payload["records"]]
            model = payload["embedding_model"]
        except FileNotFoundError:
            raise
        except RetrievalError:
            raise
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise RetrievalError("Could not read local vector index: {}".format(path)) from exc
        return cls(path=path, model=model, records=records)

    def save(self) -> None:
        """Write the index atomically with user-only file permissions."""
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "embedding_model": self.model,
            "records": [record.to_dict() for record in self.records],
        }
        temporary_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=str(self.path.parent), delete=False
            ) as temporary_file:
                temporary_path = temporary_file.name
                json.dump(payload, temporary_file, ensure_ascii=False)
                temporary_file.write("\n")
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, str(self.path))
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)

    def search(
        self, query_embedding: Sequence[float], top_k: int = 3
    ) -> List[SearchResult]:
        """Rank stored chunks by cosine similarity, highest score first."""
        if top_k < 1:
            raise ValueError("top_k must be greater than zero")
        if not query_embedding:
            raise ValueError("query_embedding must not be empty")

        query = [float(value) for value in query_embedding]
        query_norm = math.sqrt(sum(value * value for value in query))
        if query_norm == 0:
            raise ValueError("query_embedding must not be a zero vector")

        matches = []
        for record in self.records:
            if len(record.embedding) != len(query):
                raise RetrievalError(
                    "Embedding dimensions do not match for {}.".format(record.source_path)
                )
            record_norm = math.sqrt(sum(value * value for value in record.embedding))
            if record_norm == 0:
                continue
            score = sum(
                left * right for left, right in zip(query, record.embedding)
            ) / (query_norm * record_norm)
            matches.append(
                SearchResult(
                    chunk_id=record.chunk_id,
                    source_id=record.source_id,
                    source_path=record.source_path,
                    content_hash=record.content_hash,
                    chunk_index=record.chunk_index,
                    text=record.text,
                    score=score,
                )
            )

        matches.sort(key=lambda result: (-result.score, result.source_path, result.chunk_index))
        return matches[:top_k]


def index_knowledge_directory(
    directory: Path,
    index_path: Path = DEFAULT_INDEX_PATH,
    embedder: Optional[EmbeddingProvider] = None,
    chunk_size: int = 1000,
    overlap: int = 100,
) -> LocalVectorIndex:
    """Embed local knowledge chunks and persist vectors/text in the local index."""
    if embedder is None:
        embedder = GeminiEmbeddingProvider()

    chunks = ingest_directory(directory, chunk_size=chunk_size, overlap=overlap)
    records = []
    for chunk in chunks:
        title = Path(chunk.source_path).stem.replace("_", " ").replace("-", " ")
        vector = embedder.embed_document(title=title, text=chunk.text)
        if not vector or any(not math.isfinite(value) for value in vector):
            raise RetrievalError("Embedding provider returned invalid vector values.")
        records.append(IndexedChunk.from_chunk(chunk, vector))

    index = LocalVectorIndex(Path(index_path), embedder.model, records)
    index.save()
    return index


def search_knowledge(
    query: str,
    index_path: Path = DEFAULT_INDEX_PATH,
    embedder: Optional[EmbeddingProvider] = None,
    top_k: int = 3,
) -> List[SearchResult]:
    """Embed a query and search the local vector index."""
    query = query.strip()
    if not query:
        raise ValueError("query must not be blank")
    if embedder is None:
        embedder = GeminiEmbeddingProvider()

    index = LocalVectorIndex.load(Path(index_path))
    if index.model != embedder.model:
        raise RetrievalError(
            "Index uses embedding model {!r}; configured provider uses {!r}. Rebuild the index.".format(
                index.model, embedder.model
            )
        )
    query_embedding = embedder.embed_query(query)
    if not query_embedding or any(not math.isfinite(value) for value in query_embedding):
        raise RetrievalError("Embedding provider returned invalid query vector values.")
    return index.search(query_embedding, top_k=top_k)
