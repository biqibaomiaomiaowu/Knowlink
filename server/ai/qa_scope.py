from __future__ import annotations

import re
from dataclasses import replace
from typing import Any, Mapping

from server.ai.qa_types import QaScope
from server.parsers.base import clean_text


_ORDINARY_OUT_OF_SCOPE_TERM_GROUPS: tuple[tuple[str, ...], ...] = (
    ("\u5929\u6c14", "\u6c14\u8c61", "\u6c14\u6e29", "\u4e0b\u96e8", "\u964d\u96e8", "\u53f0\u98ce", "\u9884\u62a5"),
    ("\u65b0\u95fb", "\u70ed\u641c", "\u5a31\u4e50", "\u660e\u661f", "\u5a92\u4f53", "\u62a5\u9053"),
    ("\u80a1\u7968", "\u80a1\u4ef7", "\u57fa\u91d1", "\u5f69\u7968", "\u4e2d\u5956", "\u8bc1\u5238", "\u6295\u8d44"),
)
_HARD_SECURITY_TERMS: tuple[str, ...] = (
    "system prompt",
    "developer message",
    "ignore previous",
    "jailbreak",
    "api key",
    "secret",
    "token",
    "password",
    "\u7cfb\u7edf\u63d0\u793a",
    "\u7cfb\u7edf\u63d0\u793a\u8bcd",
    "\u5f00\u53d1\u8005\u6d88\u606f",
    "\u5ffd\u7565\u4e0a\u9762",
    "\u5ffd\u7565\u4e4b\u524d",
    "\u5bc6\u94a5",
    "\u4ee4\u724c",
    "\u5bc6\u7801",
    "\u79d8\u5bc6",
)
_SOURCE_FACT_TERMS: tuple[str, ...] = (
    "\u8001\u5e08",
    "\u89c6\u9891",
    "\u5b57\u5e55",
    "\u539f\u59cb\u8d44\u6599",
    "\u539f\u6587",
    "\u7b2c\u51e0\u5206\u949f",
    "\u51e0\u5206\u949f",
    "\u65f6\u95f4\u70b9",
    "\u54ea\u4e00\u9875",
    "\u7b2c\u51e0\u9875",
    "source",
    "timestamp",
    "minute",
    "page",
)


def build_qa_scope(context: Mapping[str, Any]) -> QaScope:
    current_block = _mapping_value(context.get("currentBlock")) or _mapping_value(context.get("current_block")) or {}
    return QaScope(
        course_id=_as_positive_int(_field_value(context, "activeCourseId", "active_course_id"))
        or _as_positive_int(_field_value(current_block, "courseId", "course_id")),
        active_parse_run_id=_as_positive_int(_field_value(context, "activeParseRunId", "active_parse_run_id"))
        or _as_positive_int(_field_value(current_block, "parseRunId", "parse_run_id")),
        active_handout_version_id=_as_positive_int(
            _field_value(context, "activeHandoutVersionId", "active_handout_version_id")
        )
        or _as_positive_int(_field_value(current_block, "handoutVersionId", "handout_version_id")),
        current_handout_block_id=_field_value(
            context,
            "handoutBlockId",
            "handout_block_id",
        )
        or _field_value(current_block, "handoutBlockId", "handout_block_id", "blockId", "block_id"),
        current_outline_key=_field_value(current_block, "outlineKey", "outline_key"),
        current_sort_no=_as_int(_field_value(current_block, "sortNo", "sort_no")),
    )


class QaScopeGuard:
    def __init__(self, *, scope: QaScope, context: Mapping[str, Any]) -> None:
        self.scope = scope
        self.context = context

    def is_hard_security_out_of_scope(self, question: str) -> bool:
        normalized = clean_text(question).lower()
        return any(term in normalized for term in _HARD_SECURITY_TERMS)

    def is_ordinary_out_of_scope(self, question: str) -> bool:
        normalized = clean_text(question).lower()
        if not normalized:
            return False
        course_scope_text = _course_scope_text(self.context.get("courseScope") or self.context.get("course_scope")).lower()
        for term_group in _ORDINARY_OUT_OF_SCOPE_TERM_GROUPS:
            if any(term in normalized for term in term_group) and not any(term in course_scope_text for term in term_group):
                return True
        return False

    def is_source_fact_intent(self, question: str) -> bool:
        normalized = clean_text(question).lower()
        return any(term in normalized for term in _SOURCE_FACT_TERMS)

    def is_course_related(self, question: str) -> bool:
        course_scope_text = _course_scope_text(self.context.get("courseScope") or self.context.get("course_scope"))
        if not course_scope_text or self.is_ordinary_out_of_scope(question):
            return False
        return lexical_relevance_score(question, course_scope_text) > 0


def lexical_relevance_score(question: str, text: str) -> int:
    keywords = _keywords(question)
    if not keywords:
        return 0
    compact = clean_text(text).lower()
    return sum(1 for keyword in keywords if keyword in compact)


def scope_matches_payload(
    payload: Mapping[str, Any],
    scope: QaScope,
    *,
    require_course_parse: bool = False,
    require_handout_version: bool = False,
) -> bool:
    course_id = _as_positive_int(_field_value(payload, "courseId", "course_id"))
    parse_run_id = _as_positive_int(_field_value(payload, "parseRunId", "parse_run_id"))
    handout_version_id = _as_positive_int(_field_value(payload, "handoutVersionId", "handout_version_id"))
    if require_course_parse:
        if scope.course_id is not None and course_id != scope.course_id:
            return False
        if scope.active_parse_run_id is not None and parse_run_id != scope.active_parse_run_id:
            return False
    if scope.course_id is not None and course_id is not None and course_id != scope.course_id:
        return False
    if scope.active_parse_run_id is not None and parse_run_id is not None and parse_run_id != scope.active_parse_run_id:
        return False
    if scope.active_handout_version_id is not None:
        if require_handout_version and handout_version_id != scope.active_handout_version_id:
            return False
        if handout_version_id is not None and handout_version_id != scope.active_handout_version_id:
            return False
    return True


def active_ints(scope: QaScope) -> tuple[int, int, int]:
    return (
        int(scope.course_id or 0),
        int(scope.active_parse_run_id or 0),
        int(scope.active_handout_version_id or 0),
    )


def replace_scope(scope: QaScope, **changes: Any) -> QaScope:
    return replace(scope, **changes)


def _course_scope_text(course_scope: Any) -> str:
    if not isinstance(course_scope, Mapping):
        return ""
    values: list[str] = []
    for key in ("title", "summary", "goalText", "goal_text"):
        value = course_scope.get(key)
        if isinstance(value, str) and value:
            values.append(value)
    for key in ("resourceTitles", "resource_titles", "handoutTitles", "handout_titles", "knowledgePointNames", "knowledge_point_names"):
        value = course_scope.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value if str(item).strip())
    return clean_text("\n".join(values))


def _keywords(text: str) -> set[str]:
    normalized = clean_text(text).lower()
    tokens = set(re.findall(r"[A-Za-z0-9_]{3,}", normalized))
    for run in re.findall(r"[\u4e00-\u9fff]+", normalized):
        if len(run) == 1:
            tokens.add(run)
        else:
            tokens.update(run[index : index + 2] for index in range(0, len(run) - 1))
    stopwords = {
        "\u4ec0\u4e48",
        "\u5982\u4f55",
        "\u600e\u4e48",
        "\u54ea\u4e9b",
        "\u662f\u5426",
        "\u4ee5\u53ca",
        "\u8fd9\u4e2a",
        "\u90a3\u4e2a",
        "\u95ee\u9898",
        "\u8054\u7cfb",
    }
    return {token for token in tokens if token and token not in stopwords}


def _mapping_value(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _field_value(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _as_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_positive_int(value: Any) -> int | None:
    parsed = _as_int(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed
