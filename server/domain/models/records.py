from __future__ import annotations

from datetime import datetime
from typing import TypedDict


class CitationRecord(TypedDict, total=False):
    resourceId: int
    refLabel: str
    pageNo: int
    slideNo: int
    anchorKey: str
    startSec: int
    endSec: int


class CourseRecord(TypedDict, total=False):
    courseId: int
    title: str
    entryType: str
    catalogId: str | None
    goalText: str
    preferredStyle: str
    lifecycleStatus: str
    pipelineStage: str
    pipelineStatus: str
    activeParseRunId: int
    activeHandoutVersionId: int
    updatedAt: datetime


class ResourceRecord(TypedDict, total=False):
    resourceId: int
    resourceType: str
    originalName: str
    objectKey: str
    ingestStatus: str
    validationStatus: str
    processingStatus: str


class ParseRunRecord(TypedDict, total=False):
    parseRunId: int
    courseId: int
    status: str
    progressPct: int
    startedAt: datetime
    finishedAt: datetime | None


class HandoutBlockRecord(TypedDict, total=False):
    blockId: int
    title: str
    summary: str
    contentMd: str
    startSec: int | None
    endSec: int | None
    pageFrom: int | None
    pageTo: int | None
    slideNo: int | None
    anchorKey: str | None
    citations: list[CitationRecord]


class HandoutRecord(TypedDict, total=False):
    handoutVersionId: int
    title: str
    summary: str
    totalBlocks: int
    status: str
    sourceParseRunId: int | None
    blocks: list[HandoutBlockRecord]


class QaMessageRecord(TypedDict, total=False):
    sessionId: int
    messageId: int
    answerMd: str
    citations: list[CitationRecord]


class QuizRecord(TypedDict, total=False):
    quizId: int
    courseId: int
    status: str
    questionCount: int
    questions: list[dict[str, object]]


class ReviewTaskRecord(TypedDict, total=False):
    reviewTaskId: int
    taskType: str
    priorityScore: int
    reasonText: str
    recommendedMinutes: int


class ReviewRunRecord(TypedDict, total=False):
    reviewTaskRunId: int
    courseId: int
    status: str
    generatedCount: int


class ProgressRecord(TypedDict, total=False):
    courseId: int
    handoutVersionId: int
    lastHandoutBlockId: int
    lastVideoResourceId: int
    lastPositionSec: int
    lastDocResourceId: int
    lastPageNo: int
    lastActivityAt: datetime
