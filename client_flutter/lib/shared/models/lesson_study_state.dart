import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'course_lesson_models.dart';
import 'handout_models.dart';
import 'resource_upload_models.dart';

class LessonStudyState {
  const LessonStudyState({
    this.courseId,
    this.lessonId,
    this.lessonDetail = const AsyncData<LessonDetailModel?>(null),
    this.latestHandout = const AsyncData<HandoutLatestModel?>(null),
    this.outline = const AsyncData<HandoutOutlineModel?>(null),
    this.blocks = const AsyncData<HandoutBlocksModel?>(null),
    this.currentBlock = const AsyncData<CurrentHandoutBlockModel?>(null),
    this.playback = const AsyncData<CourseResourcePlaybackModel?>(null),
    this.blockGenerateRequest =
        const AsyncData<HandoutBlockGenerateResultModel?>(null),
    this.qaSubmit = const AsyncData<QaMessageModel?>(null),
    this.selectedBlockId,
    this.qaMessagesByBlockId = const {},
    this.isOutlineOpen = false,
    this.isMaterialsOpen = false,
  });

  final String? courseId;
  final String? lessonId;
  final AsyncValue<LessonDetailModel?> lessonDetail;
  final AsyncValue<HandoutLatestModel?> latestHandout;
  final AsyncValue<HandoutOutlineModel?> outline;
  final AsyncValue<HandoutBlocksModel?> blocks;
  final AsyncValue<CurrentHandoutBlockModel?> currentBlock;
  final AsyncValue<CourseResourcePlaybackModel?> playback;
  final AsyncValue<HandoutBlockGenerateResultModel?> blockGenerateRequest;
  final AsyncValue<QaMessageModel?> qaSubmit;
  final int? selectedBlockId;
  final Map<int, List<QaMessageModel>> qaMessagesByBlockId;
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

  List<QaMessageModel> get selectedBlockQaMessages {
    final blockId = selectedBlockId;
    if (blockId == null) {
      return const [];
    }
    return qaMessagesByBlockId[blockId] ?? const [];
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
  bool get isGeneratingSelectedBlock => blockGenerateRequest.isLoading;

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
    AsyncValue<HandoutLatestModel?>? latestHandout,
    AsyncValue<HandoutOutlineModel?>? outline,
    AsyncValue<HandoutBlocksModel?>? blocks,
    AsyncValue<CurrentHandoutBlockModel?>? currentBlock,
    AsyncValue<CourseResourcePlaybackModel?>? playback,
    AsyncValue<HandoutBlockGenerateResultModel?>? blockGenerateRequest,
    AsyncValue<QaMessageModel?>? qaSubmit,
    int? selectedBlockId,
    bool clearSelectedBlockId = false,
    Map<int, List<QaMessageModel>>? qaMessagesByBlockId,
    bool clearQaMessages = false,
    bool? isOutlineOpen,
    bool? isMaterialsOpen,
  }) {
    return LessonStudyState(
      courseId: clearCourseId ? null : courseId ?? this.courseId,
      lessonId: clearLessonId ? null : lessonId ?? this.lessonId,
      lessonDetail: lessonDetail ?? this.lessonDetail,
      latestHandout: latestHandout ?? this.latestHandout,
      outline: outline ?? this.outline,
      blocks: blocks ?? this.blocks,
      currentBlock: currentBlock ?? this.currentBlock,
      playback: playback ?? this.playback,
      blockGenerateRequest: blockGenerateRequest ?? this.blockGenerateRequest,
      qaSubmit: qaSubmit ?? this.qaSubmit,
      selectedBlockId:
          clearSelectedBlockId ? null : selectedBlockId ?? this.selectedBlockId,
      qaMessagesByBlockId: clearQaMessages
          ? const {}
          : qaMessagesByBlockId ?? this.qaMessagesByBlockId,
      isOutlineOpen: isOutlineOpen ?? this.isOutlineOpen,
      isMaterialsOpen: isMaterialsOpen ?? this.isMaterialsOpen,
    );
  }
}
