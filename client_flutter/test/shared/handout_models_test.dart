import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/shared/models/handout_models.dart';

void main() {
  test('handout models parse frozen Week 3 fields', () {
    final outline = HandoutOutlineModel.fromJson({
      'handoutVersionId': 3001,
      'title': '集合的初见',
      'summary': '按视频时间线组织的讲义目录',
      'items': [
        {
          'outlineKey': 'section-1',
          'title': '集合的概念与表示',
          'summary': '从集合定义过渡到集合表示方法',
          'startSec': 0,
          'endSec': 360,
          'sortNo': 1,
          'children': [
            {
              'outlineKey': 'outline-1',
              'blockId': 4001,
              'title': '集合的基本概念',
              'summary': '介绍集合、元素和属于关系',
              'startSec': 0,
              'endSec': 180,
              'sortNo': 1,
              'generationStatus': 'pending',
              'sourceSegmentKeys': ['mp4-c1', 'mp4-c2'],
              'topicTags': ['集合'],
            },
            {
              'outlineKey': 'outline-2',
              'blockId': 4002,
              'title': '集合的表示方法',
              'summary': '从列举法过渡到描述法',
              'startSec': 180,
              'endSec': 360,
              'sortNo': 2,
              'generationStatus': 'pending',
              'sourceSegmentKeys': ['mp4-c3'],
              'topicTags': [],
            },
          ],
        },
      ],
      'outlineUsedFallback': true,
      'outlineIssues': ['缺少章节标题，已按时间线降级分组'],
    });
    final blocks = HandoutBlocksModel.fromJson({
      'items': [
        {
          'blockId': 4001,
          'outlineKey': 'outline-1',
          'title': '极限与连续',
          'summary': '先抓必考定义和题型',
          'status': 'pending',
          'generationStatus': 'ready',
          'contentMd': '### 极限与连续',
          'startSec': 120,
          'endSec': 360,
          'pageFrom': 2,
          'pageTo': 5,
          'citations': [
            {
              'resourceId': 501,
              'refLabel': 'PDF 第 2 页',
              'pageNo': 2,
            },
          ],
        },
      ],
    });
    final status = HandoutVersionStatusModel.fromJson({
      'handoutVersionId': 3001,
      'status': 'partial_success',
      'outlineStatus': 'ready',
      'totalBlocks': 3,
      'readyBlocks': 2,
      'pendingBlocks': 1,
      'sourceParseRunId': 9001,
    });
    final blockStatus = HandoutBlockStatusModel.fromJson({
      'blockId': 4002,
      'outlineKey': 'outline-2',
      'status': 'pending',
      'generationStatus': 'generating',
      'startSec': 180,
      'endSec': 360,
    });
    final readyGenerateResult = HandoutBlockGenerateResultModel.fromJson({
      'blockId': 4002,
      'outlineKey': 'outline-2',
      'status': 'ready',
      'startSec': 180,
      'endSec': 360,
    });
    final currentBlock = CurrentHandoutBlockModel.fromJson({
      'blockId': 4002,
      'outlineKey': 'outline-2',
      'startSec': 180,
      'endSec': 360,
      'generationStatus': 'pending',
      'prefetchBlockId': 4003,
    });
    final legacyCurrentBlock = CurrentHandoutBlockModel.fromJson({
      'blockId': 4002,
      'outlineKey': 'outline-2',
      'startSec': 180,
      'endSec': 360,
      'status': 'ready',
    });

    final section = outline.items.single;
    final firstChild = section.children.first;
    expect(section.outlineKey, 'section-1');
    expect(section.children, hasLength(2));
    expect(outline.children.map((child) => child.blockId), [4001, 4002]);
    expect(outline.childForBlockId(4002)?.title, '集合的表示方法');
    expect(firstChild.sourceSegmentKeys, ['mp4-c1', 'mp4-c2']);
    expect(firstChild.topicTags, ['集合']);
    expect(outline.outlineUsedFallback, isTrue);
    expect(outline.outlineIssues.single, contains('降级分组'));
    expect(blocks.items.single.citations.single.locatorText, 'PDF 第 2 页');
    expect(blocks.items.single.status, 'ready');
    expect(blocks.items.single.generationStatus, 'ready');
    expect(blocks.items.single.containsPosition(120, isLast: false), isTrue);
    expect(blocks.items.single.containsPosition(360, isLast: false), isFalse);
    expect(blocks.items.single.containsPosition(360, isLast: true), isTrue);
    expect(status.isTerminal, isTrue);
    expect(blockStatus.status, 'generating');
    expect(blockStatus.generationStatus, 'generating');
    expect(readyGenerateResult.entity, isNull);
    expect(readyGenerateResult.blockStatus?.status, 'ready');
    expect(currentBlock.prefetchBlockId, 4003);
    expect(legacyCurrentBlock.generationStatus, 'ready');
  });

  test('QA model keeps answer citations only', () {
    final message = QaMessageModel.fromJson({
      'sessionId': 6001,
      'messageId': 6002,
      'answerMd': '定义控制了题型的判断边界。',
      'citations': [],
      'retrievedDocuments': [
        {'resourceId': 999},
      ],
    });

    expect(message.answerMd, '定义控制了题型的判断边界。');
    expect(message.citations, isEmpty);
    expect(
      const QaMessageRequestModel(
        courseId: 101,
        handoutBlockId: 4001,
        question: '这个定义和题型有什么联系？',
      ).toJson(),
      {
        'courseId': 101,
        'handoutBlockId': 4001,
        'question': '这个定义和题型有什么联系？',
      },
    );
  });

  test('QA session history parses user and assistant rows', () {
    final session = QaSessionMessagesModel.fromJson({
      'items': [
        {
          'sessionId': 6001,
          'messageId': 6001,
          'role': 'user',
          'contentMd': '这个定义和题型有什么联系？',
          'question': '这个定义和题型有什么联系？',
          'answerMd': null,
          'answerType': null,
          'citations': [],
          'createdAt': '2026-04-18T15:00:00Z',
        },
        {
          'sessionId': 6001,
          'messageId': 6002,
          'role': 'assistant',
          'contentMd': '定义控制了题型的判断边界。',
          'question': '这个定义和题型有什么联系？',
          'answerMd': '定义控制了题型的判断边界。',
          'answerType': 'direct_answer',
          'citations': [],
          'createdAt': '2026-04-18T15:00:01Z',
          'generationMetadata': {'source': 'model'},
        },
      ],
    });

    expect(session.items, hasLength(2));
    expect(session.items.first.role, 'user');
    expect(session.items.first.answerMd, '');
    expect(session.items.first.question, '这个定义和题型有什么联系？');
    expect(session.items.first.createdAt, isNotNull);
    expect(session.items.last.role, 'assistant');
    expect(session.items.last.contentMd, '定义控制了题型的判断边界。');
    expect(session.items.last.answerMd, '定义控制了题型的判断边界。');
    expect(session.items.last.generationMetadata?['source'], 'model');
  });

  test('QA session list parses scoped sessions', () {
    final sessions = QaSessionsModel.fromJson({
      'items': [
        {
          'sessionId': 7001,
          'courseId': 101,
          'scopeType': 'course',
          'lessonId': null,
          'handoutBlockId': null,
          'title': 'Course question',
          'lastMessageAt': '2026-04-18T15:02:00Z',
        },
        {
          'sessionId': 8001,
          'courseId': 101,
          'scopeType': 'lesson',
          'lessonId': 2,
          'handoutBlockId': 4001,
          'title': null,
          'lastMessageAt': null,
        },
      ],
    });

    expect(sessions.items, hasLength(2));
    expect(sessions.items.first.sessionId, 7001);
    expect(sessions.items.first.courseId, '101');
    expect(sessions.items.first.scopeType, 'course');
    expect(sessions.items.first.lessonId, isNull);
    expect(sessions.items.first.title, 'Course question');
    expect(sessions.items.first.lastMessageAt, isNotNull);
    expect(sessions.items.last.lessonId, '2');
    expect(sessions.items.last.handoutBlockId, 4001);
  });

  test('citation model covers every frozen locator group', () {
    final citations = [
      CitationModel.fromJson({
        'resourceId': 501,
        'refLabel': 'PDF 第 2 页',
        'pageNo': 2,
      }),
      CitationModel.fromJson({
        'resourceId': 502,
        'refLabel': 'PPT 第 6 页',
        'slideNo': 6,
      }),
      CitationModel.fromJson({
        'resourceId': 503,
        'refLabel': 'DOCX 锚点',
        'anchorKey': 'section-integral',
      }),
      CitationModel.fromJson({
        'resourceId': 504,
        'refLabel': '视频 2:00-3:00',
        'startSec': 120,
        'endSec': 180,
      }),
    ];
    final mixedCitation = CitationModel.fromJson({
      'resourceId': 505,
      'refLabel': '混合定位',
      'pageNo': 2,
      'slideNo': 6,
    });

    expect(citations.map((citation) => citation.hasSingleLocatorGroup), [
      true,
      true,
      true,
      true,
    ]);
    expect(citations.last.locatorText, '2:00-3:00');
    expect(mixedCitation.hasSingleLocatorGroup, isFalse);
  });
}
