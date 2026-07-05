// ignore_for_file: depend_on_referenced_packages

import 'dart:typed_data';

import 'package:file_selector_platform_interface/file_selector_platform_interface.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/course_workbench/course_workbench_page.dart';
import 'package:knowlink_client/shared/models/course_lesson_models.dart';
import 'package:knowlink_client/shared/models/handout_models.dart';
import 'package:knowlink_client/shared/models/pipeline_status.dart';
import 'package:knowlink_client/shared/models/resource_upload_models.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('course workbench follows the Soft UI workspace layout',
      (tester) async {
    _useTestSurface(tester, const Size(1200, 1600));
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(_CourseWorkbenchFakeApiClient()),
        ],
        child: const MaterialApp(
          home: CourseWorkbenchPage(courseId: '101'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.widgetWithText(OutlinedButton, '返回课程库'), findsOneWidget);
    expect(find.text('数据库系统'), findsOneWidget);
    final primaryActions =
        find.byKey(const Key('course_workbench_primary_entries'));
    expect(primaryActions, findsOneWidget);
    expect(
      find.descendant(of: primaryActions, matching: find.text('问 AI')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: primaryActions, matching: find.text('新建课时')),
      findsOneWidget,
    );
    expect(find.text('课程资料'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, '上传资料'), findsOneWidget);
    expect(find.text('数据库教材.pdf'), findsOneWidget);
    expect(find.text('课程测试'), findsOneWidget);
    expect(find.text('题目数量'), findsOneWidget);
    expect(find.text('2 / 6'), findsOneWidget);
    expect(find.text('正确率'), findsOneWidget);
    expect(find.text('72%'), findsOneWidget);
    final quizActions =
        find.byKey(const Key('course_workbench_secondary_entries'));
    expect(quizActions, findsOneWidget);
    expect(
      find.descendant(of: quizActions, matching: find.text('开始课程测试')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: quizActions, matching: find.text('重新生成课程测试')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: quizActions, matching: find.text('历史课程测试')),
      findsOneWidget,
    );
    expect(find.text('课时'), findsOneWidget);
    expect(find.text('关系模型'), findsWidgets);
    expect(find.text('64%'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, '继续学习'), findsOneWidget);
    expect(find.text('正在学习'), findsNothing);
    expect(find.text('课时列表'), findsNothing);
    expect(find.text('主要入口'), findsNothing);
    expect(find.text('更多工具'), findsNothing);
    expect(find.text('课程图谱'), findsNothing);
    expect(find.text('学习报告'), findsNothing);
    expect(find.text('课程导出'), findsNothing);
    expect(find.text('课程设置'), findsNothing);
    expect(find.text('全课程 QA'), findsNothing);
    expect(find.text('课程总复习'), findsNothing);
    expect(find.text('课程级讲义工作台'), findsNothing);
  });

  testWidgets('workspace title actions keep routed course behavior',
      (tester) async {
    _useTestSurface(tester, const Size(1200, 1600));
    final router = _workbenchRouter();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(
          _CourseWorkbenchFakeApiClient(
            quickEntries: [
              {
                'key': 'lesson_study',
                'title': 'Lesson study',
                'status': 'ready',
                'enabled': true,
                'route': '/courses/101/lessons/42/handout',
                'target': '/courses/101/lessons/42',
                'action': 'open_lesson_study',
                'message': 'Continue the current lesson',
              },
            ],
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    final primaryActions =
        find.byKey(const Key('course_workbench_primary_entries'));
    await tester.tap(
      find.descendant(of: primaryActions, matching: find.text('问 AI')),
    );
    await tester.pumpAndSettle();

    expect(find.text('qa-route 101'), findsOneWidget);
    expect(find.text('review-route 101'), findsNothing);
  });

  testWidgets('new lesson action creates lesson, prepares content, and routes',
      (tester) async {
    _useTestSurface(tester, const Size(1200, 1600));
    final router = _workbenchRouter();
    final fakeApiClient = _CourseWorkbenchFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    final primaryActions =
        find.byKey(const Key('course_workbench_primary_entries'));
    await tester.tap(
      find.descendant(of: primaryActions, matching: find.text('新建课时')),
    );
    await tester.pumpAndSettle();

    expect(find.text('新建课时'), findsWidgets);
    expect(find.text('课时名称'), findsOneWidget);
    expect(find.text('上传资料'), findsWidgets);
    expect(find.text('导入 B 站链接'), findsOneWidget);
    expect(find.text('学习目标'), findsOneWidget);
    expect(find.text('当前掌握程度'), findsOneWidget);
    expect(find.text('时间预算'), findsOneWidget);

    await tester.enterText(find.byType(TextField).first, '事务与并发控制');
    await tester.tap(find.widgetWithText(FilledButton, '创建课时'));
    await tester.pumpAndSettle();

    expect(fakeApiClient.createdLessonRequests, hasLength(1));
    expect(fakeApiClient.createdLessonRequests.single['title'], '事务与并发控制');
    expect(fakeApiClient.createdLessonRequests.single['sourceType'], 'manual');
    expect(fakeApiClient.startedParseCourseIds, ['101']);
    expect(fakeApiClient.fetchPipelineStatusCount, greaterThanOrEqualTo(1));
    expect(fakeApiClient.generatedLessonHandouts, ['101/l-new']);
    expect(
        fakeApiClient.fetchHandoutVersionStatusCount, greaterThanOrEqualTo(1));
    expect(find.text('lesson-handout-route 101 l-new'), findsOneWidget);
  });

  testWidgets(
      'new lesson shows preparation animation until parse and outline finish',
      (tester) async {
    _useTestSurface(tester, const Size(1200, 1600));
    final previousFileSelector = FileSelectorPlatform.instance;
    FileSelectorPlatform.instance = _CourseWorkbenchFakeFileSelector([
      XFile.fromData(
        Uint8List.fromList([1, 2, 3, 4]),
        path: r'C:\fake\并发控制讲义.pdf',
        name: '并发控制讲义.pdf',
        mimeType: 'application/pdf',
      ),
    ]);
    addTearDown(() {
      FileSelectorPlatform.instance = previousFileSelector;
    });

    final router = _workbenchRouter();
    final fakeApiClient = _CourseWorkbenchFakeApiClient(
      pipelineStatuses: [
        _pipelineStatusJson(
          pipelineStatus: 'running',
          stepStatuses: {
            'caption_extract': 'skipped',
            'document_parse': 'running',
            'knowledge_extract': 'queued',
          },
          progressPct: 40,
        ),
        _pipelineStatusJson(
          pipelineStatus: 'succeeded',
          stepStatuses: {
            'caption_extract': 'skipped',
            'document_parse': 'succeeded',
            'knowledge_extract': 'succeeded',
          },
          progressPct: 100,
          outlineReady: true,
        ),
      ],
    );
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    final primaryActions =
        find.byKey(const Key('course_workbench_primary_entries'));
    await tester.tap(
      find.descendant(of: primaryActions, matching: find.text('新建课时')),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(OutlinedButton, '上传资料'));
    await tester.pumpAndSettle();
    expect(find.text('并发控制讲义.pdf'), findsOneWidget);

    await tester.enterText(find.byType(TextField).first, '事务与并发控制');
    await tester.tap(find.widgetWithText(FilledButton, '创建课时'));
    await tester.pump(const Duration(milliseconds: 120));
    await tester.pump();
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 360));

    expect(find.text('正在准备课时'), findsOneWidget);
    expect(find.textContaining('%'), findsWidgets);
    final preparationSteps = find.byKey(const Key('lesson_preparation_steps'));
    expect(preparationSteps, findsOneWidget);
    expect(
      find.descendant(of: preparationSteps, matching: find.text('上传资料')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: preparationSteps, matching: find.text('解析资料')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: preparationSteps, matching: find.text('生成学习目录')),
      findsOneWidget,
    );
    expect(find.byKey(const Key('lesson_preparation_loader')), findsOneWidget);

    await tester.pump(const Duration(seconds: 3));
    await tester.pumpAndSettle();

    expect(fakeApiClient.uploadInitRequests, hasLength(1));
    expect(fakeApiClient.uploadInitRequests.single.scopeType, 'lesson');
    expect(fakeApiClient.uploadInitRequests.single.lessonId, 'l-new');
    expect(
        fakeApiClient.uploadInitRequests.single.usageRole, 'lesson_material');
    expect(fakeApiClient.uploadedObjectUrls, hasLength(1));
    expect(fakeApiClient.completedUploads, hasLength(1));
    expect(fakeApiClient.completedUploads.single.scopeType, 'lesson');
    expect(fakeApiClient.completedUploads.single.lessonId, 'l-new');
    expect(fakeApiClient.completedUploads.single.originalName, '并发控制讲义.pdf');
    expect(fakeApiClient.startedParseCourseIds, ['101']);
    expect(fakeApiClient.fetchPipelineStatusCount, greaterThanOrEqualTo(2));
    expect(fakeApiClient.generatedLessonHandouts, ['101/l-new']);
    expect(
        fakeApiClient.fetchHandoutVersionStatusCount, greaterThanOrEqualTo(1));
    expect(find.text('lesson-handout-route 101 l-new'), findsOneWidget);
  });

  testWidgets('lesson tile opens the lesson handout route', (tester) async {
    _useTestSurface(tester, const Size(1200, 1600));
    final router = _workbenchRouter();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(_CourseWorkbenchFakeApiClient()),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('关系模型').last);
    await tester.pumpAndSettle();

    expect(find.text('lesson-handout-route 101 l-2'), findsOneWidget);
    expect(find.text('lesson-root-route 101 l-2'), findsNothing);
  });

  testWidgets('workspace quiz and back actions use existing routes',
      (tester) async {
    _useTestSurface(tester, const Size(1200, 1600));
    final router = _workbenchRouter();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(
          _CourseWorkbenchFakeApiClient(
            quickEntries: [
              {
                'key': 'report',
                'title': 'Disabled report',
                'status': 'placeholder',
                'route': '/courses/101/review?kind=report',
                'target': '/courses/101/review',
                'action': 'open_report',
                'message': 'Report is not ready',
              },
            ],
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    final quizButton = find.widgetWithText(FilledButton, '开始课程测试');
    expect(quizButton, findsOneWidget);

    await tester.tap(quizButton);
    await tester.pumpAndSettle();

    expect(find.text('quiz-route 101'), findsOneWidget);

    router.go('/courses/101');
    await tester.pumpAndSettle();

    final backButton = find.widgetWithText(OutlinedButton, '返回课程库');
    await tester.tap(backButton);
    await tester.pumpAndSettle();

    expect(find.text('library-route'), findsOneWidget);
  });
}

void _useTestSurface(WidgetTester tester, Size size) {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

GoRouter _workbenchRouter() {
  return GoRouter(
    initialLocation: '/courses/101',
    routes: [
      GoRoute(
        path: '/courses/:courseId',
        builder: (context, state) => CourseWorkbenchPage(
          courseId: state.pathParameters['courseId']!,
        ),
      ),
      GoRoute(
        path: '/courses',
        builder: (context, state) => const Text('library-route'),
      ),
      GoRoute(
        path: '/courses/:courseId/qa',
        builder: (context, state) =>
            Text('qa-route ${state.pathParameters['courseId']}'),
      ),
      GoRoute(
        path: '/courses/:courseId/quiz',
        builder: (context, state) =>
            Text('quiz-route ${state.pathParameters['courseId']}'),
      ),
      GoRoute(
        path: '/courses/:courseId/lessons/:lessonId/preparing',
        builder: (context, state) => LessonPreparationPage(
          courseId: state.pathParameters['courseId']!,
          lessonId: state.pathParameters['lessonId']!,
          payload: state.extra is LessonPreparationPayload
              ? state.extra! as LessonPreparationPayload
              : null,
        ),
      ),
      GoRoute(
        path: '/courses/:courseId/lessons/:lessonId/handout',
        builder: (context, state) => Text(
          'lesson-handout-route '
          '${state.pathParameters['courseId']} '
          '${state.pathParameters['lessonId']}',
        ),
      ),
      GoRoute(
        path: '/courses/:courseId/lessons/:lessonId',
        builder: (context, state) => Text(
          'lesson-root-route '
          '${state.pathParameters['courseId']} '
          '${state.pathParameters['lessonId']}',
        ),
      ),
      GoRoute(
        path: '/courses/:courseId/review',
        builder: (context, state) =>
            Text('review-route ${state.pathParameters['courseId']}'),
      ),
    ],
  );
}

class _CourseWorkbenchFakeApiClient extends ApiClient {
  _CourseWorkbenchFakeApiClient({
    this.quickEntries,
    List<Map<String, dynamic>>? pipelineStatuses,
  }) : _pipelineStatuses = pipelineStatuses ?? [_pipelineStatusJson()];

  final List<Map<String, dynamic>>? quickEntries;
  final List<Map<String, dynamic>> _pipelineStatuses;
  final createdLessonRequests = <Map<String, dynamic>>[];
  final uploadInitRequests = <ResourceUploadInitRequestModel>[];
  final uploadedObjectUrls = <String>[];
  final completedUploads = <ResourceUploadCompleteRequestModel>[];
  final startedParseCourseIds = <String>[];
  final generatedLessonHandouts = <String>[];
  var fetchPipelineStatusCount = 0;
  var fetchHandoutVersionStatusCount = 0;

  @override
  Future<CourseWorkbenchModel> fetchCourseWorkbench(String courseId) async {
    return CourseWorkbenchModel.fromJson({
      'course': {
        'courseId': courseId,
        'title': '数据库系统',
        'isCurrent': true,
        'entryType': 'bilibili',
        'learningStatus': 'learning_ready',
        'lastActivityAt': '2026-06-01T09:30:00+08:00',
        'lessonCount': 6,
        'courseResourceCount': 3,
        'currentLessonId': 'l-2',
        'currentLessonTitle': '关系模型',
        'overallMasteryScore': 0.72,
        'pendingReviewCount': 4,
        'pipelineStage': 'handout',
        'pipelineStatus': 'running',
        'lifecycleStatus': 'learning_ready',
        'archivedAt': null,
      },
      'progress': {
        'completedLessonCount': 2,
        'totalLessonCount': 6,
        'progressPct': 33,
        'lastPositionSec': 125,
      },
      'currentLesson': _lesson(),
      'lessons': [_lesson()],
      'courseResources': [
        {
          'resourceId': 501,
          'courseId': courseId,
          'resourceType': 'pdf',
          'originalName': '数据库教材.pdf',
          'scopeType': 'course',
          'lessonId': null,
          'usageRole': 'course_material',
          'visibleToCourseQa': true,
          'durationSec': null,
          'sortOrder': 1,
        },
      ],
      'quickEntries': quickEntries ??
          [
            {
              'key': 'course_qa',
              'title': '全课程 QA',
              'status': 'ready',
              'message': '基于全部课时提问',
            },
            {
              'key': 'course_graph',
              'title': '课程图谱',
              'status': 'placeholder',
              'message': '图谱生成暂未启用',
            },
            {
              'key': 'course_quiz',
              'title': '课程测试',
              'status': 'placeholder',
              'message': '课程测试等待生成',
            },
            {
              'key': 'course_review',
              'title': '课程总复习',
              'status': 'generating',
              'message': '复习计划生成中',
            },
            {
              'key': 'course_summary_handout',
              'title': '课程级讲义工作台',
              'status': 'ready',
              'message': '整课讲义入口',
            },
            {
              'key': 'report',
              'title': '学习报告',
              'status': 'placeholder',
              'message': '报告暂未启用',
            },
            {
              'key': 'export',
              'title': '课程导出',
              'status': 'placeholder',
              'message': '导出暂未启用',
            },
            {
              'key': 'settings',
              'title': '课程设置',
              'status': 'ready',
              'message': '调整课程信息',
            },
          ],
      'nextActions': [
        {
          'type': 'continue_lesson',
          'lessonId': 'l-2',
          'title': '关系模型',
        },
      ],
      'placeholderStates': {},
    });
  }

  @override
  Future<LessonSummaryModel> createLesson({
    required String courseId,
    required Map<String, dynamic> request,
    String? idempotencyKey,
  }) async {
    createdLessonRequests.add(request);
    return LessonSummaryModel.fromJson({
      'lessonId': 'l-new',
      'courseId': courseId,
      'title': request['title'],
      'orderIndex': 7,
      'lessonStatus': 'draft',
      'primaryVideoResourceId': null,
      'primaryVideoStartSec': null,
      'primaryVideoEndSec': null,
      'handoutStatus': 'not_generated',
      'quizStatus': 'not_generated',
      'reviewStatus': 'not_due',
      'masteryScore': null,
      'lastPositionSec': null,
      'lastActivityAt': null,
      'nextAction': null,
    });
  }

  Map<String, dynamic> _lesson() {
    return {
      'lessonId': 'l-2',
      'courseId': 101,
      'title': '关系模型',
      'orderIndex': 2,
      'lessonStatus': 'learning_ready',
      'primaryVideoResourceId': 601,
      'primaryVideoStartSec': 0,
      'primaryVideoEndSec': 1800,
      'handoutStatus': 'ready',
      'quizStatus': 'not_generated',
      'reviewStatus': 'due',
      'masteryScore': 0.64,
      'lastPositionSec': 125,
      'lastActivityAt': '2026-06-01T09:30:00+08:00',
      'nextAction': {
        'type': 'resume_video',
        'label': '继续看视频',
        'route': '/courses/101/lessons/l-2',
        'reason': '上次看到 02:05',
      },
    };
  }

  @override
  Future<ResourceUploadInitResultModel> initResourceUpload({
    required String courseId,
    required ResourceUploadInitRequestModel request,
  }) async {
    uploadInitRequests.add(request);
    return ResourceUploadInitResultModel(
      uploadUrl: 'https://minio.test/upload/${request.filename}',
      objectKey: 'raw/$courseId/${request.filename}',
      headers: const {'x-amz-meta-course-id': '101'},
      expiresAt: DateTime.parse('2026-04-18T15:15:00+00:00'),
    );
  }

  @override
  Future<void> uploadObject({
    required String uploadUrl,
    required Uint8List bytes,
    required Map<String, String> headers,
    required String mimeType,
  }) async {
    uploadedObjectUrls.add(uploadUrl);
  }

  @override
  Future<CourseResourceModel> completeResourceUpload({
    required String courseId,
    required ResourceUploadCompleteRequestModel request,
    required String idempotencyKey,
  }) async {
    completedUploads.add(request);
    return CourseResourceModel.fromJson({
      'resourceId': 701,
      'resourceType': request.resourceType.name,
      'originalName': request.originalName,
      'objectKey': request.objectKey,
      'ingestStatus': 'ready',
      'validationStatus': 'passed',
      'processingStatus': 'pending',
      'scopeType': request.scopeType,
      'lessonId': request.lessonId,
      'usageRole': request.usageRole,
      'visibleToCourseQa': request.visibleToCourseQa,
    });
  }

  @override
  Future<ParseStartResultModel> startParse({
    required String courseId,
    required String idempotencyKey,
  }) async {
    startedParseCourseIds.add(courseId);
    return ParseStartResultModel.fromJson({
      'taskId': 9001,
      'status': 'queued',
      'nextAction': 'poll_pipeline',
      'entity': {'type': 'parse_run', 'id': 801},
    });
  }

  @override
  Future<PipelineStatusModel> fetchPipelineStatus(String courseId) async {
    final index = fetchPipelineStatusCount < _pipelineStatuses.length
        ? fetchPipelineStatusCount
        : _pipelineStatuses.length - 1;
    fetchPipelineStatusCount += 1;
    return PipelineStatusModel.fromJson(_pipelineStatuses[index]);
  }

  @override
  Future<HandoutGenerateResultModel> generateLessonHandout({
    required String courseId,
    required String lessonId,
    required String idempotencyKey,
  }) async {
    generatedLessonHandouts.add('$courseId/$lessonId');
    return HandoutGenerateResultModel.fromJson({
      'taskId': 9101,
      'status': 'queued',
      'nextAction': 'poll_handout_version',
      'entity': {'type': 'handout_version', 'id': 901},
    });
  }

  @override
  Future<HandoutVersionStatusModel> fetchHandoutVersionStatus(
    int handoutVersionId,
  ) async {
    fetchHandoutVersionStatusCount += 1;
    return HandoutVersionStatusModel.fromJson({
      'handoutVersionId': handoutVersionId,
      'status': 'outline_ready',
      'outlineStatus': 'ready',
      'totalBlocks': 3,
      'readyBlocks': 0,
      'pendingBlocks': 3,
      'sourceParseRunId': 801,
    });
  }
}

Map<String, dynamic> _pipelineStatusJson({
  String pipelineStatus = 'succeeded',
  Map<String, String> stepStatuses = const {
    'caption_extract': 'skipped',
    'document_parse': 'succeeded',
    'knowledge_extract': 'succeeded',
  },
  int progressPct = 100,
  bool outlineReady = true,
}) {
  PipelineStep step(String code, String label) {
    return PipelineStep(
      code: code,
      label: label,
      status: stepStatuses[code] ?? 'succeeded',
    );
  }

  return {
    'courseStatus': {
      'lifecycleStatus': outlineReady ? 'learning_ready' : 'draft',
      'pipelineStage': pipelineStatus == 'succeeded' ? 'handout' : 'parse',
      'pipelineStatus': pipelineStatus,
    },
    'progressPct': progressPct,
    'steps': [
      step('caption_extract', '字幕提取').toJson(),
      step('document_parse', '文档解析').toJson(),
      step('knowledge_extract', '目录抽取').toJson(),
    ],
    'activeParseRunId': 801,
    'activeHandoutVersionId': outlineReady ? 901 : null,
    'nextAction': outlineReady ? 'enter_handout_outline' : 'none',
    'sourceOverview': {
      'videoReady': false,
      'outlineReady': outlineReady,
      'outlineItemCount': outlineReady ? 3 : 0,
      'docTypes': ['pdf'],
      'organizedSourceCount': outlineReady ? 1 : 0,
    },
    'knowledgeMap': {
      'status': outlineReady ? 'ready' : 'generating',
      'knowledgePointCount': outlineReady ? 3 : 0,
      'segmentCount': outlineReady ? 2 : 0,
    },
    'handoutOutline': {
      'status': outlineReady ? 'outline_ready' : 'generating',
      'outlineItemCount': outlineReady ? 3 : 0,
      'generatedBlockCount': 0,
    },
    'highlightSummary': {
      'status': outlineReady ? 'ready' : 'generating',
      'items': [],
    },
  };
}

class PipelineStep {
  const PipelineStep({
    required this.code,
    required this.label,
    required this.status,
  });

  final String code;
  final String label;
  final String status;

  Map<String, dynamic> toJson() {
    return {
      'code': code,
      'label': label,
      'status': status,
      'progressPct': status == 'succeeded' || status == 'skipped' ? 100 : 45,
      'failedResourceIds': [],
    };
  }
}

class _CourseWorkbenchFakeFileSelector extends FileSelectorPlatform {
  _CourseWorkbenchFakeFileSelector(this.files);

  final List<XFile> files;

  @override
  Future<List<XFile>> openFiles({
    List<XTypeGroup>? acceptedTypeGroups,
    String? initialDirectory,
    String? confirmButtonText,
  }) async {
    return files;
  }
}
