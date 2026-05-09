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

class ReviewTaskModel {
  const ReviewTaskModel({
    required this.reviewTaskId,
    required this.taskType,
    required this.priorityScore,
    required this.reasonText,
    required this.recommendedMinutes,
    this.recommendedSegment,
    this.practiceEntry,
    this.reviewOrder,
    this.intensity,
  });

  final int reviewTaskId;
  final String taskType;
  final int priorityScore;
  final String reasonText;
  final int recommendedMinutes;
  final RecommendedSegmentModel? recommendedSegment;
  final PracticeEntryModel? practiceEntry;
  final int? reviewOrder;
  final String? intensity;

  factory ReviewTaskModel.fromJson(Map<String, dynamic> json) {
    return ReviewTaskModel(
      reviewTaskId: json['reviewTaskId'] as int,
      taskType: json['taskType'] as String? ?? 'review',
      priorityScore: json['priorityScore'] as int? ?? 0,
      reasonText: json['reasonText'] as String? ?? '',
      recommendedMinutes: json['recommendedMinutes'] as int? ?? 0,
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
    );
  }
}

class RecommendedSegmentModel {
  const RecommendedSegmentModel({
    this.blockId,
    this.startSec,
    this.endSec,
    this.label,
  });

  final int? blockId;
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
      blockId: json['blockId'] as int?,
      startSec: json['startSec'] as int?,
      endSec: json['endSec'] as int?,
      label: json['label'] as String?,
    );
  }
}

class PracticeEntryModel {
  const PracticeEntryModel({
    required this.type,
    this.targetId,
    this.label,
  });

  final String type;
  final int? targetId;
  final String? label;

  factory PracticeEntryModel.fromJson(Map<String, dynamic> json) {
    return PracticeEntryModel(
      type: json['type'] as String? ?? 'practice',
      targetId: json['targetId'] as int?,
      label: json['label'] as String?,
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

String _formatSec(int seconds) {
  final minutes = seconds ~/ 60;
  final rest = seconds % 60;
  return '$minutes:${rest.toString().padLeft(2, '0')}';
}
