from __future__ import annotations

from dataclasses import dataclass
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Protocol
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from io import BytesIO

from server.parsers.base import BaseParser, ParserIssue, ParserResult, clean_text


_DEFAULT_MINERU_BASE_URL = "https://mineru.net"
_DEFAULT_MINERU_MODEL_VERSION = "vlm"
_DEFAULT_MINERU_TIMEOUT_SEC = 30.0
_DEFAULT_MINERU_POLL_INTERVAL_SEC = 3.0
_DEFAULT_MINERU_MAX_WAIT_SEC = 180.0
_DEFAULT_MINERU_MAX_RETRIES = 2
_DONE_STATE = "done"
_FAILED_STATE = "failed"


class MineruClient(Protocol):
    def parse_file(self, file_path: str | Path, *, resource_type: str) -> ParserResult:
        """Parse a local learning resource via MinerU and return a normalized document."""


class MineruApiError(RuntimeError):
    """Raised when MinerU Precision API returns an unsuccessful result."""


@dataclass(frozen=True)
class MineruPrecisionOptions:
    base_url: str = _DEFAULT_MINERU_BASE_URL
    model_version: str = _DEFAULT_MINERU_MODEL_VERSION
    language: str = "ch"
    is_ocr: bool = True
    enable_formula: bool = True
    enable_table: bool = True
    timeout_sec: float = _DEFAULT_MINERU_TIMEOUT_SEC
    poll_interval_sec: float = _DEFAULT_MINERU_POLL_INTERVAL_SEC
    max_wait_sec: float = _DEFAULT_MINERU_MAX_WAIT_SEC
    max_retries: int = _DEFAULT_MINERU_MAX_RETRIES
    download_use_proxy: bool = False


def get_configured_mineru_client() -> MineruClient | None:
    if not _env_bool("KNOWLINK_ENABLE_MINERU"):
        return None

    token = os.getenv("KNOWLINK_MINERU_TOKEN", "").strip()
    if not token:
        return None

    return MineruPrecisionClient(
        token=token,
        options=MineruPrecisionOptions(
            base_url=os.getenv("KNOWLINK_MINERU_BASE_URL", _DEFAULT_MINERU_BASE_URL),
            model_version=os.getenv("KNOWLINK_MINERU_MODEL_VERSION", _DEFAULT_MINERU_MODEL_VERSION),
            language=os.getenv("KNOWLINK_MINERU_LANGUAGE", "ch"),
            is_ocr=_env_bool("KNOWLINK_MINERU_IS_OCR", default=True),
            enable_formula=_env_bool("KNOWLINK_MINERU_ENABLE_FORMULA", default=True),
            enable_table=_env_bool("KNOWLINK_MINERU_ENABLE_TABLE", default=True),
            timeout_sec=_env_float("KNOWLINK_MINERU_TIMEOUT_SEC", _DEFAULT_MINERU_TIMEOUT_SEC),
            poll_interval_sec=_env_float("KNOWLINK_MINERU_POLL_INTERVAL_SEC", _DEFAULT_MINERU_POLL_INTERVAL_SEC),
            max_wait_sec=_env_float("KNOWLINK_MINERU_MAX_WAIT_SEC", _DEFAULT_MINERU_MAX_WAIT_SEC),
            max_retries=_env_int("KNOWLINK_MINERU_MAX_RETRIES", _DEFAULT_MINERU_MAX_RETRIES),
            download_use_proxy=_env_bool("KNOWLINK_MINERU_DOWNLOAD_USE_PROXY", default=False),
        ),
    )


class MineruPrecisionClient:
    def __init__(self, *, token: str, options: MineruPrecisionOptions | None = None) -> None:
        self._token = token
        self._options = options or MineruPrecisionOptions()
        self._base_url = self._options.base_url.rstrip("/")

    def parse_file(self, file_path: str | Path, *, resource_type: str) -> ParserResult:
        path = Path(file_path)
        data_id = _data_id(path, resource_type)
        batch_id, upload_url = self._request_upload_url(path, data_id=data_id)
        self._upload_file(upload_url, path)
        full_zip_url = self._wait_for_zip_url(batch_id, data_id=data_id, file_name=path.name)
        archive_bytes = self._download(full_zip_url)
        return mineru_archive_to_result(resource_type=resource_type, archive_bytes=archive_bytes)

    def _request_upload_url(self, path: Path, *, data_id: str) -> tuple[str, str]:
        payload: dict[str, Any] = {
            "files": [
                {
                    "name": path.name,
                    "is_ocr": self._options.is_ocr,
                    "data_id": data_id,
                }
            ],
            "model_version": self._options.model_version,
            "language": self._options.language,
            "enable_formula": self._options.enable_formula,
            "enable_table": self._options.enable_table,
        }
        response = self._request_json("/api/v4/file-urls/batch", method="POST", payload=payload)
        data = _successful_data(response)
        batch_id = str(data.get("batch_id") or "").strip()
        file_urls = data.get("file_urls")
        if not batch_id or not isinstance(file_urls, list) or not file_urls:
            raise MineruApiError("mineru upload-url response is missing batch_id or file_urls")
        return batch_id, str(file_urls[0])

    def _upload_file(self, upload_url: str, path: Path) -> None:
        last_error = ""
        for attempt in range(self._max_attempts()):
            try:
                status, body = _put_file_without_content_type(upload_url, path, timeout_sec=self._options.timeout_sec)
            except OSError as exc:
                last_error = str(exc)
            else:
                if 200 <= status < 300:
                    return
                last_error = f"http {status}: {_safe_api_message(body)}"
            self._sleep_before_retry(attempt)
        raise MineruApiError(f"mineru file upload failed: {last_error}")

    def _wait_for_zip_url(self, batch_id: str, *, data_id: str, file_name: str) -> str:
        deadline = time.monotonic() + self._options.max_wait_sec
        last_state = ""
        while time.monotonic() <= deadline:
            response = self._request_json(f"/api/v4/extract-results/batch/{batch_id}", method="GET")
            data = _successful_data(response)
            result = _select_extract_result(data.get("extract_result"), data_id=data_id, file_name=file_name)
            state = str(result.get("state") or "").strip()
            last_state = state or last_state
            if state == _DONE_STATE:
                full_zip_url = str(result.get("full_zip_url") or "").strip()
                if not full_zip_url:
                    raise MineruApiError("mineru extract result is done but full_zip_url is missing")
                return full_zip_url
            if state == _FAILED_STATE:
                err_msg = str(result.get("err_msg") or "extract failed")
                raise MineruApiError(f"mineru extract failed: {err_msg}")
            time.sleep(self._options.poll_interval_sec)

        raise MineruApiError(f"mineru extract timed out, last state: {last_state or 'unknown'}")

    def _download(self, url: str) -> bytes:
        last_error = ""
        for attempt in range(self._max_attempts()):
            try:
                return _get_url(
                    url,
                    timeout_sec=self._options.timeout_sec,
                    use_proxy=self._options.download_use_proxy,
                )
            except (OSError, urllib.error.URLError) as exc:
                last_error = str(exc)
            self._sleep_before_retry(attempt)
        raise MineruApiError(f"mineru zip download failed: {last_error}")

    def _request_json(
        self,
        path: str,
        *,
        method: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "Accept": "*/*",
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self._options.timeout_sec) as response:
                body = response.read().decode("utf-8")
                status = int(getattr(response, "status", 200))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise MineruApiError(f"mineru api request failed with http {exc.code}: {_safe_api_message(body)}") from exc
        except (OSError, urllib.error.URLError) as exc:
            raise MineruApiError(f"mineru api request failed: {exc}") from exc

        if status < 200 or status >= 300:
            raise MineruApiError(f"mineru api request failed with http {status}: {_safe_api_message(body)}")
        try:
            payload_json = json.loads(body)
        except json.JSONDecodeError as exc:
            raise MineruApiError("mineru api returned non-json response") from exc
        if not isinstance(payload_json, dict):
            raise MineruApiError("mineru api returned unexpected json response")
        return payload_json

    def _max_attempts(self) -> int:
        return max(1, self._options.max_retries + 1)

    def _sleep_before_retry(self, attempt: int) -> None:
        if attempt >= self._max_attempts() - 1:
            return
        time.sleep(min(1.0 + attempt, 3.0))


def try_parse_with_mineru(
    client: MineruClient | None,
    file_path: str | Path,
    *,
    resource_type: str,
) -> tuple[ParserResult | None, list[ParserIssue]]:
    if client is None:
        return None, []

    try:
        result = client.parse_file(file_path, resource_type=resource_type)
    except Exception as exc:
        return (
            None,
            [
                ParserIssue(
                    code=f"{resource_type}.mineru_failed",
                    message="MinerU precision parsing failed; parser will fall back to the local pipeline.",
                    details={"error": str(exc)},
                )
            ],
        )

    return result, []


def prepend_issues(result: ParserResult, issues: list[ParserIssue]) -> ParserResult:
    if not issues:
        return result
    return ParserResult(
        resource_type=result.resource_type,
        status=result.status,
        normalized_document=result.normalized_document,
        issues=issues + result.issues,
    )


def mineru_archive_to_result(*, resource_type: str, archive_bytes: bytes) -> ParserResult:
    issues: list[ParserIssue] = []
    content_items, full_markdown = _read_mineru_archive(archive_bytes)
    segments = _segments_from_content_list(resource_type, content_items)
    if not segments and full_markdown:
        issues.append(
            ParserIssue(
                code=f"{resource_type}.mineru_content_list_missing",
                message="MinerU archive has no readable content_list.json; normalized from full.md instead.",
            )
        )
        segments = [_segment_from_markdown(resource_type, full_markdown)]

    parser = _MineruResultParser(resource_type)
    if not segments:
        return parser._failed(
            ParserIssue(
                code=f"{resource_type}.mineru_empty",
                message="MinerU archive contained no clean Markdown or structured content.",
            )
        )
    return parser._succeeded(segments, issues)


class _MineruResultParser(BaseParser):
    def __init__(self, resource_type: str) -> None:
        self.resource_type = resource_type


def _read_mineru_archive(archive_bytes: bytes) -> tuple[list[dict[str, Any]], str]:
    try:
        with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
            full_markdown = _read_first_text(archive, lambda name: Path(name).name == "full.md")
            content_text = _read_first_text(
                archive,
                lambda name: Path(name).name.endswith("_content_list.json")
                and not Path(name).name.endswith("_content_list_v2.json"),
            )
    except zipfile.BadZipFile as exc:
        raise MineruApiError("mineru archive is not a valid zip file") from exc

    if not content_text:
        return [], full_markdown
    try:
        parsed = json.loads(content_text)
    except json.JSONDecodeError as exc:
        raise MineruApiError("mineru content_list.json is not valid json") from exc
    if not isinstance(parsed, list):
        raise MineruApiError("mineru content_list.json must be a list")
    return [item for item in parsed if isinstance(item, dict)], full_markdown


def _read_first_text(archive: zipfile.ZipFile, predicate: Any) -> str:
    for name in archive.namelist():
        if predicate(name):
            return archive.read(name).decode("utf-8", errors="replace")
    return ""


def _segments_from_content_list(resource_type: str, items: list[dict[str, Any]]) -> list[dict[str, object]]:
    segments: list[dict[str, object]] = []
    section_path: list[str] = []
    for item in items:
        segment_text = _content_item_text(item)
        if not segment_text:
            continue

        item_type = str(item.get("type") or "").strip()
        segment_type = _content_item_segment_type(resource_type, item_type)
        if segment_type is None:
            continue

        text_level = _safe_int(item.get("text_level"))
        if resource_type == "docx" and item_type == "text" and text_level is not None and text_level > 0:
            section_path = section_path[: max(text_level - 1, 0)]
            section_path.append(segment_text)

        order_no = len(segments) + 1
        segment: dict[str, object] = {
            "segmentKey": _segment_key(resource_type, order_no, item, segment_type),
            "segmentType": segment_type,
            "orderNo": order_no,
            "textContent": segment_text,
        }
        segment.update(_location(resource_type, item, section_path))
        segments.append(segment)
    return segments


def _segment_from_markdown(resource_type: str, markdown: str) -> dict[str, object]:
    segment: dict[str, object] = {
        "segmentKey": f"mineru-{resource_type}-full-md",
        "segmentType": _default_text_segment_type(resource_type),
        "orderNo": 1,
        "textContent": markdown,
    }
    segment.update(_location(resource_type, {}, []))
    return segment


def _content_item_text(item: dict[str, Any]) -> str:
    item_type = str(item.get("type") or "").strip()
    if item_type in {"header", "footer", "page_number", "aside_text", "page_footnote", "seal"}:
        return ""
    if item_type == "table":
        return clean_text(
            "\n".join(
                _string_or_joined_list(item.get(key))
                for key in ("table_caption", "table_body", "table_footnote", "text")
                if _string_or_joined_list(item.get(key))
            )
        )
    if item_type in {"image", "chart"}:
        return clean_text(
            "\n".join(
                _string_or_joined_list(item.get(key))
                for key in ("image_caption", "chart_caption", "content", "image_footnote", "chart_footnote")
                if _string_or_joined_list(item.get(key))
            )
        )
    if item_type == "code":
        return clean_text(
            "\n".join(
                _string_or_joined_list(item.get(key))
                for key in ("code_caption", "code_body", "code_footnote", "text")
                if _string_or_joined_list(item.get(key))
            )
        )
    return clean_text(_string_or_joined_list(item.get("text")) or _string_or_joined_list(item.get("content")))


def _content_item_segment_type(resource_type: str, item_type: str) -> str | None:
    if item_type in {"image", "chart"}:
        return "image_caption"
    if item_type == "equation":
        return "formula"
    if item_type == "table":
        return "docx_block_text" if resource_type == "docx" else "ocr_text"
    if item_type in {"text", "list", "code"}:
        return _default_text_segment_type(resource_type)
    return None


def _default_text_segment_type(resource_type: str) -> str:
    if resource_type == "pptx":
        return "ppt_slide_text"
    if resource_type == "docx":
        return "docx_block_text"
    return "pdf_page_text"


def _location(resource_type: str, item: dict[str, Any], section_path: list[str]) -> dict[str, object]:
    if resource_type == "pptx":
        return {"slideNo": _page_no(item)}
    if resource_type == "docx":
        return {"sectionPath": list(section_path)}
    return {"pageNo": _page_no(item)}


def _page_no(item: dict[str, Any]) -> int:
    page_idx = _safe_int(item.get("page_idx"))
    return page_idx + 1 if page_idx is not None and page_idx >= 0 else 1


def _segment_key(resource_type: str, order_no: int, item: dict[str, Any], segment_type: str) -> str:
    if resource_type == "pptx":
        location = f"s{_page_no(item)}"
    elif resource_type == "docx":
        location = f"b{order_no}"
    else:
        location = f"p{_page_no(item)}"
    short_type = {
        "pdf_page_text": "text",
        "ppt_slide_text": "text",
        "docx_block_text": "text",
        "ocr_text": "ocr",
        "formula": "formula",
        "image_caption": "image",
    }.get(segment_type, segment_type)
    return f"mineru-{resource_type}-{location}-{short_type}-{order_no}"


def _select_extract_result(extract_result: Any, *, data_id: str, file_name: str) -> dict[str, Any]:
    if isinstance(extract_result, dict):
        return extract_result
    if not isinstance(extract_result, list) or not extract_result:
        raise MineruApiError("mineru batch result is missing extract_result")
    dict_results = [item for item in extract_result if isinstance(item, dict)]
    for item in dict_results:
        if item.get("data_id") == data_id:
            return item
    for item in dict_results:
        if item.get("file_name") == file_name:
            return item
    if len(dict_results) == 1:
        return dict_results[0]
    raise MineruApiError("mineru batch result cannot identify the current file")


def _successful_data(payload: dict[str, Any]) -> dict[str, Any]:
    if int(payload.get("code", 0) or 0) != 0:
        raise MineruApiError(f"mineru api failed: {payload.get('msg') or payload.get('code')}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise MineruApiError("mineru api response is missing data")
    return data


def _string_or_joined_list(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if item is not None)
    return ""


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _data_id(path: Path, resource_type: str) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    suffix = uuid.uuid4().hex[:8]
    stem = re.sub(r"[^a-zA-Z0-9_.-]+", "-", path.stem)[:40].strip("-.") or "file"
    return f"knowlink-{resource_type}-{stem}-{digest}-{suffix}"[:128]


def _safe_api_message(body: str) -> str:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body[:300]
    if isinstance(payload, dict):
        return str(payload.get("msg") or payload.get("message") or payload.get("code") or "")[:300]
    return str(payload)[:300]


def _put_file_without_content_type(url: str, path: Path, *, timeout_sec: float) -> tuple[int, str]:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise MineruApiError("mineru upload url is invalid")

    body = path.read_bytes()
    connection, proxy_url = _connection_for_url(parsed, timeout_sec=timeout_sec)
    target = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    try:
        connection.request(
            "PUT",
            url if proxy_url is not None and parsed.scheme == "http" else target,
            body=body,
            headers={
                "Content-Length": str(len(body)),
            },
        )
        response = connection.getresponse()
        response_body = response.read().decode("utf-8", errors="replace")
        return int(response.status), response_body
    finally:
        connection.close()


def _get_url(url: str, *, timeout_sec: float, use_proxy: bool) -> bytes:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise MineruApiError("mineru download url is invalid")

    connection, proxy_url = _connection_for_url(parsed, timeout_sec=timeout_sec, use_proxy=use_proxy)
    target = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    try:
        connection.request(
            "GET",
            url if proxy_url is not None and parsed.scheme == "http" else target,
            headers={"Accept": "*/*"},
        )
        response = connection.getresponse()
        body = response.read()
        if int(response.status) < 200 or int(response.status) >= 300:
            raise MineruApiError(
                f"mineru zip download failed with http {response.status}: "
                f"{_safe_api_message(body.decode('utf-8', errors='replace'))}"
            )
        return body
    finally:
        connection.close()


def _connection_for_url(
    parsed: urllib.parse.SplitResult,
    *,
    timeout_sec: float,
    use_proxy: bool = True,
) -> tuple[http.client.HTTPConnection | http.client.HTTPSConnection, str | None]:
    proxy_url = _proxy_url_for(parsed) if use_proxy else None
    if proxy_url is not None:
        return _proxy_connection(proxy_url, parsed, timeout_sec=timeout_sec), proxy_url
    connection_class = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    return connection_class(parsed.netloc, timeout=timeout_sec), None


def _proxy_url_for(parsed: urllib.parse.SplitResult) -> str | None:
    if parsed.hostname and urllib.request.proxy_bypass(parsed.hostname):
        return None
    proxies = urllib.request.getproxies()
    return proxies.get(parsed.scheme) or proxies.get("all")


def _proxy_connection(
    proxy_url: str,
    target: urllib.parse.SplitResult,
    *,
    timeout_sec: float,
) -> http.client.HTTPConnection | http.client.HTTPSConnection:
    parsed_proxy = urllib.parse.urlsplit(proxy_url)
    if parsed_proxy.scheme not in {"http", "https"} or not parsed_proxy.hostname:
        raise MineruApiError("mineru upload proxy url is invalid")

    proxy_netloc = parsed_proxy.hostname
    if parsed_proxy.port is not None:
        proxy_netloc = f"{proxy_netloc}:{parsed_proxy.port}"
    connection_class = http.client.HTTPSConnection if parsed_proxy.scheme == "https" else http.client.HTTPConnection
    connection = connection_class(proxy_netloc, timeout=timeout_sec)
    if target.scheme == "https":
        connection.set_tunnel(target.netloc)
    return connection


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default
