import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/review_models.dart';
import '../models/review_state.dart';
import 'course_flow_providers.dart';
import 'course_recommend_provider.dart';

class ReviewController extends AutoDisposeNotifier<ReviewState> {
  var _isDisposed = false;
  var _latestRequestId = 0;
  String? _activeCourseId;

  @override
  ReviewState build() {
    _isDisposed = false;
    ref.onDispose(() {
      _isDisposed = true;
    });
    return ReviewState.initial();
  }

  Future<void> load(String courseId) async {
    final requestId = ++_latestRequestId;
    _activeCourseId = courseId;
    ref.read(courseFlowProvider.notifier).startCourse(courseId);
    state = state.copyWith(
      tasks: const AsyncLoading(),
      completion: const AsyncData<CompleteReviewTaskResultModel?>(null),
      clearCompletingTaskId: true,
    );

    try {
      final tasks =
          await ref.read(apiClientProvider).fetchReviewTasks(courseId);
      if (!_shouldApply(requestId, courseId: courseId)) {
        return;
      }
      state = state.copyWith(tasks: AsyncData(tasks));
    } catch (error, stackTrace) {
      if (!_shouldApply(requestId, courseId: courseId)) {
        return;
      }
      state = state.copyWith(tasks: AsyncError(error, stackTrace));
    }
  }

  Future<void> regenerateAndPoll(
    String courseId, {
    Duration interval = const Duration(seconds: 2),
    int maxAttempts = 30,
  }) async {
    if (state.isRegenerating) {
      return;
    }
    final requestId = ++_latestRequestId;
    _activeCourseId = courseId;
    ref.read(courseFlowProvider.notifier).startCourse(courseId);
    state = state.copyWith(
      tasks: const AsyncData<ReviewTasksModel?>(null),
      regeneration: const AsyncLoading(),
      runStatus: const AsyncData<ReviewRunStatusModel?>(null),
      completion: const AsyncData<CompleteReviewTaskResultModel?>(null),
      clearCompletingTaskId: true,
      isPolling: true,
    );

    try {
      final result = await ref.read(apiClientProvider).regenerateReviewTasks(
            courseId: courseId,
            idempotencyKey:
                'review-regenerate-$courseId-${DateTime.now().microsecondsSinceEpoch}',
          );
      if (!_shouldApply(requestId, courseId: courseId)) {
        return;
      }
      ref.read(courseFlowProvider.notifier).setReviewTaskRun(
            result.entity.type == 'review_task_run' ? result.entity.id : null,
          );
      state = state.copyWith(regeneration: AsyncData(result));

      if (result.entity.type != 'review_task_run') {
        return;
      }

      ReviewRunStatusModel? latestStatus;
      for (var attempt = 0; attempt < maxAttempts; attempt++) {
        if (!_shouldApply(requestId, courseId: courseId)) {
          return;
        }
        latestStatus = await ref
            .read(apiClientProvider)
            .fetchReviewRunStatus(result.entity.id);
        if (!_shouldApply(requestId, courseId: courseId)) {
          return;
        }
        state = state.copyWith(runStatus: AsyncData(latestStatus));
        if (latestStatus.isTerminal) {
          break;
        }
        await Future<void>.delayed(interval);
      }

      if (_canFetchTasksAfterRun(latestStatus)) {
        final tasks = await ref.read(apiClientProvider).fetchReviewTasks(
              courseId,
            );
        if (!_shouldApply(requestId, courseId: courseId)) {
          return;
        }
        state = state.copyWith(tasks: AsyncData(tasks));
      }
    } catch (error, stackTrace) {
      if (!_shouldApply(requestId, courseId: courseId)) {
        return;
      }
      state = state.copyWith(regeneration: AsyncError(error, stackTrace));
    } finally {
      if (_shouldApply(requestId, courseId: courseId)) {
        state = state.copyWith(isPolling: false);
      }
    }
  }

  Future<void> completeTask({
    required String courseId,
    required int reviewTaskId,
  }) async {
    if (state.isCompleting) {
      return;
    }
    final requestId = ++_latestRequestId;
    _activeCourseId = courseId;
    state = state.copyWith(
      completion: const AsyncLoading(),
      completingTaskId: reviewTaskId,
    );

    try {
      final result = await ref.read(apiClientProvider).completeReviewTask(
            reviewTaskId,
          );
      if (!_shouldApply(requestId, courseId: courseId)) {
        return;
      }
      final tasks =
          await ref.read(apiClientProvider).fetchReviewTasks(courseId);
      if (!_shouldApply(requestId, courseId: courseId)) {
        return;
      }
      state = state.copyWith(
        completion: AsyncData(result),
        tasks: AsyncData(tasks),
        clearCompletingTaskId: true,
      );
    } catch (error, stackTrace) {
      if (!_shouldApply(requestId, courseId: courseId)) {
        return;
      }
      state = state.copyWith(
        completion: AsyncError(error, stackTrace),
        clearCompletingTaskId: true,
      );
    }
  }

  bool _shouldApply(int requestId, {required String courseId}) {
    return !_isDisposed &&
        requestId == _latestRequestId &&
        _activeCourseId == courseId;
  }

  bool _canFetchTasksAfterRun(ReviewRunStatusModel? status) {
    return status != null &&
        (status.status == 'ready' ||
            status.status == 'succeeded' ||
            status.status == 'partial_success');
  }
}

final reviewProvider =
    AutoDisposeNotifierProvider<ReviewController, ReviewState>(
  ReviewController.new,
);
