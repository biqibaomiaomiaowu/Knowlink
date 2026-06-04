import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/course_detail_state.dart';
import '../models/course_summary.dart';
import 'course_flow_providers.dart';
import 'course_recommend_provider.dart';

class CourseDetailController extends AutoDisposeNotifier<CourseDetailState> {
  var _latestLoadRequestId = 0;
  var _latestSwitchRequestId = 0;
  var _isDisposed = false;

  @override
  CourseDetailState build() {
    _isDisposed = false;
    ref.onDispose(() {
      _isDisposed = true;
    });
    return const CourseDetailState();
  }

  Future<void> load(String courseId) async {
    final requestId = ++_latestLoadRequestId;
    state = state.copyWith(
      course: const AsyncLoading(),
      currentCourse: const AsyncLoading(),
    );

    final apiClient = ref.read(apiClientProvider);
    await Future.wait([
      _loadCourse(requestId, apiClient.fetchCourse(courseId)),
      _loadCurrentCourse(requestId, apiClient.fetchCurrentCourse()),
    ]);
  }

  Future<void> switchCurrentCourse(String courseId) async {
    final requestId = ++_latestSwitchRequestId;
    state = state.copyWith(currentCourseSwitch: const AsyncLoading());

    try {
      final course = await ref.read(apiClientProvider).switchCurrentCourse(
            courseId,
          );
      if (!_shouldApplySwitch(requestId)) {
        return;
      }
      ref.read(courseFlowProvider.notifier).startCourse(
            course.courseId.toString(),
          );
      state = state.copyWith(
        currentCourse: AsyncData(course),
        currentCourseSwitch: AsyncData(course),
      );
    } catch (error, stackTrace) {
      if (!_shouldApplySwitch(requestId)) {
        return;
      }
      state = state.copyWith(
        currentCourseSwitch: AsyncError(error, stackTrace),
      );
    }
  }

  Future<void> _loadCourse(
    int requestId,
    Future<CourseSummaryModel> future,
  ) async {
    try {
      final course = await future;
      if (!_shouldApplyLoad(requestId)) {
        return;
      }
      state = state.copyWith(course: AsyncData(course));
    } catch (error, stackTrace) {
      if (!_shouldApplyLoad(requestId)) {
        return;
      }
      state = state.copyWith(course: AsyncError(error, stackTrace));
    }
  }

  Future<void> _loadCurrentCourse(
    int requestId,
    Future<CourseSummaryModel> future,
  ) async {
    try {
      final course = await future;
      if (!_shouldApplyLoad(requestId)) {
        return;
      }
      state = state.copyWith(currentCourse: AsyncData(course));
    } catch (error, stackTrace) {
      if (!_shouldApplyLoad(requestId)) {
        return;
      }
      state = state.copyWith(currentCourse: AsyncError(error, stackTrace));
    }
  }

  bool _shouldApplyLoad(int requestId) {
    return !_isDisposed && requestId == _latestLoadRequestId;
  }

  bool _shouldApplySwitch(int requestId) {
    return !_isDisposed && requestId == _latestSwitchRequestId;
  }
}

final courseDetailProvider =
    AutoDisposeNotifierProvider<CourseDetailController, CourseDetailState>(
  CourseDetailController.new,
);
