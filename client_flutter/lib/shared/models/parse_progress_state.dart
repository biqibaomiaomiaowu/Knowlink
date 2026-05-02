import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'pipeline_status.dart';

class ParseProgressState {
  const ParseProgressState({
    this.startRequest = const AsyncData<ParseStartResultModel?>(null),
    this.pipelineStatus = const AsyncData<PipelineStatusModel?>(null),
    this.isPolling = false,
  });

  final AsyncValue<ParseStartResultModel?> startRequest;
  final AsyncValue<PipelineStatusModel?> pipelineStatus;
  final bool isPolling;

  bool get isStarting => startRequest.isLoading;
  bool get isRefreshing => pipelineStatus.isLoading;
  PipelineStatusModel? get currentStatus => pipelineStatus.valueOrNull;

  ParseProgressState copyWith({
    AsyncValue<ParseStartResultModel?>? startRequest,
    AsyncValue<PipelineStatusModel?>? pipelineStatus,
    bool? isPolling,
  }) {
    return ParseProgressState(
      startRequest: startRequest ?? this.startRequest,
      pipelineStatus: pipelineStatus ?? this.pipelineStatus,
      isPolling: isPolling ?? this.isPolling,
    );
  }
}
