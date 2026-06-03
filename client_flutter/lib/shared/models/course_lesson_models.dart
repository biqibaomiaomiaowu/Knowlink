class CourseLibraryItemModel {
  const CourseLibraryItemModel({
    required this.courseId,
    required this.title,
    required this.isCurrent,
    required this.entryType,
    required this.learningStatus,
    required this.lessonCount,
    required this.courseResourceCount,
    required this.pendingReviewCount,
    required this.pipelineStage,
    required this.pipelineStatus,
    required this.lifecycleStatus,
    this.lastActivityAt,
    this.currentLessonId,
    this.currentLessonTitle,
    this.overallMasteryScore,
    this.archivedAt,
  });

  final String courseId;
  final String title;
  final bool isCurrent;
  final String entryType;
  final String learningStatus;
  final DateTime? lastActivityAt;
  final int lessonCount;
  final int courseResourceCount;
  final String? currentLessonId;
  final String? currentLessonTitle;
  final double? overallMasteryScore;
  final int pendingReviewCount;
  final String pipelineStage;
  final String pipelineStatus;
  final String lifecycleStatus;
  final DateTime? archivedAt;

  factory CourseLibraryItemModel.fromJson(Map<String, dynamic> json) {
    return CourseLibraryItemModel(
      courseId: _stringId(json['courseId']),
      title: json['title'] as String? ?? '未命名课程',
      isCurrent: json['isCurrent'] as bool? ?? false,
      entryType: json['entryType'] as String? ?? 'manual_import',
      learningStatus: json['learningStatus'] as String? ??
          json['lifecycleStatus'] as String? ??
          'draft',
      lastActivityAt: _dateTime(json['lastActivityAt']),
      lessonCount: _intValue(json['lessonCount']),
      courseResourceCount: _intValue(json['courseResourceCount']),
      currentLessonId: _nullableString(json['currentLessonId']),
      currentLessonTitle: json['currentLessonTitle'] as String?,
      overallMasteryScore: _doubleValue(json['overallMasteryScore']),
      pendingReviewCount: _intValue(json['pendingReviewCount']),
      pipelineStage: json['pipelineStage'] as String? ?? 'idle',
      pipelineStatus: json['pipelineStatus'] as String? ?? 'idle',
      lifecycleStatus: json['lifecycleStatus'] as String? ?? 'draft',
      archivedAt: _dateTime(json['archivedAt']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'courseId': courseId,
      'title': title,
      'isCurrent': isCurrent,
      'entryType': entryType,
      'learningStatus': learningStatus,
      'lastActivityAt': lastActivityAt?.toIso8601String(),
      'lessonCount': lessonCount,
      'courseResourceCount': courseResourceCount,
      'currentLessonId': currentLessonId,
      'currentLessonTitle': currentLessonTitle,
      'overallMasteryScore': overallMasteryScore,
      'pendingReviewCount': pendingReviewCount,
      'pipelineStage': pipelineStage,
      'pipelineStatus': pipelineStatus,
      'lifecycleStatus': lifecycleStatus,
      'archivedAt': archivedAt?.toIso8601String(),
    };
  }
}

class CourseWorkbenchModel {
  const CourseWorkbenchModel({
    required this.course,
    required this.progress,
    required this.lessons,
    required this.courseResources,
    required this.quickEntries,
    required this.nextActions,
    required this.placeholderStates,
    this.currentLesson,
  });

  final CourseLibraryItemModel course;
  final Map<String, dynamic> progress;
  final LessonSummaryModel? currentLesson;
  final List<LessonSummaryModel> lessons;
  final List<ScopedResourceModel> courseResources;
  final List<PlaceholderEntryModel> quickEntries;
  final List<NextActionModel> nextActions;
  final Map<String, PlaceholderEntryModel> placeholderStates;

  factory CourseWorkbenchModel.fromJson(Map<String, dynamic> json) {
    final placeholderJson = Map<String, dynamic>.from(
      json['placeholderStates'] as Map? ?? const <String, dynamic>{},
    );
    final course = CourseLibraryItemModel.fromJson(
      Map<String, dynamic>.from(json['course'] as Map),
    );
    return CourseWorkbenchModel(
      course: course,
      progress: Map<String, dynamic>.from(
        json['progress'] as Map? ?? const <String, dynamic>{},
      ),
      currentLesson: json['currentLesson'] == null
          ? null
          : LessonSummaryModel.fromJson(
              Map<String, dynamic>.from(json['currentLesson'] as Map),
            ),
      lessons: _listOfMaps(json['lessons'])
          .map(LessonSummaryModel.fromJson)
          .toList(),
      courseResources: _listOfMaps(json['courseResources'])
          .map(ScopedResourceModel.fromJson)
          .toList(),
      quickEntries: _listOfMaps(json['quickEntries'])
          .map(PlaceholderEntryModel.fromJson)
          .toList(),
      nextActions: _listOfMaps(json['nextActions'])
          .map(
            (action) => NextActionModel.fromJson(
              _workbenchNextActionJson(action, courseId: course.courseId),
            ),
          )
          .toList(),
      placeholderStates: placeholderJson.map(
        (key, value) => MapEntry(
          key,
          PlaceholderEntryModel.fromJson(
              Map<String, dynamic>.from(value as Map)),
        ),
      ),
    );
  }

  int get progressPct {
    final explicit = _nullableInt(progress['progressPct']);
    if (explicit != null) {
      return explicit;
    }
    final total = _nullableInt(progress['lessonCount']) ??
        _nullableInt(progress['totalLessonCount']) ??
        lessons.length;
    final completed = _nullableInt(progress['completedLessonCount']) ?? 0;
    if (total == 0) {
      return 0;
    }
    return ((completed / total) * 100).round();
  }
}

Map<String, dynamic> _workbenchNextActionJson(
  Map<String, dynamic> json, {
  required String courseId,
}) {
  final action = Map<String, dynamic>.from(json);
  final type = action['type'] as String? ?? action['actionType'] as String?;
  final lessonId = _nullableString(action['lessonId']);
  if (type == 'continue_lesson' && lessonId != null) {
    action.putIfAbsent('route', () => '/courses/$courseId/lessons/$lessonId');
    action.putIfAbsent('label', () {
      final title =
          action['title'] as String? ?? action['lessonTitle'] as String?;
      return title == null || title.isEmpty ? '继续学习当前课时' : '继续学习$title';
    });
  }
  return action;
}

class LessonSummaryModel {
  const LessonSummaryModel({
    required this.lessonId,
    required this.courseId,
    required this.title,
    required this.orderIndex,
    required this.lessonStatus,
    required this.handoutStatus,
    required this.quizStatus,
    required this.reviewStatus,
    this.primaryVideoResourceId,
    this.primaryVideoStartSec,
    this.primaryVideoEndSec,
    this.masteryScore,
    this.lastPositionSec,
    this.lastActivityAt,
    this.nextAction,
  });

  final String lessonId;
  final String courseId;
  final String title;
  final int orderIndex;
  final String lessonStatus;
  final String? primaryVideoResourceId;
  final int? primaryVideoStartSec;
  final int? primaryVideoEndSec;
  final String handoutStatus;
  final String quizStatus;
  final String reviewStatus;
  final double? masteryScore;
  final int? lastPositionSec;
  final DateTime? lastActivityAt;
  final NextActionModel? nextAction;

  factory LessonSummaryModel.fromJson(Map<String, dynamic> json) {
    return LessonSummaryModel(
      lessonId: _stringId(json['lessonId']),
      courseId: _stringId(json['courseId']),
      title: json['title'] as String? ?? '未命名课时',
      orderIndex: _intValue(json['orderIndex']),
      lessonStatus: json['lessonStatus'] as String? ?? 'draft',
      primaryVideoResourceId: _nullableString(json['primaryVideoResourceId']),
      primaryVideoStartSec: _nullableInt(json['primaryVideoStartSec']),
      primaryVideoEndSec: _nullableInt(json['primaryVideoEndSec']),
      handoutStatus: json['handoutStatus'] as String? ?? 'not_generated',
      quizStatus: json['quizStatus'] as String? ?? 'not_generated',
      reviewStatus: json['reviewStatus'] as String? ?? 'not_due',
      masteryScore: _doubleValue(json['masteryScore']),
      lastPositionSec: _nullableInt(json['lastPositionSec']),
      lastActivityAt: _dateTime(json['lastActivityAt']),
      nextAction: json['nextAction'] == null
          ? null
          : NextActionModel.fromJson(
              Map<String, dynamic>.from(json['nextAction'] as Map),
            ),
    );
  }
}

class LessonDetailModel {
  const LessonDetailModel({
    required this.lesson,
    required this.lessonResources,
    required this.artifactSummaries,
    required this.progress,
    required this.citations,
    required this.sourceOverview,
    required this.knowledgePointPlaceholders,
    required this.weaknessPlaceholders,
    this.primaryVideo,
    this.nextAction,
  });

  final LessonSummaryModel lesson;
  final ScopedResourceModel? primaryVideo;
  final List<ScopedResourceModel> lessonResources;
  final List<PlaceholderEntryModel> artifactSummaries;
  final Map<String, dynamic> progress;
  final List<CitationModel> citations;
  final Map<String, dynamic> sourceOverview;
  final List<PlaceholderEntryModel> knowledgePointPlaceholders;
  final List<PlaceholderEntryModel> weaknessPlaceholders;
  final NextActionModel? nextAction;

  factory LessonDetailModel.fromJson(Map<String, dynamic> json) {
    return LessonDetailModel(
      lesson: LessonSummaryModel.fromJson(
        Map<String, dynamic>.from(json['lesson'] as Map),
      ),
      primaryVideo: json['primaryVideo'] == null
          ? null
          : ScopedResourceModel.fromJson(
              _primaryVideoJson(
                json['primaryVideo'],
                lesson: Map<String, dynamic>.from(json['lesson'] as Map),
              ),
            ),
      lessonResources: _listOfMaps(json['lessonResources'])
          .map(ScopedResourceModel.fromJson)
          .toList(),
      artifactSummaries: _placeholderEntries(json['artifactSummaries']),
      progress: Map<String, dynamic>.from(
        json['progress'] as Map? ?? const <String, dynamic>{},
      ),
      citations:
          _listOfMaps(json['citations']).map(CitationModel.fromJson).toList(),
      sourceOverview: Map<String, dynamic>.from(
        json['sourceOverview'] as Map? ?? const <String, dynamic>{},
      ),
      knowledgePointPlaceholders: _listOfMaps(
        json['knowledgePointPlaceholders'],
      ).map(PlaceholderEntryModel.fromJson).toList(),
      weaknessPlaceholders: _listOfMaps(json['weaknessPlaceholders'])
          .map(PlaceholderEntryModel.fromJson)
          .toList(),
      nextAction: json['nextAction'] == null
          ? null
          : NextActionModel.fromJson(
              Map<String, dynamic>.from(json['nextAction'] as Map),
            ),
    );
  }

  int? get positionSec =>
      _nullableInt(progress['lastPositionSec']) ??
      _nullableInt(progress['positionSec']);
  double? get masteryScore => _doubleValue(progress['masteryScore']);
  Map<String, PlaceholderEntryModel> get artifactSummaryByKey => {
        for (final entry in artifactSummaries) entry.key: entry,
      };
}

class ScopedResourceModel {
  const ScopedResourceModel({
    required this.resourceId,
    required this.courseId,
    required this.resourceType,
    required this.originalName,
    required this.scopeType,
    required this.usageRole,
    required this.visibleToCourseQa,
    required this.sortOrder,
    this.lessonId,
    this.durationSec,
  });

  final String resourceId;
  final String courseId;
  final String resourceType;
  final String originalName;
  final String scopeType;
  final String? lessonId;
  final String usageRole;
  final bool visibleToCourseQa;
  final int? durationSec;
  final int sortOrder;

  factory ScopedResourceModel.fromJson(Map<String, dynamic> json) {
    return ScopedResourceModel(
      resourceId: _stringId(json['resourceId']),
      courseId: _stringId(json['courseId']),
      resourceType: json['resourceType'] as String? ?? 'file',
      originalName: json['originalName'] as String? ??
          json['resourceName'] as String? ??
          '未命名资料',
      scopeType: json['scopeType'] as String? ?? 'course',
      lessonId: _nullableString(json['lessonId']),
      usageRole: json['usageRole'] as String? ?? 'course_material',
      visibleToCourseQa: json['visibleToCourseQa'] as bool? ?? true,
      durationSec: _nullableInt(json['durationSec']),
      sortOrder: _intValue(json['sortOrder']),
    );
  }
}

class PlaceholderEntryModel {
  const PlaceholderEntryModel({
    required this.key,
    required this.title,
    required this.status,
    required this.message,
    this.targetPath,
  });

  final String key;
  final String title;
  final String status;
  final String message;
  final String? targetPath;

  factory PlaceholderEntryModel.fromJson(Map<String, dynamic> json) {
    final key = json['key'] as String? ??
        json['artifactType'] as String? ??
        json['type'] as String? ??
        'placeholder';
    return PlaceholderEntryModel(
      key: key,
      title: json['title'] as String? ?? _placeholderTitle(key),
      status: json['status'] as String? ?? 'placeholder',
      message: json['message'] as String? ?? '',
      targetPath: json['targetPath'] as String? ?? json['route'] as String?,
    );
  }
}

class NextActionModel {
  const NextActionModel({
    required this.type,
    required this.label,
    this.route,
    this.reason,
  });

  final String type;
  final String label;
  final String? route;
  final String? reason;

  factory NextActionModel.fromJson(Map<String, dynamic> json) {
    return NextActionModel(
      type: json['type'] as String? ?? json['actionType'] as String? ?? 'none',
      label: json['label'] as String? ?? '暂无下一步',
      route: json['route'] as String? ?? json['targetPath'] as String?,
      reason: json['reason'] as String?,
    );
  }
}

class LessonProgressModel {
  const LessonProgressModel({
    required this.courseId,
    required this.lessonId,
    required this.handoutReadPercent,
    required this.quizStatus,
    required this.reviewStatus,
    this.lastPositionSec,
    this.lastHandoutBlockId,
    this.lastActivityAt,
  });

  final String courseId;
  final String lessonId;
  final int? lastPositionSec;
  final String? lastHandoutBlockId;
  final int handoutReadPercent;
  final String quizStatus;
  final String reviewStatus;
  final DateTime? lastActivityAt;

  factory LessonProgressModel.fromJson(Map<String, dynamic> json) {
    return LessonProgressModel(
      courseId: _stringId(json['courseId']),
      lessonId: _stringId(json['lessonId']),
      lastPositionSec: _nullableInt(json['lastPositionSec']),
      lastHandoutBlockId: _nullableString(json['lastHandoutBlockId']),
      handoutReadPercent: _intValue(json['handoutReadPercent']),
      quizStatus: json['quizStatus'] as String? ?? 'not_generated',
      reviewStatus: json['reviewStatus'] as String? ?? 'not_due',
      lastActivityAt: _dateTime(json['lastActivityAt']),
    );
  }
}

class CitationModel {
  const CitationModel({
    required this.scopeType,
    required this.refLabel,
    this.lessonId,
    this.lessonTitle,
    this.resourceId,
    this.resourceName,
    this.startSec,
    this.endSec,
    this.pageNo,
    this.slideNo,
    this.anchorKey,
    this.confidenceScore,
  });

  final String scopeType;
  final String refLabel;
  final String? lessonId;
  final String? lessonTitle;
  final String? resourceId;
  final String? resourceName;
  final int? startSec;
  final int? endSec;
  final int? pageNo;
  final int? slideNo;
  final String? anchorKey;
  final double? confidenceScore;

  factory CitationModel.fromJson(Map<String, dynamic> json) {
    return CitationModel(
      scopeType: json['scopeType'] as String? ?? 'course',
      refLabel: json['refLabel'] as String? ?? '来源',
      lessonId: _nullableString(json['lessonId']),
      lessonTitle: json['lessonTitle'] as String?,
      resourceId: _nullableString(json['resourceId']),
      resourceName: json['resourceName'] as String?,
      startSec: _nullableInt(json['startSec']),
      endSec: _nullableInt(json['endSec']),
      pageNo: _nullableInt(json['pageNo']),
      slideNo: _nullableInt(json['slideNo']),
      anchorKey: json['anchorKey'] as String?,
      confidenceScore: _doubleValue(json['confidenceScore']),
    );
  }
}

List<Map<String, dynamic>> _listOfMaps(Object? value) {
  return (value as List<dynamic>? ?? const [])
      .map((item) => Map<String, dynamic>.from(item as Map))
      .toList();
}

List<PlaceholderEntryModel> _placeholderEntries(Object? value) {
  if (value is List) {
    return value
        .map(
          (item) => PlaceholderEntryModel.fromJson(
            Map<String, dynamic>.from(item as Map),
          ),
        )
        .toList();
  }
  if (value is Map) {
    return value.entries.map(
      (entry) {
        final itemJson = Map<String, dynamic>.from(entry.value as Map);
        itemJson.putIfAbsent('key', () => entry.key.toString());
        return PlaceholderEntryModel.fromJson(itemJson);
      },
    ).toList();
  }
  return const [];
}

Map<String, dynamic> _primaryVideoJson(
  Object? value, {
  required Map<String, dynamic> lesson,
}) {
  final json = Map<String, dynamic>.from(value as Map);
  json.putIfAbsent('courseId', () => lesson['courseId']);
  json.putIfAbsent('scopeType', () => 'lesson');
  json.putIfAbsent('lessonId', () => lesson['lessonId']);
  json.putIfAbsent('usageRole', () => 'primary_video');
  json.putIfAbsent('visibleToCourseQa', () => true);
  json.putIfAbsent('sortOrder', () => 0);
  return json;
}

String _placeholderTitle(String key) {
  return switch (key) {
    'handout' || 'handout_version' || 'lesson_handout' => '本节讲义',
    'qa' || 'qa_session' || 'lesson_qa' => '本节 QA',
    'quiz' => '本节测验',
    'review' || 'review_task_run' || 'lesson_review' => '本节复习',
    'graph' || 'graph_snapshot' || 'lesson_graph' => '本节图谱',
    'course_graph' => '课程图谱',
    'course_qa' => '全课程 QA',
    'export' || 'export_run' => '课程导出',
    'course_review' => '课程总复习',
    'report' => '学习报告',
    'settings' => '课程设置',
    _ => '占位入口',
  };
}

String _stringId(Object? value) {
  if (value == null) {
    return '';
  }
  return value.toString();
}

String? _nullableString(Object? value) {
  if (value == null) {
    return null;
  }
  final text = value.toString();
  return text.isEmpty ? null : text;
}

int _intValue(Object? value) => _nullableInt(value) ?? 0;

int? _nullableInt(Object? value) {
  if (value == null) {
    return null;
  }
  if (value is int) {
    return value;
  }
  if (value is num) {
    return value.round();
  }
  return int.tryParse(value.toString());
}

double? _doubleValue(Object? value) {
  if (value == null) {
    return null;
  }
  if (value is num) {
    return value.toDouble();
  }
  return double.tryParse(value.toString());
}

DateTime? _dateTime(Object? value) {
  if (value == null) {
    return null;
  }
  return DateTime.tryParse(value.toString());
}
