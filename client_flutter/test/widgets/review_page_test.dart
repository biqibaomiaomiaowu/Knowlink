import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/review/review_page.dart';
import 'package:knowlink_client/shared/models/review_models.dart';
import 'package:knowlink_client/shared/providers/course_flow_providers.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('review page renders Task 11 aggregate summaries and tasks', (
    tester,
  ) async {
    _useTestSurface(tester);
    final fakeApiClient = _ReviewPageFakeApiClient();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: const MaterialApp(home: ReviewPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    expect(fakeApiClient.courseReviewCourseIds, ['101']);
    expect(fakeApiClient.reviewTasksCourseIds, isEmpty);
    expect(find.text('复习中心'), findsWidgets);
    expect(find.text('今日任务'), findsWidgets);
    expect(find.text('薄弱点'), findsWidgets);
    expect(find.text('错题'), findsWidgets);
    expect(find.text('掌握度'), findsWidgets);
    expect(find.text('任务摘要'), findsOneWidget);
    expect(find.text('薄弱摘要'), findsOneWidget);
    expect(find.text('错题摘要'), findsOneWidget);
    expect(find.text('掌握摘要'), findsOneWidget);
    expect(find.text('第 1 个复习任务'), findsWidgets);
    expect(find.text('第 3 个复习任务'), findsOneWidget);
    expect(find.text('第 4 个复习任务'), findsNothing);
    expect(find.text('回到讲义'), findsWidgets);
    expect(find.text('进入测试'), findsWidgets);
    expect(find.text('标记完成'), findsWidgets);

    await _tapVisible(tester, find.text('标记完成').first);
    await tester.pumpAndSettle();

    expect(fakeApiClient.completedTaskIds, [8401]);
    expect(fakeApiClient.courseReviewCourseIds, ['101', '101']);
    expect(find.text('已记录完成'), findsOneWidget);
    expect(find.text('第 1 个复习任务'), findsNothing);
  });

  testWidgets('review page can regenerate and poll course review', (
    tester,
  ) async {
    _useTestSurface(tester);
    final fakeApiClient = _ReviewPageFakeApiClient(startEmpty: true);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: const MaterialApp(home: ReviewPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('暂无复习任务'), findsOneWidget);

    await tester.tap(find.text('重新生成复习'));
    await tester.pumpAndSettle();

    expect(fakeApiClient.regeneratedCourseIds, ['101']);
    expect(fakeApiClient.statusRunIds, [8301]);
    expect(find.text('第 1 个复习任务'), findsWidgets);
    expect(find.text('生成 已就绪 · 3 条'), findsOneWidget);
  });

  testWidgets('review page does not call completion API when unsupported', (
    tester,
  ) async {
    _useTestSurface(tester);
    final fakeApiClient = _ReviewPageFakeApiClient(
      unsupportedTaskIds: {8401},
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: const MaterialApp(home: ReviewPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    final firstCompleteButton = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, '标记完成').first,
    );
    expect(firstCompleteButton.onPressed, isNull);

    expect(fakeApiClient.completedTaskIds, isEmpty);
    expect(fakeApiClient.courseReviewCourseIds, ['101']);
  });

  testWidgets('review page uses jumpRoute and linked handout block', (
    tester,
  ) async {
    _useTestSurface(tester);
    final fakeApiClient = _ReviewPageFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final router = GoRouter(
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => const ReviewPage(courseId: '101'),
        ),
        GoRoute(
          path: '/courses/:courseId/lessons/:lessonId/handout',
          builder: (context, state) => Text(
            'handout-route ${state.pathParameters['lessonId']}',
          ),
        ),
      ],
    );

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    await _tapVisible(tester, find.text('回到讲义').first);

    final resumeTarget = container.read(handoutResumeTargetProvider);
    expect(find.text('handout-route 42'), findsOneWidget);
    expect(container.read(activeBlockProvider), 4201);
    expect(resumeTarget?.courseId, '101');
    expect(resumeTarget?.blockId, 4201);
  });

  testWidgets('review page enters lesson quiz route', (tester) async {
    _useTestSurface(tester);
    final fakeApiClient = _ReviewPageFakeApiClient();
    final router = GoRouter(
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => const ReviewPage(courseId: '101'),
        ),
        GoRoute(
          path: '/courses/:courseId/lessons/:lessonId/quiz',
          builder: (context, state) => Text(
            'quiz-route ${state.pathParameters['lessonId']}',
          ),
        ),
      ],
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    await _tapVisible(tester, find.text('进入测试').first);

    expect(find.text('quiz-route 42'), findsOneWidget);
  });
}

void _useTestSurface(WidgetTester tester) {
  tester.view.physicalSize = const Size(1200, 900);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

Future<void> _tapVisible(WidgetTester tester, Finder finder) async {
  await tester.ensureVisible(finder);
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

class _ReviewPageFakeApiClient extends ApiClient {
  _ReviewPageFakeApiClient({
    this.startEmpty = false,
    this.unsupportedTaskIds = const {},
  });

  final bool startEmpty;
  final Set<int> unsupportedTaskIds;
  final courseReviewCourseIds = <String>[];
  final reviewTasksCourseIds = <String>[];
  final regeneratedCourseIds = <String>[];
  final statusRunIds = <int>[];
  final completedTaskIds = <int>[];
  var _generated = false;

  @override
  Future<CourseReviewModel> fetchCourseReview({
    required String courseId,
  }) async {
    courseReviewCourseIds.add(courseId);
    if (startEmpty && !_generated) {
      return CourseReviewModel.fromJson({
        'courseId': 101,
        'scopeType': 'course',
        'status': 'empty',
        'todayTaskCount': 0,
        'weakPointCount': 0,
        'mistakeCount': 0,
        'masteryScore': null,
        'topTasks': [],
        'items': [],
        'weakLessons': [],
        'crossLessonWeakPoints': [],
      });
    }
    return CourseReviewModel.fromJson(_courseReviewJson());
  }

  @override
  Future<ReviewTasksModel> fetchReviewTasks(String courseId) async {
    reviewTasksCourseIds.add(courseId);
    throw StateError('fetchReviewTasks should not be used for Task 11');
  }

  @override
  Future<ReviewRegenerateResultModel> regenerateReviewTasks({
    required String courseId,
    required String idempotencyKey,
  }) async {
    regeneratedCourseIds.add(courseId);
    _generated = true;
    return ReviewRegenerateResultModel.fromJson({
      'taskId': 9001,
      'status': 'queued',
      'nextAction': 'poll',
      'entity': {'type': 'review_task_run', 'id': 8301},
    });
  }

  @override
  Future<ReviewRunStatusModel> fetchReviewRunStatus(
    int reviewTaskRunId,
  ) async {
    statusRunIds.add(reviewTaskRunId);
    return ReviewRunStatusModel.fromJson({
      'reviewTaskRunId': reviewTaskRunId,
      'courseId': 101,
      'status': 'ready',
      'generatedCount': 3,
    });
  }

  @override
  Future<CompleteReviewTaskResultModel> completeReviewTask(
    int reviewTaskId,
  ) async {
    completedTaskIds.add(reviewTaskId);
    return CompleteReviewTaskResultModel.fromJson({
      'reviewTaskId': reviewTaskId,
      'completed': true,
    });
  }

  Map<String, dynamic> _courseReviewJson() {
    final tasks = [
      for (var index = 0; index < 4; index++)
        if (!completedTaskIds.contains(8401 + index))
          _reviewTaskJson(
            index: index,
            completionSupported: !unsupportedTaskIds.contains(8401 + index),
          ),
    ];
    return {
      'courseId': 101,
      'scopeType': 'course',
      'status': 'ready',
      'todayTaskCount': tasks.length,
      'weakPointCount': 2,
      'mistakeCount': 5,
      'masteryScore': 76,
      'topTasks': tasks.take(3).toList(),
      'items': tasks,
      'weakLessons': [
        {
          'lessonId': 42,
          'title': '矩阵乘法',
          'masteryScore': 58,
          'reasonText': '连续两次测验低于目标掌握度',
        },
      ],
      'crossLessonWeakPoints': [
        {
          'knowledgePointKey': 'matrix_inverse',
          'title': '逆矩阵条件',
          'lessonIds': [42, 43],
          'evidenceChain': [],
        },
      ],
    };
  }

  Map<String, dynamic> _reviewTaskJson({
    required int index,
    required bool completionSupported,
  }) {
    return {
      'reviewTaskId': 8401 + index,
      'taskId': 9401 + index,
      'taskType': index == 1 ? 'redo_quiz' : 'revisit_block',
      'priorityScore': 95 - index,
      'reasonText': '第 ${index + 1} 个复习任务',
      'recommendedMinutes': 20 - index,
      'scopeType': 'lesson',
      'lessonId': 42 + index,
      'sourceQuestionKeys': ['q-${index + 1}'],
      'reviewOrder': index + 1,
      'intensity': index == 0 ? 'high' : 'medium',
      'sourceLesson': {
        'lessonId': 42 + index,
        'title': '第 ${index + 1} 课',
        'masteryScore': 60 + index,
      },
      'linkedHandoutBlockId': 4201 + index,
      'recommendedAction': {
        'type': 'revisit_block',
        'label': '回看讲义',
        'targetBlockId': 4201 + index,
      },
      'recommendedHandoutBlock': {
        'blockId': 4201 + index,
        'title': '矩阵乘法讲义块',
      },
      'jumpRoute': '/courses/101/lessons/${42 + index}/handout',
      'completionSupported': completionSupported,
    };
  }
}
