import 'pipeline_status.dart';

class ReviewTasksModel {
  const ReviewTasksModel({
    required this.items,
  });

  final List<ReviewTaskModel> items;

  List<ReviewTaskModel> get topThree => items.take(3).toList();

  factory ReviewTasksModel.fromJson(Map<String, dynamic> json) {
    return ReviewTasksModel(
      items: (json['items'] as List<dynamic>? ?? const [])
          .map(
            (item) => ReviewTaskModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
    );
  }
}

class CourseReviewModel {
  const CourseReviewModel({
    this.courseId,
    required this.scopeType,
    this.lessonId,
    required this.status,
    required this.items,
    required this.todayTaskCount,
    required this.weakPointCount,
    required this.mistakeCount,
    this.masteryScore,
    required this.topTasks,
    required this.weakLessons,
    required this.crossLessonWeakPoints,
  });

  final int? courseId;
  final String scopeType;
  final int? lessonId;
  final String status;
  final List<ReviewTaskModel> items;
  final int todayTaskCount;
  final int weakPointCount;
  final int mistakeCount;
  final double? masteryScore;
  final List<ReviewTaskModel> topTasks;
  final List<WeakLessonReviewModel> weakLessons;
  final List<CrossLessonWeakPointModel> crossLessonWeakPoints;

  factory CourseReviewModel.fromJson(Map<String, dynamic> json) {
    return CourseReviewModel(
      courseId: _intValue(json['courseId']),
      scopeType: json['scopeType'] as String? ?? 'course',
      lessonId: _intValue(json['lessonId']),
      status: json['status'] as String? ?? 'placeholder',
      items: _reviewTasksFromJson(json['items']),
      todayTaskCount: _intValue(json['todayTaskCount']) ?? 0,
      weakPointCount: _intValue(json['weakPointCount']) ?? 0,
      mistakeCount: _intValue(json['mistakeCount']) ?? 0,
      masteryScore: (json['masteryScore'] as num?)?.toDouble(),
      topTasks: _reviewTasksFromJson(json['topTasks']),
      weakLessons: (json['weakLessons'] as List<dynamic>? ?? const [])
          .map(
            (item) => WeakLessonReviewModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
      crossLessonWeakPoints:
          (json['crossLessonWeakPoints'] as List<dynamic>? ?? const [])
              .map(
                (item) => CrossLessonWeakPointModel.fromJson(
                  Map<String, dynamic>.from(item as Map),
                ),
              )
              .toList(),
    );
  }
}

class LessonReviewModel {
  const LessonReviewModel({
    this.courseId,
    required this.scopeType,
    required this.lessonId,
    required this.status,
    required this.items,
  });

  final int? courseId;
  final String scopeType;
  final int lessonId;
  final String status;
  final List<ReviewTaskModel> items;

  factory LessonReviewModel.fromJson(Map<String, dynamic> json) {
    return LessonReviewModel(
      courseId: _intValue(json['courseId']),
      scopeType: json['scopeType'] as String? ?? 'lesson',
      lessonId: _intValue(json['lessonId']) ?? 0,
      status: json['status'] as String? ?? 'placeholder',
      items: _reviewTasksFromJson(json['items']),
    );
  }
}

class ReviewTaskModel {
  const ReviewTaskModel({
    required this.reviewTaskId,
    this.taskId,
    required this.taskType,
    required this.priorityScore,
    required this.reasonText,
    required this.recommendedMinutes,
    this.scopeType,
    this.lessonId,
    this.sourceAttemptId,
    this.sourceQuestionKeys = const [],
    this.knowledgePointKey,
    this.recommendedSegment,
    this.practiceEntry,
    this.reviewOrder,
    this.intensity,
    this.completionSupported = true,
    this.sourceLesson,
    this.linkedHandoutBlockId,
    this.recommendedAction,
    this.recommendedHandoutBlock,
    this.jumpRoute,
    this.evidenceChain = const [],
  });

  final int reviewTaskId;
  final int? taskId;
  final String taskType;
  final int priorityScore;
  final String reasonText;
  final int recommendedMinutes;
  final String? scopeType;
  final int? lessonId;
  final int? sourceAttemptId;
  final List<String> sourceQuestionKeys;
  final String? knowledgePointKey;
  final RecommendedSegmentModel? recommendedSegment;
  final PracticeEntryModel? practiceEntry;
  final int? reviewOrder;
  final String? intensity;
  final bool completionSupported;
  final SourceLessonModel? sourceLesson;
  final int? linkedHandoutBlockId;
  final RecommendedActionModel? recommendedAction;
  final RecommendedHandoutBlockModel? recommendedHandoutBlock;
  final String? jumpRoute;
  final List<EvidenceChainItemModel> evidenceChain;

  factory ReviewTaskModel.fromJson(Map<String, dynamic> json) {
    return ReviewTaskModel(
      reviewTaskId:
          _intValue(json['reviewTaskId']) ?? _intValue(json['taskId']) ?? 0,
      taskId: _intValue(json['taskId']),
      taskType: json['taskType'] as String? ?? 'review',
      priorityScore: _intValue(json['priorityScore']) ?? 0,
      reasonText: json['reasonText'] as String? ?? '',
      recommendedMinutes: _intValue(json['recommendedMinutes']) ?? 0,
      scopeType: json['scopeType'] as String?,
      lessonId: _intValue(json['lessonId']),
      sourceAttemptId: _intValue(json['sourceAttemptId']),
      sourceQuestionKeys:
          (json['sourceQuestionKeys'] as List<dynamic>? ?? const [])
              .map((item) => item.toString())
              .toList(),
      knowledgePointKey: json['knowledgePointKey'] as String?,
      recommendedSegment: json['recommendedSegment'] == null
          ? null
          : RecommendedSegmentModel.fromJson(
              Map<String, dynamic>.from(json['recommendedSegment'] as Map),
            ),
      practiceEntry: json['practiceEntry'] == null
          ? null
          : PracticeEntryModel.fromJson(
              Map<String, dynamic>.from(json['practiceEntry'] as Map),
            ),
      reviewOrder: json['reviewOrder'] as int?,
      intensity: json['intensity'] as String?,
      completionSupported: json['completionSupported'] as bool? ?? true,
      sourceLesson: json['sourceLesson'] == null
          ? null
          : SourceLessonModel.fromJson(
              Map<String, dynamic>.from(json['sourceLesson'] as Map),
            ),
      linkedHandoutBlockId: _intValue(json['linkedHandoutBlockId']),
      recommendedAction: json['recommendedAction'] == null
          ? null
          : RecommendedActionModel.fromJson(
              Map<String, dynamic>.from(json['recommendedAction'] as Map),
            ),
      recommendedHandoutBlock: json['recommendedHandoutBlock'] == null
          ? null
          : RecommendedHandoutBlockModel.fromJson(
              Map<String, dynamic>.from(
                json['recommendedHandoutBlock'] as Map,
              ),
            ),
      jumpRoute: json['jumpRoute'] as String?,
      evidenceChain: (json['evidenceChain'] as List<dynamic>? ?? const [])
          .map(
            (item) => EvidenceChainItemModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
    );
  }
}

class RecommendedSegmentModel {
  const RecommendedSegmentModel({
    this.blockId,
    this.lessonId,
    this.startSec,
    this.endSec,
    this.label,
  });

  final int? blockId;
  final int? lessonId;
  final int? startSec;
  final int? endSec;
  final String? label;

  String get displayText {
    final parts = <String>[];
    if (label != null && label!.isNotEmpty) {
      parts.add(label!);
    }
    if (startSec != null && endSec != null) {
      parts.add('${_formatSec(startSec!)}-${_formatSec(endSec!)}');
    }
    if (blockId != null) {
      parts.add('讲义块 $blockId');
    }
    return parts.isEmpty ? '复习片段' : parts.join(' · ');
  }

  factory RecommendedSegmentModel.fromJson(Map<String, dynamic> json) {
    return RecommendedSegmentModel(
      blockId: _intValue(json['blockId']),
      lessonId: _intValue(json['lessonId']),
      startSec: _intValue(json['startSec']),
      endSec: _intValue(json['endSec']),
      label: json['label'] as String?,
    );
  }
}

class PracticeEntryModel {
  const PracticeEntryModel({
    required this.type,
    this.targetId,
    this.lessonId,
    this.label,
  });

  final String type;
  final int? targetId;
  final int? lessonId;
  final String? label;

  factory PracticeEntryModel.fromJson(Map<String, dynamic> json) {
    return PracticeEntryModel(
      type: json['type'] as String? ?? 'practice',
      targetId: _intValue(json['targetId']),
      lessonId: _intValue(json['lessonId']),
      label: json['label'] as String?,
    );
  }
}

class SourceLessonModel {
  const SourceLessonModel({
    required this.lessonId,
    this.title,
    this.masteryScore,
  });

  final int lessonId;
  final String? title;
  final double? masteryScore;

  factory SourceLessonModel.fromJson(Map<String, dynamic> json) {
    return SourceLessonModel(
      lessonId: _intValue(json['lessonId']) ?? 0,
      title: json['title'] as String?,
      masteryScore: (json['masteryScore'] as num?)?.toDouble(),
    );
  }
}

class RecommendedActionModel {
  const RecommendedActionModel({
    required this.type,
    this.label,
    this.targetBlockId,
    this.targetId,
  });

  final String type;
  final String? label;
  final int? targetBlockId;
  final int? targetId;

  factory RecommendedActionModel.fromJson(Map<String, dynamic> json) {
    return RecommendedActionModel(
      type: json['type'] as String? ?? 'review',
      label: json['label'] as String?,
      targetBlockId: _intValue(json['targetBlockId']),
      targetId: _intValue(json['targetId']),
    );
  }
}

class RecommendedHandoutBlockModel {
  const RecommendedHandoutBlockModel({
    this.blockId,
    this.handoutBlockId,
    this.title,
  });

  final int? blockId;
  final int? handoutBlockId;
  final String? title;

  factory RecommendedHandoutBlockModel.fromJson(Map<String, dynamic> json) {
    return RecommendedHandoutBlockModel(
      blockId: _intValue(json['blockId']),
      handoutBlockId: _intValue(json['handoutBlockId']),
      title: json['title'] as String?,
    );
  }
}

class WeakLessonReviewModel {
  const WeakLessonReviewModel({
    required this.lessonId,
    this.title,
    this.masteryScore,
    this.reasonText,
  });

  final int lessonId;
  final String? title;
  final double? masteryScore;
  final String? reasonText;

  factory WeakLessonReviewModel.fromJson(Map<String, dynamic> json) {
    return WeakLessonReviewModel(
      lessonId: _intValue(json['lessonId']) ?? 0,
      title: json['title'] as String?,
      masteryScore: (json['masteryScore'] as num?)?.toDouble(),
      reasonText: json['reasonText'] as String?,
    );
  }
}

class CrossLessonWeakPointModel {
  const CrossLessonWeakPointModel({
    this.knowledgePointKey,
    this.title,
    this.lessonIds = const [],
    this.evidenceChain = const [],
  });

  final String? knowledgePointKey;
  final String? title;
  final List<int> lessonIds;
  final List<EvidenceChainItemModel> evidenceChain;

  factory CrossLessonWeakPointModel.fromJson(Map<String, dynamic> json) {
    return CrossLessonWeakPointModel(
      knowledgePointKey: json['knowledgePointKey'] as String?,
      title: json['title'] as String?,
      lessonIds: (json['lessonIds'] as List<dynamic>? ?? const [])
          .map(_intValue)
          .whereType<int>()
          .toList(),
      evidenceChain: (json['evidenceChain'] as List<dynamic>? ?? const [])
          .map(
            (item) => EvidenceChainItemModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
    );
  }
}

class EvidenceChainItemModel {
  const EvidenceChainItemModel({
    this.type,
    this.scopeType,
    this.courseId,
    this.lessonId,
    this.title,
  });

  final String? type;
  final String? scopeType;
  final int? courseId;
  final int? lessonId;
  final String? title;

  factory EvidenceChainItemModel.fromJson(Map<String, dynamic> json) {
    return EvidenceChainItemModel(
      type: json['type'] as String?,
      scopeType: json['scopeType'] as String?,
      courseId: _intValue(json['courseId']),
      lessonId: _intValue(json['lessonId']),
      title: json['title'] as String?,
    );
  }
}

class ReviewRegenerateResultModel {
  const ReviewRegenerateResultModel({
    required this.taskId,
    required this.status,
    required this.nextAction,
    required this.entity,
  });

  final int taskId;
  final String status;
  final String nextAction;
  final AsyncEntityModel entity;

  factory ReviewRegenerateResultModel.fromJson(Map<String, dynamic> json) {
    return ReviewRegenerateResultModel(
      taskId: json['taskId'] as int,
      status: json['status'] as String,
      nextAction: json['nextAction'] as String,
      entity: AsyncEntityModel.fromJson(
        Map<String, dynamic>.from(json['entity'] as Map),
      ),
    );
  }
}

class ReviewRunStatusModel {
  const ReviewRunStatusModel({
    required this.reviewTaskRunId,
    required this.courseId,
    required this.status,
    required this.generatedCount,
  });

  final int reviewTaskRunId;
  final int courseId;
  final String status;
  final int generatedCount;

  bool get isTerminal {
    return status == 'ready' ||
        status == 'succeeded' ||
        status == 'partial_success' ||
        status == 'failed' ||
        status == 'skipped';
  }

  factory ReviewRunStatusModel.fromJson(Map<String, dynamic> json) {
    return ReviewRunStatusModel(
      reviewTaskRunId: json['reviewTaskRunId'] as int,
      courseId: json['courseId'] as int,
      status: json['status'] as String? ?? 'unknown',
      generatedCount: json['generatedCount'] as int? ?? 0,
    );
  }
}

class CompleteReviewTaskResultModel {
  const CompleteReviewTaskResultModel({
    required this.reviewTaskId,
    required this.completed,
  });

  final int reviewTaskId;
  final bool completed;

  factory CompleteReviewTaskResultModel.fromJson(Map<String, dynamic> json) {
    return CompleteReviewTaskResultModel(
      reviewTaskId: json['reviewTaskId'] as int,
      completed: json['completed'] as bool? ?? false,
    );
  }
}

List<ReviewTaskModel> _reviewTasksFromJson(Object? value) {
  return (value as List<dynamic>? ?? const [])
      .map(
        (item) => ReviewTaskModel.fromJson(
          Map<String, dynamic>.from(item as Map),
        ),
      )
      .toList();
}

int? _intValue(Object? value) {
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

String _formatSec(int seconds) {
  final minutes = seconds ~/ 60;
  final rest = seconds % 60;
  return '$minutes:${rest.toString().padLeft(2, '0')}';
}
