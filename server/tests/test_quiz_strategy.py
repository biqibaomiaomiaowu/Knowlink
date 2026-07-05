import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from server.ai.core.errors import AIOutputParseError
from server.ai.core.types import AIModelResult
from server.ai.quiz_strategy import (
    DeepSeekQuizGenerationClient,
    build_quiz_question_refs,
    generate_quiz_payload,
    grade_quiz_attempt,
)
from server.domain.services.errors import ServiceError
from server.domain.services.quizzes import QuizService
from server.infra.repositories.memory import MemoryScaffoldRepository
from server.infra.repositories.memory_runtime import RuntimeStore
from server.schemas.requests import SubmitQuizRequest


ROOT = Path(__file__).resolve().parents[2]
QUIZ_SCHEMA = json.loads((ROOT / "schemas/ai/quiz_generation.schema.json").read_text(encoding="utf-8"))
QUIZ_VALIDATOR = Draft202012Validator(QUIZ_SCHEMA)


class FakeQuizClient:
    def __init__(self, payload: dict | list[dict]):
        self.payloads = list(payload) if isinstance(payload, list) else [payload]
        self.prompt_contexts: list[dict] = []

    def generate_quiz(self, prompt_context):
        self.prompt_contexts.append(dict(prompt_context))
        index = min(len(self.prompt_contexts) - 1, len(self.payloads) - 1)
        return self.payloads[index]


class FakeAIService:
    def __init__(self, payload: dict | None = None, error: BaseException | None = None):
        self.payload = payload if payload is not None else {}
        self.error = error
        self.requests = []

    def complete_json(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return AIModelResult(text=json.dumps(self.payload, ensure_ascii=False), parsed_json=self.payload)


class RecordingDispatcher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, dict]] = []

    def enqueue_quiz_generate(self, *, task_id: int, payload: dict) -> None:
        self.calls.append(("quiz_generate", task_id, payload))


def _generate_quiz_payload() -> dict:
    return generate_quiz_payload(
        _handout_blocks(),
        segments=_segments(),
        client=FakeQuizClient(_model_payload(3)),
    )


def _model_payload(question_count: int = 3) -> dict:
    return {
        "quizType": "chapter_review",
        "questions": [_model_question(index) for index in range(1, question_count + 1)],
    }


def _model_question(index: int) -> dict:
    source = [
        ("block-pdf", "kp-limit", "函数极限", ["pdf-p2"], "关于极限定义，哪项说法符合当前材料？"),
        ("block-video", "kp-continuity", "连续性", ["mp4-c2"], "关于连续性例题，哪项说法符合当前材料？"),
        ("block-ppt", "kp-set", "集合表示", ["ppt-s6"], "关于集合表示法，哪项说法符合当前材料？"),
    ][(index - 1) % 3]
    block_key, kp_key, kp_name, segment_keys, stem = source
    return {
        "questionKey": f"q{index}-{kp_key}",
        "questionType": "single_choice",
        "stemMd": stem,
        "options": [
            f"A. {kp_name} 的描述来自当前讲义材料。",
            "B. 当前材料没有提供任何依据。",
            "C. 这个知识点与当前讲义块无关。",
            "D. 只需要记住名称即可。",
        ],
        "correctAnswer": "A",
        "explanationMd": f"答案依据 {kp_name} 对应讲义块和来源片段。",
        "difficultyLevel": "medium",
        "knowledgePointKey": kp_key,
        "knowledgePointName": kp_name,
        "sourceBlockKey": block_key,
        "sourceSegmentKeys": segment_keys,
    }


@pytest.mark.parametrize(
    ("question_count_level", "expected_range", "question_count"),
    [
        ("small", {"min": 1, "max": 3}, 1),
        ("medium", {"min": 3, "max": 5}, 3),
        ("large", {"min": 5, "max": 10}, 5),
    ],
)
def test_generate_quiz_payload_uses_deepseek_client_context_and_count_level(
    question_count_level,
    expected_range,
    question_count,
):
    client = FakeQuizClient(_model_payload(question_count))

    payload = generate_quiz_payload(
        _handout_blocks(),
        segments=_segments(),
        course_context={"courseId": 101, "title": "高数期末冲刺课"},
        preferences={"selfLevel": "intermediate"},
        question_count_level=question_count_level,
        client=client,
    )

    QUIZ_VALIDATOR.validate(payload)
    assert payload["quizType"] == "chapter_review"
    assert len(payload["questions"]) == question_count
    assert [question["knowledgePointKey"] for question in payload["questions"]] == [
        "kp-limit",
        "kp-continuity",
        "kp-set",
        "kp-limit",
        "kp-continuity",
    ][:question_count]
    assert {question["correctAnswer"] for question in payload["questions"]} == {"A"}
    assert all(question["questionType"] == "single_choice" for question in payload["questions"])
    assert all(len(question["options"]) == 4 for question in payload["questions"])
    assert all("pageNo" not in question and "startSec" not in question for question in payload["questions"])
    assert payload["questions"][0]["sourceSegmentKeys"] == ["pdf-p2"]
    assert client.prompt_contexts[0]["questionCountRange"] == expected_range
    assert client.prompt_contexts[0]["course"]["title"] == "高数期末冲刺课"
    assert client.prompt_contexts[0]["learningPreferences"]["selfLevel"] == "intermediate"
    assert client.prompt_contexts[0]["readyHandoutBlocks"][0]["blockKey"] == "block-pdf"
    assert client.prompt_contexts[0]["allowedQuestionSources"][0] == {
        "sourceBlockKey": "block-pdf",
        "blockTitle": "极限定义",
        "allowedSourceSegmentKeys": ["pdf-p2"],
        "allowedKnowledgePointKeys": ["kp-limit"],
    }
    assert client.prompt_contexts[0]["activeParseRunSegments"][0]["segmentKey"] == "pdf-p2"


def test_generate_quiz_payload_fails_when_deepseek_is_not_configured(monkeypatch):
    monkeypatch.delenv("KNOWLINK_DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="deepseek quiz generation is not configured"):
        generate_quiz_payload(_handout_blocks(), segments=_segments())


def test_generate_quiz_payload_rejects_count_outside_requested_level():
    with pytest.raises(ValueError, match="range 1-3"):
        generate_quiz_payload(
            _handout_blocks(),
            segments=_segments(),
            question_count_level="small",
            client=FakeQuizClient(_model_payload(4)),
        )


@pytest.mark.parametrize(
    "bad_payload",
    [
        {"quizType": "chapter_review", "questions": [{**_model_question(1), "sourceBlockKey": "unknown-block"}]},
        {"quizType": "chapter_review", "questions": [{**_model_question(1), "sourceSegmentKeys": ["unknown-seg"]}]},
        {"quizType": "chapter_review", "questions": [{**_model_question(1), "correctAnswer": "E"}]},
        {"quizType": "chapter_review", "questions": [{**_model_question(1), "pageNo": 2}]},
        {"quizType": "chapter_review", "questions": [{**_model_question(1), "stemMd": 123}]},
        {"quizType": "chapter_review", "questions": [{**_model_question(1), "sourceSegmentKeys": [202]}]},
    ],
)
def test_generate_quiz_payload_rejects_invalid_model_payloads(bad_payload):
    with pytest.raises(ValueError):
        generate_quiz_payload(
            _handout_blocks(),
            segments=_segments(),
            question_count_level="small",
            client=FakeQuizClient(bad_payload),
        )


def test_generate_quiz_payload_rejects_segments_from_other_block_when_source_block_has_no_segments():
    blocks = [
        {
            "handoutBlockId": "block-with-source",
            "title": "有来源块",
            "summary": "可追溯来源。",
            "sourceSegmentKeys": ["pdf-p2"],
            "knowledgePoints": [{"knowledgePointKey": "kp-source", "displayName": "有来源知识点"}],
            "citations": [{"resourceId": 2, "segmentKey": "pdf-p2", "pageNo": 2, "refLabel": "PDF 第 2 页"}],
        },
        {
            "handoutBlockId": "block-empty-source",
            "title": "无来源块",
            "summary": "不能被模型挂靠别的来源。",
            "sourceSegmentKeys": [],
            "knowledgePoints": [{"knowledgePointKey": "kp-empty", "displayName": "无来源知识点"}],
            "citations": [],
        },
    ]
    bad_payload = {
        "quizType": "chapter_review",
        "questions": [
            {
                **_model_question(1),
                "knowledgePointKey": "kp-empty",
                "knowledgePointName": "无来源知识点",
                "sourceBlockKey": "block-empty-source",
                "sourceSegmentKeys": ["pdf-p2"],
            }
        ],
    }

    with pytest.raises(ValueError, match="without source segments"):
        generate_quiz_payload(
            blocks,
            segments=_segments(),
            question_count_level="small",
            client=FakeQuizClient(bad_payload),
        )


def test_generate_quiz_payload_retries_once_when_model_crosses_block_segment_sources():
    bad_payload = _model_payload(3)
    bad_payload["questions"][0] = {
        **bad_payload["questions"][0],
        "knowledgePointKey": "kp-continuity",
        "knowledgePointName": "连续性",
        "sourceBlockKey": "block-video",
        "sourceSegmentKeys": ["pdf-p2"],
    }
    client = FakeQuizClient([bad_payload, _model_payload(3)])

    payload = generate_quiz_payload(
        _handout_blocks(),
        segments=_segments(),
        client=client,
    )

    QUIZ_VALIDATOR.validate(payload)
    assert len(client.prompt_contexts) == 2
    repair = client.prompt_contexts[1]["repairInstruction"]
    assert "segments outside sourceBlockKey" in repair["serverError"]
    assert repair["invalidPayload"] == bad_payload
    assert client.prompt_contexts[1]["allowedQuestionSources"][1] == {
        "sourceBlockKey": "block-video",
        "blockTitle": "连续性的例题",
        "allowedSourceSegmentKeys": ["mp4-c2"],
        "allowedKnowledgePointKeys": ["kp-continuity"],
    }


def test_generate_quiz_payload_does_not_retry_schema_errors():
    bad_question = dict(_model_question(1))
    bad_question.pop("knowledgePointKey")
    client = FakeQuizClient({"quizType": "chapter_review", "questions": [bad_question]})

    with pytest.raises(ValueError, match="missing fields"):
        generate_quiz_payload(
            _handout_blocks(),
            segments=_segments(),
            question_count_level="small",
            client=client,
        )

    assert len(client.prompt_contexts) == 1


def test_quiz_prompt_context_excludes_blocks_without_source_segments():
    blocks = [
        *_handout_blocks(),
        {
            "handoutBlockId": "block-empty",
            "title": "无来源块",
            "summary": "没有来源片段。",
            "sourceSegmentKeys": [],
            "knowledgePoints": [{"knowledgePointKey": "kp-empty", "displayName": "无来源"}],
            "citations": [],
        },
    ]
    client = FakeQuizClient(_model_payload(3))

    generate_quiz_payload(blocks, segments=_segments(), client=client)

    block_keys = {item["blockKey"] for item in client.prompt_contexts[0]["readyHandoutBlocks"]}
    allowed_keys = {item["sourceBlockKey"] for item in client.prompt_contexts[0]["allowedQuestionSources"]}
    assert "block-empty" not in block_keys
    assert "block-empty" not in allowed_keys


def test_deepseek_quiz_client_uses_ai_service_json_request():
    ai_service = FakeAIService(_model_payload(3))
    client = DeepSeekQuizGenerationClient(
        api_key="fake-deepseek-key",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-v4-flash",
        reasoning_effort="high",
        timeout_sec=12,
        ai_service=ai_service,
    )

    payload = generate_quiz_payload(_handout_blocks(), segments=_segments(), client=client)

    request = ai_service.requests[0]
    assert request.provider == "deepseek"
    assert request.model == "deepseek-v4-flash"
    assert request.timeout_sec == 12
    assert request.response_format == {"type": "json_object"}
    assert request.metadata == {"max_tokens": 8192, "reasoning_effort": "high"}
    assert [message.role for message in request.messages] == ["system", "user"]
    assert "JSON" in request.messages[0].content or "json" in request.messages[0].content
    QUIZ_VALIDATOR.validate(payload)


def test_deepseek_quiz_client_rejects_bad_json():
    ai_service = FakeAIService(error=AIOutputParseError("model output does not contain a JSON object"))
    client = DeepSeekQuizGenerationClient(
        api_key="fake-deepseek-key",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
        reasoning_effort="high",
        ai_service=ai_service,
    )

    with pytest.raises(AIOutputParseError, match="JSON object"):
        client.generate_quiz({"questionCountRange": {"min": 3, "max": 5}})


def test_quiz_question_refs_are_built_from_block_citations_not_question_locators():
    payload = _generate_quiz_payload()

    refs = build_quiz_question_refs(
        payload,
        handout_blocks=_handout_blocks(),
        segments=_segments(),
    )

    assert [ref["questionKey"] for ref in refs] == [question["questionKey"] for question in payload["questions"]]
    assert refs[0] == {
        "questionKey": payload["questions"][0]["questionKey"],
        "resourceId": 2,
        "segmentId": 202,
        "segmentKey": "pdf-p2",
        "refType": "pdf_page",
        "quoteText": "函数极限描述的是自变量趋近时函数值的稳定趋势。",
        "refLabel": "PDF 第 2 页",
        "sortNo": 1,
        "pageNo": 2,
    }
    assert refs[1]["startSec"] == 120
    assert refs[1]["endSec"] == 180
    assert refs[2]["refType"] == "ppt_slide"


def test_grade_quiz_attempt_returns_score_items_and_mastery_delta():
    payload = _generate_quiz_payload()

    result = grade_quiz_attempt(
        payload,
        [
            {"questionKey": payload["questions"][0]["questionKey"], "selectedOption": "A"},
            {"questionKey": payload["questions"][1]["questionKey"], "selectedOption": "B"},
            {"questionKey": payload["questions"][2]["questionKey"], "selectedOption": "A"},
        ],
    )

    assert result["score"] == 2
    assert result["totalScore"] == 3
    assert result["accuracy"] == 0.6667
    assert [item["isCorrect"] for item in result["items"]] == [True, False, True]
    assert result["masteryDelta"][0]["knowledgePointKey"] == "kp-limit"
    assert result["masteryDelta"][0]["status"] == "improved"
    assert result["masteryDelta"][1]["knowledgePointKey"] == "kp-continuity"
    assert result["masteryDelta"][1]["status"] == "weakened"
    assert result["recommendedReviewAction"]["type"] == "revisit_block"
    assert result["recommendedReviewAction"]["targetBlockKey"] == "block-video"


def test_grade_quiz_attempt_normalizes_selected_option_text_to_option_key():
    payload = _generate_quiz_payload()
    first_question = payload["questions"][0]

    result = grade_quiz_attempt(
        payload,
        [
            {
                "questionKey": first_question["questionKey"],
                "selectedOption": first_question["options"][0],
            }
        ],
    )

    assert result["items"][0]["selectedOption"] == "A"
    assert result["items"][0]["isCorrect"] is True


def test_grade_quiz_attempt_does_not_persist_unmatched_long_option_text():
    payload = _generate_quiz_payload()

    result = grade_quiz_attempt(
        payload,
        [
            {
                "questionKey": payload["questions"][0]["questionKey"],
                "selectedOption": "这是一段无法匹配任何选项的超长中文答案文本，不能写入短选项字段",
            }
        ],
    )

    assert result["items"][0]["selectedOption"] == ""
    assert result["items"][0]["isCorrect"] is False


def test_grade_quiz_attempt_accepts_api_question_id_answers_without_dto_change():
    payload = _generate_quiz_payload()
    persisted_payload = {
        **payload,
        "questions": [
            {**question, "questionId": question_id}
            for question, question_id in zip(payload["questions"], (8101, 8102, 8103), strict=True)
        ],
    }

    result = grade_quiz_attempt(
        persisted_payload,
        [
            {"questionId": 8101, "selectedOption": "A"},
            {"questionId": 8102, "selectedOption": "A"},
            {"questionId": 8103, "selectedOption": "A"},
        ],
    )

    assert result["score"] == 3
    assert result["accuracy"] == 1.0
    assert all(item["isCorrect"] for item in result["items"])


def test_lesson_quiz_generate_submit_scores_objective_questions():
    store = RuntimeStore()
    repository = MemoryScaffoldRepository(store)
    dispatcher = RecordingDispatcher()
    service = QuizService(
        courses=repository,
        quizzes=repository,
        idempotency=repository,
        lessons=store,
        scoped_artifacts=repository,
        handouts=repository,
        resources=repository,
        task_dispatcher=dispatcher,
    )
    course = store.create_course(
        title="Database Systems",
        entry_type="manual_import",
        goal_text="Prepare final exam",
        preferred_style="balanced",
    )
    lesson = store.create_lesson(course_id=course["courseId"], title="Indexes")
    handout, _trigger, blocks = store.create_handout(
        course["courseId"],
        scope_type="lesson",
        lesson_id=lesson["lessonId"],
        artifact_kind="lesson_handout",
    )
    block = blocks[0]
    block.update(
        {
            "status": "ready",
            "generationStatus": "ready",
            "title": "B-tree index lookup",
            "summary": "Indexes reduce lookup work by narrowing candidate rows.",
            "contentMd": "A database index stores ordered keys that help locate matching rows efficiently.",
            "sourceSegmentKeys": ["seg-index-lookup"],
            "knowledgePoints": [{"knowledgePointKey": "kp-index-lookup", "displayName": "Index lookup"}],
            "citations": [{"segmentKey": "seg-index-lookup", "refLabel": "index notes"}],
        }
    )
    handout["readyBlocks"] = 1
    handout["pendingBlocks"] = max(0, handout["pendingBlocks"] - 1)

    generated = service.generate_lesson_quiz(
        course_id=course["courseId"],
        lesson_id=lesson["lessonId"],
        question_count_level="medium",
    )

    assert generated["status"] == "queued"
    assert generated["entity"]["type"] == "quiz"
    quiz = service.get_quiz(quiz_id=generated["entity"]["id"])
    assert quiz["scopeType"] == "lesson"
    assert quiz["lessonId"] == lesson["lessonId"]
    assert quiz["status"] == "queued"
    assert quiz["questionCount"] == 0
    assert quiz["questions"] == []
    task = repository.get_async_task(generated["taskId"])
    assert task["payloadJson"] == {
        "courseId": course["courseId"],
        "quizId": generated["entity"]["id"],
        "questionCountLevel": "medium",
        "scopeType": "lesson",
        "lessonId": lesson["lessonId"],
        "startLessonId": None,
        "endLessonId": None,
    }
    assert dispatcher.calls == [("quiz_generate", generated["taskId"], task["payloadJson"])]


def test_course_quiz_submit_without_review_context_does_not_create_review_run():
    store = RuntimeStore()
    repository = MemoryScaffoldRepository(store)
    service = QuizService(
        courses=repository,
        quizzes=repository,
        idempotency=repository,
    )
    course = store.create_course(
        title="Database Systems",
        entry_type="manual_import",
        goal_text="Prepare final exam",
        preferred_style="balanced",
    )
    quiz, _trigger = store.create_quiz(course["courseId"], question_count_level="small")
    quiz.update(
        {
            "status": "ready",
            "questionCount": 1,
            "questions": [
                {
                    "questionId": quiz["quizId"] * 100 + 1,
                    "questionKey": "course-q1",
                    "questionType": "single_choice",
                    "stemMd": "Which answer is supported by the course evidence?",
                    "options": ["A. Supported", "B. Unsupported", "C. Unrelated", "D. Subjective"],
                    "correctAnswer": "A",
                    "explanationMd": "The answer is supported.",
                    "difficultyLevel": "medium",
                    "knowledgePointKey": "kp-course",
                    "knowledgePointName": "Course evidence",
                    "sourceBlockKey": "course-block",
                    "sourceSegmentKeys": ["course-segment"],
                }
            ],
        }
    )

    result = service.submit_quiz(
        quiz_id=quiz["quizId"],
        payload=SubmitQuizRequest.model_validate(
            {"answers": [{"questionId": quiz["questions"][0]["questionId"], "selectedOption": "A"}]}
        ),
    )

    assert result["score"] == 1
    assert result["totalScore"] == 1
    assert result["accuracy"] == 1.0
    assert result["reviewTaskRunId"] is None
    assert store.review_runs == {}


def test_course_quiz_submit_with_review_context_creates_review_run():
    store = RuntimeStore()
    repository = MemoryScaffoldRepository(store)
    service = QuizService(
        courses=repository,
        quizzes=repository,
        idempotency=repository,
    )
    course = store.create_course(
        title="Database Systems",
        entry_type="manual_import",
        goal_text="Prepare final exam",
        preferred_style="balanced",
    )
    store.create_parse_run(course["courseId"])
    store.create_handout(course["courseId"])
    quiz, _trigger = store.create_quiz(course["courseId"], question_count_level="small")
    quiz.update(
        {
            "status": "ready",
            "questionCount": 1,
            "questions": [
                {
                    "questionId": quiz["quizId"] * 100 + 1,
                    "questionKey": "course-q1",
                    "questionType": "single_choice",
                    "stemMd": "Which answer is supported by the course evidence?",
                    "options": ["A. Supported", "B. Unsupported", "C. Unrelated", "D. Subjective"],
                    "correctAnswer": "A",
                    "explanationMd": "The answer is supported.",
                    "difficultyLevel": "medium",
                    "knowledgePointKey": "kp-course",
                    "knowledgePointName": "Course evidence",
                    "sourceBlockKey": "course-block",
                    "sourceSegmentKeys": ["course-segment"],
                }
            ],
        }
    )

    result = service.submit_quiz(
        quiz_id=quiz["quizId"],
        payload=SubmitQuizRequest.model_validate(
            {"answers": [{"questionId": quiz["questions"][0]["questionId"], "selectedOption": "A"}]}
        ),
    )

    assert result["score"] == 1
    assert result["reviewTaskRunId"] in store.review_runs


def test_course_quiz_history_lists_latest_attempt():
    store = RuntimeStore()
    repository = MemoryScaffoldRepository(store)
    service = QuizService(
        courses=repository,
        quizzes=repository,
        idempotency=repository,
    )
    course = store.create_course(
        title="Database Systems",
        entry_type="manual_import",
        goal_text="Prepare final exam",
        preferred_style="balanced",
    )
    other_course = store.create_course(
        title="Linear Algebra",
        entry_type="manual_import",
        goal_text="Review vectors",
        preferred_style="balanced",
    )
    quiz, _trigger = store.create_quiz(course["courseId"], question_count_level="small")
    other_quiz, _ = store.create_quiz(other_course["courseId"], question_count_level="small")
    for target in (quiz, other_quiz):
        target.update(
            {
                "status": "ready",
                "questionCount": 1,
                "questions": [
                    {
                        "questionId": target["quizId"] * 100 + 1,
                        "questionKey": "course-q1",
                        "questionType": "single_choice",
                        "stemMd": "Which answer is supported by the course evidence?",
                        "options": ["A. Supported", "B. Unsupported"],
                        "correctAnswer": "A",
                        "explanationMd": "The answer is supported.",
                        "difficultyLevel": "medium",
                        "knowledgePointKey": "kp-course",
                        "knowledgePointName": "Course evidence",
                        "sourceBlockKey": "course-block",
                        "sourceSegmentKeys": ["course-segment"],
                    }
                ],
            }
        )

    first_attempt = service.submit_quiz(
        quiz_id=quiz["quizId"],
        payload=SubmitQuizRequest.model_validate(
            {"answers": [{"questionId": quiz["questions"][0]["questionId"], "selectedOption": "B"}]}
        ),
    )
    latest_attempt = service.submit_quiz(
        quiz_id=quiz["quizId"],
        payload=SubmitQuizRequest.model_validate(
            {"answers": [{"questionId": quiz["questions"][0]["questionId"], "selectedOption": "A"}]}
        ),
    )

    history = service.list_course_quizzes(course_id=course["courseId"])

    assert [item["quizId"] for item in history["items"]] == [quiz["quizId"]]
    item = history["items"][0]
    assert item["courseId"] == course["courseId"]
    assert item["scopeType"] == "course"
    assert item["lessonId"] is None
    assert item["status"] == "ready"
    assert item["quizMode"] == "objective"
    assert item["questionCount"] == 1
    assert item["createdAt"] is not None
    assert item["updatedAt"] is not None
    assert item["latestAttempt"]["attemptId"] == latest_attempt["attemptId"]
    assert item["latestAttempt"]["score"] == latest_attempt["score"]
    assert item["latestAttempt"]["totalScore"] == latest_attempt["totalScore"]
    assert item["latestAttempt"]["accuracy"] == latest_attempt["accuracy"]
    assert item["latestAttempt"]["attemptId"] != first_attempt["attemptId"]


def test_lesson_quiz_generation_fails_without_lesson_handout_or_resources():
    store = RuntimeStore()
    repository = MemoryScaffoldRepository(store)
    service = QuizService(
        courses=repository,
        quizzes=repository,
        idempotency=repository,
        lessons=store,
        scoped_artifacts=repository,
        handouts=repository,
        resources=repository,
    )
    course = store.create_course(
        title="Database Systems",
        entry_type="manual_import",
        goal_text="Prepare final exam",
        preferred_style="balanced",
    )
    lesson = store.create_lesson(course_id=course["courseId"], title="No Evidence Lesson")

    with pytest.raises(ServiceError) as exc_info:
        service.generate_lesson_quiz(
            course_id=course["courseId"],
            lesson_id=lesson["lessonId"],
            question_count_level="small",
        )

    assert exc_info.value.error_code == "quiz.not_ready"
    assert exc_info.value.status_code == 409


def test_lesson_quiz_generation_queues_when_lesson_handout_blocks_are_pending():
    store = RuntimeStore()
    repository = MemoryScaffoldRepository(store)
    dispatcher = RecordingDispatcher()
    service = QuizService(
        courses=repository,
        quizzes=repository,
        idempotency=repository,
        lessons=store,
        scoped_artifacts=repository,
        handouts=repository,
        resources=repository,
        task_dispatcher=dispatcher,
    )
    course = store.create_course(
        title="Database Systems",
        entry_type="manual_import",
        goal_text="Prepare final exam",
        preferred_style="balanced",
    )
    lesson = store.create_lesson(course_id=course["courseId"], title="Pending Evidence")
    _handout, _trigger, blocks = store.create_handout(
        course["courseId"],
        scope_type="lesson",
        lesson_id=lesson["lessonId"],
        artifact_kind="lesson_handout",
    )
    blocks[0].update(
        {
            "status": "pending",
            "generationStatus": "pending",
            "title": "Pending lock evidence",
            "summary": "This summary alone must not unlock a quiz.",
            "contentMd": "Two-phase locking uses growing and shrinking phases.",
            "sourceSegmentKeys": ["seg-2pl"],
            "knowledgePoints": [{"knowledgePointKey": "kp-2pl", "displayName": "Two-phase locking"}],
            "citations": [{"segmentKey": "seg-2pl", "refLabel": "lock notes"}],
        }
    )

    generated = service.generate_lesson_quiz(
        course_id=course["courseId"],
        lesson_id=lesson["lessonId"],
        question_count_level="small",
    )

    task = repository.get_async_task(generated["taskId"])
    assert generated["status"] == "queued"
    assert task["payloadJson"]["scopeType"] == "lesson"
    assert task["payloadJson"]["lessonId"] == lesson["lessonId"]
    assert dispatcher.calls == [("quiz_generate", generated["taskId"], task["payloadJson"])]


def test_lesson_quiz_generation_queues_when_ready_handout_has_only_summary_citation_or_knowledge_points():
    store = RuntimeStore()
    repository = MemoryScaffoldRepository(store)
    dispatcher = RecordingDispatcher()
    service = QuizService(
        courses=repository,
        quizzes=repository,
        idempotency=repository,
        lessons=store,
        scoped_artifacts=repository,
        handouts=repository,
        resources=repository,
        task_dispatcher=dispatcher,
    )
    course = store.create_course(
        title="Database Systems",
        entry_type="manual_import",
        goal_text="Prepare final exam",
        preferred_style="balanced",
    )
    lesson = store.create_lesson(course_id=course["courseId"], title="Summary Only")
    handout, _trigger, blocks = store.create_handout(
        course["courseId"],
        scope_type="lesson",
        lesson_id=lesson["lessonId"],
        artifact_kind="lesson_handout",
    )
    blocks[0].update(
        {
            "status": "ready",
            "generationStatus": "ready",
            "title": "Summary-only block",
            "summary": "This summary mentions indexes but has no source evidence.",
            "contentMd": "",
            "sourceSegmentKeys": ["seg-summary-only"],
            "knowledgePoints": [{"knowledgePointKey": "kp-summary", "displayName": "Summary-only concept"}],
            "citations": [{"segmentKey": "seg-summary-citation", "refLabel": "summary note"}],
        }
    )
    handout["readyBlocks"] = 1
    handout["pendingBlocks"] = max(0, handout["pendingBlocks"] - 1)

    generated = service.generate_lesson_quiz(
        course_id=course["courseId"],
        lesson_id=lesson["lessonId"],
        question_count_level="small",
    )

    task = repository.get_async_task(generated["taskId"])
    assert generated["status"] == "queued"
    assert task["payloadJson"]["scopeType"] == "lesson"
    assert task["payloadJson"]["lessonId"] == lesson["lessonId"]
    assert dispatcher.calls == [("quiz_generate", generated["taskId"], task["payloadJson"])]


def test_lesson_quiz_uses_latest_lesson_handout_block_evidence_before_resources():
    store = RuntimeStore()
    repository = MemoryScaffoldRepository(store)
    dispatcher = RecordingDispatcher()
    service = QuizService(
        courses=repository,
        quizzes=repository,
        idempotency=repository,
        lessons=store,
        scoped_artifacts=repository,
        handouts=repository,
        resources=repository,
        task_dispatcher=dispatcher,
    )
    course = store.create_course(
        title="Database Systems",
        entry_type="manual_import",
        goal_text="Prepare final exam",
        preferred_style="balanced",
    )
    lesson = store.create_lesson(course_id=course["courseId"], title="B+ Trees")
    resource = store.create_resource(
        course["courseId"],
        {
            "resourceType": "pdf",
            "sourceType": "upload",
            "objectKey": "raw/btree.pdf",
            "originalName": "btree.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 2048,
            "checksum": "sha256:btree",
            "scopeType": "lesson",
            "lessonId": lesson["lessonId"],
            "usageRole": "lesson_material",
        },
    )
    handout, _trigger, blocks = store.create_handout(
        course["courseId"],
        scope_type="lesson",
        lesson_id=lesson["lessonId"],
        artifact_kind="lesson_handout",
    )
    block = blocks[0]
    block.update(
        {
            "status": "ready",
            "generationStatus": "ready",
            "title": "B+ Tree fanout",
            "summary": "Fanout controls tree height.",
            "contentMd": "A B+ tree keeps internal nodes broad so lookup height stays small.",
            "sourceSegmentKeys": ["seg-btree-fanout"],
            "knowledgePoints": [{"knowledgePointKey": "kp-btree-fanout", "displayName": "B+ tree fanout"}],
            "citations": [
                {
                    "resourceId": resource["resourceId"],
                    "segmentKey": "seg-btree-fanout",
                    "pageNo": 7,
                    "refLabel": "btree.pdf page 7",
                }
            ],
        }
    )
    handout["readyBlocks"] = 1
    handout["pendingBlocks"] = max(0, handout["pendingBlocks"] - 1)

    generated = service.generate_lesson_quiz(
        course_id=course["courseId"],
        lesson_id=lesson["lessonId"],
        question_count_level="small",
    )

    task = repository.get_async_task(generated["taskId"])
    assert generated["status"] == "queued"
    assert task["payloadJson"]["scopeType"] == "lesson"
    assert task["payloadJson"]["lessonId"] == lesson["lessonId"]
    assert task["payloadJson"]["questionCountLevel"] == "small"
    assert dispatcher.calls == [("quiz_generate", generated["taskId"], task["payloadJson"])]


def test_lesson_quiz_generation_fails_with_unparsed_lesson_resource_metadata_only():
    store = RuntimeStore()
    repository = MemoryScaffoldRepository(store)
    service = QuizService(
        courses=repository,
        quizzes=repository,
        idempotency=repository,
        lessons=store,
        scoped_artifacts=repository,
        handouts=repository,
        resources=repository,
    )
    course = store.create_course(
        title="Operating Systems",
        entry_type="manual_import",
        goal_text="Review scheduling",
        preferred_style="balanced",
    )
    lesson = store.create_lesson(course_id=course["courseId"], title="Schedulers")
    store.create_resource(
        course["courseId"],
        {
            "resourceType": "pdf",
            "sourceType": "upload",
            "objectKey": "raw/schedulers.pdf",
            "originalName": "schedulers.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "checksum": "sha256:schedulers",
            "scopeType": "lesson",
            "lessonId": lesson["lessonId"],
            "usageRole": "lesson_material",
        },
    )

    with pytest.raises(ServiceError) as exc_info:
        service.generate_lesson_quiz(
            course_id=course["courseId"],
            lesson_id=lesson["lessonId"],
            question_count_level="small",
        )

    assert exc_info.value.error_code == "quiz.not_ready"
    assert exc_info.value.status_code == 409


def test_lesson_quiz_generation_fails_with_resource_top_level_text_or_bare_refs():
    store = RuntimeStore()
    repository = MemoryScaffoldRepository(store)
    service = QuizService(
        courses=repository,
        quizzes=repository,
        idempotency=repository,
        lessons=store,
        scoped_artifacts=repository,
        handouts=repository,
        resources=repository,
    )
    course = store.create_course(
        title="Operating Systems",
        entry_type="manual_import",
        goal_text="Review scheduling",
        preferred_style="balanced",
    )
    lesson = store.create_lesson(course_id=course["courseId"], title="Schedulers")
    resource = store.create_resource(
        course["courseId"],
        {
            "resourceType": "pdf",
            "sourceType": "upload",
            "objectKey": "raw/schedulers.pdf",
            "originalName": "schedulers.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "checksum": "sha256:schedulers",
            "scopeType": "lesson",
            "lessonId": lesson["lessonId"],
            "usageRole": "lesson_material",
        },
    )
    resource.update(
        {
            "contentMd": "Round-robin top-level content is not parsed segment evidence.",
            "textContent": "Priority scheduling top-level text is not parsed segment evidence.",
            "plainText": "Shortest-job-first top-level plain text is not parsed segment evidence.",
            "evidenceText": "Evidence text outside segments must not unlock quiz generation.",
            "sourceSegmentKeys": ["bare-resource-segment"],
            "citations": [{"segmentKey": "bare-resource-citation", "refLabel": "resource metadata"}],
        }
    )

    with pytest.raises(ServiceError) as exc_info:
        service.generate_lesson_quiz(
            course_id=course["courseId"],
            lesson_id=lesson["lessonId"],
            question_count_level="small",
        )

    assert exc_info.value.error_code == "quiz.not_ready"
    assert exc_info.value.status_code == 409


def test_quiz_question_refs_use_generated_fallback_block_key_consistently():
    blocks = [
        {
            "title": "缺少外部 block id 的讲义块",
            "summary": "仍应能通过 block-1 反查引用。",
            "sourceSegmentKeys": ["pdf-p2"],
            "knowledgePoints": [
                {
                    "knowledgePointKey": "kp-limit",
                    "displayName": "函数极限",
                    "description": "自变量趋近某点时函数值的稳定趋势。",
                    "importanceScore": 90,
                }
            ],
            "citations": [
                {"resourceId": 2, "segmentKey": "pdf-p2", "pageNo": 2, "refLabel": "PDF 第 2 页"}
            ],
        }
    ]
    payload = generate_quiz_payload(
        blocks,
        segments=_segments(),
        client=FakeQuizClient(
            {
                "quizType": "chapter_review",
                "questions": [
                    {
                        **_model_question(1),
                        "knowledgePointKey": "kp-limit",
                        "knowledgePointName": "函数极限",
                        "sourceBlockKey": "block-1",
                        "sourceSegmentKeys": ["pdf-p2"],
                    },
                    {
                        **_model_question(2),
                        "knowledgePointKey": "kp-limit",
                        "knowledgePointName": "函数极限",
                        "sourceBlockKey": "block-1",
                        "sourceSegmentKeys": ["pdf-p2"],
                    },
                    {
                        **_model_question(3),
                        "knowledgePointKey": "kp-limit",
                        "knowledgePointName": "函数极限",
                        "sourceBlockKey": "block-1",
                        "sourceSegmentKeys": ["pdf-p2"],
                    },
                ],
            }
        ),
    )

    refs = build_quiz_question_refs(payload, handout_blocks=blocks, segments=_segments())

    assert payload["questions"][0]["sourceBlockKey"] == "block-1"
    assert refs[0]["questionKey"] == payload["questions"][0]["questionKey"]
    assert refs[0]["segmentKey"] == "pdf-p2"


def _handout_blocks() -> list[dict]:
    return [
        {
            "handoutBlockId": "block-pdf",
            "title": "极限定义",
            "summary": "解释极限的直观定义。",
            "sourceSegmentKeys": ["pdf-p2"],
            "knowledgePoints": [
                {
                    "knowledgePointKey": "kp-limit",
                    "displayName": "函数极限",
                    "description": "自变量趋近某点时函数值的稳定趋势。",
                    "difficultyLevel": "advanced",
                    "importanceScore": 95,
                }
            ],
            "citations": [
                {"resourceId": 2, "segmentKey": "pdf-p2", "pageNo": 2, "refLabel": "PDF 第 2 页"}
            ],
        },
        {
            "handoutBlockId": "block-video",
            "title": "连续性的例题",
            "summary": "用例题说明连续性的判断。",
            "sourceSegmentKeys": ["mp4-c2"],
            "knowledgePoints": [
                {
                    "knowledgePointKey": "kp-continuity",
                    "displayName": "连续性",
                    "description": "函数在一点连续需要函数值和极限一致。",
                    "difficultyLevel": "intermediate",
                    "importanceScore": 88,
                }
            ],
            "citations": [
                {
                    "resourceId": 1,
                    "segmentKey": "mp4-c2",
                    "startSec": 120,
                    "endSec": 180,
                    "refLabel": "视频 02:00-03:00",
                }
            ],
        },
        {
            "handoutBlockId": "block-ppt",
            "title": "集合表示法",
            "summary": "从列举法到描述法。",
            "sourceSegmentKeys": ["ppt-s6"],
            "knowledgePoints": [
                {
                    "knowledgePointKey": "kp-set",
                    "displayName": "集合表示",
                    "description": "集合可以用列举法或描述法表示。",
                    "difficultyLevel": "beginner",
                    "importanceScore": 70,
                }
            ],
            "citations": [
                {"resourceId": 3, "segmentKey": "ppt-s6", "slideNo": 6, "refLabel": "PPT 第 6 页"}
            ],
        },
    ]


def _segments() -> list[dict]:
    return [
        {
            "segmentId": 202,
            "segmentKey": "pdf-p2",
            "resourceId": 2,
            "pageNo": 2,
            "textContent": "函数极限描述的是自变量趋近时函数值的稳定趋势。",
        },
        {
            "segmentId": 102,
            "segmentKey": "mp4-c2",
            "resourceId": 1,
            "startSec": 120,
            "endSec": 180,
            "textContent": "连续性要求函数值和极限保持一致。",
        },
        {
            "segmentId": 306,
            "segmentKey": "ppt-s6",
            "resourceId": 3,
            "slideNo": 6,
            "textContent": "集合可以用列举法或描述法表示。",
        },
    ]
