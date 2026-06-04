import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'bilibili_import_models.dart';

class BilibiliImportState {
  const BilibiliImportState({
    this.authSession = const AsyncData(null),
    this.qrSession = const AsyncData(null),
    this.sourceUrl = '',
    this.preview = const AsyncData(null),
    this.selectedPartIds = const {},
    this.currentTask = const AsyncData(null),
    this.currentRun = const AsyncData(null),
    this.runList = const AsyncData(null),
    this.isCanceling = false,
    this.isPollingRun = false,
    this.lastIdempotencyKey,
  });

  final AsyncValue<BilibiliAuthSessionModel?> authSession;
  final AsyncValue<BilibiliQrSessionModel?> qrSession;
  final String sourceUrl;
  final AsyncValue<BilibiliPreviewModel?> preview;
  final Set<String> selectedPartIds;
  final AsyncValue<BilibiliImportTaskModel?> currentTask;
  final AsyncValue<BilibiliImportRunModel?> currentRun;
  final AsyncValue<BilibiliImportRunListModel?> runList;
  final bool isCanceling;
  final bool isPollingRun;
  final String? lastIdempotencyKey;

  bool get canPreview =>
      sourceUrl.trim().isNotEmpty &&
      !preview.isLoading;

  bool get canCreateImport =>
      preview.valueOrNull != null &&
      selectedPartIds.isNotEmpty &&
      !currentTask.isLoading &&
      !currentRun.isLoading &&
      !currentRun.hasError &&
      currentRun.valueOrNull?.canCancel != true;

  BilibiliImportState copyWith({
    AsyncValue<BilibiliAuthSessionModel?>? authSession,
    AsyncValue<BilibiliQrSessionModel?>? qrSession,
    String? sourceUrl,
    AsyncValue<BilibiliPreviewModel?>? preview,
    Set<String>? selectedPartIds,
    AsyncValue<BilibiliImportTaskModel?>? currentTask,
    AsyncValue<BilibiliImportRunModel?>? currentRun,
    AsyncValue<BilibiliImportRunListModel?>? runList,
    bool? isCanceling,
    bool? isPollingRun,
    String? lastIdempotencyKey,
    bool clearLastIdempotencyKey = false,
  }) {
    return BilibiliImportState(
      authSession: authSession ?? this.authSession,
      qrSession: qrSession ?? this.qrSession,
      sourceUrl: sourceUrl ?? this.sourceUrl,
      preview: preview ?? this.preview,
      selectedPartIds: selectedPartIds ?? this.selectedPartIds,
      currentTask: currentTask ?? this.currentTask,
      currentRun: currentRun ?? this.currentRun,
      runList: runList ?? this.runList,
      isCanceling: isCanceling ?? this.isCanceling,
      isPollingRun: isPollingRun ?? this.isPollingRun,
      lastIdempotencyKey: clearLastIdempotencyKey
          ? null
          : lastIdempotencyKey ?? this.lastIdempotencyKey,
    );
  }
}
