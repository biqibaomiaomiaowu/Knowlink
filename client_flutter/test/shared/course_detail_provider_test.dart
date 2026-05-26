import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/shared/models/course_summary.dart';
import 'package:knowlink_client/shared/providers/course_detail_provider.dart';
import 'package:knowlink_client/shared/providers/course_flow_providers.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  test('load fetches course and current course', () async {
    final fakeApiClient = _FakeCourseDetailApiClient();
    final container = _container(fakeApiClient);

    await container.read(courseDetailProvider.notifier).load('101');

    final state = container.read(courseDetailProvider);
    expect(fakeApiClient.fetchedCourseIds, ['101']);
    expect(state.course.valueOrNull?.courseId, 101);
    expect(state.currentCourse.valueOrNull?.courseId, 202);
  });

  test('load keeps course when current course fetch fails', () async {
    final fakeApiClient = _FakeCourseDetailApiClient(
      currentCourseError: StateError('no current course'),
    );
    final container = _container(fakeApiClient);

    await container.read(courseDetailProvider.notifier).load('101');

    final state = container.read(courseDetailProvider);
    expect(state.course.valueOrNull?.courseId, 101);
    expect(state.currentCourse.hasError, isTrue);
  });

  test('load exposes course before current course request completes', () async {
    final currentCourseCompleter = Completer<CourseSummaryModel>();
    final fakeApiClient = _FakeCourseDetailApiClient(
      currentCourseCompleter: currentCourseCompleter,
    );
    final container = _container(fakeApiClient);
    final subscription = container.listen(
      courseDetailProvider,
      (previous, next) {},
    );
    addTearDown(subscription.close);

    final future = container.read(courseDetailProvider.notifier).load('101');
    await Future<void>.delayed(Duration.zero);

    var state = container.read(courseDetailProvider);
    expect(state.course.valueOrNull?.courseId, 101);
    expect(state.currentCourse.isLoading, isTrue);

    currentCourseCompleter.complete(_course(202));
    await future;

    state = container.read(courseDetailProvider);
    expect(state.currentCourse.valueOrNull?.courseId, 202);
  });

  test('load ignores late current course after disposal', () async {
    final currentCourseCompleter = Completer<CourseSummaryModel>();
    final fakeApiClient = _FakeCourseDetailApiClient(
      currentCourseCompleter: currentCourseCompleter,
    );
    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(fakeApiClient)],
    );

    final future = container.read(courseDetailProvider.notifier).load('101');
    await Future<void>.delayed(Duration.zero);

    container.dispose();
    currentCourseCompleter.complete(_course(202));

    await expectLater(future, completes);
  });

  test('switchCurrentCourse syncs course flow', () async {
    final fakeApiClient = _FakeCourseDetailApiClient();
    final container = _container(fakeApiClient);

    await container
        .read(courseDetailProvider.notifier)
        .switchCurrentCourse('101');

    expect(fakeApiClient.switchedCourseIds, ['101']);
    expect(container.read(courseFlowProvider).courseId, '101');
    expect(
      container
          .read(courseDetailProvider)
          .currentCourseSwitch
          .valueOrNull
          ?.courseId,
      101,
    );
  });

  test('switchCurrentCourse ignores late result after disposal', () async {
    final switchCompleter = Completer<CourseSummaryModel>();
    final fakeApiClient = _FakeCourseDetailApiClient(
      switchCompleter: switchCompleter,
    );
    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(fakeApiClient)],
    );

    final future = container
        .read(courseDetailProvider.notifier)
        .switchCurrentCourse('101');
    await Future<void>.delayed(Duration.zero);

    container.dispose();
    switchCompleter.complete(_course(101));

    await expectLater(future, completes);
  });
}

ProviderContainer _container(_FakeCourseDetailApiClient fakeApiClient) {
  final container = ProviderContainer(
    overrides: [apiClientProvider.overrideWithValue(fakeApiClient)],
  );
  addTearDown(container.dispose);
  return container;
}

class _FakeCourseDetailApiClient extends ApiClient {
  _FakeCourseDetailApiClient({
    this.currentCourseError,
    this.currentCourseCompleter,
    this.switchCompleter,
  });

  final Object? currentCourseError;
  final Completer<CourseSummaryModel>? currentCourseCompleter;
  final Completer<CourseSummaryModel>? switchCompleter;
  final fetchedCourseIds = <String>[];
  final switchedCourseIds = <String>[];

  @override
  Future<CourseSummaryModel> fetchCourse(String courseId) async {
    fetchedCourseIds.add(courseId);
    return _course(int.parse(courseId));
  }

  @override
  Future<CourseSummaryModel> fetchCurrentCourse() async {
    final completer = currentCourseCompleter;
    if (completer != null) {
      return completer.future;
    }
    final error = currentCourseError;
    if (error != null) {
      throw error;
    }
    return _course(202);
  }

  @override
  Future<CourseSummaryModel> switchCurrentCourse(String courseId) async {
    switchedCourseIds.add(courseId);
    final completer = switchCompleter;
    if (completer != null) {
      return completer.future;
    }
    return _course(int.parse(courseId));
  }
}

CourseSummaryModel _course(int courseId) {
  return CourseSummaryModel.fromJson({
    'courseId': courseId,
    'title': '课程 $courseId',
    'entryType': 'recommendation',
    'catalogId': 'math-final-01',
    'lifecycleStatus': 'learning_ready',
    'pipelineStage': 'handout',
    'pipelineStatus': 'succeeded',
    'updatedAt': '2026-05-25T10:00:00+08:00',
  });
}
