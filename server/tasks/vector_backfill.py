from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.infra.db.models import VectorDocument


_LATIN_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[_-][a-z0-9]+)*")
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def build_search_text(content_text: str, metadata_json: Mapping[str, Any] | None = None) -> str:
    """Build coarse lexical text for hybrid retrieval fallback and backfill."""
    parts = [content_text]
    if metadata_json:
        parts.extend(_metadata_text_values(metadata_json))
    raw_text = " ".join(str(part) for part in parts if part is not None).lower()
    tokens: list[str] = []
    seen: set[str] = set()
    for token in _LATIN_TOKEN_RE.findall(raw_text):
        if token not in seen:
            seen.add(token)
            tokens.append(token)
    cjk_chars = _CJK_RE.findall(raw_text)
    for index in range(len(cjk_chars) - 1):
        token = "".join(cjk_chars[index : index + 2])
        if token not in seen:
            seen.add(token)
            tokens.append(token)
    return " ".join(tokens)


def rebuild_vector_documents(
    *,
    session: Session,
    rebuild_embeddings: bool = False,
    embedding_client: Any | None = None,
) -> dict[str, Any]:
    """Rebuild vector document metadata that does not require provider calls.

    This skeleton intentionally supports search_text/status repair only. Passing
    rebuild_embeddings=True requires a future embedding client implementation.
    """
    if rebuild_embeddings and embedding_client is None:
        raise ValueError("embedding client is required to rebuild embedding vectors")

    updated = 0
    documents = session.scalars(select(VectorDocument).order_by(VectorDocument.id.asc())).all()
    for document in documents:
        changed = False
        search_text = build_search_text(document.content_text, document.metadata_json)
        if document.search_text != search_text:
            document.search_text = search_text
            changed = True
        if not rebuild_embeddings and document.embedding_vector is None and document.embedding_status != "pending":
            document.embedding_status = "pending"
            document.embedding_error = None
            changed = True
        if changed:
            updated += 1
    session.commit()
    return {
        "updated": updated,
        "embeddingBackfill": "pending_provider" if rebuild_embeddings else "skipped",
    }


def _metadata_text_values(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        values: list[str] = []
        for key, nested in value.items():
            values.append(str(key))
            values.extend(_metadata_text_values(nested))
        return values
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(_metadata_text_values(item))
        return values
    if value is None:
        return []
    return [str(value)]
