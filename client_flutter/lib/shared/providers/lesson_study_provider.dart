import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/course_flow_state.dart';
import '../models/course_lesson_models.dart';
import '../models/handout_models.dart';
import '../models/lesson_study_state.dart';
import '../models/resource_upload_models.dart';
import 'course_flow_providers.dart';
import 'course_recommend_provider.dart';

class LessonStudyController extends AutoDisposeNotifier<LessonStudyState> {
  static const _progressDebounceDuration = Duration(seconds: 2);
  static const _progressSignificantDeltaSec = 15;

  var _isDisposed = false;
  var _loadRequestId = 0;
  var _currentBlockRequestId = 0;
  var _qaRequestId = 0;
  var _qaEntryId = 0;
  var _progressRequestId = 0;
  Timer? _progressDebounce;
  int? _pendingProgressPositionSec;
  String? _pendingProgressBlockId;
  int? _lastSavedPositionSec;
  String? _lastSavedBlockId;

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
      _flushPendingProgressOnDispose();
      _progressDebounce?.cancel();
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
      lessonProgress: const AsyncLoading(),
      progressSave: const AsyncData(null),
      latestHandout: const AsyncLoading(),
      outline: const AsyncLoading(),
      blocks: const AsyncLoading(),
      currentBlock: const AsyncLoading(),
      playback: const AsyncLoading(),
      materialAction: const AsyncData(null),
      materialPreview: const AsyncData(null),
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
        lessonProgress: AsyncError(error, stackTrace),
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
    final progressState = await _fetchProgressForLoad(
      requestId: requestId,
      courseId: courseId,
      lessonId: lessonId,
    );
    if (!_shouldApplyLoad(requestId, courseId, lessonId)) {
      return;
    }
    final progress = progressState.valueOrNull;
    final resumePositionSec = _resolveResumePosition(
      requestedPositionSec: positionSec,
      detail: detail,
      progress: progress,
    );
    _syncResumePosition(
      courseId: courseId,
      lessonId: lessonId,
      positionSec: resumePositionSec,
    );
    _lastSavedPositionSec = progress?.lastPositionSec;
    _lastSavedBlockId = progress?.lastHandoutBlockId;
    state = state.copyWith(
      lessonDetail: AsyncData(detail),
      lessonProgress: progressState,
    );
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

    final progressBlockId = int.tryParse(progress?.lastHandoutBlockId ?? '');
    final selectedBlockId = _resolveBlockId(outline, blocks, progressBlockId) ??
        _resolveDefaultBlockId(outline, blocks);
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
        currentSec: resumePositionSec,
      );
      if (!_shouldApplyLoad(requestId, courseId, lessonId)) {
        return;
      }
      final currentBlockId =
          _resolveBlockId(outline, blocks, current.blockId) ?? selectedBlockId;
      _applySelectedBlockId(currentBlockId);
      state = state.copyWith(
        currentBlock: AsyncData(current),
        selectedBlockId: currentBlockId,
        clearSelectedBlockId: currentBlockId == null,
      );
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
    final nextQaEntries = selectionChanged
        ? _removePendingQaEntriesForBlock(
            state.qaEntriesByBlockId,
            state.selectedBlockId,
          )
        : state.qaEntriesByBlockId;
    state = state.copyWith(
      selectedBlockId: block.blockId,
      currentBlock:
          selectionChanged ? const AsyncData(null) : state.currentBlock,
      qaSubmit: selectionChanged ? const AsyncData(null) : state.qaSubmit,
      qaEntriesByBlockId: nextQaEntries,
    );
    ref.read(activeBlockProvider.notifier).state = block.blockId;
    ref.read(playerStateProvider.notifier).state =
        ref.read(playerStateProvider).copyWith(positionSec: block.startSec);
    unawaited(
      flushProgress(
        positionSec: block.startSec,
        blockId: block.blockId.toString(),
      ),
    );
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
        qaEntriesByBlockId: selectionChanged
            ? _removePendingQaEntriesForBlock(
                state.qaEntriesByBlockId,
                state.selectedBlockId,
              )
            : state.qaEntriesByBlockId,
      );
      ref.read(activeBlockProvider.notifier).state = current.blockId;
    } catch (error, stackTrace) {
      if (!_shouldApplyCurrentBlock(requestId, courseId, lessonId)) {
        return;
      }
      state = state.copyWith(currentBlock: AsyncError(error, stackTrace));
    }
  }

  void recordPlaybackProgress({
    required int positionSec,
    bool? isPlaying,
  }) {
    final normalizedPosition = positionSec < 0 ? 0 : positionSec;
    final player = ref.read(playerStateProvider);
    final shouldUpdatePlayer =
        (player.positionSec - normalizedPosition).abs() >= 1 ||
            (isPlaying != null && player.isPlaying != isPlaying);
    if (shouldUpdatePlayer) {
      ref.read(playerStateProvider.notifier).state = player.copyWith(
        positionSec: normalizedPosition,
        isPlaying: isPlaying,
      );
    }
    if (!_isSignificantProgressChange(normalizedPosition)) {
      return;
    }
    _pendingProgressPositionSec = normalizedPosition;
    _pendingProgressBlockId = state.selectedBlockId?.toString();
    _progressDebounce?.cancel();
    _progressDebounce = Timer(_progressDebounceDuration, () {
      unawaited(flushProgress());
    });
  }

  Future<void> flushProgress({
    int? positionSec,
    String? blockId,
  }) async {
    _progressDebounce?.cancel();
    _progressDebounce = null;
    final currentPositionSec = positionSec ??
        _pendingProgressPositionSec ??
        ref.read(playerStateProvider).positionSec;
    final normalizedPosition = currentPositionSec < 0 ? 0 : currentPositionSec;
    final currentBlockId =
        blockId ?? _pendingProgressBlockId ?? state.selectedBlockId?.toString();
    _pendingProgressPositionSec = null;
    _pendingProgressBlockId = null;
    if (normalizedPosition <= 0 && currentBlockId == null) {
      return;
    }
    if (_lastSavedPositionSec == normalizedPosition &&
        _lastSavedBlockId == currentBlockId) {
      return;
    }
    await _saveProgress(
      positionSec: normalizedPosition,
      blockId: currentBlockId,
      applyState: true,
    );
  }

  Future<void> askQuestion(String question) {
    return _submitQuestion(question);
  }

  Future<void> retryQuestion(LessonStudyQaEntry entry) {
    return _submitQuestion(entry.question, retryEntryId: entry.entryId);
  }

  Future<void> _submitQuestion(
    String question, {
    int? retryEntryId,
  }) async {
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
    final entryId = retryEntryId ?? ++_qaEntryId;
    state = state.copyWith(
      qaSubmit: const AsyncLoading(),
      qaEntriesByBlockId: _upsertQaEntry(
        entriesByBlockId: state.qaEntriesByBlockId,
        blockId: blockId,
        entry: LessonStudyQaEntry(
          entryId: entryId,
          question: trimmed,
          answer: const AsyncLoading(),
        ),
      ),
    );
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
      state = state.copyWith(
        qaSubmit: AsyncData(answer),
        qaEntriesByBlockId: _updateQaEntryAnswer(
          entriesByBlockId: state.qaEntriesByBlockId,
          blockId: blockId,
          entryId: entryId,
          answer: AsyncData(answer),
        ),
      );
    } catch (error, stackTrace) {
      if (!_shouldApplyQa(requestId, courseId, lessonId, blockId)) {
        return;
      }
      state = state.copyWith(
        qaSubmit: AsyncError(error, stackTrace),
        qaEntriesByBlockId: _updateQaEntryAnswer(
          entriesByBlockId: state.qaEntriesByBlockId,
          blockId: blockId,
          entryId: entryId,
          answer: AsyncError(error, stackTrace),
        ),
      );
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

  Future<bool> refreshMaterials() async {
    final courseId = state.courseId;
    final lessonId = state.lessonId;
    if (courseId == null ||
        lessonId == null ||
        state.materialAction.isLoading) {
      return false;
    }
    state = state.copyWith(materialAction: const AsyncLoading());
    try {
      final detail = await ref.read(apiClientProvider).fetchLessonDetail(
            courseId: courseId,
            lessonId: lessonId,
          );
      if (!_isCurrentLesson(courseId, lessonId)) {
        return false;
      }
      state = state.copyWith(
        lessonDetail: AsyncData(detail),
        materialAction: const AsyncData(null),
      );
      return true;
    } catch (error, stackTrace) {
      if (_isCurrentLesson(courseId, lessonId)) {
        state = state.copyWith(materialAction: AsyncError(error, stackTrace));
      }
      return false;
    }
  }

  Future<bool> deleteMaterial(ScopedResourceModel material) async {
    final courseId = state.courseId;
    final lessonId = state.lessonId;
    final resourceId = int.tryParse(material.resourceId);
    if (courseId == null ||
        lessonId == null ||
        resourceId == null ||
        state.materialAction.isLoading) {
      return false;
    }
    state = state.copyWith(
      materialAction: const AsyncLoading(),
      clearMaterialPreview: true,
    );
    try {
      await ref.read(apiClientProvider).deleteCourseResource(
            courseId: courseId,
            resourceId: resourceId,
          );
      if (!_isCurrentLesson(courseId, lessonId)) {
        return false;
      }
      final detail = await ref.read(apiClientProvider).fetchLessonDetail(
            courseId: courseId,
            lessonId: lessonId,
          );
      if (!_isCurrentLesson(courseId, lessonId)) {
        return false;
      }
      state = state.copyWith(
        lessonDetail: AsyncData(detail),
        materialAction: const AsyncData(null),
      );
      return true;
    } catch (error, stackTrace) {
      if (_isCurrentLesson(courseId, lessonId)) {
        state = state.copyWith(materialAction: AsyncError(error, stackTrace));
      }
      return false;
    }
  }

  Future<CourseResourcePlaybackModel?> previewMaterial(
    ScopedResourceModel material,
  ) async {
    final resourceId = int.tryParse(material.resourceId);
    if (resourceId == null || !_isVideoMaterial(material)) {
      return null;
    }
    state = state.copyWith(materialPreview: const AsyncLoading());
    try {
      final playback =
          await ref.read(apiClientProvider).fetchCourseResourcePlayback(
                resourceId,
              );
      state = state.copyWith(materialPreview: AsyncData(playback));
      return playback;
    } catch (error, stackTrace) {
      state = state.copyWith(materialPreview: AsyncError(error, stackTrace));
      return null;
    }
  }

  Future<AsyncValue<LessonProgressModel?>> _fetchProgressForLoad({
    required int requestId,
    required String courseId,
    required String lessonId,
  }) async {
    try {
      final progress = await ref.read(apiClientProvider).fetchLessonProgress(
            courseId: courseId,
            lessonId: lessonId,
          );
      if (!_shouldApplyLoad(requestId, courseId, lessonId)) {
        return const AsyncData(null);
      }
      return AsyncData(progress);
    } catch (error, stackTrace) {
      if (!_shouldApplyLoad(requestId, courseId, lessonId)) {
        return const AsyncData(null);
      }
      return AsyncError(error, stackTrace);
    }
  }

  int _resolveResumePosition({
    required int requestedPositionSec,
    required LessonDetailModel detail,
    required LessonProgressModel? progress,
  }) {
    final progressPosition = progress?.lastPositionSec;
    if (progressPosition != null) {
      return progressPosition < 0 ? 0 : progressPosition;
    }
    if (requestedPositionSec > 0) {
      return requestedPositionSec;
    }
    final detailPosition = detail.positionSec ?? 0;
    return detailPosition < 0 ? 0 : detailPosition;
  }

  void _syncResumePosition({
    required String courseId,
    required String lessonId,
    required int positionSec,
  }) {
    ref.read(playerStateProvider.notifier).state =
        ref.read(playerStateProvider).copyWith(positionSec: positionSec);
    ref.read(activeLessonProvider.notifier).state = LessonResumeTarget(
      courseId: courseId,
      lessonId: lessonId,
      positionSec: positionSec,
    );
  }

  bool _isSignificantProgressChange(int positionSec) {
    final baseline = _pendingProgressPositionSec ?? _lastSavedPositionSec;
    if (baseline == null) {
      return positionSec > 0;
    }
    return (positionSec - baseline).abs() >= _progressSignificantDeltaSec;
  }

  Future<void> _saveProgress({
    required int positionSec,
    required String? blockId,
    required bool applyState,
  }) async {
    final courseId = state.courseId;
    final lessonId = state.lessonId;
    if (courseId == null || lessonId == null) {
      return;
    }
    final requestId = ++_progressRequestId;
    if (applyState && _isCurrentLesson(courseId, lessonId)) {
      state = state.copyWith(progressSave: const AsyncLoading());
    }
    final request = <String, dynamic>{
      'lastPositionSec': positionSec,
      if (blockId != null) 'lastHandoutBlockId': blockId,
    };
    try {
      final progress = await ref.read(apiClientProvider).updateLessonProgress(
            courseId: courseId,
            lessonId: lessonId,
            request: request,
          );
      _lastSavedPositionSec = progress.lastPositionSec ?? positionSec;
      _lastSavedBlockId = progress.lastHandoutBlockId ?? blockId;
      if (!applyState ||
          _isDisposed ||
          requestId != _progressRequestId ||
          !_isCurrentLesson(courseId, lessonId)) {
        return;
      }
      state = state.copyWith(
        lessonProgress: AsyncData(progress),
        progressSave: AsyncData(progress),
      );
    } catch (error, stackTrace) {
      if (!applyState ||
          _isDisposed ||
          requestId != _progressRequestId ||
          !_isCurrentLesson(courseId, lessonId)) {
        return;
      }
      state = state.copyWith(progressSave: AsyncError(error, stackTrace));
    }
  }

  void _flushPendingProgressOnDispose() {
    final positionSec = _pendingProgressPositionSec;
    final blockId = _pendingProgressBlockId;
    if (positionSec == null) {
      return;
    }
    if ((positionSec <= 0 && blockId == null) ||
        (_lastSavedPositionSec == positionSec &&
            _lastSavedBlockId == blockId)) {
      return;
    }
    unawaited(
      _saveProgress(
        positionSec: positionSec,
        blockId: blockId,
        applyState: false,
      ),
    );
  }

  Map<int, List<LessonStudyQaEntry>> _upsertQaEntry({
    required Map<int, List<LessonStudyQaEntry>> entriesByBlockId,
    required int blockId,
    required LessonStudyQaEntry entry,
  }) {
    final next = {
      for (final blockEntries in entriesByBlockId.entries)
        blockEntries.key: List<LessonStudyQaEntry>.from(blockEntries.value),
    };
    final entries = next[blockId] ?? <LessonStudyQaEntry>[];
    final index =
        entries.indexWhere((candidate) => candidate.entryId == entry.entryId);
    if (index == -1) {
      next[blockId] = [...entries, entry];
    } else {
      entries[index] = entry;
      next[blockId] = entries;
    }
    return next;
  }

  Map<int, List<LessonStudyQaEntry>> _updateQaEntryAnswer({
    required Map<int, List<LessonStudyQaEntry>> entriesByBlockId,
    required int blockId,
    required int entryId,
    required AsyncValue<QaMessageModel> answer,
  }) {
    final next = {
      for (final blockEntries in entriesByBlockId.entries)
        blockEntries.key: List<LessonStudyQaEntry>.from(blockEntries.value),
    };
    final entries = next[blockId];
    if (entries == null) {
      return entriesByBlockId;
    }
    final index =
        entries.indexWhere((candidate) => candidate.entryId == entryId);
    if (index == -1) {
      return entriesByBlockId;
    }
    entries[index] = entries[index].copyWith(answer: answer);
    next[blockId] = entries;
    return next;
  }

  Map<int, List<LessonStudyQaEntry>> _removePendingQaEntriesForBlock(
    Map<int, List<LessonStudyQaEntry>> entriesByBlockId,
    int? blockId,
  ) {
    if (blockId == null || !entriesByBlockId.containsKey(blockId)) {
      return entriesByBlockId;
    }
    final next = {
      for (final blockEntries in entriesByBlockId.entries)
        blockEntries.key: List<LessonStudyQaEntry>.from(blockEntries.value),
    };
    final entries = next[blockId]!
        .where((entry) => !entry.answer.isLoading)
        .toList(growable: false);
    if (entries.isEmpty) {
      next.remove(blockId);
    } else {
      next[blockId] = entries;
    }
    return next;
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

  int? _resolveBlockId(
    HandoutOutlineModel outline,
    HandoutBlocksModel blocks,
    int? blockId,
  ) {
    if (blockId == null) {
      return null;
    }
    if (outline.children.any((child) => child.blockId == blockId)) {
      return blockId;
    }
    if (blocks.items.any((block) => block.blockId == blockId)) {
      return blockId;
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

  bool _isVideoMaterial(ScopedResourceModel material) {
    final type = material.resourceType.toLowerCase();
    return type == 'mp4' || type == 'video';
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
    _flushPendingProgressOnDispose();
    _progressDebounce?.cancel();
    _progressDebounce = null;
    _pendingProgressPositionSec = null;
    _pendingProgressBlockId = null;
    _lastSavedPositionSec = null;
    _lastSavedBlockId = null;
    _loadRequestId++;
    _invalidateSelectionSideEffects();
    state = const LessonStudyState();
  }
}

final lessonStudyProvider =
    AutoDisposeNotifierProvider<LessonStudyController, LessonStudyState>(
  LessonStudyController.new,
);
