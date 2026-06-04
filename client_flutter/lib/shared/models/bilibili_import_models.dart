class BilibiliQrSessionModel {
  const BilibiliQrSessionModel({
    required this.sessionId,
    required this.status,
    required this.qrCodeUrl,
    required this.expiresAt,
  });

  factory BilibiliQrSessionModel.fromJson(Map<String, dynamic> json) {
    return BilibiliQrSessionModel(
      sessionId: json['sessionId'] as String,
      status: json['status'] as String,
      qrCodeUrl: json['qrCodeUrl'] as String?,
      expiresAt: json['expiresAt'] == null
          ? null
          : DateTime.parse(json['expiresAt'] as String),
    );
  }

  final String sessionId;
  final String status;
  final String? qrCodeUrl;
  final DateTime? expiresAt;

  bool get isConfirmed => status == 'confirmed';

  bool get isTerminal => {
        'confirmed',
        'expired',
        'failed',
      }.contains(status);
}

String _sourceTypeLabel(String sourceType) {
  return switch (sourceType) {
    'single_video' => '单视频',
    'multi_p' => '多 P 视频',
    'collection' => '合集',
    'bangumi' => '番剧',
    _ => sourceType,
  };
}

String _selectionModeLabel(String selectionMode) {
  return switch (selectionMode) {
    'current_part' => '当前条目',
    'all_parts' => '全部条目',
    'selected_parts' => '指定条目',
    _ => selectionMode,
  };
}

String _runStatusLabel(String status) {
  return switch (status) {
    'pending' => '等待处理',
    'fetching_metadata' => '读取元数据',
    'waiting_download' => '等待下载',
    'downloading' => '下载中',
    'merging' => '合并中',
    'uploading' => '上传中',
    'imported' => '已导入',
    'failed' => '导入失败',
    'recoverable' => '可重试',
    'canceled' => '已取消',
    _ => status,
  };
}

String _stageLabel(String stage) {
  return switch (stage) {
    'queued' => '已入队',
    'metadata' => '获取元数据',
    'download' => '下载音视频',
    'ffmpeg' => '合并音视频',
    'object_storage' => '上传对象存储',
    'resource_import' => '创建课程资源',
    'done' => '已完成',
    'error' => '失败',
    'canceling' => '取消中',
    'canceled' => '已取消',
    _ => stage,
  };
}

class BilibiliAuthSessionModel {
  const BilibiliAuthSessionModel({
    required this.loginStatus,
    required this.userNickname,
    required this.expiresAt,
  });

  factory BilibiliAuthSessionModel.fromJson(Map<String, dynamic> json) {
    return BilibiliAuthSessionModel(
      loginStatus: json['loginStatus'] as String,
      userNickname: json['userNickname'] as String?,
      expiresAt: json['expiresAt'] == null
          ? null
          : DateTime.parse(json['expiresAt'] as String),
    );
  }

  final String loginStatus;
  final String? userNickname;
  final DateTime? expiresAt;

  bool get isActive => loginStatus == 'active';
}

class BilibiliPreviewPartModel {
  const BilibiliPreviewPartModel({
    required this.partId,
    required this.title,
    required this.durationSec,
    required this.cid,
    required this.pageNo,
    required this.selectedByDefault,
  });

  factory BilibiliPreviewPartModel.fromJson(Map<String, dynamic> json) {
    return BilibiliPreviewPartModel(
      partId: json['partId'] as String,
      title: json['title'] as String,
      durationSec: json['durationSec'] as int,
      cid: json['cid'] as int,
      pageNo: json['pageNo'] as int,
      selectedByDefault: json['selectedByDefault'] as bool,
    );
  }

  final String partId;
  final String title;
  final int durationSec;
  final int cid;
  final int pageNo;
  final bool selectedByDefault;

  String get displayDuration {
    if (durationSec <= 0) {
      return '0 分钟';
    }
    final minutes = durationSec ~/ 60;
    if (minutes < 1) {
      return '1 分钟';
    }
    return '$minutes 分钟';
  }
}

class BilibiliPreviewModel {
  const BilibiliPreviewModel({
    required this.previewId,
    required this.sourceUrl,
    required this.sourceType,
    required this.title,
    required this.coverUrl,
    required this.totalParts,
    required this.parts,
    required this.defaultSelectionMode,
  });

  factory BilibiliPreviewModel.fromJson(Map<String, dynamic> json) {
    return BilibiliPreviewModel(
      previewId: json['previewId'] as String,
      sourceUrl: json['sourceUrl'] as String,
      sourceType: json['sourceType'] as String,
      title: json['title'] as String,
      coverUrl: json['coverUrl'] as String?,
      totalParts: json['totalParts'] as int,
      parts: (json['parts'] as List<dynamic>)
          .map(
            (item) => BilibiliPreviewPartModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
      defaultSelectionMode: json['defaultSelectionMode'] as String,
    );
  }

  final String previewId;
  final String sourceUrl;
  final String sourceType;
  final String title;
  final String? coverUrl;
  final int totalParts;
  final List<BilibiliPreviewPartModel> parts;
  final String defaultSelectionMode;

  List<String> get defaultSelectedPartIds {
    final selectedPartIds = parts
        .where((part) => part.selectedByDefault)
        .map((part) => part.partId)
        .toList();
    if (selectedPartIds.isNotEmpty || parts.isEmpty) {
      return selectedPartIds;
    }
    return [parts.first.partId];
  }

  String get sourceTypeLabel => _sourceTypeLabel(sourceType);

  String get defaultSelectionModeLabel =>
      _selectionModeLabel(defaultSelectionMode);
}

class BilibiliImportCreateRequestModel {
  const BilibiliImportCreateRequestModel({
    required this.previewId,
    required this.sourceUrl,
    required this.selectionMode,
    required this.selectedPartIds,
    this.qualityPreference = 'android_safe',
  });

  final String previewId;
  final String sourceUrl;
  final String selectionMode;
  final List<String> selectedPartIds;
  final String qualityPreference;

  Map<String, dynamic> toJson() {
    return {
      'previewId': previewId,
      'sourceUrl': sourceUrl,
      'selectionMode': selectionMode,
      'selectedPartIds': selectedPartIds,
      'qualityPreference': qualityPreference,
    };
  }
}

class BilibiliImportTaskEntityModel {
  const BilibiliImportTaskEntityModel({
    required this.type,
    required this.id,
  });

  factory BilibiliImportTaskEntityModel.fromJson(Map<String, dynamic> json) {
    return BilibiliImportTaskEntityModel(
      type: json['type'] as String,
      id: json['id'] as int,
    );
  }

  final String type;
  final int id;
}

class BilibiliImportTaskModel {
  const BilibiliImportTaskModel({
    required this.taskId,
    required this.status,
    required this.nextAction,
    required this.entity,
  });

  factory BilibiliImportTaskModel.fromJson(Map<String, dynamic> json) {
    return BilibiliImportTaskModel(
      taskId: json['taskId'] as int,
      status: json['status'] as String,
      nextAction: json['nextAction'] as String,
      entity: BilibiliImportTaskEntityModel.fromJson(
        Map<String, dynamic>.from(json['entity'] as Map),
      ),
    );
  }

  final int taskId;
  final String status;
  final String nextAction;
  final BilibiliImportTaskEntityModel entity;

  int? get importRunId {
    if (entity.type != 'bilibili_import_run') {
      return null;
    }
    return entity.id;
  }
}

class BilibiliImportRunPreviewPartModel {
  const BilibiliImportRunPreviewPartModel({
    required this.partId,
    required this.title,
    required this.durationSec,
  });

  factory BilibiliImportRunPreviewPartModel.fromJson(
    Map<String, dynamic> json,
  ) {
    return BilibiliImportRunPreviewPartModel(
      partId: json['partId'] as String,
      title: json['title'] as String,
      durationSec: json['durationSec'] as int,
    );
  }

  final String partId;
  final String title;
  final int durationSec;
}

class BilibiliImportRunPreviewModel {
  const BilibiliImportRunPreviewModel({
    required this.title,
    required this.parts,
  });

  factory BilibiliImportRunPreviewModel.fromJson(Map<String, dynamic> json) {
    return BilibiliImportRunPreviewModel(
      title: json['title'] as String,
      parts: (json['parts'] as List<dynamic>)
          .map(
            (item) => BilibiliImportRunPreviewPartModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
    );
  }

  final String title;
  final List<BilibiliImportRunPreviewPartModel> parts;
}

class BilibiliImportRunModel {
  const BilibiliImportRunModel({
    required this.importRunId,
    required this.courseId,
    required this.sourceUrl,
    required this.sourceType,
    required this.status,
    required this.progressPct,
    required this.stage,
    required this.taskId,
    required this.resourceIds,
    required this.preview,
    required this.errorCode,
    required this.failureReason,
    required this.recoverable,
    required this.nextAction,
  });

  factory BilibiliImportRunModel.fromJson(Map<String, dynamic> json) {
    return BilibiliImportRunModel(
      importRunId: json['importRunId'] as int,
      courseId: json['courseId'] as int,
      sourceUrl: json['sourceUrl'] as String,
      sourceType: json['sourceType'] as String,
      status: json['status'] as String,
      progressPct: json['progressPct'] as int,
      stage: json['stage'] as String,
      taskId: json['taskId'] as int?,
      resourceIds: (json['resourceIds'] as List<dynamic>)
          .map((item) => item as int)
          .toList(),
      preview: json['preview'] == null
          ? null
          : BilibiliImportRunPreviewModel.fromJson(
              Map<String, dynamic>.from(json['preview'] as Map),
            ),
      errorCode: json['errorCode'] as String?,
      failureReason: json['failureReason'] as String?,
      recoverable: json['recoverable'] as bool,
      nextAction: json['nextAction'] as String?,
    );
  }

  final int importRunId;
  final int courseId;
  final String sourceUrl;
  final String sourceType;
  final String status;
  final int progressPct;
  final String stage;
  final int? taskId;
  final List<int> resourceIds;
  final BilibiliImportRunPreviewModel? preview;
  final String? errorCode;
  final String? failureReason;
  final bool recoverable;
  final String? nextAction;

  String? get previewTitle => preview?.title;

  bool get isTerminal => {
        'imported',
        'failed',
        'recoverable',
        'canceled',
      }.contains(status);

  bool get canCancel => !isTerminal;

  bool get isImported => status == 'imported';

  bool get isFailed => status == 'failed' || status == 'recoverable';

  String get sourceTypeLabel => _sourceTypeLabel(sourceType);

  String get statusLabel => _runStatusLabel(status);

  String get stageLabel => _stageLabel(stage);

  bool get canRetry => recoverable && nextAction == 'retry' && taskId != null;

  String? get resourceIdsLabel =>
      resourceIds.isEmpty ? null : '资源：${resourceIds.join('、')}';
}

class BilibiliImportRunListModel {
  const BilibiliImportRunListModel({
    required this.items,
  });

  factory BilibiliImportRunListModel.fromJson(Map<String, dynamic> json) {
    return BilibiliImportRunListModel(
      items: (json['items'] as List<dynamic>)
          .map(
            (item) => BilibiliImportRunModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
    );
  }

  final List<BilibiliImportRunModel> items;
}
