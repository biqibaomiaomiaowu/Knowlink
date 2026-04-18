from __future__ import annotations

from typing import Literal

from server.schemas.base import CamelModel


class ResourceManifestItem(CamelModel):
    resource_type: str
    required: bool
    description: str


class AsyncEntity(CamelModel):
    type: Literal["parse_run", "handout_version", "quiz", "review_task_run", "bilibili_import_run"]
    id: int


class StepStatus(CamelModel):
    code: str
    label: str
    status: str


class InquiryQuestionOption(CamelModel):
    label: str
    value: str


class Citation(CamelModel):
    resource_id: int
    ref_label: str
    page_no: int | None = None
    slide_no: int | None = None
    anchor_key: str | None = None
    start_sec: int | None = None
    end_sec: int | None = None
