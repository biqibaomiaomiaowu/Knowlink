import 'course_summary.dart';
import 'review_models.dart';

class HomeDashboardModel {
  const HomeDashboardModel({
    required this.recentCourses,
    required this.topReviewTasks,
    required this.recommendationEntryEnabled,
    required this.dailyRecommendedKnowledgePoints,
    required this.learningStats,
    this.currentCourse,
    this.continueLearning,
    this.nextStep,
  });

  final List<CourseSummaryModel> recentCourses;
  final List<ReviewTaskModel> topReviewTasks;
  final bool recommendationEntryEnabled;
  final List<DailyRecommendedKnowledgePointModel>
      dailyRecommendedKnowledgePoints;
  final LearningStatsModel learningStats;
  final CourseSummaryModel? currentCourse;
  final HomeRouteTargetModel? continueLearning;
  final HomeRouteTargetModel? nextStep;

  factory HomeDashboardModel.fromJson(Map<String, dynamic> json) {
    return HomeDashboardModel(
      recentCourses: (json['recentCourses'] as List<dynamic>? ?? const [])
          .map(
            (item) => CourseSummaryModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
      topReviewTasks: (json['topReviewTasks'] as List<dynamic>? ?? const [])
          .map(
            (item) => ReviewTaskModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
      recommendationEntryEnabled:
          json['recommendationEntryEnabled'] as bool? ?? true,
      dailyRecommendedKnowledgePoints:
          (json['dailyRecommendedKnowledgePoints'] as List<dynamic>? ??
                  const [])
              .map(
                (item) => DailyRecommendedKnowledgePointModel.fromJson(
                  Map<String, dynamic>.from(item as Map),
                ),
              )
              .toList(),
      learningStats: LearningStatsModel.fromJson(
        Map<String, dynamic>.from(
          json['learningStats'] as Map? ?? const <String, dynamic>{},
        ),
      ),
      currentCourse: _parseCourse(json['currentCourse']),
      continueLearning: _parseRouteTarget(json['continueLearning']),
      nextStep: _parseRouteTarget(json['nextStep']),
    );
  }
}

class HomeRouteTargetModel {
  const HomeRouteTargetModel({
    this.courseId,
    this.lessonId,
    this.nextRoute,
  });

  final int? courseId;
  final String? lessonId;
  final String? nextRoute;

  factory HomeRouteTargetModel.fromJson(Map<String, dynamic> json) {
    return HomeRouteTargetModel(
      courseId: _parseInt(json['courseId']),
      lessonId: json['lessonId']?.toString(),
      nextRoute: _parseNonEmptyString(json['nextRoute']),
    );
  }
}

class DailyRecommendedKnowledgePointModel {
  const DailyRecommendedKnowledgePointModel({
    required this.knowledgePoint,
    required this.reason,
    this.targetCourseId,
  });

  final String knowledgePoint;
  final String reason;
  final int? targetCourseId;

  factory DailyRecommendedKnowledgePointModel.fromJson(
    Map<String, dynamic> json,
  ) {
    return DailyRecommendedKnowledgePointModel(
      knowledgePoint: json['knowledgePoint'] as String? ?? '知识点',
      reason: json['reason'] as String? ?? '',
      targetCourseId: json['targetCourseId'] as int?,
    );
  }
}

CourseSummaryModel? _parseCourse(Object? value) {
  if (value is! Map) {
    return null;
  }
  return CourseSummaryModel.fromJson(Map<String, dynamic>.from(value));
}

HomeRouteTargetModel? _parseRouteTarget(Object? value) {
  if (value is! Map) {
    return null;
  }
  return HomeRouteTargetModel.fromJson(Map<String, dynamic>.from(value));
}

int? _parseInt(Object? value) {
  if (value is int) {
    return value;
  }
  if (value is String) {
    return int.tryParse(value);
  }
  return null;
}

String? _parseNonEmptyString(Object? value) {
  final text = value?.toString();
  if (text == null || text.isEmpty) {
    return null;
  }
  return text;
}

class LearningStatsModel {
  const LearningStatsModel({
    required this.streakDays,
    required this.completedCourses,
    required this.reviewTasksCompleted,
    required this.totalLearningMinutes,
  });

  final int streakDays;
  final int completedCourses;
  final int reviewTasksCompleted;
  final int totalLearningMinutes;

  factory LearningStatsModel.fromJson(Map<String, dynamic> json) {
    return LearningStatsModel(
      streakDays: json['streakDays'] as int? ?? 0,
      completedCourses: json['completedCourses'] as int? ?? 0,
      reviewTasksCompleted: json['reviewTasksCompleted'] as int? ?? 0,
      totalLearningMinutes: json['totalLearningMinutes'] as int? ?? 0,
    );
  }
}
