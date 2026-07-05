import 'course_summary.dart';
import 'review_models.dart';

class HomeDashboardModel {
  const HomeDashboardModel({
    required this.recentCourses,
    required this.topReviewTasks,
    required this.recommendationEntryEnabled,
    required this.dailyRecommendedKnowledgePoints,
    required this.learningStats,
    required this.todayReviewTasks,
    required this.courseQuickEntries,
    this.currentCourse,
    this.currentLesson,
    this.continueLearning,
    this.nextStep,
    this.recommendedNextLesson,
    this.recommendedCourseQuiz,
  });

  final List<CourseSummaryModel> recentCourses;
  final List<ReviewTaskModel> topReviewTasks;
  final bool recommendationEntryEnabled;
  final List<DailyRecommendedKnowledgePointModel>
      dailyRecommendedKnowledgePoints;
  final LearningStatsModel learningStats;
  final List<HomeReviewTaskModel> todayReviewTasks;
  final List<HomeQuickEntryModel> courseQuickEntries;
  final CourseSummaryModel? currentCourse;
  final HomeLessonModel? currentLesson;
  final HomeRouteTargetModel? continueLearning;
  final HomeRouteTargetModel? nextStep;
  final HomeRouteTargetModel? recommendedNextLesson;
  final HomeRouteTargetModel? recommendedCourseQuiz;

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
      currentLesson: _parseLesson(json['currentLesson']),
      continueLearning: _parseRouteTarget(json['continueLearning']),
      nextStep: _parseRouteTarget(json['nextStep']),
      todayReviewTasks: (json['todayReviewTasks'] as List<dynamic>? ?? const [])
          .map(
            (item) => HomeReviewTaskModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
      recommendedNextLesson: _parseRouteTarget(json['recommendedNextLesson']),
      recommendedCourseQuiz: _parseRouteTarget(json['recommendedCourseQuiz']),
      courseQuickEntries:
          (json['courseQuickEntries'] as List<dynamic>? ?? const [])
              .map(
                (item) => HomeQuickEntryModel.fromJson(
                  Map<String, dynamic>.from(item as Map),
                ),
              )
              .toList(),
    );
  }
}

class HomeRouteTargetModel {
  const HomeRouteTargetModel({
    this.courseId,
    this.lessonId,
    this.startLessonId,
    this.endLessonId,
    this.completedLessonCount,
    this.lastPositionSec,
    this.lastHandoutBlockId,
    this.nextRoute,
    this.type,
    this.scopeType,
    this.title,
    this.reason,
    this.action,
    this.nextAction,
  });

  final int? courseId;
  final String? lessonId;
  final String? startLessonId;
  final String? endLessonId;
  final int? completedLessonCount;
  final int? lastPositionSec;
  final int? lastHandoutBlockId;
  final String? nextRoute;
  final String? type;
  final String? scopeType;
  final String? title;
  final String? reason;
  final String? action;
  final HomeNextActionModel? nextAction;

  factory HomeRouteTargetModel.fromJson(Map<String, dynamic> json) {
    return HomeRouteTargetModel(
      courseId: _parseInt(json['courseId']),
      lessonId: json['lessonId']?.toString(),
      startLessonId: json['startLessonId']?.toString(),
      endLessonId: json['endLessonId']?.toString(),
      completedLessonCount: _parseInt(json['completedLessonCount']),
      lastPositionSec: _parseInt(json['lastPositionSec']),
      lastHandoutBlockId: _parseInt(json['lastHandoutBlockId']),
      nextRoute: _parseNonEmptyString(json['nextRoute']),
      type: _parseNonEmptyString(json['type']),
      scopeType: _parseNonEmptyString(json['scopeType']),
      title: _parseNonEmptyString(json['title']),
      reason: _parseNonEmptyString(json['reason']),
      action: _parseNonEmptyString(json['action']),
      nextAction: _parseNextAction(json['nextAction']),
    );
  }
}

class HomeNextActionModel {
  const HomeNextActionModel({
    required this.type,
    this.label,
    this.positionSec,
    this.action,
  });

  final String type;
  final String? label;
  final int? positionSec;
  final String? action;

  factory HomeNextActionModel.fromJson(Map<String, dynamic> json) {
    return HomeNextActionModel(
      type: json['type'] as String? ?? 'action',
      label: _parseNonEmptyString(json['label']),
      positionSec: _parseInt(json['positionSec']),
      action: _parseNonEmptyString(json['action']),
    );
  }
}

class HomeLessonModel {
  const HomeLessonModel({
    required this.lessonId,
    required this.title,
    this.orderIndex,
    this.lessonStatus,
    this.handoutReadPercent,
    this.quizStatus,
    this.reviewStatus,
    this.lastPositionSec,
    this.lastHandoutBlockId,
    this.lastActivityAt,
  });

  final String lessonId;
  final String title;
  final int? orderIndex;
  final String? lessonStatus;
  final int? handoutReadPercent;
  final String? quizStatus;
  final String? reviewStatus;
  final int? lastPositionSec;
  final int? lastHandoutBlockId;
  final DateTime? lastActivityAt;

  factory HomeLessonModel.fromJson(Map<String, dynamic> json) {
    return HomeLessonModel(
      lessonId: json['lessonId']?.toString() ?? '',
      title: json['title'] as String? ?? '未命名课时',
      orderIndex: _parseInt(json['orderIndex']),
      lessonStatus: _parseNonEmptyString(json['lessonStatus']),
      handoutReadPercent: _parseInt(json['handoutReadPercent']),
      quizStatus: _parseNonEmptyString(json['quizStatus']),
      reviewStatus: _parseNonEmptyString(json['reviewStatus']),
      lastPositionSec: _parseInt(json['lastPositionSec']),
      lastHandoutBlockId: _parseInt(json['lastHandoutBlockId']),
      lastActivityAt: _parseDateTime(json['lastActivityAt']),
    );
  }
}

class HomeReviewTaskModel {
  const HomeReviewTaskModel({
    required this.type,
    this.courseId,
    this.lessonId,
    required this.title,
    required this.priorityScore,
    required this.reasonText,
    this.nextRoute,
  });

  final String type;
  final int? courseId;
  final String? lessonId;
  final String title;
  final int priorityScore;
  final String reasonText;
  final String? nextRoute;

  factory HomeReviewTaskModel.fromJson(Map<String, dynamic> json) {
    return HomeReviewTaskModel(
      type: json['type'] as String? ?? 'review',
      courseId: _parseInt(json['courseId']),
      lessonId: json['lessonId']?.toString(),
      title: json['title'] as String? ?? '复习任务',
      priorityScore: _parseInt(json['priorityScore']) ?? 0,
      reasonText: json['reasonText'] as String? ?? '',
      nextRoute: _parseNonEmptyString(json['nextRoute']),
    );
  }
}

class HomeQuickEntryModel {
  const HomeQuickEntryModel({
    required this.key,
    required this.title,
    required this.status,
    required this.enabled,
    this.target,
    this.message,
    this.route,
    this.action,
  });

  final String key;
  final String title;
  final String status;
  final bool enabled;
  final String? target;
  final String? message;
  final String? route;
  final String? action;

  factory HomeQuickEntryModel.fromJson(Map<String, dynamic> json) {
    return HomeQuickEntryModel(
      key: json['key'] as String? ?? '',
      title: json['title'] as String? ?? '入口',
      status: json['status'] as String? ?? 'placeholder',
      enabled: json['enabled'] as bool? ?? false,
      target: _parseNonEmptyString(json['target']),
      message: _parseNonEmptyString(json['message']),
      route: _parseNonEmptyString(json['route']),
      action: _parseNonEmptyString(json['action']),
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

HomeLessonModel? _parseLesson(Object? value) {
  if (value is! Map) {
    return null;
  }
  return HomeLessonModel.fromJson(Map<String, dynamic>.from(value));
}

HomeNextActionModel? _parseNextAction(Object? value) {
  if (value is! Map) {
    return null;
  }
  return HomeNextActionModel.fromJson(Map<String, dynamic>.from(value));
}

int? _parseInt(Object? value) {
  if (value == null || value is bool) {
    return null;
  }
  if (value is int) {
    return value;
  }
  if (value is num) {
    return value.toInt();
  }
  return int.tryParse(value.toString());
}

String? _parseNonEmptyString(Object? value) {
  final text = value?.toString();
  if (text == null || text.isEmpty) {
    return null;
  }
  return text;
}

DateTime? _parseDateTime(Object? value) {
  final text = _parseNonEmptyString(value);
  if (text == null) {
    return null;
  }
  return DateTime.tryParse(text);
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
