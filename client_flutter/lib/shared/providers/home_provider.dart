import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/course_progress_models.dart';
import '../models/home_state.dart';
import 'course_recommend_provider.dart';

class HomeController extends AutoDisposeNotifier<HomeState> {
  var _isDisposed = false;
  var _latestDashboardRequestId = 0;
  var _latestProgressSaveRequestId = 0;
  final Map<int, int> _latestProgressRequestIds = <int, int>{};
  final Map<String, int> _latestProgressSaveRequestIds = <String, int>{};

  @override
  HomeState build() {
    _isDisposed = false;
    ref.onDispose(() {
      _isDisposed = true;
    });
    return HomeState.initial();
  }

  Future<void> loadDashboard() async {
    final requestId = ++_latestDashboardRequestId;
    state = state.copyWith(dashboard: const AsyncLoading());

    try {
      final dashboard = await ref.read(apiClientProvider).fetchHomeDashboard();
      if (!_shouldApplyDashboard(requestId)) {
        return;
      }
      state = state.copyWith(dashboard: AsyncData(dashboard));
      for (final course in dashboard.recentCourses.take(3)) {
        unawaited(fetchProgress(course.courseId).then((_) {}));
      }
    } catch (error, stackTrace) {
      if (!_shouldApplyDashboard(requestId)) {
        return;
      }
      state = state.copyWith(dashboard: AsyncError(error, stackTrace));
    }
  }

  Future<CourseProgressModel?> fetchProgress(int courseId) async {
    final requestId = (_latestProgressRequestIds[courseId] ?? 0) + 1;
    _latestProgressRequestIds[courseId] = requestId;
    state = state.copyWith(
      progressByCourseId: {
        ...state.progressByCourseId,
        courseId: const AsyncLoading<CourseProgressModel>(),
      },
    );

    try {
      final progress = await ref
          .read(apiClientProvider)
          .fetchCourseProgress(courseId.toString());
      if (!_shouldApplyProgress(courseId, requestId)) {
        return null;
      }
      state = state.copyWith(
        progressByCourseId: {
          ...state.progressByCourseId,
          courseId: AsyncData(progress),
        },
      );
      return progress;
    } catch (error, stackTrace) {
      if (!_shouldApplyProgress(courseId, requestId)) {
        return null;
      }
      state = state.copyWith(
        progressByCourseId: {
          ...state.progressByCourseId,
          courseId: AsyncError(error, stackTrace),
        },
      );
      return null;
    }
  }

  Future<CourseProgressModel?> saveProgress({
    required String courseId,
    required CourseProgressUpdateModel request,
  }) async {
    final requestId = ++_latestProgressSaveRequestId;
    _latestProgressSaveRequestIds[courseId] = requestId;
    state = state.copyWith(progressSave: const AsyncLoading());
    try {
      final progress = await ref.read(apiClientProvider).updateCourseProgress(
            courseId: courseId,
            request: request,
          );
      if (!_shouldApplyProgressSaveCache(courseId, requestId)) {
        return null;
      }
      if (progress.courseId.toString() != courseId) {
        final error = StateError('课程进度响应课程不匹配');
        if (_shouldApplyLatestProgressSave(requestId)) {
          state = state.copyWith(
            progressSave: AsyncError(error, StackTrace.current),
          );
        }
        return null;
      }
      state = state.copyWith(
        progressSave: _shouldApplyLatestProgressSave(requestId)
            ? AsyncData(progress)
            : state.progressSave,
        progressByCourseId: {
          ...state.progressByCourseId,
          progress.courseId: AsyncData(progress),
        },
      );
      return progress;
    } catch (error, stackTrace) {
      if (!_shouldApplyLatestProgressSave(requestId)) {
        return null;
      }
      state = state.copyWith(
        progressSave: AsyncError(error, stackTrace),
      );
      return null;
    }
  }

  bool _shouldApplyDashboard(int requestId) {
    return !_isDisposed && requestId == _latestDashboardRequestId;
  }

  bool _shouldApplyProgress(int courseId, int requestId) {
    return !_isDisposed && _latestProgressRequestIds[courseId] == requestId;
  }

  bool _shouldApplyProgressSaveCache(String courseId, int requestId) {
    return !_isDisposed && _latestProgressSaveRequestIds[courseId] == requestId;
  }

  bool _shouldApplyLatestProgressSave(int requestId) {
    return !_isDisposed && requestId == _latestProgressSaveRequestId;
  }
}

final homeProvider =
    AutoDisposeNotifierProvider<HomeController, HomeState>(HomeController.new);
