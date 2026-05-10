import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'handout_models.dart';
import 'resource_upload_models.dart';

class HandoutState {
  const HandoutState({
    this.latest = const AsyncData<HandoutLatestModel?>(null),
    this.versionStatus = const AsyncData<HandoutVersionStatusModel?>(null),
    this.outline = const AsyncData<HandoutOutlineModel?>(null),
    this.blocks = const AsyncData<HandoutBlocksModel?>(null),
    this.generateRequest = const AsyncData<HandoutGenerateResultModel?>(null),
    this.blockGenerateRequest =
        const AsyncData<HandoutBlockGenerateResultModel?>(null),
    this.blockGenerateRequestsById = const {},
    this.currentBlock = const AsyncData<CurrentHandoutBlockModel?>(null),
    this.jumpTarget = const AsyncData<HandoutJumpTargetModel?>(null),
    this.playback = const AsyncData<CourseResourcePlaybackModel?>(null),
    this.qaSubmit = const AsyncData<QaMessageModel?>(null),
    this.qaMessagesByBlockId = const {},
    this.selectedCitation,
    this.selectedBlockId,
    this.isPolling = false,
  });

  final AsyncValue<HandoutLatestModel?> latest;
  final AsyncValue<HandoutVersionStatusModel?> versionStatus;
  final AsyncValue<HandoutOutlineModel?> outline;
  final AsyncValue<HandoutBlocksModel?> blocks;
  final AsyncValue<HandoutGenerateResultModel?> generateRequest;
  final AsyncValue<HandoutBlockGenerateResultModel?> blockGenerateRequest;
  final Map<int, AsyncValue<HandoutBlockGenerateResultModel?>>
      blockGenerateRequestsById;
  final AsyncValue<CurrentHandoutBlockModel?> currentBlock;
  final AsyncValue<HandoutJumpTargetModel?> jumpTarget;
  final AsyncValue<CourseResourcePlaybackModel?> playback;
  final AsyncValue<QaMessageModel?> qaSubmit;
  final Map<int, List<QaMessageModel>> qaMessagesByBlockId;
  final CitationModel? selectedCitation;
  final int? selectedBlockId;
  final bool isPolling;

  bool get isLoading {
    return latest.isLoading || outline.isLoading || blocks.isLoading;
  }

  bool get isGenerating => generateRequest.isLoading || isPolling;
  bool get isSubmittingQuestion => qaSubmit.isLoading;

  List<HandoutOutlineChildModel> get outlineChildren {
    return outline.valueOrNull?.children ?? const [];
  }

  HandoutOutlineChildModel? get selectedOutlineChild {
    final children = outlineChildren;
    if (children.isEmpty) {
      return null;
    }
    if (selectedBlockId == null) {
      return null;
    }
    for (final child in children) {
      if (child.blockId == selectedBlockId) {
        return child;
      }
    }
    return null;
  }

  HandoutBlockModel? get selectedBlock {
    final child = selectedOutlineChild;
    if (child == null) {
      return null;
    }
    return blockForId(child.blockId);
  }

  AsyncValue<HandoutBlockGenerateResultModel?> blockGenerateRequestFor(
    int blockId,
  ) {
    return blockGenerateRequestsById[blockId] ?? const AsyncData(null);
  }

  bool isBlockGenerating(int blockId) {
    return blockGenerateRequestFor(blockId).isLoading ||
        effectiveBlockStatus(blockId) == 'generating';
  }

  String effectiveBlockStatus(int blockId) {
    final request = blockGenerateRequestsById[blockId];
    if (request != null && request.isLoading) {
      return 'generating';
    }
    final requestStatus = request?.valueOrNull?.blockStatus?.generationStatus;
    if (requestStatus == 'ready' ||
        requestStatus == 'generating' ||
        requestStatus == 'failed') {
      return requestStatus!;
    }
    final block = blockForId(blockId);
    final child = outline.valueOrNull?.childForBlockId(blockId);
    final childStatus = child?.generationStatus;
    if (block?.status == 'pending' &&
        childStatus != null &&
        childStatus != 'pending') {
      return childStatus;
    }
    if (block != null) {
      return block.status;
    }
    return childStatus ?? 'pending';
  }

  HandoutBlockModel? blockForId(int blockId) {
    final items = blocks.valueOrNull?.items ?? const [];
    for (final block in items) {
      if (block.blockId == blockId) {
        return block;
      }
    }
    return null;
  }

  List<QaMessageModel> get selectedBlockQaMessages {
    final blockId = selectedOutlineChild?.blockId;
    if (blockId == null) {
      return const [];
    }
    return qaMessagesByBlockId[blockId] ?? const [];
  }

  HandoutOutlineChildModel? highlightedChildFor(int positionSec) {
    final children = outlineChildren;
    for (var index = 0; index < children.length; index++) {
      final child = children[index];
      if (child.containsPosition(
        positionSec,
        isLast: index == children.length - 1,
      )) {
        return child;
      }
    }
    return null;
  }

  HandoutBlockModel? highlightedBlockFor(int positionSec) {
    final child = highlightedChildFor(positionSec);
    if (child == null) {
      return null;
    }
    return blockForId(child.blockId);
  }

  HandoutOutlineChildModel? nextChildNearPosition(
    int positionSec, {
    required int thresholdSec,
  }) {
    final children = outlineChildren;
    for (var index = 0; index < children.length - 1; index++) {
      final child = children[index];
      if (!child.containsPosition(positionSec, isLast: false)) {
        continue;
      }
      final distanceToEnd = child.endSec - positionSec;
      if (distanceToEnd < 0 || distanceToEnd > thresholdSec) {
        return null;
      }
      return children[index + 1];
    }
    return null;
  }

  HandoutState copyWith({
    AsyncValue<HandoutLatestModel?>? latest,
    AsyncValue<HandoutVersionStatusModel?>? versionStatus,
    AsyncValue<HandoutOutlineModel?>? outline,
    AsyncValue<HandoutBlocksModel?>? blocks,
    AsyncValue<HandoutGenerateResultModel?>? generateRequest,
    AsyncValue<HandoutBlockGenerateResultModel?>? blockGenerateRequest,
    Map<int, AsyncValue<HandoutBlockGenerateResultModel?>>?
        blockGenerateRequestsById,
    bool clearBlockGenerateRequests = false,
    AsyncValue<CurrentHandoutBlockModel?>? currentBlock,
    AsyncValue<HandoutJumpTargetModel?>? jumpTarget,
    AsyncValue<CourseResourcePlaybackModel?>? playback,
    AsyncValue<QaMessageModel?>? qaSubmit,
    Map<int, List<QaMessageModel>>? qaMessagesByBlockId,
    bool clearQaMessages = false,
    CitationModel? selectedCitation,
    bool clearSelectedCitation = false,
    int? selectedBlockId,
    bool clearSelectedBlockId = false,
    bool? isPolling,
  }) {
    return HandoutState(
      latest: latest ?? this.latest,
      versionStatus: versionStatus ?? this.versionStatus,
      outline: outline ?? this.outline,
      blocks: blocks ?? this.blocks,
      generateRequest: generateRequest ?? this.generateRequest,
      blockGenerateRequest: blockGenerateRequest ?? this.blockGenerateRequest,
      blockGenerateRequestsById: clearBlockGenerateRequests
          ? const {}
          : blockGenerateRequestsById ?? this.blockGenerateRequestsById,
      currentBlock: currentBlock ?? this.currentBlock,
      jumpTarget: jumpTarget ?? this.jumpTarget,
      playback: playback ?? this.playback,
      qaSubmit: qaSubmit ?? this.qaSubmit,
      qaMessagesByBlockId: clearQaMessages
          ? const {}
          : qaMessagesByBlockId ?? this.qaMessagesByBlockId,
      selectedCitation: clearSelectedCitation
          ? null
          : selectedCitation ?? this.selectedCitation,
      selectedBlockId:
          clearSelectedBlockId ? null : selectedBlockId ?? this.selectedBlockId,
      isPolling: isPolling ?? this.isPolling,
    );
  }
}
