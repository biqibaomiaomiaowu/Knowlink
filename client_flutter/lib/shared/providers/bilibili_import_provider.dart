import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/bilibili_import_models.dart';
import '../models/bilibili_import_state.dart';
import 'course_recommend_provider.dart';

class BilibiliImportIdempotencyStore {
  final Map<String, String> _keysByFingerprint = {};

  String resolveKey({
    required String fingerprint,
    required String courseId,
  }) {
    return _keysByFingerprint.putIfAbsent(
      fingerprint,
      () => 'bilibili-import-$courseId-'
          '${DateTime.now().microsecondsSinceEpoch}',
    );
  }
}

final bilibiliImportIdempotencyStoreProvider =
    Provider<BilibiliImportIdempotencyStore>(
  (ref) => BilibiliImportIdempotencyStore(),
);

class BilibiliImportController
    extends AutoDisposeNotifier<BilibiliImportState> {
  String? _lastCreateFingerprint;
  var _previewRequestId = 0;

  @override
  BilibiliImportState build() => const BilibiliImportState();

  Future<void> loadInitialState(String courseId) async {
    final apiClient = ref.read(apiClientProvider);
    state = state.copyWith(
      authSession: const AsyncLoading(),
      runList: const AsyncLoading(),
      currentRun: const AsyncLoading(),
    );

    try {
      final authSession = await apiClient.fetchBilibiliAuthSession();
      state = state.copyWith(authSession: AsyncData(authSession));
    } catch (error, stackTrace) {
      state = state.copyWith(
        authSession: AsyncError(error, stackTrace),
      );
    }

    try {
      final runList = await apiClient.fetchBilibiliImportRuns(courseId);
      state = state.copyWith(
        runList: AsyncData(runList),
        currentRun: AsyncData(
          runList.items.isEmpty ? null : runList.items.first,
        ),
      );
    } catch (error, stackTrace) {
      state = state.copyWith(
        runList: AsyncError(error, stackTrace),
        currentRun: AsyncError(error, stackTrace),
      );
    }
  }

  void updateSourceUrl(String value) {
    _lastCreateFingerprint = null;
    _previewRequestId++;
    state = state.copyWith(
      sourceUrl: value,
      selectedPartIds: const {},
      preview: const AsyncData(null),
      currentTask: const AsyncData(null),
      clearLastIdempotencyKey: true,
    );
  }

  Future<void> createQrSession() async {
    state = state.copyWith(qrSession: const AsyncLoading());
    try {
      final qrSession =
          await ref.read(apiClientProvider).createBilibiliQrSession();
      state = state.copyWith(qrSession: AsyncData(qrSession));
    } catch (error, stackTrace) {
      state = state.copyWith(qrSession: AsyncError(error, stackTrace));
      rethrow;
    }
  }

  Future<void> pollQrSession() async {
    final currentQrSession = state.qrSession.valueOrNull;
    if (currentQrSession == null || currentQrSession.isTerminal) {
      return;
    }

    state = state.copyWith(qrSession: const AsyncLoading());
    try {
      final qrSession = await ref
          .read(apiClientProvider)
          .fetchBilibiliQrSession(currentQrSession.sessionId);
      state = state.copyWith(qrSession: AsyncData(qrSession));
    } catch (error, stackTrace) {
      state = state.copyWith(qrSession: AsyncError(error, stackTrace));
      rethrow;
    }

    final qrSession = state.qrSession.valueOrNull;
    if (qrSession?.isConfirmed == true) {
      await refreshAuthSession();
    }
  }

  Future<void> refreshAuthSession() async {
    state = state.copyWith(authSession: const AsyncLoading());
    try {
      final authSession =
          await ref.read(apiClientProvider).fetchBilibiliAuthSession();
      state = state.copyWith(authSession: AsyncData(authSession));
    } catch (error, stackTrace) {
      state = state.copyWith(authSession: AsyncError(error, stackTrace));
      rethrow;
    }
  }

  Future<void> logout() async {
    await ref.read(apiClientProvider).deleteBilibiliAuthSession();
    state = state.copyWith(
      authSession: const AsyncData(null),
      qrSession: const AsyncData(null),
    );
  }

  Future<void> preview(String courseId) async {
    if (!state.canPreview) {
      return;
    }

    final requestId = ++_previewRequestId;
    final sourceUrl = state.sourceUrl.trim();
    state = state.copyWith(
      preview: const AsyncLoading(),
      selectedPartIds: const {},
      currentTask: const AsyncData(null),
      clearLastIdempotencyKey: true,
    );

    try {
      final preview = await ref.read(apiClientProvider).previewBilibiliImport(
            courseId: courseId,
            sourceUrl: sourceUrl,
          );
      if (!_shouldApplyPreviewResult(
        requestId: requestId,
        sourceUrl: sourceUrl,
      )) {
        return;
      }
      _lastCreateFingerprint = null;
      state = state.copyWith(
        preview: AsyncData(preview),
        selectedPartIds: preview.defaultSelectedPartIds.toSet(),
      );
    } catch (error, stackTrace) {
      if (!_shouldApplyPreviewResult(
        requestId: requestId,
        sourceUrl: sourceUrl,
      )) {
        return;
      }
      state = state.copyWith(
        preview: AsyncError(error, stackTrace),
        selectedPartIds: const {},
      );
      rethrow;
    }
  }

  void togglePart(String partId, {required bool selected}) {
    final selectedPartIds = {...state.selectedPartIds};
    if (selected) {
      selectedPartIds.add(partId);
    } else {
      selectedPartIds.remove(partId);
    }

    _lastCreateFingerprint = null;
    state = state.copyWith(
      selectedPartIds: selectedPartIds,
      clearLastIdempotencyKey: true,
    );
  }

  Future<void> createImport(String courseId) async {
    final preview = state.preview.valueOrNull;
    if (!state.canCreateImport || preview == null) {
      return;
    }

    final selectedPartIds = _selectedPartIdsInPreviewOrder(preview);
    final selectionMode = _selectionModeFor(
      preview: preview,
      selectedPartIds: selectedPartIds,
    );
    final request = BilibiliImportCreateRequestModel(
      previewId: preview.previewId,
      sourceUrl: state.sourceUrl.trim(),
      selectionMode: selectionMode,
      selectedPartIds: selectedPartIds,
    );
    final fingerprint = _createFingerprint(
      courseId: courseId,
      request: request,
    );
    final idempotencyKey = _resolveIdempotencyKey(
      courseId: courseId,
      fingerprint: fingerprint,
    );

    state = state.copyWith(
      currentTask: const AsyncLoading(),
      lastIdempotencyKey: idempotencyKey,
    );

    late final BilibiliImportTaskModel task;
    try {
      task = await ref.read(apiClientProvider).createBilibiliImport(
            courseId: courseId,
            request: request,
            idempotencyKey: idempotencyKey,
          );
      state = state.copyWith(
        currentTask: AsyncData(task),
        lastIdempotencyKey: idempotencyKey,
      );
    } catch (error, stackTrace) {
      state = state.copyWith(
        currentTask: AsyncError(error, stackTrace),
        lastIdempotencyKey: idempotencyKey,
      );
      rethrow;
    }

    final importRunId = task.importRunId;
    if (importRunId != null) {
      await refreshCurrentRun(importRunId);
    }
  }

  Future<void> refreshCurrentRun(int importRunId) async {
    state = state.copyWith(currentRun: const AsyncLoading());
    try {
      final currentRun = await ref
          .read(apiClientProvider)
          .fetchBilibiliImportRunStatus(importRunId);
      state = state.copyWith(
        currentRun: AsyncData(currentRun),
        runList: AsyncData(_replaceRun(state.runList.valueOrNull, currentRun)),
      );
    } catch (error, stackTrace) {
      state = state.copyWith(currentRun: AsyncError(error, stackTrace));
      rethrow;
    }
  }

  Future<void> cancelCurrentRun() async {
    final currentRun = state.currentRun.valueOrNull;
    if (currentRun == null || !currentRun.canCancel || state.isCanceling) {
      return;
    }
    final previousRun = state.currentRun;
    final previousRunList = state.runList;

    state = state.copyWith(
      currentTask: const AsyncLoading(),
      isCanceling: true,
    );
    try {
      final task = await ref
          .read(apiClientProvider)
          .cancelBilibiliImportRun(currentRun.importRunId);
      state = state.copyWith(
        currentTask: AsyncData(task),
      );
      final importRunId = task.importRunId ?? currentRun.importRunId;
      try {
        await refreshCurrentRun(importRunId);
      } catch (_) {
        state = state.copyWith(
          currentRun: previousRun,
          runList: previousRunList,
          isCanceling: false,
        );
        rethrow;
      }
      state = state.copyWith(isCanceling: false);
    } catch (error, stackTrace) {
      state = state.copyWith(
        currentTask: state.currentTask.valueOrNull == null
            ? AsyncError(error, stackTrace)
            : state.currentTask,
        isCanceling: false,
      );
      rethrow;
    }
  }

  List<String> _selectedPartIdsInPreviewOrder(BilibiliPreviewModel preview) {
    final selectedPartIds = state.selectedPartIds;
    return preview.parts
        .where((part) => selectedPartIds.contains(part.partId))
        .map((part) => part.partId)
        .toList();
  }

  bool _shouldApplyPreviewResult({
    required int requestId,
    required String sourceUrl,
  }) {
    return requestId == _previewRequestId &&
        sourceUrl == state.sourceUrl.trim();
  }

  String _selectionModeFor({
    required BilibiliPreviewModel preview,
    required List<String> selectedPartIds,
  }) {
    final selectedSet = selectedPartIds.toSet();
    final allSet = preview.parts.map((part) => part.partId).toSet();
    if (selectedSet.length == allSet.length &&
        selectedSet.containsAll(allSet)) {
      return 'all_parts';
    }

    final defaultSet = preview.defaultSelectedPartIds.toSet();
    if (selectedSet.length == defaultSet.length &&
        selectedSet.containsAll(defaultSet)) {
      return 'current_part';
    }

    return 'selected_parts';
  }

  String _createFingerprint({
    required String courseId,
    required BilibiliImportCreateRequestModel request,
  }) {
    return jsonEncode({
      'courseId': courseId,
      'request': request.toJson(),
    });
  }

  String _resolveIdempotencyKey({
    required String courseId,
    required String fingerprint,
  }) {
    if (_lastCreateFingerprint == fingerprint &&
        state.lastIdempotencyKey != null) {
      return state.lastIdempotencyKey!;
    }

    _lastCreateFingerprint = fingerprint;
    return ref.read(bilibiliImportIdempotencyStoreProvider).resolveKey(
          fingerprint: fingerprint,
          courseId: courseId,
        );
  }

  BilibiliImportRunListModel _replaceRun(
    BilibiliImportRunListModel? runList,
    BilibiliImportRunModel currentRun,
  ) {
    var replaced = false;
    final updated =
        (runList?.items ?? const <BilibiliImportRunModel>[]).map((item) {
      if (item.importRunId != currentRun.importRunId) {
        return item;
      }
      replaced = true;
      return currentRun;
    }).toList();
    if (replaced) {
      return BilibiliImportRunListModel(items: updated);
    }
    return BilibiliImportRunListModel(items: [currentRun, ...updated]);
  }
}

final bilibiliImportProvider =
    AutoDisposeNotifierProvider<BilibiliImportController, BilibiliImportState>(
  BilibiliImportController.new,
);
