import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'course_lesson_models.dart';
import 'handout_models.dart';
import 'resource_upload_models.dart';

class LessonStudyQaEntry {
  const LessonStudyQaEntry({
    required this.entryId,
    required this.question,
    required this.answer,
  });

  final int entryId;
  final String question;
  final AsyncValue<QaMessageModel> answer;

  LessonStudyQaEntry copyWith({
    String? question,
    AsyncValue<QaMessageModel>? answer,
  }) {
    return LessonStudyQaEntry(
      entryId: entryId,
      question: question ?? this.question,
      answer: answer ?? this.answer,
    );
  }
}

class LessonStudyState {
  const LessonStudyState({
    this.courseId,
    this.lessonId,
    this.lessonDetail = const AsyncData<LessonDetailModel?>(null),
    this.lessonProgress = const AsyncData<LessonProgressModel?>(null),
    this.progressSave = const AsyncData<LessonProgressModel?>(null),
    this.latestHandout = const AsyncData<HandoutLatestModel?>(null),
    this.outline = const AsyncData<HandoutOutlineModel?>(null),
    this.blocks = const AsyncData<HandoutBlocksModel?>(null),
    this.currentBlock = const AsyncData<CurrentHandoutBlockModel?>(null),
    this.playback = const AsyncData<CourseResourcePlaybackModel?>(null),
    this.materialAction = const AsyncData<void>(null),
    this.materialPreview = const AsyncData<CourseResourcePlaybackModel?>(null),
    this.blockGenerateRequest =
        const AsyncData<HandoutBlockGenerateResultModel?>(null),
    this.qaSubmit = const AsyncData<QaMessageModel?>(null),
    this.selectedBlockId,
    this.qaEntriesByBlockId = const {},
    this.isOutlineOpen = false,
    this.isMaterialsOpen = false,
  });

  final String? courseId;
  final String? lessonId;
  final AsyncValue<LessonDetailModel?> lessonDetail;
  final AsyncValue<LessonProgressModel?> lessonProgress;
  final AsyncValue<LessonProgressModel?> progressSave;
  final AsyncValue<HandoutLatestModel?> latestHandout;
  final AsyncValue<HandoutOutlineModel?> outline;
  final AsyncValue<HandoutBlocksModel?> blocks;
  final AsyncValue<CurrentHandoutBlockModel?> currentBlock;
  final AsyncValue<CourseResourcePlaybackModel?> playback;
  final AsyncValue<void> materialAction;
  final AsyncValue<CourseResourcePlaybackModel?> materialPreview;
  final AsyncValue<HandoutBlockGenerateResultModel?> blockGenerateRequest;
  final AsyncValue<QaMessageModel?> qaSubmit;
  final int? selectedBlockId;
  final Map<int, List<LessonStudyQaEntry>> qaEntriesByBlockId;
  final bool isOutlineOpen;
  final bool isMaterialsOpen;

  List<ScopedResourceModel> get materials {
    return lessonDetail.valueOrNull?.lessonResources ?? const [];
  }

  List<HandoutOutlineChildModel> get outlineChildren {
    return outline.valueOrNull?.children ?? const [];
  }

  HandoutBlockModel? get selectedBlock {
    final blockId = selectedBlockId;
    if (blockId == null) {
      return null;
    }
    return blockForId(blockId);
  }

  List<LessonStudyQaEntry> get selectedBlockQaEntries {
    final blockId = selectedBlockId;
    if (blockId == null) {
      return const [];
    }
    return qaEntriesByBlockId[blockId] ?? const [];
  }

  List<QaMessageModel> get selectedBlockQaMessages {
    final blockId = selectedBlockId;
    if (blockId == null) {
      return const [];
    }
    return [
      for (final entry in qaEntriesByBlockId[blockId] ?? const [])
        ...entry.answer.map(
          data: (answer) => [answer.value],
          error: (_) => const <QaMessageModel>[],
          loading: (_) => const <QaMessageModel>[],
        ),
    ];
  }

  Map<int, List<QaMessageModel>> get qaMessagesByBlockId {
    return {
      for (final blockEntries in qaEntriesByBlockId.entries)
        blockEntries.key: [
          for (final entry in blockEntries.value)
            ...entry.answer.map(
              data: (answer) => [answer.value],
              error: (_) => const <QaMessageModel>[],
              loading: (_) => const <QaMessageModel>[],
            ),
        ],
    };
  }

  bool get isLoading {
    return lessonDetail.isLoading ||
        latestHandout.isLoading ||
        outline.isLoading ||
        blocks.isLoading ||
        currentBlock.isLoading ||
        playback.isLoading;
  }

  bool get isSubmittingQuestion => qaSubmit.isLoading;
  bool get isSavingProgress => progressSave.isLoading;
  bool get isGeneratingSelectedBlock {
    if (blockGenerateRequest.isLoading) {
      return true;
    }
    final blockId = selectedBlockId;
    if (blockId == null) {
      return false;
    }
    final selected = selectedBlock;
    if (_isActiveBlockGenerationStatus(selected?.generationStatus)) {
      return true;
    }
    final result = blockGenerateRequest.valueOrNull;
    final blockStatus = result?.blockStatus;
    if (blockStatus != null && blockStatus.blockId == blockId) {
      return _isActiveGenerateRequestStatus(blockStatus.generationStatus) ||
          _isActiveGenerateRequestStatus(blockStatus.status);
    }
    final entity = result?.entity;
    if (entity?.type == 'handout_block' && entity?.id == blockId) {
      return _isActiveGenerateRequestStatus(result?.status);
    }
    return false;
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

  LessonStudyState copyWith({
    String? courseId,
    bool clearCourseId = false,
    String? lessonId,
    bool clearLessonId = false,
    AsyncValue<LessonDetailModel?>? lessonDetail,
    AsyncValue<LessonProgressModel?>? lessonProgress,
    AsyncValue<LessonProgressModel?>? progressSave,
    AsyncValue<HandoutLatestModel?>? latestHandout,
    AsyncValue<HandoutOutlineModel?>? outline,
    AsyncValue<HandoutBlocksModel?>? blocks,
    AsyncValue<CurrentHandoutBlockModel?>? currentBlock,
    AsyncValue<CourseResourcePlaybackModel?>? playback,
    AsyncValue<void>? materialAction,
    AsyncValue<CourseResourcePlaybackModel?>? materialPreview,
    bool clearMaterialPreview = false,
    AsyncValue<HandoutBlockGenerateResultModel?>? blockGenerateRequest,
    AsyncValue<QaMessageModel?>? qaSubmit,
    int? selectedBlockId,
    bool clearSelectedBlockId = false,
    Map<int, List<LessonStudyQaEntry>>? qaEntriesByBlockId,
    bool clearQaMessages = false,
    bool? isOutlineOpen,
    bool? isMaterialsOpen,
  }) {
    return LessonStudyState(
      courseId: clearCourseId ? null : courseId ?? this.courseId,
      lessonId: clearLessonId ? null : lessonId ?? this.lessonId,
      lessonDetail: lessonDetail ?? this.lessonDetail,
      lessonProgress: lessonProgress ?? this.lessonProgress,
      progressSave: progressSave ?? this.progressSave,
      latestHandout: latestHandout ?? this.latestHandout,
      outline: outline ?? this.outline,
      blocks: blocks ?? this.blocks,
      currentBlock: currentBlock ?? this.currentBlock,
      playback: playback ?? this.playback,
      materialAction: materialAction ?? this.materialAction,
      materialPreview: clearMaterialPreview
          ? const AsyncData(null)
          : materialPreview ?? this.materialPreview,
      blockGenerateRequest: blockGenerateRequest ?? this.blockGenerateRequest,
      qaSubmit: qaSubmit ?? this.qaSubmit,
      selectedBlockId:
          clearSelectedBlockId ? null : selectedBlockId ?? this.selectedBlockId,
      qaEntriesByBlockId: clearQaMessages
          ? const {}
          : qaEntriesByBlockId ?? this.qaEntriesByBlockId,
      isOutlineOpen: isOutlineOpen ?? this.isOutlineOpen,
      isMaterialsOpen: isMaterialsOpen ?? this.isMaterialsOpen,
    );
  }
}

bool _isActiveBlockGenerationStatus(String? status) {
  final normalized = status?.toLowerCase();
  return normalized == 'generating' ||
      normalized == 'running' ||
      normalized == 'queued';
}

bool _isActiveGenerateRequestStatus(String? status) {
  final normalized = status?.toLowerCase();
  return normalized == 'generating' ||
      normalized == 'running' ||
      normalized == 'queued' ||
      normalized == 'pending';
}
