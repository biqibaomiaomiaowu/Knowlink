"""Shared API schemas."""

from server.schemas.common import AsyncEntity, Citation, InquiryQuestionOption, ResourceManifestItem
from server.schemas.requests import (
    ConfirmRecommendationRequest,
    CreateCourseRequest,
    InquiryAnswersRequest,
    ProgressData,
    QaMessageRequest,
    RecommendationRequest,
    SubmitQuizRequest,
    UploadCompleteRequest,
    UploadInitRequest,
)
from server.schemas.responses import (
    CourseSummary,
    DashboardData,
    HandoutBlock,
    JumpTargetData,
    ParseRunData,
    QaMessageData,
    QuizData,
    RecommendationCard,
    ReviewTask,
)

__all__ = [
    "AsyncEntity",
    "Citation",
    "ConfirmRecommendationRequest",
    "CourseSummary",
    "CreateCourseRequest",
    "DashboardData",
    "HandoutBlock",
    "InquiryAnswersRequest",
    "InquiryQuestionOption",
    "JumpTargetData",
    "ParseRunData",
    "ProgressData",
    "QaMessageData",
    "QaMessageRequest",
    "QuizData",
    "RecommendationCard",
    "RecommendationRequest",
    "ResourceManifestItem",
    "ReviewTask",
    "SubmitQuizRequest",
    "UploadCompleteRequest",
    "UploadInitRequest",
]
