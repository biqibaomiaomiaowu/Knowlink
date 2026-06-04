class CourseProgressModel {
  const CourseProgressModel({
    required this.courseId,
    this.handoutVersionId,
    this.lastHandoutBlockId,
    this.lastVideoResourceId,
    this.lastPositionSec,
    this.lastDocResourceId,
    this.lastPageNo,
    this.lastSlideNo,
    this.lastAnchorKey,
    this.lastActivityAt,
    this.currentLessonId,
    this.currentLessonTitle,
  });

  final int courseId;
  final int? handoutVersionId;
  final int? lastHandoutBlockId;
  final int? lastVideoResourceId;
  final int? lastPositionSec;
  final int? lastDocResourceId;
  final int? lastPageNo;
  final int? lastSlideNo;
  final String? lastAnchorKey;
  final DateTime? lastActivityAt;
  final String? currentLessonId;
  final String? currentLessonTitle;

  bool get hasResumeTarget {
    return lastHandoutBlockId != null ||
        lastPositionSec != null ||
        lastPageNo != null ||
        lastSlideNo != null ||
        (lastAnchorKey != null && lastAnchorKey!.isNotEmpty);
  }

  factory CourseProgressModel.fromJson(Map<String, dynamic> json) {
    return CourseProgressModel(
      courseId: json['courseId'] as int,
      handoutVersionId: json['handoutVersionId'] as int?,
      lastHandoutBlockId: json['lastHandoutBlockId'] as int?,
      lastVideoResourceId: json['lastVideoResourceId'] as int?,
      lastPositionSec: json['lastPositionSec'] as int?,
      lastDocResourceId: json['lastDocResourceId'] as int?,
      lastPageNo: json['lastPageNo'] as int?,
      lastSlideNo: json['lastSlideNo'] as int?,
      lastAnchorKey: json['lastAnchorKey'] as String?,
      lastActivityAt: _parseDateTime(json['lastActivityAt'] as String?),
      currentLessonId: json['currentLessonId']?.toString(),
      currentLessonTitle: json['currentLessonTitle'] as String?,
    );
  }
}

class CourseProgressUpdateModel {
  const CourseProgressUpdateModel({
    this.handoutVersionId,
    this.lastHandoutBlockId,
    this.lastVideoResourceId,
    this.lastPositionSec,
    this.lastDocResourceId,
    this.lastPageNo,
    this.lastSlideNo,
    this.lastAnchorKey,
  });

  final int? handoutVersionId;
  final int? lastHandoutBlockId;
  final int? lastVideoResourceId;
  final int? lastPositionSec;
  final int? lastDocResourceId;
  final int? lastPageNo;
  final int? lastSlideNo;
  final String? lastAnchorKey;

  Map<String, dynamic> toJson() {
    return {
      if (handoutVersionId != null) 'handoutVersionId': handoutVersionId,
      if (lastHandoutBlockId != null) 'lastHandoutBlockId': lastHandoutBlockId,
      if (lastVideoResourceId != null)
        'lastVideoResourceId': lastVideoResourceId,
      if (lastPositionSec != null) 'lastPositionSec': lastPositionSec,
      if (lastDocResourceId != null) 'lastDocResourceId': lastDocResourceId,
      if (lastPageNo != null) 'lastPageNo': lastPageNo,
      if (lastSlideNo != null) 'lastSlideNo': lastSlideNo,
      if (lastAnchorKey != null) 'lastAnchorKey': lastAnchorKey,
    };
  }
}

DateTime? _parseDateTime(String? value) {
  if (value == null || value.isEmpty) {
    return null;
  }
  return DateTime.tryParse(value);
}
