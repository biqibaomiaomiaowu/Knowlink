class CourseFlowState {
  const CourseFlowState({
    this.courseId,
    this.lifecycleStatus = 'draft',
    this.pipelineStage = 'idle',
    this.pipelineStatus = 'idle',
    this.inquiryVersion = 0,
    this.activeParseRunId,
    this.handoutVersionId,
    this.qaSessionId,
    this.quizAttemptId,
    this.reviewTaskCount = 0,
    this.progressPct = 0,
  });

  final String? courseId;
  final String lifecycleStatus;
  final String pipelineStage;
  final String pipelineStatus;
  final int inquiryVersion;
  final int? activeParseRunId;
  final int? handoutVersionId;
  final int? qaSessionId;
  final int? quizAttemptId;
  final int reviewTaskCount;
  final int progressPct;

  CourseFlowState copyWith({
    String? courseId,
    String? lifecycleStatus,
    String? pipelineStage,
    String? pipelineStatus,
    int? inquiryVersion,
    int? activeParseRunId,
    int? handoutVersionId,
    int? qaSessionId,
    int? quizAttemptId,
    int? reviewTaskCount,
    int? progressPct,
  }) {
    return CourseFlowState(
      courseId: courseId ?? this.courseId,
      lifecycleStatus: lifecycleStatus ?? this.lifecycleStatus,
      pipelineStage: pipelineStage ?? this.pipelineStage,
      pipelineStatus: pipelineStatus ?? this.pipelineStatus,
      inquiryVersion: inquiryVersion ?? this.inquiryVersion,
      activeParseRunId: activeParseRunId ?? this.activeParseRunId,
      handoutVersionId: handoutVersionId ?? this.handoutVersionId,
      qaSessionId: qaSessionId ?? this.qaSessionId,
      quizAttemptId: quizAttemptId ?? this.quizAttemptId,
      reviewTaskCount: reviewTaskCount ?? this.reviewTaskCount,
      progressPct: progressPct ?? this.progressPct,
    );
  }
}
