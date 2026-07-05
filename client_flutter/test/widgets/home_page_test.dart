import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/home/home_page.dart';
import 'package:knowlink_client/shared/models/course_progress_models.dart';
import 'package:knowlink_client/shared/models/course_summary.dart';
import 'package:knowlink_client/shared/models/home_dashboard_models.dart';
import 'package:knowlink_client/shared/providers/course_flow_providers.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('home answers what to continue today and resumes lesson handout',
      (tester) async {
    _useTestSurface(tester);
    final fakeApiClient = _HomePageFakeApiClient();
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
          builder: (context, state) => const HomePage(),
        ),
        GoRoute(
          path: '/courses/:courseId/lessons/:lessonId/handout',
          builder: (context, state) => Text(
            'lesson-handout-${state.pathParameters['courseId']}-'
            '${state.pathParameters['lessonId']}',
          ),
        ),
        GoRoute(
          path: '/courses/:courseId/lessons/:lessonId/review',
          builder: (context, state) => const Text('lesson-review-route'),
        ),
        GoRoute(
          path: '/courses/:courseId',
          builder: (context, state) =>
              Text('course-detail-${state.pathParameters['courseId']}'),
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

    expect(find.text('今天继续什么'), findsOneWidget);
    expect(find.text('当前课程'), findsOneWidget);
    expect(find.text('KnowLink 固定联调课'), findsWidgets);
    expect(find.text('当前课时'), findsOneWidget);
    expect(find.text('关系模型'), findsWidgets);
    expect(find.text('进度摘要'), findsOneWidget);
    expect(find.text('推荐下一步'), findsOneWidget);
    expect(find.text('今日复习任务'), findsOneWidget);
    expect(find.text('最近课程'), findsOneWidget);
    expect(find.text('继续第 3 节：范式'), findsOneWidget);
    expect(find.text('本节复习已到期。'), findsOneWidget);
    expect(find.text('自主导入'), findsNothing);
    expect(find.text('智能课程推荐'), findsNothing);
    expect(find.text('今日推荐知识点'), findsNothing);

    await tester.tap(find.widgetWithText(FilledButton, '继续学习'));
    await tester.pumpAndSettle();

    expect(find.text('lesson-handout-101-42'), findsOneWidget);
    expect(container.read(courseFlowProvider).courseId, '101');
    expect(container.read(activeBlockProvider), 4001);
    expect(container.read(playerStateProvider).positionSec, 180);
    expect(container.read(activeLessonProvider)?.lessonId, '42');
  });

  testWidgets('recent courses still expose detail and current course switch',
      (tester) async {
    _useTestSurface(tester);
    final fakeApiClient = _HomePageFakeApiClient(switchCourseId: 202);
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
          builder: (context, state) => const HomePage(),
        ),
        GoRoute(
          path: '/courses/:courseId',
          builder: (context, state) =>
              Text('course-detail-${state.pathParameters['courseId']}'),
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

    final switchButton = find.widgetWithText(OutlinedButton, '设为当前').first;
    await tester.ensureVisible(switchButton);
    await tester.tap(switchButton);
    await tester.pumpAndSettle();

    expect(fakeApiClient.switchedCourseIds, ['101']);
    expect(container.read(courseFlowProvider).courseId, '202');
    expect(find.text('当前课程已切换'), findsOneWidget);

    final detailButton = find.widgetWithText(OutlinedButton, '课程详情').first;
    await tester.ensureVisible(detailButton);
    await tester.tap(detailButton);
    await tester.pumpAndSettle();

    expect(find.text('course-detail-101'), findsOneWidget);
  });

  testWidgets('home renders empty dashboard states on mobile', (tester) async {
    tester.view.physicalSize = const Size(390, 900);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final fakeApiClient = _HomePageFakeApiClient(empty: true);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: const MaterialApp(home: HomePage()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('还没有当前课程'), findsOneWidget);
    expect(find.text('暂无推荐下一步'), findsOneWidget);
    expect(find.text('今天没有到期复习任务'), findsOneWidget);
    expect(find.text('暂无最近课程'), findsOneWidget);
  });
}

void _useTestSurface(WidgetTester tester) {
  tester.view.physicalSize = const Size(1200, 900);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

class _HomePageFakeApiClient extends ApiClient {
  _HomePageFakeApiClient({
    this.empty = false,
    this.switchCourseId,
  });

  final bool empty;
  final int? switchCourseId;
  final switchedCourseIds = <String>[];

  @override
  Future<HomeDashboardModel> fetchHomeDashboard() async {
    if (empty) {
      return HomeDashboardModel.fromJson({
        'recentCourses': [],
        'topReviewTasks': [],
        'recommendationEntryEnabled': true,
        'dailyRecommendedKnowledgePoints': [],
        'learningStats': {},
        'currentCourse': null,
        'currentLesson': null,
        'continueLearning': null,
        'nextStep': null,
        'todayReviewTasks': [],
        'recommendedNextLesson': null,
        'recommendedStageQuiz': null,
        'courseQuickEntries': [],
      });
    }
    return HomeDashboardModel.fromJson({
      'recentCourses': [
        _courseJson(101, title: 'KnowLink 固定联调课'),
        _courseJson(202, title: '课程 202'),
      ],
      'topReviewTasks': [],
      'recommendationEntryEnabled': true,
      'dailyRecommendedKnowledgePoints': [],
      'learningStats': {
        'streakDays': 3,
        'completedCourses': 1,
        'reviewTasksCompleted': 2,
        'totalLearningMinutes': 95,
      },
      'currentCourse': _courseJson(101, title: 'KnowLink 固定联调课'),
      'currentLesson': {
        'lessonId': 42,
        'title': '关系模型',
        'orderIndex': 2,
        'handoutReadPercent': 35,
        'quizStatus': 'not_started',
        'reviewStatus': 'due',
        'lastPositionSec': 180,
        'lastHandoutBlockId': 4001,
      },
      'continueLearning': {
        'courseId': 101,
        'lessonId': 42,
        'lastPositionSec': 180,
        'lastHandoutBlockId': 4001,
        'nextRoute': '/courses/101/lessons/42/handout',
        'nextAction': {
          'type': 'continue_video',
          'label': '继续学习 关系模型',
          'positionSec': 180,
          'action': 'open_lesson_study',
        },
      },
      'nextStep': {
        'type': 'continue_lesson',
        'courseId': 101,
        'lessonId': 42,
        'title': '关系模型',
        'nextRoute': '/courses/101/lessons/42/handout',
        'action': 'open_lesson_study',
      },
      'todayReviewTasks': [
        {
          'type': 'lesson_review',
          'courseId': 101,
          'lessonId': 42,
          'title': '关系模型',
          'priorityScore': 80,
          'reasonText': '本节复习已到期。',
          'nextRoute': '/courses/101/lessons/42/review',
        },
      ],
      'recommendedNextLesson': {
        'type': 'next_lesson',
        'scopeType': 'lesson',
        'courseId': 101,
        'lessonId': 43,
        'title': '继续第 3 节：范式',
        'reason': '按进度继续',
        'nextRoute': '/courses/101/lessons/43',
      },
      'recommendedStageQuiz': {
        'type': 'stage_quiz',
        'scopeType': 'lesson_range',
        'courseId': 101,
        'startLessonId': 41,
        'endLessonId': 42,
        'completedLessonCount': 2,
        'title': '生成阶段测验',
        'reason': '已完成 2 节',
        'nextRoute': '/courses/101/quizzes/stage',
      },
      'courseQuickEntries': [
        {
          'key': 'lesson_study',
          'title': '课时学习',
          'status': 'ready',
          'enabled': true,
          'target': '/courses/101/lessons/42/handout',
          'message': '继续当前课时讲义学习',
          'route': '/courses/101/lessons/42/handout',
          'action': 'open_lesson_study',
        },
      ],
    });
  }

  @override
  Future<CourseProgressModel> fetchCourseProgress(String courseId) async {
    return CourseProgressModel.fromJson({
      'courseId': int.parse(courseId),
      'handoutVersionId': 3001,
      'lastHandoutBlockId': 4001,
      'lastPositionSec': 180,
      'currentLessonId': '42',
      'currentLessonTitle': '关系模型',
      'lastActivityAt': '2026-05-11T10:00:00+00:00',
    });
  }

  @override
  Future<CourseSummaryModel> switchCurrentCourse(String courseId) async {
    switchedCourseIds.add(courseId);
    return CourseSummaryModel.fromJson(
      _courseJson(switchCourseId ?? int.parse(courseId)),
    );
  }
}

Map<String, dynamic> _courseJson(int courseId, {String? title}) {
  return {
    'courseId': courseId,
    'title': title ?? 'KnowLink 固定联调课',
    'entryType': 'manual_import',
    'catalogId': null,
    'lifecycleStatus': 'learning_ready',
    'pipelineStage': 'handout',
    'pipelineStatus': 'succeeded',
    'updatedAt': '2026-05-11T10:00:00+00:00',
    'currentLessonId': '42',
    'currentLessonTitle': '关系模型',
    'lastPositionSec': 180,
  };
}
