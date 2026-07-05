import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/shared/models/review_models.dart';
import 'package:knowlink_client/shared/providers/course_flow_providers.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';
import 'package:knowlink_client/shared/providers/review_provider.dart';

void main() {
  test('load fetches course review aggregate and syncs course flow', () async {
    final fakeApiClient = _FakeReviewApiClient();
    final container = _createContainer(fakeApiClient);

    await container.read(reviewProvider.notifier).load('101');

    expect(fakeApiClient.courseReviewCourseIds, ['101']);
    expect(fakeApiClient.reviewTasksCourseIds, isEmpty);
    expect(container.read(courseFlowProvider).courseId, '101');
  });

  test('regenerateAndPoll stores run id and refreshes course review', () async {
    final fakeApiClient = _FakeReviewApiClient();
    final container = _createContainer(fakeApiClient);

    await container.read(reviewProvider.notifier).regenerateAndPoll(
          '101',
          interval: Duration.zero,
          maxAttempts: 1,
        );

    final state = container.read(reviewProvider);
    expect(fakeApiClient.regeneratedCourseIds, ['101']);
    expect(fakeApiClient.statusRunIds, [8301]);
    expect(fakeApiClient.courseReviewCourseIds, ['101']);
    expect(state.runStatusValue?.status, 'ready');
    expect(container.read(courseFlowProvider).reviewTaskRunId, 8301);
  });

  test('completeTask completes selected task and refreshes course review',
      () async {
    final fakeApiClient = _FakeReviewApiClient();
    final container = _createContainer(fakeApiClient);

    await container.read(reviewProvider.notifier).load('101');
    await container.read(reviewProvider.notifier).completeTask(
          courseId: '101',
          reviewTaskId: 8401,
        );

    final remainingIds = fakeApiClient.latestTaskIds;
    expect(fakeApiClient.completedTaskIds, [8401]);
    expect(fakeApiClient.courseReviewCourseIds, ['101', '101']);
    expect(remainingIds, isNot(contains(8401)));
  });

  test('completeTask skips unsupported tasks without calling completion API',
      () async {
    final fakeApiClient = _FakeReviewApiClient(
      unsupportedTaskIds: {8401},
    );
    final container = _createContainer(fakeApiClient);

    await container.read(reviewProvider.notifier).load('101');
    await container.read(reviewProvider.notifier).completeTask(
          courseId: '101',
          reviewTaskId: 8401,
        );

    expect(fakeApiClient.completedTaskIds, isEmpty);
    expect(fakeApiClient.courseReviewCourseIds, ['101']);
  });

  test('regenerateAndPoll does not fetch review before run is ready', () async {
    final fakeApiClient = _FakeReviewApiClient(status: 'running');
    final container = _createContainer(fakeApiClient);

    await container.read(reviewProvider.notifier).regenerateAndPoll(
          '101',
          interval: Duration.zero,
          maxAttempts: 1,
        );

    expect(fakeApiClient.statusRunIds, [8301]);
    expect(fakeApiClient.courseReviewCourseIds, isEmpty);
  });
}

ProviderContainer _createContainer(_FakeReviewApiClient fakeApiClient) {
  final container = ProviderContainer(
    overrides: [
      apiClientProvider.overrideWithValue(fakeApiClient),
    ],
  );
  final subscription = container.listen(reviewProvider, (_, __) {});
  addTearDown(subscription.close);
  addTearDown(container.dispose);
  return container;
}

class _FakeReviewApiClient extends ApiClient {
  _FakeReviewApiClient({
    this.status = 'ready',
    this.unsupportedTaskIds = const {},
  });

  final String status;
  final Set<int> unsupportedTaskIds;
  final courseReviewCourseIds = <String>[];
  final reviewTasksCourseIds = <String>[];
  final regeneratedCourseIds = <String>[];
  final statusRunIds = <int>[];
  final completedTaskIds = <int>[];
  List<int> latestTaskIds = const [];

  @override
  Future<CourseReviewModel> fetchCourseReview({
    required String courseId,
  }) async {
    courseReviewCourseIds.add(courseId);
    final review = CourseReviewModel.fromJson(
      _courseReviewJson(unsupportedTaskIds: unsupportedTaskIds),
    );
    latestTaskIds = review.items.map((task) => task.reviewTaskId).toList();
    return review;
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

  Map<String, dynamic> _courseReviewJson({
    required Set<int> unsupportedTaskIds,
  }) {
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
    final reviewTaskId = 8401 + index;
    return {
      'reviewTaskId': reviewTaskId,
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
