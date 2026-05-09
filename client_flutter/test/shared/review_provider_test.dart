import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/shared/models/review_models.dart';
import 'package:knowlink_client/shared/providers/course_flow_providers.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';
import 'package:knowlink_client/shared/providers/review_provider.dart';

void main() {
  test('load fetches review tasks and syncs course flow', () async {
    final fakeApiClient = _FakeReviewApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    final subscription = container.listen(reviewProvider, (_, __) {});
    addTearDown(subscription.close);
    addTearDown(container.dispose);

    await container.read(reviewProvider.notifier).load('101');

    final state = container.read(reviewProvider);
    expect(fakeApiClient.loadedCourseIds, ['101']);
    expect(state.tasksValue?.items, hasLength(4));
    expect(state.tasksValue?.topThree, hasLength(3));
    expect(container.read(courseFlowProvider).courseId, '101');
  });

  test('regenerateAndPoll stores run id and refreshes tasks', () async {
    final fakeApiClient = _FakeReviewApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    final subscription = container.listen(reviewProvider, (_, __) {});
    addTearDown(subscription.close);
    addTearDown(container.dispose);

    await container.read(reviewProvider.notifier).regenerateAndPoll(
          '101',
          interval: Duration.zero,
          maxAttempts: 1,
        );

    final state = container.read(reviewProvider);
    expect(fakeApiClient.regeneratedCourseIds, ['101']);
    expect(fakeApiClient.statusRunIds, [8301]);
    expect(state.runStatusValue?.status, 'ready');
    expect(state.tasksValue?.topThree, hasLength(3));
    expect(container.read(courseFlowProvider).reviewTaskRunId, 8301);
  });

  test('completeTask completes selected task and refreshes tasks', () async {
    final fakeApiClient = _FakeReviewApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    final subscription = container.listen(reviewProvider, (_, __) {});
    addTearDown(subscription.close);
    addTearDown(container.dispose);

    await container.read(reviewProvider.notifier).load('101');
    await container.read(reviewProvider.notifier).completeTask(
          courseId: '101',
          reviewTaskId: 8401,
        );

    final state = container.read(reviewProvider);
    expect(fakeApiClient.completedTaskIds, [8401]);
    expect(state.completion.valueOrNull?.completed, isTrue);
    expect(state.tasksValue?.items.map((task) => task.reviewTaskId),
        isNot(contains(8401)));
  });

  test('regenerateAndPoll does not fetch tasks before run is ready', () async {
    final fakeApiClient = _FakeReviewApiClient(status: 'running');
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    final subscription = container.listen(reviewProvider, (_, __) {});
    addTearDown(subscription.close);
    addTearDown(container.dispose);

    await container.read(reviewProvider.notifier).regenerateAndPoll(
          '101',
          interval: Duration.zero,
          maxAttempts: 1,
        );

    expect(fakeApiClient.statusRunIds, [8301]);
    expect(fakeApiClient.loadedCourseIds, isEmpty);
    expect(container.read(reviewProvider).tasksValue, isNull);
  });
}

class _FakeReviewApiClient extends ApiClient {
  _FakeReviewApiClient({
    this.status = 'ready',
  });

  final String status;
  final loadedCourseIds = <String>[];
  final regeneratedCourseIds = <String>[];
  final statusRunIds = <int>[];
  final completedTaskIds = <int>[];

  @override
  Future<ReviewTasksModel> fetchReviewTasks(String courseId) async {
    loadedCourseIds.add(courseId);
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
      'status': status,
      'generatedCount': status == 'ready' ? 3 : 0,
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
