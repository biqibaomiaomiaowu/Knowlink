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
    state = state.copyWith(courseId: courseId);
  }

  void setPipelineStatus(String status) {
    state = state.copyWith(pipelineStatus: status);
  }

  void setInquiryVersion(int version) {
    state = state.copyWith(inquiryVersion: version);
  }

  void setHandoutVersion(int? handoutVersionId) {
    state = state.copyWith(handoutVersionId: handoutVersionId);
  }

  void setQaSession(int? sessionId) {
    state = state.copyWith(qaSessionId: sessionId);
  }

  void setQuizAttempt(int? attemptId) {
    state = state.copyWith(quizAttemptId: attemptId);
  }

  void setReviewTaskCount(int count) {
    state = state.copyWith(reviewTaskCount: count);
  }

  void setProgressPercent(int percent) {
    state = state.copyWith(progressPercent: percent);
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
