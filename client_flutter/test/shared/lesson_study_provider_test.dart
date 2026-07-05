import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/shared/models/course_lesson_models.dart'
    as lessons;
import 'package:knowlink_client/shared/models/handout_models.dart' as handouts;
import 'package:knowlink_client/shared/models/resource_upload_models.dart'
    as resources;
import 'package:knowlink_client/shared/providers/course_flow_providers.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';
import 'package:knowlink_client/shared/providers/lesson_study_provider.dart';

void main() {
  test('load reads lesson study data and selects the first outline child',
      () async {
    final fakeApiClient = _LessonStudyFakeApiClient();
    final container = _container(fakeApiClient);
    container.read(playerStateProvider.notifier).state =
        const PlayerState(positionSec: 128);

    await container.read(lessonStudyProvider.notifier).load(
          courseId: '101',
          lessonId: '42',
        );

    final state = container.read(lessonStudyProvider);
    expect(state.courseId, '101');
    expect(state.lessonId, '42');
    expect(state.lessonDetail.valueOrNull?.lesson.lessonId, '42');
    expect(state.materials.map((item) => item.resourceId), ['501', '502']);
    expect(state.latestHandout.valueOrNull?.handoutVersionId, 4200);
    expect(state.outlineChildren.map((child) => child.blockId), [4201, 4202]);
    expect(state.blocks.valueOrNull?.items.map((block) => block.blockId),
        [4202, 4201]);
    expect(state.currentBlock.valueOrNull?.blockId, 4202);
    expect(state.playback.valueOrNull?.resourceId, 501);
    expect(state.playback.valueOrNull?.playbackUrl, 'https://cdn.test/501.mp4');
    expect(state.selectedBlockId, 4201);
    expect(state.selectedBlock?.blockId, 4201);
    expect(container.read(activeBlockProvider), 4201);
    expect(container.read(activeLessonProvider)?.courseId, '101');
    expect(container.read(activeLessonProvider)?.lessonId, '42');
    expect(container.read(activeLessonProvider)?.positionSec, 128);
    expect(fakeApiClient.currentBlockRequests.single.currentSec, 128);
    expect(fakeApiClient.playbackResourceIds, [501]);
  });

  test('load keeps lesson data when lesson handout is still placeholder',
      () async {
    final fakeApiClient = _PlaceholderHandoutLessonStudyFakeApiClient();
    final container = _container(fakeApiClient);

    await container.read(lessonStudyProvider.notifier).load(
          courseId: '101',
          lessonId: '42',
        );

    final state = container.read(lessonStudyProvider);
    expect(state.lessonDetail.valueOrNull?.lesson.lessonId, '42');
    expect(state.latestHandout.valueOrNull?.status, 'placeholder');
    expect(state.outline.valueOrNull, isNull);
    expect(state.blocks.valueOrNull, isNull);
    expect(state.currentBlock.valueOrNull, isNull);
    expect(state.selectedBlockId, isNull);
    expect(container.read(activeBlockProvider), isNull);
    expect(fakeApiClient.outlineRequestCount, 0);
    expect(fakeApiClient.blocksRequestCount, 0);
    expect(fakeApiClient.currentBlockRequests, isEmpty);
  });

  test('current-block load failure keeps already loaded lesson surfaces',
      () async {
    final fakeApiClient = _CurrentBlockErrorLessonStudyFakeApiClient();
    final container = _container(fakeApiClient);

    await container.read(lessonStudyProvider.notifier).load(
          courseId: '101',
          lessonId: '42',
        );

    final state = container.read(lessonStudyProvider);
    expect(state.lessonDetail.valueOrNull?.lesson.lessonId, '42');
    expect(state.latestHandout.valueOrNull?.handoutVersionId, 4200);
    expect(state.outlineChildren.map((child) => child.blockId), [4201, 4202]);
    expect(state.blocks.valueOrNull?.items.length, 2);
    expect(state.playback.valueOrNull?.resourceId, 501);
    expect(state.currentBlock.hasError, isTrue);
    expect(state.selectedBlockId, 4201);
    expect(container.read(activeBlockProvider), 4201);
  });

  test('load uses lesson summary primaryVideoResourceId for playback fallback',
      () async {
    final fakeApiClient = _SummaryPrimaryVideoLessonStudyFakeApiClient();
    final container = _container(fakeApiClient);

    await container.read(lessonStudyProvider.notifier).load(
          courseId: '101',
          lessonId: '42',
        );

    expect(fakeApiClient.playbackResourceIds.first, 503);
    expect(container.read(lessonStudyProvider).playback.valueOrNull?.resourceId,
        503);
  });

  test('outline and materials surfaces default closed and can toggle', () {
    final fakeApiClient = _LessonStudyFakeApiClient();
    final container = _container(fakeApiClient);
    final controller = container.read(lessonStudyProvider.notifier);

    expect(container.read(lessonStudyProvider).isOutlineOpen, isFalse);
    expect(container.read(lessonStudyProvider).isMaterialsOpen, isFalse);

    controller.openOutline();
    controller.openMaterials();
    expect(container.read(lessonStudyProvider).isOutlineOpen, isTrue);
    expect(container.read(lessonStudyProvider).isMaterialsOpen, isTrue);

    controller.closeOutline();
    controller.closeMaterials();
    expect(container.read(lessonStudyProvider).isOutlineOpen, isFalse);
    expect(container.read(lessonStudyProvider).isMaterialsOpen, isFalse);
  });

  test('askQuestion sends a lesson scoped QA request for selected block',
      () async {
    final fakeApiClient = _LessonStudyFakeApiClient();
    final container = _container(fakeApiClient);

    await container.read(lessonStudyProvider.notifier).load(
          courseId: '101',
          lessonId: '42',
        );
    await container
        .read(lessonStudyProvider.notifier)
        .askQuestion('  Explain this block  ');

    final qaCall = fakeApiClient.lessonQaRequests.single;
    expect(qaCall.courseId, '101');
    expect(qaCall.lessonId, '42');
    expect(qaCall.request.scopeType, 'lesson');
    expect(qaCall.request.courseId, '101');
    expect(qaCall.request.lessonId, '42');
    expect(qaCall.request.handoutBlockId, 4201);
    expect(qaCall.request.question, 'Explain this block');
    expect(container.read(courseFlowProvider).sessionId, 6201);
    expect(
      container
          .read(lessonStudyProvider)
          .selectedBlockQaMessages
          .single
          .messageId,
      6202,
    );
  });

  test(
      'generateSelectedBlock regenerates the selected block and refreshes data',
      () async {
    final fakeApiClient = _LessonStudyFakeApiClient();
    final container = _container(fakeApiClient);

    await container.read(lessonStudyProvider.notifier).load(
          courseId: '101',
          lessonId: '42',
        );
    final accepted = await container
        .read(lessonStudyProvider.notifier)
        .generateSelectedBlock();

    expect(accepted, isTrue);
    expect(fakeApiClient.generatedBlockIds, [4201]);
    expect(fakeApiClient.outlineRequestCount, 2);
    expect(fakeApiClient.blocksRequestCount, 2);
    expect(container.read(lessonStudyProvider).blockGenerateRequest.valueOrNull,
        isNotNull);
    expect(container.read(lessonStudyProvider).selectedBlockId, 4201);
    expect(container.read(activeBlockProvider), 4201);
  });

  test('stale QA response is ignored after selecting another block', () async {
    final fakeApiClient = _DelayedQaLessonStudyFakeApiClient();
    final container = _container(fakeApiClient);

    await container.read(lessonStudyProvider.notifier).load(
          courseId: '101',
          lessonId: '42',
        );
    final pendingQa =
        container.read(lessonStudyProvider.notifier).askQuestion('slow answer');
    await fakeApiClient.qaRequested.future;

    final secondBlock = container
        .read(lessonStudyProvider)
        .blocks
        .valueOrNull!
        .items
        .singleWhere((block) => block.blockId == 4202);
    container.read(lessonStudyProvider.notifier).selectBlock(secondBlock);
    fakeApiClient.qaResponse.complete(
      handouts.QaMessageModel.fromJson({
        'sessionId': 6201,
        'messageId': 6299,
        'answerMd': 'stale answer',
        'citations': [],
      }),
    );
    await pendingQa;

    final state = container.read(lessonStudyProvider);
    expect(state.selectedBlockId, 4202);
    expect(state.selectedBlockQaMessages, isEmpty);
    expect(state.qaMessagesByBlockId, isEmpty);
    expect(state.qaSubmit.isLoading, isFalse);
    expect(container.read(activeBlockProvider), 4202);
    expect(container.read(courseFlowProvider).sessionId, isNull);
  });

  test('stale current-block response is ignored and does not stay loading',
      () async {
    final fakeApiClient = _DelayedCurrentBlockLessonStudyFakeApiClient();
    final container = _container(fakeApiClient);

    await container.read(lessonStudyProvider.notifier).load(
          courseId: '101',
          lessonId: '42',
        );
    final pendingCurrent = container
        .read(lessonStudyProvider.notifier)
        .syncCurrentBlockFromPosition(positionSec: 130);
    await fakeApiClient.currentBlockRequested.future;

    final secondBlock = container
        .read(lessonStudyProvider)
        .blocks
        .valueOrNull!
        .items
        .singleWhere((block) => block.blockId == 4202);
    container.read(lessonStudyProvider.notifier).selectBlock(secondBlock);
    fakeApiClient.currentBlockResponse.complete(
      handouts.CurrentHandoutBlockModel.fromJson({
        'blockId': 4201,
        'outlineKey': 'block-42-a',
        'startSec': 0,
        'endSec': 120,
        'generationStatus': 'ready',
      }),
    );
    await pendingCurrent;

    final state = container.read(lessonStudyProvider);
    expect(state.selectedBlockId, 4202);
    expect(state.currentBlock.isLoading, isFalse);
    expect(state.currentBlock.valueOrNull, isNull);
    expect(container.read(activeBlockProvider), 4202);
  });

  test('stale load response cannot overwrite a newer lesson', () async {
    final fakeApiClient = _DelayedLoadLessonStudyFakeApiClient();
    final container = _container(fakeApiClient);

    final staleLoad = container.read(lessonStudyProvider.notifier).load(
          courseId: '101',
          lessonId: '42',
        );
    await fakeApiClient.oldLessonRequested.future;

    await container.read(lessonStudyProvider.notifier).load(
          courseId: '101',
          lessonId: '43',
        );
    fakeApiClient.oldLessonDetail.complete(
      lessons.LessonDetailModel.fromJson(_lessonDetailJson(lessonId: '42')),
    );
    await staleLoad;

    final state = container.read(lessonStudyProvider);
    expect(state.courseId, '101');
    expect(state.lessonId, '43');
    expect(state.lessonDetail.valueOrNull?.lesson.lessonId, '43');
    expect(state.latestHandout.valueOrNull?.handoutVersionId, 4300);
    expect(state.selectedBlockId, 4301);
    expect(container.read(activeBlockProvider), 4301);
    expect(container.read(activeLessonProvider)?.lessonId, '43');
  });
}

ProviderContainer _container(ApiClient apiClient) {
  final container = ProviderContainer(
    overrides: [
      apiClientProvider.overrideWithValue(apiClient),
    ],
  );
  addTearDown(container.dispose);
  final subscription = container.listen(lessonStudyProvider, (_, __) {});
  addTearDown(subscription.close);
  return container;
}

class _LessonStudyFakeApiClient extends ApiClient {
  final lessonQaRequests = <_LessonQaCall>[];
  final currentBlockRequests = <_CurrentBlockCall>[];
  final playbackResourceIds = <int>[];
  final generatedBlockIds = <int>[];
  var outlineRequestCount = 0;
  var blocksRequestCount = 0;

  @override
  Future<lessons.LessonDetailModel> fetchLessonDetail({
    required String courseId,
    required String lessonId,
  }) async {
    return lessons.LessonDetailModel.fromJson(
      _lessonDetailJson(courseId: courseId, lessonId: lessonId),
    );
  }

  @override
  Future<handouts.HandoutLatestModel> fetchLessonHandout({
    required String courseId,
    required String lessonId,
  }) async {
    return handouts.HandoutLatestModel.fromJson(
      _latestHandoutJson(lessonId: lessonId),
    );
  }

  @override
  Future<handouts.HandoutOutlineModel> fetchLessonHandoutOutline({
    required String courseId,
    required String lessonId,
  }) async {
    outlineRequestCount++;
    return handouts.HandoutOutlineModel.fromJson(
      _outlineJson(lessonId: lessonId),
    );
  }

  @override
  Future<handouts.HandoutBlocksModel> fetchLessonHandoutBlocks({
    required String courseId,
    required String lessonId,
  }) async {
    blocksRequestCount++;
    return handouts.HandoutBlocksModel.fromJson(
      _blocksJson(lessonId: lessonId),
    );
  }

  @override
  Future<handouts.HandoutBlockGenerateResultModel> generateHandoutBlock({
    required int blockId,
    required String idempotencyKey,
  }) async {
    generatedBlockIds.add(blockId);
    return handouts.HandoutBlockGenerateResultModel.fromJson({
      'blockId': blockId,
      'outlineKey': 'block-42-a',
      'status': 'ready',
      'generationStatus': 'ready',
      'startSec': 0,
      'endSec': 120,
    });
  }

  @override
  Future<handouts.CurrentHandoutBlockModel> fetchLessonCurrentHandoutBlock({
    required String courseId,
    required String lessonId,
    required int currentSec,
  }) async {
    currentBlockRequests.add(
      _CurrentBlockCall(
        courseId: courseId,
        lessonId: lessonId,
        currentSec: currentSec,
      ),
    );
    return handouts.CurrentHandoutBlockModel.fromJson(
      _currentBlockJson(lessonId: lessonId),
    );
  }

  @override
  Future<resources.CourseResourcePlaybackModel> fetchCourseResourcePlayback(
    int resourceId,
  ) async {
    playbackResourceIds.add(resourceId);
    return resources.CourseResourcePlaybackModel.fromJson({
      'resourceId': resourceId,
      'resourceType': 'mp4',
      'playbackUrl': 'https://cdn.test/$resourceId.mp4',
      'mimeType': 'video/mp4',
      'expiresAt': '2026-07-05T12:00:00Z',
      'durationSec': 600,
    });
  }

  @override
  Future<handouts.QaMessageModel> createLessonQaMessage({
    required String courseId,
    required String lessonId,
    required handouts.ScopedQaMessageRequestModel request,
  }) async {
    lessonQaRequests.add(
      _LessonQaCall(
        courseId: courseId,
        lessonId: lessonId,
        request: request,
      ),
    );
    return handouts.QaMessageModel.fromJson({
      'sessionId': 6201,
      'messageId': 6202,
      'answerMd': 'Answer for ${request.handoutBlockId}',
      'citations': [],
    });
  }
}

class _DelayedQaLessonStudyFakeApiClient extends _LessonStudyFakeApiClient {
  final qaRequested = Completer<void>();
  final qaResponse = Completer<handouts.QaMessageModel>();

  @override
  Future<handouts.QaMessageModel> createLessonQaMessage({
    required String courseId,
    required String lessonId,
    required handouts.ScopedQaMessageRequestModel request,
  }) {
    lessonQaRequests.add(
      _LessonQaCall(
        courseId: courseId,
        lessonId: lessonId,
        request: request,
      ),
    );
    qaRequested.complete();
    return qaResponse.future;
  }
}

class _PlaceholderHandoutLessonStudyFakeApiClient
    extends _LessonStudyFakeApiClient {
  @override
  Future<handouts.HandoutLatestModel> fetchLessonHandout({
    required String courseId,
    required String lessonId,
  }) async {
    return handouts.HandoutLatestModel.fromJson({
      'scopeType': 'lesson',
      'lessonId': int.parse(lessonId),
      'artifactKind': 'lesson_handout',
      'status': 'placeholder',
      'canGenerate': true,
      'requiredSources': [],
      'message': 'Not generated',
    });
  }
}

class _CurrentBlockErrorLessonStudyFakeApiClient
    extends _LessonStudyFakeApiClient {
  @override
  Future<handouts.CurrentHandoutBlockModel> fetchLessonCurrentHandoutBlock({
    required String courseId,
    required String lessonId,
    required int currentSec,
  }) async {
    currentBlockRequests.add(
      _CurrentBlockCall(
        courseId: courseId,
        lessonId: lessonId,
        currentSec: currentSec,
      ),
    );
    throw StateError('current block unavailable');
  }
}

class _SummaryPrimaryVideoLessonStudyFakeApiClient
    extends _LessonStudyFakeApiClient {
  @override
  Future<lessons.LessonDetailModel> fetchLessonDetail({
    required String courseId,
    required String lessonId,
  }) async {
    final json = _lessonDetailJson(courseId: courseId, lessonId: lessonId);
    json['primaryVideo'] = null;
    (json['lesson'] as Map<String, dynamic>)['primaryVideoResourceId'] = '503';
    return lessons.LessonDetailModel.fromJson(json);
  }
}

class _DelayedCurrentBlockLessonStudyFakeApiClient
    extends _LessonStudyFakeApiClient {
  final currentBlockRequested = Completer<void>();
  final currentBlockResponse = Completer<handouts.CurrentHandoutBlockModel>();

  @override
  Future<handouts.CurrentHandoutBlockModel> fetchLessonCurrentHandoutBlock({
    required String courseId,
    required String lessonId,
    required int currentSec,
  }) {
    if (currentBlockRequests.isEmpty) {
      return super.fetchLessonCurrentHandoutBlock(
        courseId: courseId,
        lessonId: lessonId,
        currentSec: currentSec,
      );
    }
    currentBlockRequests.add(
      _CurrentBlockCall(
        courseId: courseId,
        lessonId: lessonId,
        currentSec: currentSec,
      ),
    );
    currentBlockRequested.complete();
    return currentBlockResponse.future;
  }
}

class _DelayedLoadLessonStudyFakeApiClient extends _LessonStudyFakeApiClient {
  final oldLessonRequested = Completer<void>();
  final oldLessonDetail = Completer<lessons.LessonDetailModel>();

  @override
  Future<lessons.LessonDetailModel> fetchLessonDetail({
    required String courseId,
    required String lessonId,
  }) {
    if (lessonId == '42') {
      oldLessonRequested.complete();
      return oldLessonDetail.future;
    }
    return super.fetchLessonDetail(courseId: courseId, lessonId: lessonId);
  }
}

class _LessonQaCall {
  const _LessonQaCall({
    required this.courseId,
    required this.lessonId,
    required this.request,
  });

  final String courseId;
  final String lessonId;
  final handouts.ScopedQaMessageRequestModel request;
}

class _CurrentBlockCall {
  const _CurrentBlockCall({
    required this.courseId,
    required this.lessonId,
    required this.currentSec,
  });

  final String courseId;
  final String lessonId;
  final int currentSec;
}

Map<String, dynamic> _lessonDetailJson({
  String courseId = '101',
  required String lessonId,
}) {
  return {
    'lesson': {
      'lessonId': lessonId,
      'courseId': courseId,
      'title': 'Lesson $lessonId',
      'orderIndex': lessonId == '43' ? 2 : 1,
      'lessonStatus': 'ready',
      'handoutStatus': 'ready',
      'quizStatus': 'not_generated',
      'reviewStatus': 'not_due',
      'lastPositionSec': 12,
    },
    'primaryVideo': {
      'resourceId': '501',
      'resourceType': 'video',
      'originalName': 'lesson-$lessonId.mp4',
      'durationSec': 600,
    },
    'lessonResources': [
      {
        'resourceId': '501',
        'courseId': courseId,
        'lessonId': lessonId,
        'resourceType': 'video',
        'originalName': 'lesson-$lessonId.mp4',
        'scopeType': 'lesson',
        'usageRole': 'primary_video',
        'visibleToCourseQa': true,
        'durationSec': 600,
        'sortOrder': 0,
      },
      {
        'resourceId': '502',
        'courseId': courseId,
        'lessonId': lessonId,
        'resourceType': 'pdf',
        'originalName': 'lesson-$lessonId.pdf',
        'scopeType': 'lesson',
        'usageRole': 'supplement',
        'visibleToCourseQa': true,
        'sortOrder': 1,
      },
    ],
    'artifactSummaries': [],
    'progress': {
      'lastPositionSec': 12,
      'masteryScore': 0.6,
    },
    'citations': [],
    'sourceOverview': {},
    'knowledgePointPlaceholders': [],
    'weaknessPlaceholders': [],
  };
}

Map<String, dynamic> _latestHandoutJson({required String lessonId}) {
  final versionId = lessonId == '43' ? 4300 : 4200;
  return {
    'handoutVersionId': versionId,
    'title': 'Lesson $lessonId handout',
    'summary': 'Summary for lesson $lessonId',
    'totalBlocks': lessonId == '43' ? 1 : 2,
    'status': 'ready',
  };
}

Map<String, dynamic> _outlineJson({required String lessonId}) {
  if (lessonId == '43') {
    return {
      'handoutVersionId': 4300,
      'title': 'Lesson 43 handout',
      'summary': 'Summary for lesson 43',
      'items': [
        {
          'outlineKey': 'section-43',
          'title': 'Section 43',
          'summary': '',
          'startSec': 0,
          'endSec': 120,
          'sortNo': 1,
          'children': [
            _outlineChildJson(
              blockId: 4301,
              outlineKey: 'block-43-a',
              startSec: 0,
              endSec: 120,
              title: 'Newer lesson block',
            ),
          ],
        },
      ],
      'outlineUsedFallback': false,
      'outlineIssues': [],
    };
  }

  return {
    'handoutVersionId': 4200,
    'title': 'Lesson 42 handout',
    'summary': 'Summary for lesson 42',
    'items': [
      {
        'outlineKey': 'section-42',
        'title': 'Section 42',
        'summary': '',
        'startSec': 0,
        'endSec': 240,
        'sortNo': 1,
        'children': [
          _outlineChildJson(
            blockId: 4201,
            outlineKey: 'block-42-a',
            startSec: 0,
            endSec: 120,
            title: 'First outline child',
          ),
          _outlineChildJson(
            blockId: 4202,
            outlineKey: 'block-42-b',
            startSec: 120,
            endSec: 240,
            title: 'Second outline child',
          ),
        ],
      },
    ],
    'outlineUsedFallback': false,
    'outlineIssues': [],
  };
}

Map<String, dynamic> _outlineChildJson({
  required int blockId,
  required String outlineKey,
  required int startSec,
  required int endSec,
  required String title,
}) {
  return {
    'outlineKey': outlineKey,
    'blockId': blockId,
    'title': title,
    'summary': '',
    'startSec': startSec,
    'endSec': endSec,
    'sortNo': blockId,
    'generationStatus': 'ready',
    'sourceSegmentKeys': ['segment-$blockId'],
    'topicTags': ['topic-$blockId'],
  };
}

Map<String, dynamic> _blocksJson({required String lessonId}) {
  if (lessonId == '43') {
    return {
      'items': [
        _blockJson(
          blockId: 4301,
          outlineKey: 'block-43-a',
          startSec: 0,
          endSec: 120,
          title: 'Newer lesson block',
        ),
      ],
    };
  }

  return {
    'items': [
      _blockJson(
        blockId: 4202,
        outlineKey: 'block-42-b',
        startSec: 120,
        endSec: 240,
        title: 'Second outline child',
      ),
      _blockJson(
        blockId: 4201,
        outlineKey: 'block-42-a',
        startSec: 0,
        endSec: 120,
        title: 'First outline child',
      ),
    ],
  };
}

Map<String, dynamic> _blockJson({
  required int blockId,
  required String outlineKey,
  required int startSec,
  required int endSec,
  required String title,
}) {
  return {
    'blockId': blockId,
    'outlineKey': outlineKey,
    'title': title,
    'summary': '',
    'status': 'ready',
    'contentMd': '### $title',
    'startSec': startSec,
    'endSec': endSec,
    'citations': [],
  };
}

Map<String, dynamic> _currentBlockJson({required String lessonId}) {
  if (lessonId == '43') {
    return {
      'blockId': 4301,
      'outlineKey': 'block-43-a',
      'startSec': 0,
      'endSec': 120,
      'generationStatus': 'ready',
    };
  }

  return {
    'blockId': 4202,
    'outlineKey': 'block-42-b',
    'startSec': 120,
    'endSec': 240,
    'generationStatus': 'ready',
  };
}
