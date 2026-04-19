import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/course_flow_state.dart';

class PlayerState {
  const PlayerState({
    this.positionSec = 0,
    this.isPlaying = false,
  });

  final int positionSec;
  final bool isPlaying;

  PlayerState copyWith({
    int? positionSec,
    bool? isPlaying,
  }) {
    return PlayerState(
      positionSec: positionSec ?? this.positionSec,
      isPlaying: isPlaying ?? this.isPlaying,
    );
  }
}

class CourseFlowController extends Notifier<CourseFlowState> {
  @override
  CourseFlowState build() => const CourseFlowState();

  void startCourse(String courseId) {
    if (state.courseId == courseId) {
      return;
    }
    state = state.copyWith(courseId: courseId);
  }

  void setLifecycleStatus(String status) {
    state = state.copyWith(lifecycleStatus: status);
  }

  void setPipelineStage(String stage) {
    state = state.copyWith(pipelineStage: stage);
  }

  void setPipelineStatus(String status) {
    state = state.copyWith(pipelineStatus: status);
  }

  void setProgressPct(int progressPct) {
    state = state.copyWith(progressPct: progressPct);
  }

  void setActiveParseRun(int? parseRunId) {
    state = parseRunId == null
        ? state.copyWith(clearActiveParseRunId: true)
        : state.copyWith(activeParseRunId: parseRunId);
  }

  void setActiveHandoutVersion(int? handoutVersionId) {
    state = handoutVersionId == null
        ? state.copyWith(clearActiveHandoutVersionId: true)
        : state.copyWith(activeHandoutVersionId: handoutVersionId);
  }

  void setNextAction(String nextAction) {
    state = state.copyWith(nextAction: nextAction);
  }

  void setSession(int? sessionId) {
    state = sessionId == null
        ? state.copyWith(clearSessionId: true)
        : state.copyWith(sessionId: sessionId);
  }

  void setQuiz(int? quizId) {
    state = quizId == null
        ? state.copyWith(clearQuizId: true)
        : state.copyWith(quizId: quizId);
  }

  void setQuizAttempt(int? attemptId) {
    state = attemptId == null
        ? state.copyWith(clearQuizAttemptId: true)
        : state.copyWith(quizAttemptId: attemptId);
  }

  void setReviewTaskRun(int? reviewTaskRunId) {
    state = reviewTaskRunId == null
        ? state.copyWith(clearReviewTaskRunId: true)
        : state.copyWith(reviewTaskRunId: reviewTaskRunId);
  }
}

final courseFlowProvider =
    NotifierProvider<CourseFlowController, CourseFlowState>(
  CourseFlowController.new,
);

final activeCourseIdProvider = Provider<String?>(
  (ref) => ref.watch(courseFlowProvider).courseId,
);

final activeBlockProvider = StateProvider<int?>((ref) => null);

final playerStateProvider = StateProvider<PlayerState>(
  (ref) => const PlayerState(),
);
