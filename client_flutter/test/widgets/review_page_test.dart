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
  testWidgets('review page renders top three tasks and completes one', (
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

    expect(find.text('今日 Top3'), findsOneWidget);
    expect(find.text('第 1 个复习任务'), findsWidgets);
    expect(find.text('第 3 个复习任务'), findsOneWidget);
    expect(find.text('第 4 个复习任务'), findsNothing);
    expect(
      tester
          .widget<OutlinedButton>(find.widgetWithText(OutlinedButton, '刷新'))
          .onPressed,
      isNotNull,
    );
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, '重新生成复习'))
          .onPressed,
      isNotNull,
    );

    await tester.tap(find.text('完成任务').first);
    await tester.pumpAndSettle();

    expect(fakeApiClient.completedTaskIds, [8401]);
    expect(find.text('已记录完成'), findsOneWidget);
    expect(find.text('第 1 个复习任务'), findsNothing);
  });

  testWidgets('review page can regenerate and poll tasks', (tester) async {
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

  testWidgets('review page sets handout resume target when opening segment', (
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

    await tester.tap(find.text('跳回讲义').first);
    await tester.pumpAndSettle();

    final resumeTarget = container.read(handoutResumeTargetProvider);
    expect(find.text('handout-route'), findsOneWidget);
    expect(container.read(activeBlockProvider), 4001);
    expect(resumeTarget?.courseId, '101');
    expect(resumeTarget?.blockId, 4001);
  });
}

void _useTestSurface(WidgetTester tester) {
  tester.view.physicalSize = const Size(1200, 900);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

class _ReviewPageFakeApiClient extends ApiClient {
  _ReviewPageFakeApiClient({
    this.startEmpty = false,
  });

  final bool startEmpty;
  final regeneratedCourseIds = <String>[];
  final statusRunIds = <int>[];
  final completedTaskIds = <int>[];
  var _generated = false;

  @override
  Future<ReviewTasksModel> fetchReviewTasks(String courseId) async {
    if (startEmpty && !_generated) {
      return const ReviewTasksModel(items: []);
    }
    return ReviewTasksModel.fromJson({
      'items': [
        for (var index = 0; index < 4; index++)
          if (!completedTaskIds.contains(8401 + index))
            {
              'reviewTaskId': 8401 + index,
              'taskType': index == 1 ? 'redo_quiz' : 'revisit_block',
              'priorityScore': 95 - index,
              'reasonText': '第 ${index + 1} 个复习任务',
              'recommendedMinutes': 20 - index,
              'recommendedSegment': {
                'blockId': 4001 + index,
                'startSec': 120,
                'endSec': 240,
                'label': '建议优先回看片段',
              },
              'practiceEntry': {
                'type': 'quiz',
                'targetId': 8001,
                'label': '再练 1 题',
              },
              'reviewOrder': index + 1,
              'intensity': index == 0 ? 'high' : 'medium',
            },
      ],
    });
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
}
