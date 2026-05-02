from __future__ import annotations

import json
import os
import uuid
import urllib.error
import urllib.request
from typing import Any, Protocol, Sequence


_DEFAULT_EMBEDDING_MODEL = "m3e-base"
_DEFAULT_EMBEDDING_TIMEOUT_SEC = 10.0
MappingLike = dict[str, Any]


class EmbeddingClient(Protocol):
    def embed_texts(self, sentences: Sequence[str]) -> list[list[float]]:
        """Return one embedding vector for each input sentence."""


def get_configured_embedding_client() -> EmbeddingClient | None:
    if not _env_bool("KNOWLINK_ENABLE_VIVO_EMBEDDING"):
        return None

    app_key = os.getenv("KNOWLINK_VIVO_APP_KEY", "").strip()
    if not app_key:
        return None

    return VivoEmbeddingClient(
        app_key=app_key,
        base_url=os.getenv("KNOWLINK_VIVO_BASE_URL", "https://api-ai.vivo.com.cn"),
        model=os.getenv("KNOWLINK_VIVO_EMBEDDING_MODEL", _DEFAULT_EMBEDDING_MODEL),
        timeout_sec=_env_float("KNOWLINK_VIVO_EMBEDDING_TIMEOUT_SEC", _DEFAULT_EMBEDDING_TIMEOUT_SEC),
    )


class VivoEmbeddingClient:
    def __init__(
        self,
        *,
        app_key: str,
        base_url: str,
        model: str,
        timeout_sec: float | None = None,
    ) -> None:
        self._app_key = app_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_sec = timeout_sec if timeout_sec is not None else _DEFAULT_EMBEDDING_TIMEOUT_SEC

    def embed_texts(self, sentences: Sequence[str]) -> list[list[float]]:
        clean_sentences: list[str] = []
        for index, sentence in enumerate(sentences):
            text = str(sentence)
            if not text.strip():
                raise ValueError(f"embedding sentence at index {index} is empty")
            clean_sentences.append(text)
        if not clean_sentences:
            return []

        body = {
            "model_name": self._model,
            "sentences": clean_sentences,
        }
        request = urllib.request.Request(
            f"{self._embedding_base_url()}/embedding-model-api/predict/batch?requestId={uuid.uuid4()}",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._app_key}",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout_sec) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"vivo embedding request failed: {exc}") from exc

        embeddings = _parse_embeddings(payload)
        if len(embeddings) != len(clean_sentences):
            raise RuntimeError(
                f"vivo embedding returned {len(embeddings)} vectors for {len(clean_sentences)} sentences"
            )
        return embeddings

    def _embedding_base_url(self) -> str:
        trimmed = self._base_url.rstrip("/")
        if trimmed.endswith("/v1"):
            return trimmed[:-3]
        return trimmed


def _parse_embeddings(payload: dict[str, Any]) -> list[list[float]]:
    if "error" in payload:
        raise RuntimeError(f"vivo embedding failed: {payload['error']}")
    code = _as_int(payload.get("code") or payload.get("error_code") or payload.get("errorCode"))
    if code is not None and code != 0:
        raise RuntimeError(f"vivo embedding failed: {payload}")

    candidates = [
        payload.get("embeddings"),
        payload.get("vectors"),
        _nested(payload, "data", "embeddings"),
        _nested(payload, "data", "vectors"),
        _nested(payload, "result", "embeddings"),
        _nested(payload, "result", "vectors"),
    ]
    data = payload.get("data")
    if isinstance(data, list):
        candidates.append(data)

    for candidate in candidates:
        embeddings = _coerce_embeddings(candidate)
        if embeddings is not None:
            return embeddings
    raise RuntimeError(f"vivo embedding response missing vectors: {payload}")


def _coerce_embeddings(value: Any) -> list[list[float]] | None:
    if not isinstance(value, list):
        return None
    output: list[list[float]] = []
    for item in value:
        vector = item.get("embedding") if isinstance(item, dict) else item
        if not isinstance(vector, list):
            return None
        clean_vector: list[float] = []
        for number in vector:
            try:
                clean_vector.append(float(number))
            except (TypeError, ValueError):
                return None
        output.append(clean_vector)
    return output


def _nested(payload: MappingLike, *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default
