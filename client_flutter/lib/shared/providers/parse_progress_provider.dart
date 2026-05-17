import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/parse_progress_state.dart';
import '../models/pipeline_status.dart';
import 'course_flow_providers.dart';
import 'course_recommend_provider.dart';

class ParseProgressController extends AutoDisposeNotifier<ParseProgressState> {
  var _isDisposed = false;

  @override
  ParseProgressState build() {
    _isDisposed = false;
    ref.onDispose(() {
      _isDisposed = true;
    });
    return const ParseProgressState();
  }

  Future<void> refresh(String courseId) async {
    state = state.copyWith(pipelineStatus: const AsyncLoading());

    try {
      final status = await ref.read(apiClientProvider).fetchPipelineStatus(
            courseId,
          );
      if (_isDisposed) {
        return;
      }
      _syncCourseFlow(status);
      state = state.copyWith(pipelineStatus: AsyncData(status));
    } catch (error, stackTrace) {
      if (_isDisposed) {
        return;
      }
      state = state.copyWith(
        pipelineStatus: AsyncError(error, stackTrace),
      );
    }
  }

  Future<void> startAndPoll(
    String courseId, {
    Duration interval = const Duration(seconds: 2),
    int maxAttempts = 30,
  }) async {
    if (state.isStarting || state.isPolling) {
      return;
    }

    state = state.copyWith(
      startRequest: const AsyncLoading(),
      isPolling: true,
    );

    try {
      final result = await ref.read(apiClientProvider).startParse(
            courseId: courseId,
            idempotencyKey:
                'parse-start-$courseId-${DateTime.now().microsecondsSinceEpoch}',
          );
      if (_isDisposed) {
        return;
      }
      ref.read(courseFlowProvider.notifier).setActiveParseRun(
            result.entity.type == 'parse_run' ? result.entity.id : null,
          );
      state = state.copyWith(startRequest: AsyncData(result));

      for (var attempt = 0; attempt < maxAttempts; attempt++) {
        if (_isDisposed) {
          return;
        }

        final status = await ref.read(apiClientProvider).fetchPipelineStatus(
              courseId,
            );
        if (_isDisposed) {
          return;
        }

        _syncCourseFlow(status);
        state = state.copyWith(pipelineStatus: AsyncData(status));
        if (status.isTerminal) {
          break;
        }
        await Future<void>.delayed(interval);
      }
    } catch (error, stackTrace) {
      if (_isDisposed) {
        return;
      }
      state = state.copyWith(
        startRequest: AsyncError(error, stackTrace),
      );
    } finally {
      if (!_isDisposed) {
        state = state.copyWith(isPolling: false);
      }
    }
  }

  void _syncCourseFlow(PipelineStatusModel status) {
    ref.read(courseFlowProvider.notifier).syncPipelineStatus(
          lifecycleStatus: status.courseStatus.lifecycleStatus,
          pipelineStage: status.courseStatus.pipelineStage,
          pipelineStatus: status.courseStatus.pipelineStatus,
          progressPct: status.progressPct,
          activeParseRunId: status.activeParseRunId,
          activeHandoutVersionId: status.activeHandoutVersionId,
          nextAction: status.nextAction,
        );
  }
}

final parseProgressProvider =
    AutoDisposeNotifierProvider<ParseProgressController, ParseProgressState>(
  ParseProgressController.new,
);
