"""Build and query a local vector index using Gemini embeddings."""

import argparse
import json
import os
from pathlib import Path
from typing import List, Optional

from support_intelligence.retrieval import (
    DEFAULT_INDEX_PATH,
    GeminiEmbeddingProvider,
    RetrievalError,
    index_knowledge_directory,
    search_knowledge,
)


def _load_local_env() -> None:
    """Load ignored .env configuration when the optional dependency is installed."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create and query a local semantic index with Gemini embeddings."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="embed the local knowledge directory")
    index_parser.add_argument("directory", nargs="?", type=Path, default=Path("knowledge_base"))
    index_parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    index_parser.add_argument("--chunk-size", type=int, default=1000)
    index_parser.add_argument("--overlap", type=int, default=100)

    search_parser = subparsers.add_parser("search", help="search the existing local index")
    search_parser.add_argument("query")
    search_parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    search_parser.add_argument("--top-k", type=int, default=3)

    args = parser.parse_args(argv)
    _load_local_env()
    if not os.environ.get("GEMINI_API_KEY"):
        parser.error("GEMINI_API_KEY is missing; configure it in your ignored .env file")

    try:
        embedder = GeminiEmbeddingProvider()
        if args.command == "index":
            index = index_knowledge_directory(
                args.directory,
                index_path=args.index_path,
                embedder=embedder,
                chunk_size=args.chunk_size,
                overlap=args.overlap,
            )
            output = {
                "indexed_chunks": len(index.records),
                "embedding_model": index.model,
                "index_path": str(index.path),
            }
        else:
            results = search_knowledge(
                args.query,
                index_path=args.index_path,
                embedder=embedder,
                top_k=args.top_k,
            )
            output = {
                "query": args.query,
                "results": [
                    {
                        "source_path": result.source_path,
                        "chunk_index": result.chunk_index,
                        "score": round(result.score, 4),
                        "text": result.text,
                    }
                    for result in results
                ],
            }
    except (OSError, ValueError, RetrievalError) as exc:
        parser.error(str(exc))

    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
