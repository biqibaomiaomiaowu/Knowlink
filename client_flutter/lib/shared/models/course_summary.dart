class CourseSummaryModel {
  const CourseSummaryModel({
    required this.courseId,
    required this.title,
    required this.entryType,
    required this.lifecycleStatus,
    required this.pipelineStage,
    required this.pipelineStatus,
    required this.updatedAt,
    this.catalogId,
    this.currentLessonId,
    this.currentLessonTitle,
    this.lastPositionSec,
  });

  final int courseId;
  final String title;
  final String entryType;
  final String? catalogId;
  final String lifecycleStatus;
  final String pipelineStage;
  final String pipelineStatus;
  final DateTime updatedAt;
  final String? currentLessonId;
  final String? currentLessonTitle;
  final int? lastPositionSec;

  factory CourseSummaryModel.fromJson(Map<String, dynamic> json) {
    return CourseSummaryModel(
      courseId: json['courseId'] as int,
      title: json['title'] as String,
      entryType: json['entryType'] as String,
      catalogId: json['catalogId'] as String?,
      lifecycleStatus: json['lifecycleStatus'] as String,
      pipelineStage: json['pipelineStage'] as String,
      pipelineStatus: json['pipelineStatus'] as String,
      updatedAt: DateTime.parse(json['updatedAt'] as String),
      currentLessonId: json['currentLessonId']?.toString(),
      currentLessonTitle: json['currentLessonTitle'] as String?,
      lastPositionSec: json['lastPositionSec'] as int?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'courseId': courseId,
      'title': title,
      'entryType': entryType,
      'catalogId': catalogId,
      'lifecycleStatus': lifecycleStatus,
      'pipelineStage': pipelineStage,
      'pipelineStatus': pipelineStatus,
      'updatedAt': updatedAt.toIso8601String(),
      'currentLessonId': currentLessonId,
      'currentLessonTitle': currentLessonTitle,
      'lastPositionSec': lastPositionSec,
    };
  }
}
