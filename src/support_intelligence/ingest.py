"""Command-line entry point for inspecting local knowledge ingestion."""

import argparse
import json
from pathlib import Path
from typing import List, Optional

from support_intelligence.knowledge import ingest_directory


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read and chunk UTF-8 Markdown and plain-text knowledge files."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=Path("knowledge_base"),
        help="directory to scan recursively (default: knowledge_base)",
    )
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--overlap", type=int, default=100)
    args = parser.parse_args(argv)

    try:
        chunks = ingest_directory(
            args.directory, chunk_size=args.chunk_size, overlap=args.overlap
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    summary = {
        "document_count": len({chunk.source_path for chunk in chunks}),
        "chunk_count": len(chunks),
        "sources": sorted({chunk.source_path for chunk in chunks}),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
