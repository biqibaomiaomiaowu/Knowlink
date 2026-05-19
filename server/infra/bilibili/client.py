from __future__ import annotations

import json
import uuid
from http.cookies import SimpleCookie
from datetime import datetime, timedelta, timezone
from http.cookiejar import CookieJar
from typing import Any, Callable, Protocol
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

from server.domain.services.errors import ServiceError
from server.infra.bilibili.models import BilibiliPart, BilibiliPreview, BilibiliSourceType
from server.infra.bilibili.url import BilibiliUrlKind, parse_bilibili_url


VIEW_API_URL = "https://api.bilibili.com/x/web-interface/view"
PLAYURL_API_URL = "https://api.bilibili.com/x/player/wbi/playurl"
QR_GENERATE_API_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
QR_POLL_API_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"


class BiliTransport(Protocol):
    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        cookies: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...


class UrllibBiliTransport:
    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        cookies: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        query = urlencode(params or {})
        request_url = f"{url}?{query}" if query else url
        headers = {
            "User-Agent": "KnowLink/0.1",
            "Referer": "https://www.bilibili.com/",
        }
        if cookies:
            headers["Cookie"] = "; ".join(f"{key}={value}" for key, value in cookies.items())
        request = Request(request_url, headers=headers)
        cookie_jar = CookieJar()
        opener = build_opener(HTTPCookieProcessor(cookie_jar))
        with opener.open(request, timeout=15) as response:
            payload = response.read().decode("utf-8")
            headers = dict(response.headers.items())
            set_cookie_values = response.headers.get_all("Set-Cookie", [])
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise ServiceError(
                message="Bilibili API returned an invalid JSON payload.",
                error_code="bilibili.metadata_failed",
                status_code=502,
            )
        response_cookies = {cookie.name: cookie.value for cookie in cookie_jar}
        response_cookies.update(_cookies_from_set_cookie_values(set_cookie_values))
        if response_cookies:
            data["cookies"] = response_cookies
        if headers:
            data["headers"] = headers
        return data


class BiliClient:
    def __init__(
        self,
        *,
        transport: BiliTransport | None = None,
        preview_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.transport = transport or UrllibBiliTransport()
        self.preview_id_factory = preview_id_factory or (lambda: f"bili_preview_{uuid.uuid4().hex}")

    def create_qr_session(self) -> dict[str, Any]:
        payload = self._require_success(
            self.transport.get_json(QR_GENERATE_API_URL),
            error_code="bilibili.auth_required",
            message="Failed to create Bilibili QR session.",
        )
        qr_key = str(payload.get("qrcode_key") or "")
        if not qr_key:
            raise ServiceError(
                message="Bilibili QR session response did not include qrcode_key.",
                error_code="bilibili.auth_required",
                status_code=502,
            )
        return {
            "sessionId": qr_key,
            "qrCodeUrl": str(payload.get("url") or ""),
            "status": "pending_scan",
            "expiresAt": datetime.now(timezone.utc) + timedelta(minutes=3),
            "pollPayload": {"qrcode_key": qr_key},
        }

    def refresh_qr_session(
        self,
        session_id: str,
        poll_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        qrcode_key = str((poll_payload or {}).get("qrcode_key") or session_id)
        response = self.transport.get_json(QR_POLL_API_URL, params={"qrcode_key": qrcode_key})
        payload = self._require_success(
            response,
            error_code="bilibili.auth_required",
            message="Failed to refresh Bilibili QR session.",
        )
        status = _qr_status(payload.get("code"))
        return {
            "sessionId": session_id,
            "status": status,
            "qrCodeUrl": None,
            "expiresAt": datetime.now(timezone.utc) + timedelta(minutes=3),
            "pollPayload": {"qrcode_key": qrcode_key},
            "cookies": _extract_response_cookies(response, payload) if status == "confirmed" else None,
        }

    def preview(self, source_url: str, cookies: dict[str, Any]) -> BilibiliPreview:
        parsed = parse_bilibili_url(source_url)
        if parsed.kind not in {BilibiliUrlKind.SINGLE_VIDEO, BilibiliUrlKind.MULTI_P} or not parsed.bvid:
            raise ServiceError(
                message="Only Bilibili single video and multi-P previews are supported in this adapter boundary.",
                error_code="bilibili.unsupported_url",
                status_code=422,
            )
        payload = self._require_success(
            self.transport.get_json(VIEW_API_URL, params={"bvid": parsed.bvid}, cookies=cookies),
            error_code="bilibili.metadata_failed",
            message="Failed to fetch Bilibili video metadata.",
        )
        pages = payload.get("pages")
        if not isinstance(pages, list) or not pages:
            pages = [
                {
                    "cid": payload.get("cid"),
                    "page": 1,
                    "part": payload.get("title") or parsed.bvid,
                    "duration": payload.get("duration") or 0,
                }
            ]

        selected_page_no = parsed.page_no
        page_numbers = {int(page.get("page") or index + 1) for index, page in enumerate(pages)}
        if selected_page_no is not None and selected_page_no not in page_numbers:
            raise ServiceError(
                message="Selected Bilibili page does not exist in metadata.",
                error_code="bilibili.selection_invalid",
                status_code=422,
            )

        source_type = BilibiliSourceType.MULTI_P if len(pages) > 1 else BilibiliSourceType.SINGLE_VIDEO
        default_selection_mode = "current_part" if selected_page_no is not None else "all_parts"
        parts = [
            _part_from_page(page, index=index, selected_page_no=selected_page_no)
            for index, page in enumerate(pages)
        ]
        return BilibiliPreview(
            preview_id=self.preview_id_factory(),
            source_url=source_url,
            source_type=source_type,
            title=str(payload.get("title") or parsed.bvid),
            cover_url=str(payload["pic"]) if payload.get("pic") else None,
            total_parts=len(parts),
            default_selection_mode=default_selection_mode,
            parts=parts,
        )

    def playurl(
        self,
        *,
        bvid: str,
        cid: int,
        cookies: dict[str, Any],
        qn: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"bvid": bvid, "cid": cid, "fnval": 16}
        if qn is not None:
            params["qn"] = qn
        return self._require_success(
            self.transport.get_json(PLAYURL_API_URL, params=params, cookies=cookies),
            error_code="bilibili.playurl_failed",
            message="Failed to fetch Bilibili playurl.",
        )

    @staticmethod
    def _require_success(response: dict[str, Any], *, error_code: str, message: str) -> dict[str, Any]:
        if response.get("code") != 0 or not isinstance(response.get("data"), dict):
            mapped_error = _mapped_bili_error(response, default_error_code=error_code)
            raise ServiceError(
                message=message,
                error_code=mapped_error[0],
                status_code=mapped_error[1],
            )
        return dict(response["data"])


class UnavailableBiliClient:
    def create_qr_session(self) -> dict[str, Any]:
        raise ServiceError(
            message="Bilibili client is not implemented yet.",
            error_code="bilibili.auth_required",
            status_code=401,
        )

    def refresh_qr_session(
        self,
        session_id: str,
        poll_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        raise ServiceError(
            message="Bilibili client is not implemented yet.",
            error_code="bilibili.auth_required",
            status_code=401,
        )

    def preview(self, source_url: str, cookies: dict[str, Any]) -> dict[str, Any]:
        raise ServiceError(
            message="Bilibili client is not implemented yet.",
            error_code="bilibili.metadata_failed",
            status_code=502,
        )

    def playurl(self, *, bvid: str, cid: int, cookies: dict[str, Any], qn: int | None = None) -> dict[str, Any]:
        raise ServiceError(
            message="Bilibili client is not implemented yet.",
            error_code="bilibili.playurl_failed",
            status_code=502,
        )


def _part_from_page(page: Any, *, index: int, selected_page_no: int | None) -> BilibiliPart:
    page_dict = page if isinstance(page, dict) else {}
    page_no = int(page_dict.get("page") or index + 1)
    cid = page_dict.get("cid")
    if cid is None:
        raise ServiceError(
            message="Bilibili metadata page did not include cid.",
            error_code="bilibili.metadata_failed",
            status_code=502,
        )
    selected = page_no == selected_page_no if selected_page_no is not None else True
    return BilibiliPart(
        part_id=f"p{page_no}",
        title=str(page_dict.get("part") or f"P{page_no}"),
        duration_sec=int(page_dict.get("duration") or 0),
        cid=int(cid),
        page_no=page_no,
        selected_by_default=selected,
    )


def _qr_status(code: Any) -> str:
    mapping = {
        0: "confirmed",
        86038: "expired",
        86090: "scanned",
        86101: "pending_scan",
    }
    try:
        numeric_code = int(code)
    except (TypeError, ValueError):
        return "failed"
    return mapping.get(numeric_code, "failed")


def _mapped_bili_error(response: dict[str, Any], *, default_error_code: str) -> tuple[str, int]:
    code = response.get("code")
    message = str(response.get("message") or response.get("msg") or "")
    try:
        numeric_code = int(code)
    except (TypeError, ValueError):
        numeric_code = None
    if numeric_code in {-101, -102, -111} or any(keyword in message for keyword in ("未登录", "登录", "cookie")):
        return ("bilibili.auth_expired", 401)
    if numeric_code in {-403, -10403, 62002, 62012} or any(
        keyword in message
        for keyword in ("权限", "付费", "会员", "地区", "风控", "访问被拒绝", "access denied")
    ):
        return ("bilibili.access_denied", 403)
    return (default_error_code, 502)


def _extract_response_cookies(response: dict[str, Any], payload: dict[str, Any]) -> dict[str, str] | None:
    cookies: dict[str, str] = {}
    for source in (response.get("cookies"), payload.get("cookies")):
        if isinstance(source, dict):
            cookies.update({str(key): str(value) for key, value in source.items()})
    headers = response.get("headers")
    if isinstance(headers, dict):
        cookies.update(_cookies_from_headers(headers))
    return cookies or None


def _cookies_from_headers(headers: dict[str, Any]) -> dict[str, str]:
    raw_values = headers.get("Set-Cookie") or headers.get("set-cookie")
    return _cookies_from_set_cookie_values(raw_values)


def _cookies_from_set_cookie_values(raw_values: Any) -> dict[str, str]:
    if not raw_values:
        return {}
    values = raw_values if isinstance(raw_values, list) else [raw_values]
    cookies: dict[str, str] = {}
    for value in values:
        parsed = SimpleCookie()
        parsed.load(str(value))
        cookies.update({key: morsel.value for key, morsel in parsed.items()})
    return cookies
