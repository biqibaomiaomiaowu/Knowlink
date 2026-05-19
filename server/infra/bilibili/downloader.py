from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.request import Request, urlopen


class CancelToken(Protocol):
    canceled: bool


class ByteStream(Protocol):
    def iter_bytes(self):
        ...

    def close(self) -> None:
        ...


class UrllibByteStream:
    def __init__(self, url: str, *, cookies: dict[str, Any] | None = None) -> None:
        headers = {
            "User-Agent": "KnowLink/0.1",
            "Referer": "https://www.bilibili.com/",
        }
        if cookies:
            headers["Cookie"] = "; ".join(f"{key}={value}" for key, value in cookies.items())
        self._response = urlopen(Request(url, headers=headers), timeout=30)

    def iter_bytes(self):
        while True:
            chunk = self._response.read(1024 * 256)
            if not chunk:
                break
            yield chunk

    def close(self) -> None:
        self._response.close()


class BiliDownloader:
    def __init__(
        self,
        *,
        stream_factory: Callable[..., ByteStream] | None = None,
    ) -> None:
        self.stream_factory = stream_factory or UrllibByteStream

    def download(
        self,
        url: str,
        output_path: str | Path,
        *,
        cookies: dict[str, Any] | None = None,
        cancel_token: CancelToken | None = None,
        progress_callback: Callable[[dict[str, int]], None] | None = None,
    ) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.stream_factory(url, cookies=cookies)
        downloaded = 0
        try:
            with path.open("wb") as output:
                for chunk in stream.iter_bytes():
                    if cancel_token is not None and cancel_token.canceled:
                        raise DownloadCanceled()
                    if not chunk:
                        continue
                    output.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback is not None:
                        progress_callback({"downloadedBytes": downloaded})
            if cancel_token is not None and cancel_token.canceled:
                raise DownloadCanceled()
            return path
        except Exception:
            path.unlink(missing_ok=True)
            raise
        finally:
            stream.close()


class DownloadCanceled(Exception):
    pass
