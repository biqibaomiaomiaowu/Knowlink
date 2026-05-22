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
from server.infra.bilibili.url import BilibiliUrlKind, ParsedBilibiliUrl, parse_bilibili_url


VIEW_API_URL = "https://api.bilibili.com/x/web-interface/view"
PLAYURL_API_URL = "https://api.bilibili.com/x/player/wbi/playurl"
COLLECTION_API_URL = "https://api.bilibili.com/x/polymer/web-space/seasons_archives_list"
BANGUMI_SEASON_API_URL = "https://api.bilibili.com/pgc/view/web/season"
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
        try:
            parsed = parse_bilibili_url(source_url)
        except ValueError as exc:
            raise ServiceError(
                message="Unsupported Bilibili URL.",
                error_code="bilibili.unsupported_url",
                status_code=422,
            ) from exc
        if parsed.kind in {BilibiliUrlKind.SINGLE_VIDEO, BilibiliUrlKind.MULTI_P} and parsed.bvid:
            return self._preview_video(parsed, source_url, cookies)
        if parsed.kind == BilibiliUrlKind.COLLECTION:
            return self._preview_collection(parsed, source_url, cookies)
        if parsed.kind == BilibiliUrlKind.BANGUMI:
            return self._preview_bangumi(parsed, source_url, cookies)
        raise ServiceError(
            message="Unsupported Bilibili URL.",
            error_code="bilibili.unsupported_url",
            status_code=422,
        )

    def _preview_video(
        self,
        parsed: ParsedBilibiliUrl,
        source_url: str,
        cookies: dict[str, Any],
    ) -> BilibiliPreview:
        payload = self._require_success(
            self.transport.get_json(VIEW_API_URL, params={"bvid": parsed.bvid}, cookies=cookies),
            error_code="bilibili.metadata_failed",
            message="Failed to fetch Bilibili video metadata.",
        )
        pages = payload.get("pages")
        if not isinstance(pages, list) or not pages:
            duration = payload.get("duration")
            pages = [
                {
                    "cid": payload.get("cid"),
                    "page": 1,
                    "part": payload.get("title") or parsed.bvid,
                    "duration": 0 if duration is None else duration,
                }
            ]

        selected_page_no = parsed.page_no
        page_numbers = {
            _metadata_int(
                index + 1
                if not isinstance(page, dict) or page.get("page") is None
                else page.get("page"),
                field_name="page",
            )
            for index, page in enumerate(pages)
        }
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

    def _preview_collection(
        self,
        parsed: ParsedBilibiliUrl,
        source_url: str,
        cookies: dict[str, Any],
    ) -> BilibiliPreview:
        if not parsed.collection_owner_mid or not parsed.collection_id:
            raise ServiceError(
                message="Unsupported Bilibili URL.",
                error_code="bilibili.unsupported_url",
                status_code=422,
            )
        payload = self._fetch_collection_page(parsed, page_num=1, cookies=cookies)
        archives = _collection_archives(payload)
        page_count = _collection_page_count(payload["page"]) if "page" in payload else 1
        for page_num in range(2, page_count + 1):
            page_payload = self._fetch_collection_page(parsed, page_num=page_num, cookies=cookies)
            archives.extend(_collection_archives(page_payload))
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        parts: list[BilibiliPart] = []
        for index, item in enumerate(archives, start=1):
            parts.extend(self._collection_parts_from_archive(parsed.collection_id, item, index, cookies))
        return BilibiliPreview(
            preview_id=self.preview_id_factory(),
            source_url=source_url,
            source_type=BilibiliSourceType.COLLECTION,
            title=str(meta.get("name") or payload.get("title") or parsed.collection_id),
            cover_url=str(meta["cover"]) if meta.get("cover") else None,
            total_parts=len(parts),
            default_selection_mode="all_parts",
            parts=parts,
        )

    def _fetch_collection_page(
        self,
        parsed: ParsedBilibiliUrl,
        *,
        page_num: int,
        cookies: dict[str, Any],
    ) -> dict[str, Any]:
        return self._require_success(
            self.transport.get_json(
                COLLECTION_API_URL,
                params={
                    "mid": parsed.collection_owner_mid,
                    "season_id": parsed.collection_id,
                    "page_num": page_num,
                    "page_size": 100,
                },
                cookies=cookies,
            ),
            error_code="bilibili.metadata_failed",
            message="Failed to fetch Bilibili collection metadata.",
        )

    def _collection_parts_from_archive(
        self,
        collection_id: str,
        archive: Any,
        index: int,
        cookies: dict[str, Any],
    ) -> list[BilibiliPart]:
        archive_dict = archive if isinstance(archive, dict) else {}
        if archive_dict.get("cid") is not None:
            return [_collection_part(collection_id, archive_dict, index)]
        bvid = str(archive_dict.get("bvid") or "")
        if not bvid:
            raise ServiceError(
                message="Bilibili collection archive did not include bvid.",
                error_code="bilibili.metadata_failed",
                status_code=502,
            )
        payload = self._require_success(
            self.transport.get_json(VIEW_API_URL, params={"bvid": bvid}, cookies=cookies),
            error_code="bilibili.metadata_failed",
            message="Failed to fetch Bilibili collection archive metadata.",
        )
        pages = payload.get("pages")
        if not isinstance(pages, list) or not pages:
            raise ServiceError(
                message="Bilibili collection archive metadata did not include pages.",
                error_code="bilibili.metadata_failed",
                status_code=502,
            )
        return [
            _collection_part(collection_id, _collection_archive_page(bvid, archive_dict, page), page_index)
            for page_index, page in enumerate(pages, start=1)
        ]

    def _preview_bangumi(
        self,
        parsed: ParsedBilibiliUrl,
        source_url: str,
        cookies: dict[str, Any],
    ) -> BilibiliPreview:
        if not parsed.episode_numeric_id:
            raise ServiceError(
                message="Unsupported Bilibili URL.",
                error_code="bilibili.unsupported_url",
                status_code=422,
            )
        response = self.transport.get_json(
            BANGUMI_SEASON_API_URL,
            params={"ep_id": parsed.episode_numeric_id},
            cookies=cookies,
        )
        duration_milliseconds = isinstance(response.get("result"), dict)
        payload = self._require_success_result(
            response,
            error_code="bilibili.metadata_failed",
            message="Failed to fetch Bilibili bangumi metadata.",
        )
        episodes = payload.get("episodes")
        if not isinstance(episodes, list) or not episodes:
            raise ServiceError(
                message="Bilibili bangumi metadata did not include episodes.",
                error_code="bilibili.metadata_failed",
                status_code=502,
            )
        current_episode = _find_bangumi_episode(episodes, parsed.episode_numeric_id)
        if current_episode is None or not _episode_has_playable_identity(current_episode):
            raise ServiceError(
                message="Bilibili current bangumi episode is not playable with current auth.",
                error_code="bilibili.access_denied",
                status_code=403,
            )
        playable_episodes = [item for item in episodes if _episode_has_playable_identity(item)]
        if not playable_episodes:
            raise ServiceError(
                message="Bilibili bangumi episodes are not playable with current auth.",
                error_code="bilibili.access_denied",
                status_code=403,
            )
        parts = [
            _bangumi_part(
                parsed.episode_numeric_id,
                item,
                index,
                duration_milliseconds=duration_milliseconds,
            )
            for index, item in enumerate(playable_episodes, start=1)
        ]
        return BilibiliPreview(
            preview_id=self.preview_id_factory(),
            source_url=source_url,
            source_type=BilibiliSourceType.BANGUMI,
            title=str(payload.get("title") or parsed.episode_id or parsed.episode_numeric_id),
            cover_url=str(payload["cover"]) if payload.get("cover") else None,
            total_parts=len(parts),
            default_selection_mode="current_part",
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

    @staticmethod
    def _require_success_result(response: dict[str, Any], *, error_code: str, message: str) -> dict[str, Any]:
        payload = response.get("result") if isinstance(response.get("result"), dict) else response.get("data")
        if response.get("code") != 0 or not isinstance(payload, dict):
            mapped_error = _mapped_bili_error(response, default_error_code=error_code)
            raise ServiceError(
                message=message,
                error_code=mapped_error[0],
                status_code=mapped_error[1],
            )
        return dict(payload)


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
    page_value = page_dict.get("page")
    page_no = _metadata_int(index + 1 if page_value is None else page_value, field_name="page")
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
        duration_sec=_metadata_int(
            0 if page_dict.get("duration") is None else page_dict.get("duration"),
            field_name="duration",
        ),
        cid=_metadata_int(cid, field_name="cid"),
        page_no=page_no,
        selected_by_default=selected,
    )


def _collection_archives(payload: dict[str, Any]) -> list[Any]:
    archives = payload.get("archives")
    if not isinstance(archives, list) or not archives:
        raise ServiceError(
            message="Bilibili collection metadata did not include archives.",
            error_code="bilibili.metadata_failed",
            status_code=502,
        )
    return list(archives)


def _collection_page_count(page: Any) -> int:
    if not isinstance(page, dict):
        raise ServiceError(
            message="Bilibili collection pagination metadata was invalid.",
            error_code="bilibili.metadata_failed",
            status_code=502,
        )
    if "total" not in page or "page_size" not in page:
        raise ServiceError(
            message="Bilibili collection pagination metadata was incomplete.",
            error_code="bilibili.metadata_failed",
            status_code=502,
        )
    total = _metadata_int(page.get("total"), field_name="total")
    page_size = _metadata_int(page.get("page_size"), field_name="page_size")
    if page_size <= 0:
        raise ServiceError(
            message="Bilibili collection pagination page_size must be positive.",
            error_code="bilibili.metadata_failed",
            status_code=502,
        )
    if total <= page_size:
        return 1
    return (total + page_size - 1) // page_size


def _collection_part(collection_id: str, item: Any, index: int) -> BilibiliPart:
    item_dict = item if isinstance(item, dict) else {}
    bvid = str(item_dict.get("bvid") or "")
    cid = item_dict.get("cid")
    if not bvid or cid is None:
        raise ServiceError(
            message="Bilibili collection archive did not include bvid and cid.",
            error_code="bilibili.metadata_failed",
            status_code=502,
        )
    cid_int = _metadata_int(cid, field_name="cid")
    page_value = item_dict.get("page")
    if page_value is None:
        page_value = item_dict.get("page_no")
    if page_value is None:
        page_value = index
    page_no = _metadata_int(page_value, field_name="page")
    duration_value = item_dict.get("duration")
    duration_sec = _metadata_int(0 if duration_value is None else duration_value, field_name="duration")
    return BilibiliPart(
        part_id=f"collection-{collection_id}-bv-{bvid}-cid-{cid_int}-p{page_no}",
        title=str(item_dict.get("title") or item_dict.get("part") or f"P{page_no}"),
        duration_sec=duration_sec,
        cid=cid_int,
        page_no=page_no,
        selected_by_default=True,
    )


def _collection_archive_page(bvid: str, archive: dict[str, Any], page: Any) -> dict[str, Any]:
    page_dict = page if isinstance(page, dict) else {}
    merged = dict(page_dict)
    merged["bvid"] = bvid
    if "title" not in merged and "part" in merged:
        merged["title"] = merged["part"]
    if "title" not in merged and "title" in archive:
        merged["title"] = archive["title"]
    if "duration" not in merged and "duration" in archive:
        merged["duration"] = archive["duration"]
    return merged


def _episode_has_playable_identity(item: Any) -> bool:
    item_dict = item if isinstance(item, dict) else {}
    return bool(item_dict.get("bvid")) and "cid" in item_dict and item_dict["cid"] is not None


def _find_bangumi_episode(episodes: list[Any], episode_id: str) -> Any | None:
    for item in episodes:
        item_dict = item if isinstance(item, dict) else {}
        if str(item_dict.get("id") or "") == episode_id:
            return item
    return None


def _bangumi_part(
    current_ep_id: str | None,
    item: Any,
    index: int,
    *,
    duration_milliseconds: bool,
) -> BilibiliPart:
    item_dict = item if isinstance(item, dict) else {}
    bvid = str(item_dict.get("bvid") or "")
    cid = item_dict.get("cid")
    if not bvid or cid is None:
        raise ServiceError(
            message="Bilibili bangumi episode did not include bvid and cid.",
            error_code="bilibili.metadata_failed",
            status_code=502,
        )
    episode_id = str(item_dict.get("id") or current_ep_id or "unknown")
    cid_int = _metadata_int(cid, field_name="cid")
    page_no = index
    title = str(item_dict.get("long_title") or item_dict.get("title") or f"EP{page_no}")
    return BilibiliPart(
        part_id=f"bangumi-ep-{episode_id}-bv-{bvid}-cid-{cid_int}-p{page_no}",
        title=title,
        duration_sec=_bangumi_duration_seconds(
            item_dict.get("duration"),
            milliseconds=duration_milliseconds,
        ),
        cid=cid_int,
        page_no=page_no,
        selected_by_default=episode_id == str(current_ep_id),
    )


def _bangumi_duration_seconds(value: Any, *, milliseconds: bool) -> int:
    duration = _metadata_int(0 if value is None else value, field_name="duration")
    if milliseconds:
        return duration // 1000
    return duration


def _metadata_int(value: Any, *, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ServiceError(
            message=f"Bilibili metadata field is not numeric: {field_name}.",
            error_code="bilibili.metadata_failed",
            status_code=502,
        ) from exc


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
