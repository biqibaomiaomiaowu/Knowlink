import 'course_summary.dart';
import 'review_models.dart';

class HomeDashboardModel {
  const HomeDashboardModel({
    required this.recentCourses,
    required this.topReviewTasks,
    required this.recommendationEntryEnabled,
    required this.dailyRecommendedKnowledgePoints,
    required this.learningStats,
  });

  final List<CourseSummaryModel> recentCourses;
  final List<ReviewTaskModel> topReviewTasks;
  final bool recommendationEntryEnabled;
  final List<DailyRecommendedKnowledgePointModel>
      dailyRecommendedKnowledgePoints;
  final LearningStatsModel learningStats;

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
