import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/shared/models/course_progress_models.dart';
import 'package:knowlink_client/shared/models/home_dashboard_models.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';
import 'package:knowlink_client/shared/providers/home_provider.dart';

void main() {
  test('loadDashboard fetches dashboard and prefetches recent progress',
      () async {
    final fakeApiClient = _FakeHomeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    final subscription = container.listen(homeProvider, (_, __) {});
    addTearDown(subscription.close);
    addTearDown(container.dispose);

    await container.read(homeProvider.notifier).loadDashboard();
    await Future<void>.delayed(Duration.zero);

    final state = container.read(homeProvider);
    expect(state.dashboardValue?.recentCourses.single.courseId, 101);
    expect(state.dashboardValue?.topReviewTasks, hasLength(1));
    expect(fakeApiClient.progressCourseIds, [101]);
    expect(
        state.progressByCourseId[101]?.valueOrNull?.lastHandoutBlockId, 4001);
  });

  test('saveProgress posts progress update and caches returned progress',
      () async {
    final fakeApiClient = _FakeHomeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    final subscription = container.listen(homeProvider, (_, __) {});
    addTearDown(subscription.close);
    addTearDown(container.dispose);

    await container.read(homeProvider.notifier).saveProgress(
          courseId: '101',
          request: const CourseProgressUpdateModel(
            lastHandoutBlockId: 4002,
            lastPositionSec: 240,
          ),
        );

    expect(fakeApiClient.savedProgress.single.toJson(), {
      'lastHandoutBlockId': 4002,
      'lastPositionSec': 240,
    });
    expect(
        container.read(homeProvider).progressSave.valueOrNull?.courseId, 101);
  });

  test('saveProgress ignores stale responses for the same course', () async {
    final fakeApiClient = _SlowSaveHomeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    final subscription = container.listen(homeProvider, (_, __) {});
    addTearDown(subscription.close);
    addTearDown(container.dispose);

    final first = container.read(homeProvider.notifier).saveProgress(
          courseId: '101',
          request: const CourseProgressUpdateModel(
            lastHandoutBlockId: 4001,
            lastPositionSec: 120,
          ),
        );
    final second = container.read(homeProvider.notifier).saveProgress(
          courseId: '101',
          request: const CourseProgressUpdateModel(
            lastHandoutBlockId: 4002,
            lastPositionSec: 240,
          ),
        );

    fakeApiClient.secondSave.complete(fakeApiClient.progress(
      blockId: 4002,
      positionSec: 240,
    ));
    await second;
    fakeApiClient.firstSave.complete(fakeApiClient.progress(
      blockId: 4001,
      positionSec: 120,
    ));
    await first;

    final state = container.read(homeProvider);
    expect(
        state.progressByCourseId[101]?.valueOrNull?.lastHandoutBlockId, 4002);
    expect(state.progressSave.valueOrNull?.lastHandoutBlockId, 4002);
  });
}

class _FakeHomeApiClient extends ApiClient {
  final progressCourseIds = <int>[];
  final savedProgress = <CourseProgressUpdateModel>[];

  @override
  Future<HomeDashboardModel> fetchHomeDashboard() async {
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
    progressCourseIds.add(int.parse(courseId));
    return _progress();
  }

  @override
  Future<CourseProgressModel> updateCourseProgress({
    required String courseId,
    required CourseProgressUpdateModel request,
  }) async {
    savedProgress.add(request);
    return _progress(
      blockId: request.lastHandoutBlockId,
      positionSec: request.lastPositionSec,
    );
  }

  CourseProgressModel _progress({
    int? blockId = 4001,
    int? positionSec = 180,
  }) {
    return CourseProgressModel.fromJson({
      'courseId': 101,
      'handoutVersionId': 3001,
      'lastHandoutBlockId': blockId,
      'lastPositionSec': positionSec,
      'lastActivityAt': '2026-05-11T10:00:00+00:00',
    });
  }

  CourseProgressModel progress({
    int? blockId = 4001,
    int? positionSec = 180,
  }) {
    return _progress(
      blockId: blockId,
      positionSec: positionSec,
    );
  }
}

class _SlowSaveHomeApiClient extends _FakeHomeApiClient {
  final firstSave = Completer<CourseProgressModel>();
  final secondSave = Completer<CourseProgressModel>();
  var saveCalls = 0;

  @override
  Future<CourseProgressModel> updateCourseProgress({
    required String courseId,
    required CourseProgressUpdateModel request,
  }) {
    savedProgress.add(request);
    saveCalls++;
    if (saveCalls == 1) {
      return firstSave.future;
    }
    return secondSave.future;
  }
}
