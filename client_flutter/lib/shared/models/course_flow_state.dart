class CourseFlowState {
  const CourseFlowState({
    this.courseId,
    this.lifecycleStatus = 'draft',
    this.pipelineStage = 'idle',
    this.pipelineStatus = 'idle',
    this.progressPct = 0,
    this.activeParseRunId,
    this.activeHandoutVersionId,
    this.nextAction = 'none',
    this.sessionId,
    this.quizId,
    this.quizAttemptId,
    this.reviewTaskRunId,
  });

  final String? courseId;
  final String lifecycleStatus;
  final String pipelineStage;
  final String pipelineStatus;
  final int progressPct;
  final int? activeParseRunId;
  final int? activeHandoutVersionId;
  final String nextAction;
  final int? sessionId;
  final int? quizId;
  final int? quizAttemptId;
  final int? reviewTaskRunId;

  CourseFlowState copyWith({
    String? courseId,
    String? lifecycleStatus,
    String? pipelineStage,
    String? pipelineStatus,
    int? progressPct,
    int? activeParseRunId,
    bool clearActiveParseRunId = false,
    int? activeHandoutVersionId,
    bool clearActiveHandoutVersionId = false,
    String? nextAction,
    int? sessionId,
    bool clearSessionId = false,
    int? quizId,
    bool clearQuizId = false,
    int? quizAttemptId,
    bool clearQuizAttemptId = false,
    int? reviewTaskRunId,
    bool clearReviewTaskRunId = false,
  }) {
    return CourseFlowState(
      courseId: courseId ?? this.courseId,
      lifecycleStatus: lifecycleStatus ?? this.lifecycleStatus,
      pipelineStage: pipelineStage ?? this.pipelineStage,
      pipelineStatus: pipelineStatus ?? this.pipelineStatus,
      progressPct: progressPct ?? this.progressPct,
      activeParseRunId: clearActiveParseRunId
          ? null
          : activeParseRunId ?? this.activeParseRunId,
      activeHandoutVersionId: clearActiveHandoutVersionId
          ? null
          : activeHandoutVersionId ?? this.activeHandoutVersionId,
      nextAction: nextAction ?? this.nextAction,
      sessionId: clearSessionId ? null : sessionId ?? this.sessionId,
      quizId: clearQuizId ? null : quizId ?? this.quizId,
      quizAttemptId: clearQuizAttemptId ? null : quizAttemptId ?? this.quizAttemptId,
      reviewTaskRunId: clearReviewTaskRunId
          ? null
          : reviewTaskRunId ?? this.reviewTaskRunId,
    );
  }
}
