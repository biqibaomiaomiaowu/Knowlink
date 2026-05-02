from __future__ import annotations

import json
import math
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
import urllib.error
import urllib.parse
import urllib.request


_DEFAULT_ASR_TIMEOUT_SEC = 30.0
_DEFAULT_ASR_POLL_INTERVAL_SEC = 3.0
_DEFAULT_ASR_MAX_WAIT_SEC = 600.0
_DEFAULT_ASR_ENGINE_ID = "fileasrrecorder"
_DEFAULT_ASR_SLICE_SIZE = 5 * 1024 * 1024


@dataclass(frozen=True)
class AsrSegment:
    text: str
    start_sec: int
    end_sec: int


class AsrClient(Protocol):
    def transcribe(self, file_path: str | Path) -> list[AsrSegment]:
        """Return timestamped transcript segments for a local media file."""


def get_configured_asr_client() -> AsrClient | None:
    if not _env_bool("KNOWLINK_ENABLE_VIVO_ASR"):
        return None

    app_key = os.getenv("KNOWLINK_VIVO_APP_KEY", "").strip()
    if not app_key:
        return None

    app_id = os.getenv("KNOWLINK_VIVO_APP_ID", "").strip()
    return VivoLongAsrClient(
        app_key=app_key,
        base_url=os.getenv("KNOWLINK_VIVO_BASE_URL", "https://api-ai.vivo.com.cn"),
        user_id=os.getenv("KNOWLINK_VIVO_ASR_USER_ID", "").strip() or _default_user_id(app_id),
        engine_id=os.getenv("KNOWLINK_VIVO_ASR_ENGINE_ID", _DEFAULT_ASR_ENGINE_ID),
        client_version=os.getenv("KNOWLINK_VIVO_ASR_CLIENT_VERSION", "unknown"),
        package=os.getenv("KNOWLINK_VIVO_ASR_PACKAGE", "unknown"),
        timeout_sec=_env_float("KNOWLINK_VIVO_ASR_TIMEOUT_SEC", _DEFAULT_ASR_TIMEOUT_SEC),
        poll_interval_sec=_env_float("KNOWLINK_VIVO_ASR_POLL_INTERVAL_SEC", _DEFAULT_ASR_POLL_INTERVAL_SEC),
        max_wait_sec=_env_float("KNOWLINK_VIVO_ASR_MAX_WAIT_SEC", _DEFAULT_ASR_MAX_WAIT_SEC),
    )


class VivoLongAsrClient:
    def __init__(
        self,
        *,
        app_key: str,
        base_url: str,
        user_id: str,
        engine_id: str,
        client_version: str,
        package: str,
        timeout_sec: float | None = None,
        poll_interval_sec: float | None = None,
        max_wait_sec: float | None = None,
    ) -> None:
        self._app_key = app_key
        self._base_url = base_url.rstrip("/")
        self._user_id = user_id
        self._engine_id = engine_id
        self._client_version = client_version
        self._package = package
        self._timeout_sec = timeout_sec if timeout_sec is not None else _DEFAULT_ASR_TIMEOUT_SEC
        self._poll_interval_sec = poll_interval_sec if poll_interval_sec is not None else _DEFAULT_ASR_POLL_INTERVAL_SEC
        self._max_wait_sec = max_wait_sec if max_wait_sec is not None else _DEFAULT_ASR_MAX_WAIT_SEC

    def transcribe(self, file_path: str | Path) -> list[AsrSegment]:
        path = Path(file_path)
        if not path.is_file():
            raise RuntimeError(f"asr input file not found: {path}")

        session_id = str(uuid.uuid4())
        audio_bytes = path.read_bytes()
        slice_num = max(1, math.ceil(len(audio_bytes) / _DEFAULT_ASR_SLICE_SIZE))
        if slice_num > 100:
            raise RuntimeError("vivo asr input exceeds 100 slices")

        audio_id = self._create_audio(session_id=session_id, audio_type=_audio_type(path), slice_num=slice_num)
        self._upload_slices(audio_id=audio_id, session_id=session_id, audio_bytes=audio_bytes)
        task_id = self._run_task(audio_id=audio_id, session_id=session_id)
        self._wait_until_done(task_id=task_id, session_id=session_id)
        return self._query_result(task_id=task_id, session_id=session_id)

    def _create_audio(self, *, session_id: str, audio_type: str, slice_num: int) -> str:
        payload = {
            "audio_type": audio_type,
            "x-sessionId": session_id,
            "slice_num": slice_num,
        }
        response = self._post_json("/lasr/create", payload)
        audio_id = _response_data(response).get("audio_id")
        if not isinstance(audio_id, str) or not audio_id:
            raise RuntimeError(f"vivo asr create response missing audio_id: {response}")
        return audio_id

    def _upload_slices(self, *, audio_id: str, session_id: str, audio_bytes: bytes) -> None:
        for slice_index, offset in enumerate(range(0, len(audio_bytes), _DEFAULT_ASR_SLICE_SIZE)):
            chunk = audio_bytes[offset : offset + _DEFAULT_ASR_SLICE_SIZE]
            extra_query = {
                "audio_id": audio_id,
                "x-sessionId": session_id,
                "slice_index": str(slice_index),
            }
            self._post_multipart("/lasr/upload", extra_query=extra_query, file_bytes=chunk)

    def _run_task(self, *, audio_id: str, session_id: str) -> str:
        response = self._post_json(
            os.getenv("KNOWLINK_VIVO_ASR_RUN_PATH", "/lasr/run"),
            {
                "audio_id": audio_id,
                "x-sessionId": session_id,
            },
        )
        task_id = _response_data(response).get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise RuntimeError(f"vivo asr run response missing task_id: {response}")
        return task_id

    def _wait_until_done(self, *, task_id: str, session_id: str) -> None:
        deadline = time.monotonic() + self._max_wait_sec
        last_progress = None
        while time.monotonic() <= deadline:
            response = self._post_json(
                "/lasr/progress",
                {
                    "task_id": task_id,
                    "x-sessionId": session_id,
                },
            )
            progress = _as_int(_response_data(response).get("progress"))
            if progress is not None:
                last_progress = progress
            if progress is not None and progress >= 100:
                return
            time.sleep(self._poll_interval_sec)

        raise RuntimeError(f"vivo asr timed out waiting for result; last_progress={last_progress}")

    def _query_result(self, *, task_id: str, session_id: str) -> list[AsrSegment]:
        response = self._post_json(
            "/lasr/result",
            {
                "task_id": task_id,
                "x-sessionId": session_id,
            },
        )
        result = _response_data(response).get("result")
        if not isinstance(result, list):
            raise RuntimeError(f"vivo asr result response missing result list: {response}")

        segments: list[AsrSegment] = []
        for item in result:
            if not isinstance(item, dict):
                continue
            text = item.get("onebest")
            start_ms = _as_int(item.get("bg"))
            end_ms = _as_int(item.get("ed"))
            if not isinstance(text, str) or start_ms is None or end_ms is None or end_ms <= start_ms:
                continue
            start_sec = max(0, math.ceil(start_ms / 1000))
            end_sec = max(start_sec + 1, math.ceil(end_ms / 1000))
            segments.append(
                AsrSegment(
                    text=text.strip(),
                    start_sec=start_sec,
                    end_sec=end_sec,
                )
            )
        return [segment for segment in segments if segment.text]

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self._url(path),
            data=body,
            headers={
                "Authorization": f"Bearer {self._app_key}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            method="POST",
        )
        return self._open_json(request)

    def _post_multipart(self, path: str, *, extra_query: dict[str, str], file_bytes: bytes) -> dict[str, Any]:
        boundary = f"----KnowLink{uuid.uuid4().hex}"
        body = _multipart_body(boundary=boundary, field_name="file", filename="audio.slice", file_bytes=file_bytes)
        request = urllib.request.Request(
            self._url(path, extra_query=extra_query),
            data=body,
            headers={
                "Authorization": f"Bearer {self._app_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        return self._open_json(request)

    def _open_json(self, request: urllib.request.Request) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_sec) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"vivo asr http {exc.code}: {body}") from exc
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"vivo asr request failed: {exc}") from exc

        code = _as_int(payload.get("code"))
        if code is not None and code != 0:
            raise RuntimeError(f"vivo asr failed: {payload}")
        return payload

    def _url(self, path: str, *, extra_query: dict[str, str] | None = None) -> str:
        query = {
            "client_version": self._client_version,
            "package": self._package,
            "user_id": self._user_id,
            "system_time": str(int(time.time() * 1000)),
            "engineid": self._engine_id,
            "requestId": str(uuid.uuid4()),
        }
        if extra_query:
            query.update(extra_query)
        return f"{self._api_base_url()}{path}?{urllib.parse.urlencode(query)}"

    def _api_base_url(self) -> str:
        trimmed = self._base_url.rstrip("/")
        if trimmed.endswith("/v1"):
            return trimmed[:-3]
        return trimmed


def _response_data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"vivo asr response missing data: {payload}")
    return data


def _multipart_body(*, boundary: str, field_name: str, filename: str, file_bytes: bytes) -> bytes:
    parts = [
        f"--{boundary}\r\n".encode("utf-8"),
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8"),
        b"Content-Type: application/octet-stream\r\n\r\n",
        file_bytes,
        b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    return b"".join(parts)


def _audio_type(path: Path) -> str:
    return "pcm" if path.suffix.lower() == ".pcm" else "auto"


def _default_user_id(app_id: str) -> str:
    normalized = "".join(char for char in app_id.lower() if char.isalnum())
    if not normalized:
        normalized = "knowlinkdemo"
    return (normalized + "0" * 32)[:32]


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
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
