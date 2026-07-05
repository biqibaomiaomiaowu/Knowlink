import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/course_flow_state.dart';
import '../models/course_lesson_models.dart';
import '../models/handout_models.dart';
import '../models/lesson_study_state.dart';
import 'course_flow_providers.dart';
import 'course_recommend_provider.dart';

class LessonStudyController extends AutoDisposeNotifier<LessonStudyState> {
  var _isDisposed = false;
  var _loadRequestId = 0;
  var _currentBlockRequestId = 0;
  var _qaRequestId = 0;

  @override
  LessonStudyState build() {
    _isDisposed = false;
    ref.listen<CourseFlowState>(courseFlowProvider, (previous, next) {
      if (previous?.courseId == next.courseId) {
        return;
      }
      _resetForCourseSwitch();
    });
    ref.onDispose(() {
      _isDisposed = true;
    });
    return const LessonStudyState();
  }

  Future<void> load({
    required String courseId,
    required String lessonId,
  }) async {
    final previousCourseId = ref.read(courseFlowProvider).courseId;
    final requestedPositionSec = ref.read(playerStateProvider).positionSec;
    ref.read(courseFlowProvider.notifier)
      ..startCourse(courseId)
      ..setActiveHandoutVersion(null)
      ..setSession(null);
    final positionSec = previousCourseId == null || previousCourseId == courseId
        ? requestedPositionSec
        : ref.read(playerStateProvider).positionSec;
    ref.read(activeLessonProvider.notifier).state = LessonResumeTarget(
      courseId: courseId,
      lessonId: lessonId,
      positionSec: positionSec,
    );

    final requestId = ++_loadRequestId;
    _invalidateSelectionSideEffects();
    _clearActiveBlock();
    state = state.copyWith(
      courseId: courseId,
      lessonId: lessonId,
      lessonDetail: const AsyncLoading(),
      latestHandout: const AsyncLoading(),
      outline: const AsyncLoading(),
      blocks: const AsyncLoading(),
      currentBlock: const AsyncLoading(),
      playback: const AsyncLoading(),
      blockGenerateRequest: const AsyncData(null),
      qaSubmit: const AsyncData(null),
      clearSelectedBlockId: true,
      clearQaMessages: true,
    );

    final apiClient = ref.read(apiClientProvider);
    LessonDetailModel detail;
    try {
      detail = await apiClient.fetchLessonDetail(
        courseId: courseId,
        lessonId: lessonId,
      );
    } catch (error, stackTrace) {
      if (!_shouldApplyLoad(requestId, courseId, lessonId)) {
        return;
      }
      state = state.copyWith(
        lessonDetail: AsyncError(error, stackTrace),
        latestHandout: AsyncError(error, stackTrace),
        outline: AsyncError(error, stackTrace),
        blocks: AsyncError(error, stackTrace),
        currentBlock: AsyncError(error, stackTrace),
        playback: AsyncError(error, stackTrace),
        clearSelectedBlockId: true,
      );
      ref.read(courseFlowProvider.notifier)
        ..setActiveHandoutVersion(null)
        ..setSession(null);
      _clearActiveBlock();
      return;
    }
    if (!_shouldApplyLoad(requestId, courseId, lessonId)) {
      return;
    }
    state = state.copyWith(lessonDetail: AsyncData(detail));
    await _loadPlaybackForLessonDetail(
      detail: detail,
      requestId: requestId,
      courseId: courseId,
      lessonId: lessonId,
    );
    if (!_shouldApplyLoad(requestId, courseId, lessonId)) {
      return;
    }

    HandoutLatestModel latest;
    try {
      latest = await apiClient.fetchLessonHandout(
        courseId: courseId,
        lessonId: lessonId,
      );
    } catch (error, stackTrace) {
      if (!_shouldApplyLoad(requestId, courseId, lessonId)) {
        return;
      }
      state = state.copyWith(
        latestHandout: AsyncError(error, stackTrace),
        outline: const AsyncData(null),
        blocks: const AsyncData(null),
        currentBlock: const AsyncData(null),
        clearSelectedBlockId: true,
      );
      ref.read(courseFlowProvider.notifier).setActiveHandoutVersion(null);
      _clearActiveBlock();
      return;
    }
    if (!_shouldApplyLoad(requestId, courseId, lessonId)) {
      return;
    }
    state = state.copyWith(latestHandout: AsyncData(latest));
    ref.read(courseFlowProvider.notifier).setActiveHandoutVersion(
          latest.handoutVersionId > 0 ? latest.handoutVersionId : null,
        );
    if (_isPlaceholderHandout(latest)) {
      _clearActiveBlock();
      state = state.copyWith(
        outline: const AsyncData(null),
        blocks: const AsyncData(null),
        currentBlock: const AsyncData(null),
        clearSelectedBlockId: true,
      );
      return;
    }

    HandoutOutlineModel outline;
    HandoutBlocksModel blocks;
    try {
      outline = await apiClient.fetchLessonHandoutOutline(
        courseId: courseId,
        lessonId: lessonId,
      );
      if (!_shouldApplyLoad(requestId, courseId, lessonId)) {
        return;
      }
      blocks = await apiClient.fetchLessonHandoutBlocks(
        courseId: courseId,
        lessonId: lessonId,
      );
    } catch (error, stackTrace) {
      if (!_shouldApplyLoad(requestId, courseId, lessonId)) {
        return;
      }
      state = state.copyWith(
        outline: AsyncError(error, stackTrace),
        blocks: AsyncError(error, stackTrace),
        currentBlock: const AsyncData(null),
        clearSelectedBlockId: true,
      );
      _clearActiveBlock();
      return;
    }
    if (!_shouldApplyLoad(requestId, courseId, lessonId)) {
      return;
    }

    final selectedBlockId = _resolveDefaultBlockId(outline, blocks);
    _applySelectedBlockId(selectedBlockId);
    state = state.copyWith(
      outline: AsyncData(outline),
      blocks: AsyncData(blocks),
      selectedBlockId: selectedBlockId,
      clearSelectedBlockId: selectedBlockId == null,
    );

    try {
      final current = await apiClient.fetchLessonCurrentHandoutBlock(
        courseId: courseId,
        lessonId: lessonId,
        currentSec: positionSec,
      );
      if (!_shouldApplyLoad(requestId, courseId, lessonId)) {
        return;
      }
      state = state.copyWith(currentBlock: AsyncData(current));
    } catch (error, stackTrace) {
      if (!_shouldApplyLoad(requestId, courseId, lessonId)) {
        return;
      }
      state = state.copyWith(currentBlock: AsyncError(error, stackTrace));
    }
  }

  void selectBlock(HandoutBlockModel block) {
    if (state.blockForId(block.blockId) == null) {
      return;
    }
    final selectionChanged = state.selectedBlockId != block.blockId;
    if (selectionChanged) {
      _invalidateSelectionSideEffects();
      ref.read(courseFlowProvider.notifier).setSession(null);
    }
    state = state.copyWith(
      selectedBlockId: block.blockId,
      currentBlock:
          selectionChanged ? const AsyncData(null) : state.currentBlock,
      qaSubmit: selectionChanged ? const AsyncData(null) : state.qaSubmit,
    );
    ref.read(activeBlockProvider.notifier).state = block.blockId;
  }

  Future<bool> generateSelectedBlock() async {
    final courseId = state.courseId;
    final lessonId = state.lessonId;
    final block = state.selectedBlock;
    if (courseId == null ||
        lessonId == null ||
        block == null ||
        state.blockGenerateRequest.isLoading) {
      return false;
    }

    final requestId = _loadRequestId;
    state = state.copyWith(blockGenerateRequest: const AsyncLoading());
    try {
      final result = await ref.read(apiClientProvider).generateHandoutBlock(
            blockId: block.blockId,
            idempotencyKey:
                'lesson-handout-block-generate-${block.blockId}-${DateTime.now().microsecondsSinceEpoch}',
          );
      if (!_shouldApplyLoad(requestId, courseId, lessonId)) {
        return true;
      }

      final outline =
          await ref.read(apiClientProvider).fetchLessonHandoutOutline(
                courseId: courseId,
                lessonId: lessonId,
              );
      if (!_shouldApplyLoad(requestId, courseId, lessonId)) {
        return true;
      }

      final blocks = await ref.read(apiClientProvider).fetchLessonHandoutBlocks(
            courseId: courseId,
            lessonId: lessonId,
          );
      if (!_shouldApplyLoad(requestId, courseId, lessonId)) {
        return true;
      }

      final selectedBlockId = _resolveSelectedBlockId(outline, blocks);
      _applySelectedBlockId(selectedBlockId);
      state = state.copyWith(
        outline: AsyncData(outline),
        blocks: AsyncData(blocks),
        selectedBlockId: selectedBlockId,
        clearSelectedBlockId: selectedBlockId == null,
        blockGenerateRequest: AsyncData(result),
      );
      return true;
    } catch (error, stackTrace) {
      if (_shouldApplyLoad(requestId, courseId, lessonId)) {
        state = state.copyWith(
          blockGenerateRequest: AsyncError(error, stackTrace),
        );
      }
      return false;
    }
  }

  Future<void> syncCurrentBlockFromPosition({int? positionSec}) async {
    final courseId = state.courseId;
    final lessonId = state.lessonId;
    if (courseId == null || lessonId == null) {
      return;
    }
    final requestId = ++_currentBlockRequestId;
    final currentSec = positionSec ?? ref.read(playerStateProvider).positionSec;
    state = state.copyWith(currentBlock: const AsyncLoading());
    try {
      final current =
          await ref.read(apiClientProvider).fetchLessonCurrentHandoutBlock(
                courseId: courseId,
                lessonId: lessonId,
                currentSec: currentSec,
              );
      if (!_shouldApplyCurrentBlock(requestId, courseId, lessonId)) {
        return;
      }
      final selectionChanged = state.selectedBlockId != current.blockId;
      if (selectionChanged) {
        _qaRequestId++;
        ref.read(courseFlowProvider.notifier).setSession(null);
      }
      state = state.copyWith(
        currentBlock: AsyncData(current),
        selectedBlockId: current.blockId,
      );
      ref.read(activeBlockProvider.notifier).state = current.blockId;
    } catch (error, stackTrace) {
      if (!_shouldApplyCurrentBlock(requestId, courseId, lessonId)) {
        return;
      }
      state = state.copyWith(currentBlock: AsyncError(error, stackTrace));
    }
  }

  Future<void> askQuestion(String question) async {
    final trimmed = question.trim();
    final courseId = state.courseId;
    final lessonId = state.lessonId;
    final blockId = state.selectedBlockId;
    if (trimmed.isEmpty ||
        courseId == null ||
        lessonId == null ||
        blockId == null) {
      return;
    }

    final requestId = ++_qaRequestId;
    state = state.copyWith(qaSubmit: const AsyncLoading());
    try {
      final answer = await ref.read(apiClientProvider).createLessonQaMessage(
            courseId: courseId,
            lessonId: lessonId,
            request: ScopedQaMessageRequestModel(
              question: trimmed,
              sessionId: ref.read(courseFlowProvider).sessionId,
              handoutBlockId: blockId,
              scopeType: 'lesson',
              courseId: courseId,
              lessonId: lessonId,
            ),
          );
      if (!_shouldApplyQa(requestId, courseId, lessonId, blockId)) {
        return;
      }
      ref.read(courseFlowProvider.notifier).setSession(answer.sessionId);
      final nextMessages = Map<int, List<QaMessageModel>>.from(
        state.qaMessagesByBlockId,
      );
      nextMessages[blockId] = [...nextMessages[blockId] ?? const [], answer];
      state = state.copyWith(
        qaSubmit: AsyncData(answer),
        qaMessagesByBlockId: nextMessages,
      );
    } catch (error, stackTrace) {
      if (!_shouldApplyQa(requestId, courseId, lessonId, blockId)) {
        return;
      }
      state = state.copyWith(qaSubmit: AsyncError(error, stackTrace));
    }
  }

  void openOutline() {
    state = state.copyWith(isOutlineOpen: true);
  }

  void closeOutline() {
    state = state.copyWith(isOutlineOpen: false);
  }

  void openMaterials() {
    state = state.copyWith(isMaterialsOpen: true);
  }

  void closeMaterials() {
    state = state.copyWith(isMaterialsOpen: false);
  }

  int? _resolveDefaultBlockId(
    HandoutOutlineModel outline,
    HandoutBlocksModel blocks,
  ) {
    return _resolveSelectedBlockId(outline, blocks);
  }

  int? _resolveSelectedBlockId(
    HandoutOutlineModel outline,
    HandoutBlocksModel blocks,
  ) {
    final children = outline.children;
    final current = state.selectedBlockId;
    if (current != null && children.any((child) => child.blockId == current)) {
      return current;
    }
    if (children.isNotEmpty) {
      return children.first.blockId;
    }
    final items = blocks.items;
    if (current != null && items.any((block) => block.blockId == current)) {
      return current;
    }
    if (items.isNotEmpty) {
      return items.first.blockId;
    }
    return null;
  }

  Future<void> _loadPlaybackForLessonDetail({
    required LessonDetailModel detail,
    required int requestId,
    required String courseId,
    required String lessonId,
  }) async {
    final resourceId = _primaryVideoResourceId(detail);
    if (resourceId == null) {
      state = state.copyWith(playback: const AsyncData(null));
      return;
    }
    state = state.copyWith(playback: const AsyncLoading());
    try {
      final playback =
          await ref.read(apiClientProvider).fetchCourseResourcePlayback(
                resourceId,
              );
      if (!_shouldApplyLoad(requestId, courseId, lessonId)) {
        return;
      }
      state = state.copyWith(playback: AsyncData(playback));
    } catch (error, stackTrace) {
      if (!_shouldApplyLoad(requestId, courseId, lessonId)) {
        return;
      }
      state = state.copyWith(playback: AsyncError(error, stackTrace));
    }
  }

  int? _primaryVideoResourceId(LessonDetailModel detail) {
    final primaryResourceId = int.tryParse(
      detail.primaryVideo?.resourceId ?? '',
    );
    if (primaryResourceId != null) {
      return primaryResourceId;
    }
    final summaryResourceId = int.tryParse(
      detail.lesson.primaryVideoResourceId ?? '',
    );
    if (summaryResourceId != null) {
      return summaryResourceId;
    }
    for (final resource in detail.lessonResources) {
      if (resource.usageRole != 'primary_video' &&
          resource.resourceType != 'mp4' &&
          resource.resourceType != 'video') {
        continue;
      }
      final resourceId = int.tryParse(resource.resourceId);
      if (resourceId != null) {
        return resourceId;
      }
    }
    return null;
  }

  bool _isPlaceholderHandout(HandoutLatestModel latest) {
    return latest.status == 'placeholder' || latest.handoutVersionId <= 0;
  }

  void _applySelectedBlockId(int? blockId) {
    if (blockId == null) {
      _clearActiveBlock();
      return;
    }
    ref.read(activeBlockProvider.notifier).state = blockId;
  }

  bool _shouldApplyLoad(
    int requestId,
    String courseId,
    String lessonId,
  ) {
    return !_isDisposed &&
        requestId == _loadRequestId &&
        _isCurrentLesson(courseId, lessonId);
  }

  bool _shouldApplyCurrentBlock(
    int requestId,
    String courseId,
    String lessonId,
  ) {
    return !_isDisposed &&
        requestId == _currentBlockRequestId &&
        _isCurrentLesson(courseId, lessonId);
  }

  bool _shouldApplyQa(
    int requestId,
    String courseId,
    String lessonId,
    int blockId,
  ) {
    return !_isDisposed &&
        requestId == _qaRequestId &&
        state.selectedBlockId == blockId &&
        _isCurrentLesson(courseId, lessonId);
  }

  bool _isCurrentLesson(String courseId, String lessonId) {
    return state.courseId == courseId &&
        state.lessonId == lessonId &&
        ref.read(courseFlowProvider).courseId == courseId &&
        ref.read(activeLessonProvider)?.lessonId == lessonId;
  }

  void _invalidateSelectionSideEffects() {
    _currentBlockRequestId++;
    _qaRequestId++;
  }

  void _clearActiveBlock() {
    ref.read(activeBlockProvider.notifier).state = null;
  }

  void _resetForCourseSwitch() {
    _loadRequestId++;
    _invalidateSelectionSideEffects();
    state = const LessonStudyState();
  }
}

final lessonStudyProvider =
    AutoDisposeNotifierProvider<LessonStudyController, LessonStudyState>(
  LessonStudyController.new,
);
