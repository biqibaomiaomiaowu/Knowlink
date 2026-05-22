from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import parse_qs, urlparse


_BVID_RE = re.compile(r"^BV[0-9A-Za-z]{10}$")
_BANGUMI_EP_RE = re.compile(r"^ep[0-9]+$")


class BilibiliUrlKind(StrEnum):
    SINGLE_VIDEO = "single_video"
    MULTI_P = "multi_p"
    COLLECTION = "collection"
    BANGUMI = "bangumi"
    SHORT = "short"


@dataclass(frozen=True)
class ParsedBilibiliUrl:
    original_url: str
    kind: BilibiliUrlKind
    bvid: str | None = None
    page_no: int | None = None
    collection_id: str | None = None
    collection_owner_mid: str | None = None
    episode_id: str | None = None
    episode_numeric_id: str | None = None


def parse_bilibili_url(url: str) -> ParsedBilibiliUrl:
    normalized_url = url.strip()
    parsed = urlparse(normalized_url)
    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    if parsed.scheme != "https":
        raise ValueError("unsupported Bilibili URL")

    if host == "www.bilibili.com":
        return _parse_www_bilibili(normalized_url, path_parts, parsed.query)
    if host == "space.bilibili.com":
        return _parse_space_bilibili(normalized_url, path_parts, parsed.query)
    if host == "b23.tv":
        return _parse_b23(normalized_url, path_parts)

    raise ValueError("unsupported Bilibili URL")


def _parse_www_bilibili(original_url: str, path_parts: list[str], query: str) -> ParsedBilibiliUrl:
    if len(path_parts) >= 2 and path_parts[0] == "video" and _BVID_RE.match(path_parts[1]):
        page_no = _page_no(query)
        if page_no is None:
            return ParsedBilibiliUrl(
                original_url=original_url,
                kind=BilibiliUrlKind.SINGLE_VIDEO,
                bvid=path_parts[1],
            )
        return ParsedBilibiliUrl(
            original_url=original_url,
            kind=BilibiliUrlKind.MULTI_P,
            bvid=path_parts[1],
            page_no=page_no,
        )

    if (
        len(path_parts) >= 3
        and path_parts[0] == "bangumi"
        and path_parts[1] == "play"
        and _BANGUMI_EP_RE.match(path_parts[2])
    ):
        return ParsedBilibiliUrl(
            original_url=original_url,
            kind=BilibiliUrlKind.BANGUMI,
            episode_id=path_parts[2],
            episode_numeric_id=path_parts[2].removeprefix("ep"),
        )

    raise ValueError("unsupported Bilibili URL")


def _parse_space_bilibili(original_url: str, path_parts: list[str], query: str) -> ParsedBilibiliUrl:
    query_values = parse_qs(query)
    sid_values = query_values.get("sid", [])
    if (
        len(path_parts) >= 3
        and path_parts[0].isdigit()
        and path_parts[1] == "channel"
        and path_parts[2] == "collectiondetail"
        and sid_values
        and sid_values[0]
    ):
        return ParsedBilibiliUrl(
            original_url=original_url,
            kind=BilibiliUrlKind.COLLECTION,
            collection_id=sid_values[0],
            collection_owner_mid=path_parts[0],
        )

    raise ValueError("unsupported Bilibili URL")


def _parse_b23(original_url: str, path_parts: list[str]) -> ParsedBilibiliUrl:
    if path_parts:
        bvid = path_parts[0] if _BVID_RE.match(path_parts[0]) else None
        return ParsedBilibiliUrl(
            original_url=original_url,
            kind=BilibiliUrlKind.SHORT,
            bvid=bvid,
        )

    raise ValueError("unsupported Bilibili URL")


def _page_no(query: str) -> int | None:
    query_values = parse_qs(query)
    values = query_values.get("p", [])
    if not values:
        return None
    try:
        page_no = int(values[0])
    except ValueError:
        return None
    if page_no < 1:
        return None
    return page_no
