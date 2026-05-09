import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/home/home_page.dart';
import 'package:knowlink_client/shared/models/course_progress_models.dart';
import 'package:knowlink_client/shared/models/home_dashboard_models.dart';
import 'package:knowlink_client/shared/providers/course_flow_providers.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('home page renders dashboard data and resumes latest learning',
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
          path: '/courses/:courseId/handout',
          builder: (context, state) => const Text('handout-route'),
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

    expect(find.text('KnowLink 固定联调课'), findsOneWidget);
    expect(find.textContaining('讲义块 4001'), findsOneWidget);
    expect(find.text('极限定义'), findsOneWidget);
    expect(find.text('95 分钟'), findsOneWidget);
    expect(find.text('该块是考试高频点'), findsWidgets);

    await tester.tap(find.text('继续学习'));
    await tester.pumpAndSettle();

    expect(find.text('handout-route'), findsOneWidget);
    expect(container.read(courseFlowProvider).courseId, '101');
    expect(container.read(activeBlockProvider), 4001);
    expect(container.read(playerStateProvider).positionSec, 180);
  });

  testWidgets('home resume clears stale state when progress has no target',
      (tester) async {
    _useTestSurface(tester);
    final fakeApiClient = _HomePageFakeApiClient(
      progressBlockId: null,
      progressPositionSec: null,
    );
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    container.read(courseFlowProvider.notifier).startCourse('101');
    container.read(activeBlockProvider.notifier).state = 4999;
    container.read(playerStateProvider.notifier).state =
        const PlayerState(positionSec: 999);
    final router = GoRouter(
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => const HomePage(),
        ),
        GoRoute(
          path: '/courses/:courseId/handout',
          builder: (context, state) => const Text('handout-route'),
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

    await tester.tap(find.text('继续学习'));
    await tester.pumpAndSettle();

    expect(find.text('handout-route'), findsOneWidget);
    expect(container.read(courseFlowProvider).courseId, '101');
    expect(container.read(activeBlockProvider), isNull);
    expect(container.read(handoutResumeTargetProvider), isNull);
    expect(container.read(playerStateProvider).positionSec, 0);
  });

  testWidgets('home page renders empty dashboard states on mobile', (
    tester,
  ) async {
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

    expect(find.text('暂无最近学习课程。'), findsOneWidget);
    expect(find.text('暂无今日推荐知识点。'), findsOneWidget);
    expect(find.text('完成测验后会在这里展示 Top3 复习任务。'), findsOneWidget);
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
    this.progressBlockId = 4001,
    this.progressPositionSec = 180,
  });

  final bool empty;
  final int? progressBlockId;
  final int? progressPositionSec;

  @override
  Future<HomeDashboardModel> fetchHomeDashboard() async {
    if (empty) {
      return HomeDashboardModel.fromJson({
        'recentCourses': [],
        'topReviewTasks': [],
        'recommendationEntryEnabled': true,
        'dailyRecommendedKnowledgePoints': [],
        'learningStats': {},
      });
    }
    return HomeDashboardModel.fromJson({
      'recentCourses': [
        {
          'courseId': 101,
          'title': 'KnowLink 固定联调课',
          'entryType': 'manual_import',
          'catalogId': null,
          'lifecycleStatus': 'learning_ready',
          'pipelineStage': 'handout',
          'pipelineStatus': 'succeeded',
          'updatedAt': '2026-05-11T10:00:00+00:00',
        },
      ],
      'topReviewTasks': [
        {
          'reviewTaskId': 8401,
          'taskType': 'revisit_block',
          'priorityScore': 95,
          'reasonText': '该块是考试高频点',
          'recommendedMinutes': 20,
          'reviewOrder': 1,
          'intensity': 'high',
        },
      ],
      'recommendationEntryEnabled': true,
      'dailyRecommendedKnowledgePoints': [
        {
          'knowledgePoint': '极限定义',
          'reason': '高频考点且建议今天优先回看',
          'targetCourseId': 101,
        },
      ],
      'learningStats': {
        'streakDays': 3,
        'completedCourses': 1,
        'reviewTasksCompleted': 2,
        'totalLearningMinutes': 95,
      },
    });
  }

  @override
  Future<CourseProgressModel> fetchCourseProgress(String courseId) async {
    return CourseProgressModel.fromJson({
      'courseId': 101,
      'handoutVersionId': 3001,
      'lastHandoutBlockId': progressBlockId,
      'lastPositionSec': progressPositionSec,
      'lastActivityAt': '2026-05-11T10:00:00+00:00',
    });
  }
}
