import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/course_flow_state.dart';
import '../models/handout_models.dart';
import '../models/handout_state.dart';
import 'course_flow_providers.dart';
import 'course_recommend_provider.dart';

class HandoutController extends AutoDisposeNotifier<HandoutState> {
  var _isDisposed = false;
  var _loadRequestId = 0;
  var _jumpTargetRequestId = 0;
  var _currentBlockRequestId = 0;
  var _qaRequestId = 0;

  @override
  HandoutState build() {
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
    return const HandoutState();
  }

  Future<void> load(
    String courseId, {
    bool autoGenerate = true,
    Duration pollInterval = const Duration(seconds: 2),
    int maxAttempts = 30,
  }) async {
    ref.read(courseFlowProvider.notifier)
      ..startCourse(courseId)
      ..setActiveHandoutVersion(null)
      ..setSession(null);
    final requestId = ++_loadRequestId;
    _invalidateSelectionSideEffects();
    _clearActiveBlock();
    state = state.copyWith(
      latest: const AsyncLoading(),
      versionStatus: const AsyncLoading(),
      outline: const AsyncLoading(),
      blocks: const AsyncLoading(),
      generateRequest: const AsyncData(null),
      blockGenerateRequest: const AsyncData(null),
      isPolling: false,
      jumpTarget: const AsyncData(null),
      currentBlock: const AsyncData(null),
      qaSubmit: const AsyncData(null),
      clearQaMessages: true,
      clearSelectedBlockId: true,
      clearSelectedCitation: true,
    );

    try {
      final latest = await ref.read(apiClientProvider).fetchLatestHandout(
            courseId,
          );
      if (!_shouldApply(requestId, courseId)) {
        return;
      }
      await _loadKnownHandout(
        courseId: courseId,
        latest: latest,
        requestId: requestId,
        pollInterval: pollInterval,
        maxAttempts: maxAttempts,
      );
    } catch (error, stackTrace) {
      if (!_shouldApply(requestId, courseId)) {
        return;
      }
      if (autoGenerate && _isNoActiveHandoutError(error)) {
        state = state.copyWith(
          latest: const AsyncData(null),
          versionStatus: const AsyncData(null),
          outline: const AsyncData(null),
          blocks: const AsyncData(null),
        );
        await generateAndPoll(
          courseId,
          requestId: requestId,
          pollInterval: pollInterval,
          maxAttempts: maxAttempts,
        );
        return;
      }
      state = state.copyWith(
        latest: AsyncError(error, stackTrace),
        versionStatus: AsyncError(error, stackTrace),
        outline: AsyncError(error, stackTrace),
        blocks: AsyncError(error, stackTrace),
        clearSelectedBlockId: true,
        clearSelectedCitation: true,
      );
      ref.read(courseFlowProvider.notifier).setActiveHandoutVersion(null);
      _clearActiveBlock();
    }
  }

  Future<void> refreshData(String courseId) async {
    await load(courseId, autoGenerate: false);
  }

  Future<void> generateAndPoll(
    String courseId, {
    int? requestId,
    Duration pollInterval = const Duration(seconds: 2),
    int maxAttempts = 30,
  }) async {
    if (requestId == null && state.isGenerating) {
      return;
    }

    ref.read(courseFlowProvider.notifier)
      ..startCourse(courseId)
      ..setActiveHandoutVersion(null)
      ..setSession(null);
    final activeRequestId = requestId ?? ++_loadRequestId;
    _invalidateSelectionSideEffects();
    _clearActiveBlock();
    state = state.copyWith(
      generateRequest: const AsyncLoading(),
      blockGenerateRequest: const AsyncData(null),
      versionStatus: const AsyncLoading(),
      outline: const AsyncLoading(),
      blocks: const AsyncLoading(),
      jumpTarget: const AsyncData(null),
      currentBlock: const AsyncData(null),
      qaSubmit: const AsyncData(null),
      clearQaMessages: true,
      clearSelectedBlockId: true,
      clearSelectedCitation: true,
      isPolling: true,
    );

    try {
      final result = await ref.read(apiClientProvider).generateHandout(
            courseId: courseId,
            idempotencyKey:
                'handout-generate-$courseId-${DateTime.now().microsecondsSinceEpoch}',
          );
      if (!_shouldApply(activeRequestId, courseId)) {
        return;
      }
      if (result.entity.type == 'handout_version') {
        ref.read(courseFlowProvider.notifier).setActiveHandoutVersion(
              result.entity.id,
            );
      }
      state = state.copyWith(generateRequest: AsyncData(result));

      if (result.entity.type != 'handout_version') {
        throw StateError(
          '讲义生成返回了不支持的实体类型：${result.entity.type}',
        );
      }
      await _pollVersion(
        courseId: courseId,
        handoutVersionId: result.entity.id,
        requestId: activeRequestId,
        pollInterval: pollInterval,
        maxAttempts: maxAttempts,
      );
    } catch (error, stackTrace) {
      if (!_shouldApply(activeRequestId, courseId)) {
        return;
      }
      state = state.copyWith(
        generateRequest: AsyncError(error, stackTrace),
        versionStatus: AsyncError(error, stackTrace),
        outline: AsyncError(error, stackTrace),
        blocks: AsyncError(error, stackTrace),
        clearSelectedBlockId: true,
        clearSelectedCitation: true,
      );
      ref.read(courseFlowProvider.notifier).setActiveHandoutVersion(null);
      _clearActiveBlock();
    } finally {
      if (_shouldApply(activeRequestId, courseId)) {
        state = state.copyWith(isPolling: false);
      }
    }
  }

  Future<void> generateBlock(
    int blockId, {
    required String courseId,
    Duration pollInterval = const Duration(seconds: 2),
    int maxAttempts = 30,
  }) async {
    if (state.blockGenerateRequest.isLoading) {
      return;
    }
    final requestId = _loadRequestId;
    state = state.copyWith(blockGenerateRequest: const AsyncLoading());
    try {
      final result = await ref.read(apiClientProvider).generateHandoutBlock(
            blockId: blockId,
            idempotencyKey:
                'handout-block-generate-$blockId-${DateTime.now().microsecondsSinceEpoch}',
          );
      if (!_shouldApply(requestId, courseId)) {
        return;
      }
      final blockStatus = result.blockStatus;
      if (blockStatus != null) {
        if (blockStatus.blockId != blockId) {
          throw StateError(
            '讲义块生成返回了不匹配的 blockId：${blockStatus.blockId}',
          );
        }
        await _loadOutlineAndBlocks(
          courseId: courseId,
          requestId: requestId,
        );
        if (!_shouldApply(requestId, courseId)) {
          return;
        }
        state = state.copyWith(blockGenerateRequest: AsyncData(result));
        return;
      }
      final entity = result.entity;
      if (entity == null || entity.type != 'handout_block') {
        throw StateError(
          '讲义块生成返回了不支持的实体类型：${entity?.type ?? 'missing'}',
        );
      }
      if (entity.id != blockId) {
        throw StateError('讲义块生成返回了不匹配的 entity.id：${entity.id}');
      }
      await _pollBlockAndRefresh(
        courseId: courseId,
        blockId: blockId,
        requestId: requestId,
        pollInterval: pollInterval,
        maxAttempts: maxAttempts,
      );
      if (!_shouldApply(requestId, courseId)) {
        return;
      }
      state = state.copyWith(blockGenerateRequest: AsyncData(result));
    } catch (error, stackTrace) {
      if (!_shouldApply(requestId, courseId)) {
        return;
      }
      state = state.copyWith(
        blockGenerateRequest: AsyncError(error, stackTrace),
      );
    }
  }

  Future<void> selectBlock(
    HandoutBlockModel block, {
    bool syncPlayer = true,
  }) async {
    final selectionChanged = state.selectedBlockId != block.blockId;
    if (selectionChanged) {
      _invalidateSelectionSideEffects();
      _clearQaSession();
    }
    state = state.copyWith(
      selectedBlockId: block.blockId,
      currentBlock:
          selectionChanged ? const AsyncData(null) : state.currentBlock,
      jumpTarget: const AsyncLoading(),
      qaSubmit: selectionChanged ? const AsyncData(null) : state.qaSubmit,
      blockGenerateRequest:
          selectionChanged ? const AsyncData(null) : state.blockGenerateRequest,
      clearSelectedCitation: true,
    );
    ref.read(activeBlockProvider.notifier).state = block.blockId;
    if (syncPlayer) {
      ref.read(playerStateProvider.notifier).state =
          ref.read(playerStateProvider).copyWith(
                positionSec: block.startSec,
              );
    }
    await requestJumpTarget(block.blockId);
  }

  void syncHighlightedBlock(int positionSec) {
    final block = state.highlightedBlockFor(positionSec);
    if (block == null || block.blockId == state.selectedBlockId) {
      return;
    }
    _invalidateSelectionSideEffects();
    _clearQaSession();
    ref.read(activeBlockProvider.notifier).state = block.blockId;
    state = state.copyWith(
      selectedBlockId: block.blockId,
      currentBlock: const AsyncData(null),
      jumpTarget: const AsyncData(null),
      qaSubmit: const AsyncData(null),
      blockGenerateRequest: const AsyncData(null),
      clearSelectedCitation: true,
    );
    unawaited(requestJumpTarget(block.blockId));
  }

  Future<void> syncCurrentBlockFromPosition({
    required String courseId,
    required int positionSec,
  }) async {
    final requestId = ++_currentBlockRequestId;
    state = state.copyWith(currentBlock: const AsyncLoading());
    try {
      final current =
          await ref.read(apiClientProvider).fetchCurrentHandoutBlock(
                courseId: courseId,
                currentSec: positionSec,
              );
      if (!_shouldApplyCurrentBlock(requestId, courseId)) {
        return;
      }
      final selectionChanged = state.selectedBlockId != current.blockId;
      if (selectionChanged) {
        _invalidateSelectionSideEffects(includeCurrentBlock: false);
        _clearQaSession();
      }
      ref.read(activeBlockProvider.notifier).state = current.blockId;
      state = state.copyWith(
        currentBlock: AsyncData(current),
        selectedBlockId: current.blockId,
        jumpTarget: selectionChanged ? const AsyncData(null) : state.jumpTarget,
        qaSubmit: selectionChanged ? const AsyncData(null) : state.qaSubmit,
        blockGenerateRequest: selectionChanged
            ? const AsyncData(null)
            : state.blockGenerateRequest,
        clearSelectedCitation: selectionChanged,
      );
      if (selectionChanged) {
        unawaited(requestJumpTarget(current.blockId));
      }
    } catch (error, stackTrace) {
      if (!_shouldApplyCurrentBlock(requestId, courseId)) {
        return;
      }
      state = state.copyWith(currentBlock: AsyncError(error, stackTrace));
    }
  }

  Future<void> requestJumpTarget(
    int blockId, {
    CitationModel? citation,
  }) async {
    final requestId = ++_jumpTargetRequestId;
    final requestCourseId = ref.read(courseFlowProvider).courseId;
    state = state.copyWith(
      jumpTarget: const AsyncLoading(),
      selectedCitation: citation,
      clearSelectedCitation: citation == null,
    );
    try {
      final target = await ref.read(apiClientProvider).fetchHandoutJumpTarget(
            blockId,
          );
      if (!_shouldApplyJumpTarget(requestId, blockId, requestCourseId)) {
        return;
      }
      if (target.blockId != blockId) {
        throw StateError('跳转信息返回了不匹配的 blockId：${target.blockId}');
      }
      state = state.copyWith(jumpTarget: AsyncData(target));
    } catch (error, stackTrace) {
      if (!_shouldApplyJumpTarget(requestId, blockId, requestCourseId)) {
        return;
      }
      state = state.copyWith(jumpTarget: AsyncError(error, stackTrace));
    }
  }

  Future<void> submitQuestion({
    required String courseId,
    required String question,
  }) async {
    final trimmed = question.trim();
    final selected = state.selectedBlock;
    final numericCourseId = int.tryParse(courseId);
    if (trimmed.isEmpty || selected == null || numericCourseId == null) {
      return;
    }

    final requestId = ++_qaRequestId;
    final blockId = selected.blockId;
    state = state.copyWith(qaSubmit: const AsyncLoading());
    try {
      final answer = await ref.read(apiClientProvider).createQaMessage(
            request: QaMessageRequestModel(
              courseId: numericCourseId,
              handoutBlockId: blockId,
              question: trimmed,
            ),
          );
      if (!_shouldApplyQa(requestId, blockId, courseId)) {
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
      if (!_shouldApplyQa(requestId, blockId, courseId)) {
        return;
      }
      state = state.copyWith(qaSubmit: AsyncError(error, stackTrace));
    }
  }

  Future<void> _pollBlockAndRefresh({
    required String courseId,
    required int blockId,
    required int requestId,
    required Duration pollInterval,
    required int maxAttempts,
  }) async {
    HandoutBlockStatusModel? latestStatus;
    for (var attempt = 0; attempt < maxAttempts; attempt++) {
      if (!_shouldApply(requestId, courseId)) {
        return;
      }
      latestStatus = await ref.read(apiClientProvider).fetchHandoutBlockStatus(
            blockId,
          );
      if (!_shouldApply(requestId, courseId)) {
        return;
      }
      if (latestStatus.status == 'ready' || latestStatus.status == 'failed') {
        break;
      }
      await Future<void>.delayed(pollInterval);
    }
    if (!_shouldApply(requestId, courseId) || latestStatus == null) {
      return;
    }
    if (latestStatus.status != 'ready' && latestStatus.status != 'failed') {
      throw StateError('讲义块生成轮询超时，请稍后刷新状态。');
    }
    await _loadOutlineAndBlocks(
      courseId: courseId,
      requestId: requestId,
    );
  }

  Future<void> _loadKnownHandout({
    required String courseId,
    required HandoutLatestModel latest,
    required int requestId,
    required Duration pollInterval,
    required int maxAttempts,
  }) async {
    ref.read(courseFlowProvider.notifier).setActiveHandoutVersion(
          latest.handoutVersionId,
        );
    ref.read(courseFlowProvider.notifier).setSession(null);
    state = state.copyWith(latest: AsyncData(latest));

    final versionStatus = await ref
        .read(apiClientProvider)
        .fetchHandoutVersionStatus(latest.handoutVersionId);
    if (!_shouldApply(requestId, courseId)) {
      return;
    }
    state = state.copyWith(versionStatus: AsyncData(versionStatus));
    if (!versionStatus.isTerminal) {
      await _pollVersion(
        courseId: courseId,
        handoutVersionId: latest.handoutVersionId,
        requestId: requestId,
        pollInterval: pollInterval,
        maxAttempts: maxAttempts,
      );
      return;
    }
    if (versionStatus.status != 'failed') {
      await _loadOutlineAndBlocks(
        courseId: courseId,
        requestId: requestId,
      );
    } else {
      state = state.copyWith(
        outline: const AsyncData(null),
        blocks: const AsyncData(null),
        clearSelectedBlockId: true,
        clearSelectedCitation: true,
      );
      ref.read(courseFlowProvider.notifier).setActiveHandoutVersion(null);
      _clearActiveBlock();
    }
  }

  Future<void> _pollVersion({
    required String courseId,
    required int handoutVersionId,
    required int requestId,
    required Duration pollInterval,
    required int maxAttempts,
  }) async {
    state = state.copyWith(isPolling: true);
    HandoutVersionStatusModel? latestStatus;
    try {
      for (var attempt = 0; attempt < maxAttempts; attempt++) {
        if (!_shouldApply(requestId, courseId)) {
          return;
        }
        latestStatus = await ref
            .read(apiClientProvider)
            .fetchHandoutVersionStatus(handoutVersionId);
        if (!_shouldApply(requestId, courseId)) {
          return;
        }
        state = state.copyWith(versionStatus: AsyncData(latestStatus));
        if (latestStatus.isTerminal) {
          break;
        }
        await Future<void>.delayed(pollInterval);
      }

      if (!_shouldApply(requestId, courseId)) {
        return;
      }
      if (latestStatus == null || !latestStatus.isTerminal) {
        final timeout = StateError('讲义生成轮询超时，请稍后刷新状态。');
        state = state.copyWith(
          versionStatus: AsyncError(timeout, StackTrace.current),
          outline: AsyncError(timeout, StackTrace.current),
          blocks: AsyncError(timeout, StackTrace.current),
          clearSelectedBlockId: true,
          clearSelectedCitation: true,
        );
        ref.read(courseFlowProvider.notifier).setActiveHandoutVersion(null);
        _clearActiveBlock();
        return;
      }

      if (latestStatus.status == 'failed') {
        state = state.copyWith(
          outline: const AsyncData(null),
          blocks: const AsyncData(null),
          clearSelectedBlockId: true,
          clearSelectedCitation: true,
        );
        ref.read(courseFlowProvider.notifier).setActiveHandoutVersion(null);
        _clearActiveBlock();
        return;
      }

      final latest = await ref.read(apiClientProvider).fetchLatestHandout(
            courseId,
          );
      if (!_shouldApply(requestId, courseId)) {
        return;
      }
      ref
          .read(courseFlowProvider.notifier)
          .setActiveHandoutVersion(latest.handoutVersionId);
      state = state.copyWith(latest: AsyncData(latest));
      await _loadOutlineAndBlocks(
        courseId: courseId,
        requestId: requestId,
      );
    } catch (error, stackTrace) {
      if (!_shouldApply(requestId, courseId)) {
        return;
      }
      state = state.copyWith(
        versionStatus: AsyncError(error, stackTrace),
        outline: AsyncError(error, stackTrace),
        blocks: AsyncError(error, stackTrace),
        clearSelectedBlockId: true,
        clearSelectedCitation: true,
      );
      ref.read(courseFlowProvider.notifier).setActiveHandoutVersion(null);
      _clearActiveBlock();
    } finally {
      if (_shouldApply(requestId, courseId)) {
        state = state.copyWith(isPolling: false);
      }
    }
  }

  Future<void> _loadOutlineAndBlocks({
    required String courseId,
    required int requestId,
  }) async {
    state = state.copyWith(
      outline: const AsyncLoading(),
      blocks: const AsyncLoading(),
    );
    try {
      final outline =
          await ref.read(apiClientProvider).fetchLatestHandoutOutline(
                courseId,
              );
      final blocks = await ref.read(apiClientProvider).fetchLatestHandoutBlocks(
            courseId,
          );
      if (!_shouldApply(requestId, courseId)) {
        return;
      }
      final selectedBlockId = _resolveSelectedBlockId(blocks.items);
      final selectionChanged = state.selectedBlockId != selectedBlockId;
      if (selectionChanged) {
        _invalidateSelectionSideEffects();
        _clearQaSession();
      }
      if (selectedBlockId != null) {
        ref.read(activeBlockProvider.notifier).state = selectedBlockId;
      } else {
        _clearActiveBlock();
      }
      state = state.copyWith(
        outline: AsyncData(outline),
        blocks: AsyncData(blocks),
        selectedBlockId: selectedBlockId,
        clearSelectedBlockId: selectedBlockId == null,
        currentBlock:
            selectionChanged ? const AsyncData(null) : state.currentBlock,
        jumpTarget: selectionChanged ? const AsyncData(null) : state.jumpTarget,
        qaSubmit: selectionChanged ? const AsyncData(null) : state.qaSubmit,
        blockGenerateRequest: selectionChanged
            ? const AsyncData(null)
            : state.blockGenerateRequest,
        clearSelectedCitation: selectionChanged,
      );
    } catch (error, stackTrace) {
      if (!_shouldApply(requestId, courseId)) {
        return;
      }
      state = state.copyWith(
        outline: AsyncError(error, stackTrace),
        blocks: AsyncError(error, stackTrace),
        clearSelectedBlockId: true,
        clearSelectedCitation: true,
      );
      ref.read(courseFlowProvider.notifier).setActiveHandoutVersion(null);
      _clearActiveBlock();
    }
  }

  int? _resolveSelectedBlockId(List<HandoutBlockModel> blocks) {
    if (blocks.isEmpty) {
      return null;
    }
    final current = state.selectedBlockId;
    if (current != null && blocks.any((block) => block.blockId == current)) {
      return current;
    }
    return blocks.first.blockId;
  }

  bool _shouldApply(int requestId, [String? courseId]) {
    return !_isDisposed &&
        requestId == _loadRequestId &&
        _isCurrentCourse(courseId);
  }

  bool _shouldApplyJumpTarget(
    int requestId,
    int blockId,
    String? courseId,
  ) {
    return !_isDisposed &&
        requestId == _jumpTargetRequestId &&
        state.selectedBlockId == blockId &&
        _isCurrentCourse(courseId);
  }

  bool _shouldApplyCurrentBlock(int requestId, String courseId) {
    return !_isDisposed &&
        requestId == _currentBlockRequestId &&
        _isCurrentCourse(courseId);
  }

  bool _shouldApplyQa(int requestId, int blockId, String courseId) {
    return !_isDisposed &&
        requestId == _qaRequestId &&
        state.selectedBlockId == blockId &&
        _isCurrentCourse(courseId);
  }

  bool _isCurrentCourse(String? courseId) {
    return courseId == null ||
        ref.read(courseFlowProvider).courseId == courseId;
  }

  void _invalidateSelectionSideEffects({
    bool includeCurrentBlock = true,
  }) {
    _jumpTargetRequestId++;
    _qaRequestId++;
    if (includeCurrentBlock) {
      _currentBlockRequestId++;
    }
  }

  void _clearActiveBlock() {
    ref.read(activeBlockProvider.notifier).state = null;
  }

  void _clearQaSession() {
    ref.read(courseFlowProvider.notifier).setSession(null);
  }

  void _resetForCourseSwitch() {
    _loadRequestId++;
    _invalidateSelectionSideEffects();
    state = const HandoutState();
  }

  bool _isNoActiveHandoutError(Object error) {
    if (error is! DioException) {
      return false;
    }
    final data = error.response?.data;
    if (data is Map) {
      return data['errorCode'] == 'handout.no_active_version';
    }
    return error.response?.statusCode == 404;
  }
}

final handoutProvider =
    AutoDisposeNotifierProvider<HandoutController, HandoutState>(
  HandoutController.new,
);
