class CourseFlowState {
  const CourseFlowState({
    this.courseId,
    this.pipelineStatus = 'idle',
    this.inquiryVersion = 0,
    this.handoutVersionId,
    this.qaSessionId,
    this.quizAttemptId,
    this.reviewTaskCount = 0,
    this.progressPercent = 0,
  });

  final String? courseId;
  final String pipelineStatus;
  final int inquiryVersion;
  final int? handoutVersionId;
  final int? qaSessionId;
  final int? quizAttemptId;
  final int reviewTaskCount;
  final int progressPercent;

  CourseFlowState copyWith({
    String? courseId,
    String? pipelineStatus,
    int? inquiryVersion,
    int? handoutVersionId,
    int? qaSessionId,
    int? quizAttemptId,
    int? reviewTaskCount,
    int? progressPercent,
  }) {
    return CourseFlowState(
      courseId: courseId ?? this.courseId,
      pipelineStatus: pipelineStatus ?? this.pipelineStatus,
      inquiryVersion: inquiryVersion ?? this.inquiryVersion,
      handoutVersionId: handoutVersionId ?? this.handoutVersionId,
      qaSessionId: qaSessionId ?? this.qaSessionId,
      quizAttemptId: quizAttemptId ?? this.quizAttemptId,
      reviewTaskCount: reviewTaskCount ?? this.reviewTaskCount,
      progressPercent: progressPercent ?? this.progressPercent,
    );
  }
}
