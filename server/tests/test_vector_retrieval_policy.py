from server.ai.vector_projection import (
    VectorDocumentInput,
    VectorRetrievalScope,
    filter_vector_document_candidates,
    order_vector_document_candidates,
    select_vector_retrieval_candidates,
    vector_document_matches_scope,
)


SCOPE = VectorRetrievalScope(course_id=101, active_parse_run_id=9001, active_handout_version_id=7001)


def test_vector_document_scope_hard_filters_course_and_parse_run():
    docs = [
        _doc("segment", 1, course_id=101, parse_run_id=9001),
        _doc("segment", 2, course_id=202, parse_run_id=9001),
        _doc("segment", 3, course_id=101, parse_run_id=8001),
        _doc("segment", 4, course_id=None, parse_run_id=9001),
    ]

    filtered = filter_vector_document_candidates(docs, scope=SCOPE)

    assert [_owner_id(doc) for doc in filtered] == [1]


def test_handout_block_vector_documents_require_active_handout_version():
    current = _doc("handout_block", 1, course_id=101, parse_run_id=9001, handout_version_id=7001)
    old = _doc("handout_block", 2, course_id=101, parse_run_id=9001, handout_version_id=7000)
    missing = _doc("handout_block", 3, course_id=101, parse_run_id=9001, handout_version_id=None)

    assert vector_document_matches_scope(current, SCOPE)
    assert not vector_document_matches_scope(old, SCOPE)
    assert not vector_document_matches_scope(missing, SCOPE)


def test_segment_and_knowledge_point_vectors_do_not_cross_handout_versions():
    segment_with_version = _doc("segment", 1, course_id=101, parse_run_id=9001, handout_version_id=7001)
    kp_with_version = _doc("knowledge_point", 2, course_id=101, parse_run_id=9001, handout_version_id=7001)
    clean_segment = _doc("segment", 3, course_id=101, parse_run_id=9001)

    assert not vector_document_matches_scope(segment_with_version, SCOPE)
    assert not vector_document_matches_scope(kp_with_version, SCOPE)
    assert vector_document_matches_scope(clean_segment, SCOPE)


def test_vector_retrieval_orders_by_owner_type_priority_after_filtering():
    docs = [
        _doc("segment", 3, course_id=101, parse_run_id=9001),
        _doc("handout_block", 1, course_id=101, parse_run_id=9001, handout_version_id=7001),
        _doc("knowledge_point", 2, course_id=101, parse_run_id=9001),
    ]

    ordered = order_vector_document_candidates(docs)

    assert [_owner_type(doc) for doc in ordered] == ["handout_block", "knowledge_point", "segment"]


def test_vector_retrieval_selection_filters_cross_scope_and_applies_owner_priority():
    docs = [
        _doc("segment", 1, course_id=202, parse_run_id=9001),
        _doc("segment", 2, course_id=101, parse_run_id=9001),
        _doc("handout_block", 3, course_id=101, parse_run_id=9001, handout_version_id=7000),
        _doc("knowledge_point", 4, course_id=101, parse_run_id=9001),
        _doc("handout_block", 5, course_id=101, parse_run_id=9001, handout_version_id=7001),
    ]

    selected = select_vector_retrieval_candidates(docs, scope=SCOPE)

    assert [(_owner_type(doc), _owner_id(doc)) for doc in selected] == [
        ("handout_block", 5),
        ("knowledge_point", 4),
        ("segment", 2),
    ]


def test_vector_retrieval_empty_allowed_owner_types_returns_no_candidates():
    docs = [_doc("segment", 1, course_id=101, parse_run_id=9001)]

    selected = select_vector_retrieval_candidates(docs, scope=SCOPE, allowed_owner_types=set())

    assert selected == []


def test_vector_retrieval_policy_accepts_camel_case_documents():
    docs = [
        {
            "ownerType": "handout_block",
            "ownerId": 1,
            "courseId": 101,
            "parseRunId": 9001,
            "handoutVersionId": 7001,
            "contentText": "集合讲义块",
        }
    ]

    selected = select_vector_retrieval_candidates(docs, scope=SCOPE)

    assert selected == docs


def test_vector_retrieval_policy_accepts_projected_dataclass_inputs():
    docs = [
        VectorDocumentInput(
            owner_type="segment",
            owner_id=1,
            content_text="集合定义",
            metadata_json={},
            course_id=101,
            parse_run_id=9001,
        ),
        VectorDocumentInput(
            owner_type="handout_block",
            owner_id=2,
            content_text="旧讲义",
            metadata_json={},
            course_id=101,
            parse_run_id=9001,
            handout_version_id=7000,
        ),
    ]

    selected = select_vector_retrieval_candidates(docs, scope=SCOPE)

    assert len(selected) == 1
    assert selected[0].owner_id == 1


def _doc(
    owner_type,
    owner_id,
    *,
    course_id,
    parse_run_id,
    handout_version_id=None,
):
    doc = {
        "owner_type": owner_type,
        "owner_id": owner_id,
        "course_id": course_id,
        "parse_run_id": parse_run_id,
        "content_text": f"{owner_type}-{owner_id}",
        "metadata_json": {},
    }
    if handout_version_id is not None:
        doc["handout_version_id"] = handout_version_id
    return doc


def _owner_type(doc):
    return doc.owner_type if isinstance(doc, VectorDocumentInput) else doc["owner_type"]


def _owner_id(doc):
    return doc.owner_id if isinstance(doc, VectorDocumentInput) else doc["owner_id"]
