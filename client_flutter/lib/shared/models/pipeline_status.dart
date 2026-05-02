class AsyncEntityModel {
  const AsyncEntityModel({
    required this.type,
    required this.id,
  });

  final String type;
  final int id;

  factory AsyncEntityModel.fromJson(Map<String, dynamic> json) {
    return AsyncEntityModel(
      type: json['type'] as String,
      id: json['id'] as int,
    );
  }
}

class ParseStartResultModel {
  const ParseStartResultModel({
    required this.taskId,
    required this.status,
    required this.nextAction,
    required this.entity,
  });

  final int taskId;
  final String status;
  final String nextAction;
  final AsyncEntityModel entity;

  factory ParseStartResultModel.fromJson(Map<String, dynamic> json) {
    return ParseStartResultModel(
      taskId: json['taskId'] as int,
      status: json['status'] as String,
      nextAction: json['nextAction'] as String,
      entity: AsyncEntityModel.fromJson(
        Map<String, dynamic>.from(json['entity'] as Map),
      ),
    );
  }
}

class CoursePipelineStatusModel {
  const CoursePipelineStatusModel({
    required this.lifecycleStatus,
    required this.pipelineStage,
    required this.pipelineStatus,
  });

  final String lifecycleStatus;
  final String pipelineStage;
  final String pipelineStatus;

  factory CoursePipelineStatusModel.fromJson(Map<String, dynamic> json) {
    return CoursePipelineStatusModel(
      lifecycleStatus: json['lifecycleStatus'] as String,
      pipelineStage: json['pipelineStage'] as String,
      pipelineStatus: json['pipelineStatus'] as String,
    );
  }
}

class PipelineStepModel {
  const PipelineStepModel({
    required this.code,
    required this.label,
    required this.status,
    this.progressPct,
    this.message,
    this.failedResourceIds = const [],
  });

  final String code;
  final String label;
  final String status;
  final int? progressPct;
  final String? message;
  final List<int> failedResourceIds;

  factory PipelineStepModel.fromJson(Map<String, dynamic> json) {
    return PipelineStepModel(
      code: json['code'] as String,
      label: json['label'] as String,
      status: json['status'] as String,
      progressPct: json['progressPct'] as int?,
      message: json['message'] as String?,
      failedResourceIds:
          (json['failedResourceIds'] as List<dynamic>? ?? const [])
              .map((item) => item as int)
              .toList(),
    );
  }
}

class SourceOverviewModel {
  const SourceOverviewModel({
    required this.videoReady,
    required this.outlineReady,
    required this.outlineItemCount,
    required this.docTypes,
    required this.organizedSourceCount,
  });

  final bool videoReady;
  final bool outlineReady;
  final int outlineItemCount;
  final List<String> docTypes;
  final int organizedSourceCount;

  factory SourceOverviewModel.fromJson(Map<String, dynamic> json) {
    return SourceOverviewModel(
      videoReady: json['videoReady'] as bool? ?? false,
      outlineReady: json['outlineReady'] as bool? ?? false,
      outlineItemCount: json['outlineItemCount'] as int? ?? 0,
      docTypes: (json['docTypes'] as List<dynamic>? ?? const [])
          .map((item) => item as String)
          .toList(),
      organizedSourceCount: json['organizedSourceCount'] as int? ?? 0,
    );
  }
}

class KnowledgeMapModel {
  const KnowledgeMapModel({
    required this.status,
    required this.knowledgePointCount,
    required this.segmentCount,
  });

  final String status;
  final int knowledgePointCount;
  final int segmentCount;

  factory KnowledgeMapModel.fromJson(Map<String, dynamic> json) {
    return KnowledgeMapModel(
      status: json['status'] as String? ?? 'unknown',
      knowledgePointCount: json['knowledgePointCount'] as int? ?? 0,
      segmentCount: json['segmentCount'] as int? ?? 0,
    );
  }
}

class HandoutOutlineProgressModel {
  const HandoutOutlineProgressModel({
    required this.status,
    required this.outlineItemCount,
    required this.generatedBlockCount,
  });

  final String status;
  final int outlineItemCount;
  final int generatedBlockCount;

  factory HandoutOutlineProgressModel.fromJson(Map<String, dynamic> json) {
    return HandoutOutlineProgressModel(
      status: json['status'] as String? ?? 'unknown',
      outlineItemCount: json['outlineItemCount'] as int? ?? 0,
      generatedBlockCount: json['generatedBlockCount'] as int? ?? 0,
    );
  }
}

class HighlightSummaryModel {
  const HighlightSummaryModel({
    required this.status,
    required this.items,
  });

  final String status;
  final List<String> items;

  factory HighlightSummaryModel.fromJson(Map<String, dynamic> json) {
    return HighlightSummaryModel(
      status: json['status'] as String? ?? 'unknown',
      items: (json['items'] as List<dynamic>? ?? const [])
          .map((item) => item as String)
          .toList(),
    );
  }
}

class PipelineStatusModel {
  const PipelineStatusModel({
    required this.courseStatus,
    required this.progressPct,
    required this.steps,
    required this.activeParseRunId,
    required this.activeHandoutVersionId,
    required this.nextAction,
    required this.sourceOverview,
    required this.knowledgeMap,
    required this.handoutOutline,
    required this.highlightSummary,
  });

  final CoursePipelineStatusModel courseStatus;
  final int progressPct;
  final List<PipelineStepModel> steps;
  final int? activeParseRunId;
  final int? activeHandoutVersionId;
  final String nextAction;
  final SourceOverviewModel? sourceOverview;
  final KnowledgeMapModel? knowledgeMap;
  final HandoutOutlineProgressModel? handoutOutline;
  final HighlightSummaryModel? highlightSummary;

  bool get isTerminal {
    return courseStatus.pipelineStatus == 'succeeded' ||
        courseStatus.pipelineStatus == 'partial_success' ||
        courseStatus.pipelineStatus == 'failed';
  }

  bool get canEnterInquiry {
    return nextAction == 'enter_inquiry' ||
        nextAction == 'enter_handout_outline';
  }

  bool get canEnterHandoutOutline => nextAction == 'enter_handout_outline';

  factory PipelineStatusModel.fromJson(Map<String, dynamic> json) {
    return PipelineStatusModel(
      courseStatus: CoursePipelineStatusModel.fromJson(
        Map<String, dynamic>.from(json['courseStatus'] as Map),
      ),
      progressPct: json['progressPct'] as int? ?? 0,
      steps: (json['steps'] as List<dynamic>? ?? const [])
          .map(
            (item) => PipelineStepModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
      activeParseRunId: json['activeParseRunId'] as int?,
      activeHandoutVersionId: json['activeHandoutVersionId'] as int?,
      nextAction: json['nextAction'] as String? ?? 'none',
      sourceOverview: _nullableObject(
        json['sourceOverview'],
        SourceOverviewModel.fromJson,
      ),
      knowledgeMap: _nullableObject(
        json['knowledgeMap'],
        KnowledgeMapModel.fromJson,
      ),
      handoutOutline: _nullableObject(
        json['handoutOutline'],
        HandoutOutlineProgressModel.fromJson,
      ),
      highlightSummary: _nullableObject(
        json['highlightSummary'],
        HighlightSummaryModel.fromJson,
      ),
    );
  }
}

T? _nullableObject<T>(
  Object? value,
  T Function(Map<String, dynamic> json) parser,
) {
  if (value == null) {
    return null;
  }
  return parser(Map<String, dynamic>.from(value as Map));
}
