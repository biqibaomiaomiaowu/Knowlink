import 'pipeline_status.dart';

class CitationModel {
  const CitationModel({
    required this.resourceId,
    required this.refLabel,
    this.pageNo,
    this.slideNo,
    this.anchorKey,
    this.startSec,
    this.endSec,
  });

  final int resourceId;
  final String refLabel;
  final int? pageNo;
  final int? slideNo;
  final String? anchorKey;
  final int? startSec;
  final int? endSec;

  int get locatorGroupCount {
    var count = 0;
    if (pageNo != null) {
      count++;
    }
    if (slideNo != null) {
      count++;
    }
    if (anchorKey != null) {
      count++;
    }
    if (startSec != null || endSec != null) {
      count++;
    }
    return count;
  }

  bool get hasSingleLocatorGroup {
    if (locatorGroupCount != 1) {
      return false;
    }
    if (startSec != null || endSec != null) {
      return startSec != null && endSec != null;
    }
    return true;
  }

  String get locatorText {
    if (pageNo != null) {
      return 'PDF 第 $pageNo 页';
    }
    if (slideNo != null) {
      return 'PPT 第 $slideNo 页';
    }
    if (anchorKey != null && anchorKey!.isNotEmpty) {
      return '文档锚点 $anchorKey';
    }
    if (startSec != null && endSec != null) {
      return '${_formatSec(startSec!)}-${_formatSec(endSec!)}';
    }
    return '来源 $resourceId';
  }

  factory CitationModel.fromJson(Map<String, dynamic> json) {
    return CitationModel(
      resourceId: json['resourceId'] as int,
      refLabel: json['refLabel'] as String? ?? '来源',
      pageNo: json['pageNo'] as int?,
      slideNo: json['slideNo'] as int?,
      anchorKey: json['anchorKey'] as String?,
      startSec: json['startSec'] as int?,
      endSec: json['endSec'] as int?,
    );
  }
}

class HandoutGenerateResultModel {
  const HandoutGenerateResultModel({
    required this.taskId,
    required this.status,
    required this.nextAction,
    required this.entity,
  });

  final int taskId;
  final String status;
  final String nextAction;
  final AsyncEntityModel entity;

  factory HandoutGenerateResultModel.fromJson(Map<String, dynamic> json) {
    return HandoutGenerateResultModel(
      taskId: json['taskId'] as int,
      status: json['status'] as String,
      nextAction: json['nextAction'] as String,
      entity: AsyncEntityModel.fromJson(
        Map<String, dynamic>.from(json['entity'] as Map),
      ),
    );
  }
}

class HandoutBlockGenerateResultModel {
  const HandoutBlockGenerateResultModel({
    this.taskId,
    required this.status,
    this.nextAction,
    this.entity,
    this.blockStatus,
  });

  final int? taskId;
  final String status;
  final String? nextAction;
  final AsyncEntityModel? entity;
  final HandoutBlockStatusModel? blockStatus;

  factory HandoutBlockGenerateResultModel.fromJson(Map<String, dynamic> json) {
    if (json.containsKey('entity')) {
      return HandoutBlockGenerateResultModel(
        taskId: json['taskId'] as int,
        status: json['status'] as String,
        nextAction: json['nextAction'] as String,
        entity: AsyncEntityModel.fromJson(
          Map<String, dynamic>.from(json['entity'] as Map),
        ),
      );
    }
    final blockStatus = HandoutBlockStatusModel.fromJson(json);
    return HandoutBlockGenerateResultModel(
      status: blockStatus.status,
      blockStatus: blockStatus,
    );
  }
}

class HandoutVersionStatusModel {
  const HandoutVersionStatusModel({
    required this.handoutVersionId,
    required this.status,
    required this.outlineStatus,
    required this.totalBlocks,
    required this.readyBlocks,
    required this.pendingBlocks,
    required this.sourceParseRunId,
  });

  final int handoutVersionId;
  final String status;
  final String outlineStatus;
  final int totalBlocks;
  final int readyBlocks;
  final int pendingBlocks;
  final int? sourceParseRunId;

  bool get isTerminal {
    return status == 'outline_ready' ||
        status == 'ready' ||
        status == 'partial_success' ||
        status == 'failed';
  }

  factory HandoutVersionStatusModel.fromJson(Map<String, dynamic> json) {
    return HandoutVersionStatusModel(
      handoutVersionId: json['handoutVersionId'] as int,
      status: json['status'] as String,
      outlineStatus: json['outlineStatus'] as String? ?? 'unknown',
      totalBlocks: json['totalBlocks'] as int? ?? 0,
      readyBlocks: json['readyBlocks'] as int? ?? 0,
      pendingBlocks: json['pendingBlocks'] as int? ?? 0,
      sourceParseRunId: json['sourceParseRunId'] as int?,
    );
  }
}

class HandoutBlockStatusModel {
  const HandoutBlockStatusModel({
    required this.blockId,
    required this.outlineKey,
    required this.status,
    required this.startSec,
    required this.endSec,
  });

  final int blockId;
  final String outlineKey;
  final String status;
  final int startSec;
  final int endSec;

  factory HandoutBlockStatusModel.fromJson(Map<String, dynamic> json) {
    return HandoutBlockStatusModel(
      blockId: json['blockId'] as int,
      outlineKey: json['outlineKey'] as String,
      status: json['status'] as String,
      startSec: json['startSec'] as int? ?? 0,
      endSec: json['endSec'] as int? ?? 0,
    );
  }
}

class HandoutLatestModel {
  const HandoutLatestModel({
    required this.handoutVersionId,
    required this.title,
    required this.summary,
    required this.totalBlocks,
    required this.status,
  });

  final int handoutVersionId;
  final String title;
  final String summary;
  final int totalBlocks;
  final String status;

  factory HandoutLatestModel.fromJson(Map<String, dynamic> json) {
    return HandoutLatestModel(
      handoutVersionId: json['handoutVersionId'] as int,
      title: json['title'] as String,
      summary: json['summary'] as String? ?? '',
      totalBlocks: json['totalBlocks'] as int? ?? 0,
      status: json['status'] as String,
    );
  }
}

class CurrentHandoutBlockModel {
  const CurrentHandoutBlockModel({
    required this.blockId,
    required this.outlineKey,
    required this.startSec,
    required this.endSec,
    required this.generationStatus,
    this.prefetchBlockId,
  });

  final int blockId;
  final String outlineKey;
  final int startSec;
  final int endSec;
  final String generationStatus;
  final int? prefetchBlockId;

  factory CurrentHandoutBlockModel.fromJson(Map<String, dynamic> json) {
    return CurrentHandoutBlockModel(
      blockId: json['blockId'] as int,
      outlineKey: json['outlineKey'] as String,
      startSec: json['startSec'] as int? ?? 0,
      endSec: json['endSec'] as int? ?? 0,
      generationStatus: json['generationStatus'] as String? ?? 'pending',
      prefetchBlockId: json['prefetchBlockId'] as int?,
    );
  }
}

class HandoutOutlineModel {
  const HandoutOutlineModel({
    required this.handoutVersionId,
    required this.title,
    required this.summary,
    required this.items,
    required this.outlineUsedFallback,
    required this.outlineIssues,
  });

  final int handoutVersionId;
  final String title;
  final String summary;
  final List<HandoutOutlineSectionModel> items;
  final bool outlineUsedFallback;
  final List<String> outlineIssues;

  List<HandoutOutlineChildModel> get children {
    return [
      for (final section in items) ...section.children,
    ];
  }

  HandoutOutlineChildModel? childForBlockId(int? blockId) {
    if (blockId == null) {
      return null;
    }
    for (final child in children) {
      if (child.blockId == blockId) {
        return child;
      }
    }
    return null;
  }

  factory HandoutOutlineModel.fromJson(Map<String, dynamic> json) {
    return HandoutOutlineModel(
      handoutVersionId: json['handoutVersionId'] as int,
      title: json['title'] as String,
      summary: json['summary'] as String? ?? '',
      items: (json['items'] as List<dynamic>? ?? const [])
          .map(
            (item) => HandoutOutlineSectionModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
      outlineUsedFallback: json['outlineUsedFallback'] as bool? ?? false,
      outlineIssues: (json['outlineIssues'] as List<dynamic>? ?? const [])
          .map((item) => item as String)
          .toList(),
    );
  }
}

class HandoutOutlineSectionModel {
  const HandoutOutlineSectionModel({
    required this.outlineKey,
    required this.title,
    required this.summary,
    required this.startSec,
    required this.endSec,
    required this.sortNo,
    required this.children,
  });

  final String outlineKey;
  final String title;
  final String summary;
  final int startSec;
  final int endSec;
  final int sortNo;
  final List<HandoutOutlineChildModel> children;

  factory HandoutOutlineSectionModel.fromJson(Map<String, dynamic> json) {
    return HandoutOutlineSectionModel(
      outlineKey: json['outlineKey'] as String,
      title: json['title'] as String,
      summary: json['summary'] as String? ?? '',
      startSec: json['startSec'] as int? ?? 0,
      endSec: json['endSec'] as int? ?? 0,
      sortNo: json['sortNo'] as int? ?? 0,
      children: (json['children'] as List<dynamic>? ?? const [])
          .map(
            (item) => HandoutOutlineChildModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
    );
  }
}

class HandoutOutlineChildModel {
  const HandoutOutlineChildModel({
    required this.outlineKey,
    required this.blockId,
    required this.title,
    required this.summary,
    required this.startSec,
    required this.endSec,
    required this.sortNo,
    required this.generationStatus,
    required this.sourceSegmentKeys,
    required this.topicTags,
  });

  final String outlineKey;
  final int blockId;
  final String title;
  final String summary;
  final int startSec;
  final int endSec;
  final int sortNo;
  final String generationStatus;
  final List<String> sourceSegmentKeys;
  final List<String> topicTags;

  bool containsPosition(int positionSec, {required bool isLast}) {
    if (positionSec < startSec) {
      return false;
    }
    return isLast ? positionSec <= endSec : positionSec < endSec;
  }

  factory HandoutOutlineChildModel.fromJson(Map<String, dynamic> json) {
    return HandoutOutlineChildModel(
      outlineKey: json['outlineKey'] as String,
      blockId: json['blockId'] as int,
      title: json['title'] as String,
      summary: json['summary'] as String? ?? '',
      startSec: json['startSec'] as int? ?? 0,
      endSec: json['endSec'] as int? ?? 0,
      sortNo: json['sortNo'] as int? ?? 0,
      generationStatus: json['generationStatus'] as String? ?? 'pending',
      sourceSegmentKeys:
          (json['sourceSegmentKeys'] as List<dynamic>? ?? const [])
              .map((item) => item as String)
              .toList(),
      topicTags: (json['topicTags'] as List<dynamic>? ?? const [])
          .map((item) => item as String)
          .toList(),
    );
  }
}

class HandoutBlocksModel {
  const HandoutBlocksModel({
    required this.items,
  });

  final List<HandoutBlockModel> items;

  factory HandoutBlocksModel.fromJson(Map<String, dynamic> json) {
    return HandoutBlocksModel(
      items: (json['items'] as List<dynamic>? ?? const [])
          .map(
            (item) => HandoutBlockModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
    );
  }
}

class HandoutBlockModel {
  const HandoutBlockModel({
    required this.blockId,
    required this.outlineKey,
    required this.title,
    required this.summary,
    required this.status,
    required this.contentMd,
    required this.startSec,
    required this.endSec,
    required this.citations,
    this.pageFrom,
    this.pageTo,
  });

  final int blockId;
  final String outlineKey;
  final String title;
  final String summary;
  final String status;
  final String? contentMd;
  final int startSec;
  final int endSec;
  final int? pageFrom;
  final int? pageTo;
  final List<CitationModel> citations;

  bool containsPosition(int positionSec, {required bool isLast}) {
    if (positionSec < startSec) {
      return false;
    }
    return isLast ? positionSec <= endSec : positionSec < endSec;
  }

  factory HandoutBlockModel.fromJson(Map<String, dynamic> json) {
    return HandoutBlockModel(
      blockId: json['blockId'] as int,
      outlineKey: json['outlineKey'] as String,
      title: json['title'] as String,
      summary: json['summary'] as String? ?? '',
      status: json['status'] as String? ??
          json['generationStatus'] as String? ??
          'pending',
      contentMd: json['contentMd'] as String?,
      startSec: json['startSec'] as int? ?? 0,
      endSec: json['endSec'] as int? ?? 0,
      pageFrom: json['pageFrom'] as int?,
      pageTo: json['pageTo'] as int?,
      citations: (json['citations'] as List<dynamic>? ?? const [])
          .map(
            (item) => CitationModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
    );
  }
}

class HandoutJumpTargetModel {
  const HandoutJumpTargetModel({
    required this.blockId,
    this.videoResourceId,
    this.startSec,
    this.endSec,
    this.docResourceId,
    this.pageNo,
    this.slideNo,
    this.anchorKey,
  });

  final int blockId;
  final int? videoResourceId;
  final int? startSec;
  final int? endSec;
  final int? docResourceId;
  final int? pageNo;
  final int? slideNo;
  final String? anchorKey;

  String get displayText {
    final parts = <String>[];
    if (startSec != null) {
      final video = videoResourceId == null ? '视频' : '视频 $videoResourceId';
      parts.add('$video ${_formatSec(startSec!)}');
    }
    if (docResourceId != null ||
        pageNo != null ||
        slideNo != null ||
        anchorKey != null) {
      final doc = docResourceId == null ? '文档' : '文档 $docResourceId';
      if (pageNo != null) {
        parts.add('$doc 第 $pageNo 页');
      } else if (slideNo != null) {
        parts.add('$doc 第 $slideNo 页');
      } else if (anchorKey != null) {
        parts.add('$doc $anchorKey');
      } else {
        parts.add(doc);
      }
    }
    if (parts.isEmpty) {
      return '讲义块 $blockId';
    }
    return parts.join(' · ');
  }

  factory HandoutJumpTargetModel.fromJson(Map<String, dynamic> json) {
    return HandoutJumpTargetModel(
      blockId: json['blockId'] as int,
      videoResourceId: json['videoResourceId'] as int?,
      startSec: json['startSec'] as int?,
      endSec: json['endSec'] as int?,
      docResourceId: json['docResourceId'] as int?,
      pageNo: json['pageNo'] as int?,
      slideNo: json['slideNo'] as int?,
      anchorKey: json['anchorKey'] as String?,
    );
  }
}

class QaMessageRequestModel {
  const QaMessageRequestModel({
    required this.courseId,
    required this.handoutBlockId,
    required this.question,
  });

  final int courseId;
  final int handoutBlockId;
  final String question;

  Map<String, dynamic> toJson() {
    return {
      'courseId': courseId,
      'handoutBlockId': handoutBlockId,
      'question': question,
    };
  }
}

class QaMessageModel {
  const QaMessageModel({
    required this.sessionId,
    required this.messageId,
    required this.answerMd,
    required this.citations,
  });

  final int sessionId;
  final int messageId;
  final String answerMd;
  final List<CitationModel> citations;

  factory QaMessageModel.fromJson(Map<String, dynamic> json) {
    return QaMessageModel(
      sessionId: json['sessionId'] as int,
      messageId: json['messageId'] as int,
      answerMd: json['answerMd'] as String,
      citations: (json['citations'] as List<dynamic>? ?? const [])
          .map(
            (item) => CitationModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
    );
  }
}

class QaSessionMessagesModel {
  const QaSessionMessagesModel({
    required this.items,
  });

  final List<QaMessageModel> items;

  factory QaSessionMessagesModel.fromJson(Map<String, dynamic> json) {
    return QaSessionMessagesModel(
      items: (json['items'] as List<dynamic>? ?? const [])
          .map(
            (item) => QaMessageModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
    );
  }
}

String _formatSec(int seconds) {
  final minutes = seconds ~/ 60;
  final rest = seconds % 60;
  return '$minutes:${rest.toString().padLeft(2, '0')}';
}
