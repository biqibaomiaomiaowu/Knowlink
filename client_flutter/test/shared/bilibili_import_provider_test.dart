import 'dart:async';
import 'dart:collection';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/shared/models/bilibili_import_models.dart';
import 'package:knowlink_client/shared/providers/bilibili_import_provider.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  test('loadInitialState fetches auth session and latest import run', () async {
    final fakeApiClient = FakeBilibiliApiClient(
      authSession: const BilibiliAuthSessionModel(
        loginStatus: 'active',
        userNickname: 'KnowLink Demo',
        expiresAt: null,
      ),
      runList: [
        _run(importRunId: 9102, status: 'imported'),
        _run(importRunId: 9101, status: 'downloading'),
      ],
    );
    final container = _container(fakeApiClient);

    await container
        .read(bilibiliImportProvider.notifier)
        .loadInitialState('101');

    final state = container.read(bilibiliImportProvider);
    expect(fakeApiClient.authFetchCount, 1);
    expect(fakeApiClient.runListCourseIds, ['101']);
    expect(state.authSession.valueOrNull?.isActive, isTrue);
    expect(state.authSession.valueOrNull?.userNickname, 'KnowLink Demo');
    expect(
      state.runList.valueOrNull?.items.map((item) => item.importRunId),
      [9102, 9101],
    );
    expect(state.currentRun.valueOrNull?.importRunId, 9102);
  });

  test('loadInitialState keeps auth data when run list fails', () async {
    final fakeApiClient = FakeBilibiliApiClient(
      authSession: const BilibiliAuthSessionModel(
        loginStatus: 'active',
        userNickname: 'KnowLink Demo',
        expiresAt: null,
      ),
      failRunList: true,
    );
    final container = _container(fakeApiClient);

    await container
        .read(bilibiliImportProvider.notifier)
        .loadInitialState('101');

    final state = container.read(bilibiliImportProvider);
    expect(state.authSession.valueOrNull?.userNickname, 'KnowLink Demo');
    expect(state.authSession.hasError, isFalse);
    expect(state.runList.hasError, isTrue);
    expect(state.currentRun.hasError, isTrue);
  });

  test('loadInitialState keeps run list when auth fails', () async {
    final fakeApiClient = FakeBilibiliApiClient(
      failAuthSession: true,
      runList: [
        _run(importRunId: 9102, status: 'imported'),
      ],
    );
    final container = _container(fakeApiClient);

    await container
        .read(bilibiliImportProvider.notifier)
        .loadInitialState('101');

    final state = container.read(bilibiliImportProvider);
    expect(state.authSession.hasError, isTrue);
    expect(state.runList.valueOrNull?.items.single.importRunId, 9102);
    expect(state.currentRun.valueOrNull?.importRunId, 9102);
  });

  test('preview and create import do not require active B站 auth session',
      () async {
    final fakeApiClient = FakeBilibiliApiClient(
      previewResult: _preview(defaultSelectedPartIds: const ['cid-1002']),
      createdTask: _task(taskId: 71, importRunId: 9101, status: 'queued'),
      runStatus: _run(importRunId: 9101, status: 'queued'),
    );
    final container = _container(fakeApiClient);
    final notifier = container.read(bilibiliImportProvider.notifier);

    notifier.updateSourceUrl('https://www.bilibili.com/video/BV1xx411c7mD?p=2');

    var state = container.read(bilibiliImportProvider);
    expect(state.authSession.valueOrNull, isNull);
    expect(state.canPreview, isTrue);

    await notifier.preview('101');

    state = container.read(bilibiliImportProvider);
    expect(state.preview.valueOrNull?.previewId, 'bili_preview_9101');
    expect(state.selectedPartIds, {'cid-1002'});
    expect(state.canCreateImport, isTrue);

    await notifier.createImport('101');

    expect(fakeApiClient.createCalls, hasLength(1));
    expect(
      fakeApiClient.createCalls.single.request.selectedPartIds,
      ['cid-1002'],
    );
  });

  test('preview selects defaults and createImport reuses idempotency key',
      () async {
    final fakeApiClient = FakeBilibiliApiClient(
      authSession: const BilibiliAuthSessionModel(
        loginStatus: 'active',
        userNickname: 'KnowLink Demo',
        expiresAt: null,
      ),
      previewResult: _preview(defaultSelectedPartIds: const ['cid-1002']),
      createdTask: _task(taskId: 71, importRunId: 9101, status: 'queued'),
      runStatus: _run(importRunId: 9101, status: 'queued'),
    );
    final container = _container(fakeApiClient);
    final notifier = container.read(bilibiliImportProvider.notifier);

    notifier.updateSourceUrl('https://www.bilibili.com/video/BV1xx411c7mD?p=2');
    await notifier.refreshAuthSession();
    await notifier.preview('101');

    var state = container.read(bilibiliImportProvider);
    expect(state.preview.valueOrNull?.previewId, 'bili_preview_9101');
    expect(state.selectedPartIds, {'cid-1002'});
    expect(state.canCreateImport, isTrue);

    await notifier.createImport('101');
    state = container.read(bilibiliImportProvider);
    final firstKey = state.lastIdempotencyKey;

    expect(fakeApiClient.createCalls, hasLength(1));
    expect(
        fakeApiClient.createCalls.first.request.selectionMode, 'current_part');
    expect(
        fakeApiClient.createCalls.first.request.selectedPartIds, ['cid-1002']);
    expect(fakeApiClient.createCalls.first.idempotencyKey, firstKey);
    expect(
      container
          .read(bilibiliImportProvider)
          .currentRun
          .valueOrNull
          ?.importRunId,
      9101,
    );
  });

  test('canCreateImport is false while current run is refreshing', () async {
    final runStatusStarted = Completer<void>();
    final runStatusCompleter = Completer<BilibiliImportRunModel>();
    final fakeApiClient = FakeBilibiliApiClient(
      authSession: const BilibiliAuthSessionModel(
        loginStatus: 'active',
        userNickname: 'KnowLink Demo',
        expiresAt: null,
      ),
      previewResult: _preview(defaultSelectedPartIds: const ['cid-1002']),
      createdTask: _task(taskId: 71, importRunId: 9101, status: 'queued'),
      onFetchRunStatus: (_) {
        runStatusStarted.complete();
        return runStatusCompleter.future;
      },
    );
    final container = _container(fakeApiClient);
    final notifier = container.read(bilibiliImportProvider.notifier);

    notifier.updateSourceUrl('https://www.bilibili.com/video/BV1xx411c7mD?p=2');
    await notifier.refreshAuthSession();
    await notifier.preview('101');

    final createFuture = notifier.createImport('101');
    await runStatusStarted.future;

    var state = container.read(bilibiliImportProvider);
    expect(state.currentRun.isLoading, isTrue);
    expect(state.canCreateImport, isFalse);

    runStatusCompleter.complete(_run(importRunId: 9101, status: 'queued'));
    await createFuture;

    state = container.read(bilibiliImportProvider);
    expect(state.currentRun.valueOrNull?.importRunId, 9101);
    expect(state.canCreateImport, isFalse);
  });

  test('createImport ignores direct call while an import run is active',
      () async {
    final fakeApiClient = FakeBilibiliApiClient(
      authSession: const BilibiliAuthSessionModel(
        loginStatus: 'active',
        userNickname: 'KnowLink Demo',
        expiresAt: null,
      ),
      runList: [
        _run(importRunId: 9101, status: 'queued'),
      ],
      previewResult: _preview(defaultSelectedPartIds: const ['cid-1002']),
    );
    final container = _container(fakeApiClient);
    final notifier = container.read(bilibiliImportProvider.notifier);

    await notifier.loadInitialState('101');
    notifier.updateSourceUrl('https://www.bilibili.com/video/BV1xx411c7mD?p=2');
    await notifier.preview('101');

    final state = container.read(bilibiliImportProvider);
    expect(state.currentRun.valueOrNull?.canCancel, isTrue);
    expect(state.preview.valueOrNull?.previewId, 'bili_preview_9101');
    expect(state.selectedPartIds, {'cid-1002'});
    expect(state.canCreateImport, isFalse);

    await notifier.createImport('101');

    expect(fakeApiClient.createCalls, isEmpty);
  });

  test(
      'createImport ignores direct call when current run is unknown after error',
      () async {
    final fakeApiClient = FakeBilibiliApiClient(
      authSession: const BilibiliAuthSessionModel(
        loginStatus: 'active',
        userNickname: 'KnowLink Demo',
        expiresAt: null,
      ),
      failRunList: true,
      previewResult: _preview(defaultSelectedPartIds: const ['cid-1002']),
    );
    final container = _container(fakeApiClient);
    final notifier = container.read(bilibiliImportProvider.notifier);

    await notifier.loadInitialState('101');
    notifier.updateSourceUrl('https://www.bilibili.com/video/BV1xx411c7mD?p=2');
    await notifier.preview('101');

    final state = container.read(bilibiliImportProvider);
    expect(state.authSession.valueOrNull?.isActive, isTrue);
    expect(state.currentRun.hasError, isTrue);
    expect(state.preview.valueOrNull?.previewId, 'bili_preview_9101');
    expect(state.selectedPartIds, {'cid-1002'});
    expect(state.canCreateImport, isFalse);

    await notifier.createImport('101');

    expect(fakeApiClient.createCalls, isEmpty);
  });

  test('stale preview result is ignored after source URL changes', () async {
    final previewStarted = Completer<void>();
    final previewCompleter = Completer<BilibiliPreviewModel>();
    final fakeApiClient = FakeBilibiliApiClient(
      authSession: const BilibiliAuthSessionModel(
        loginStatus: 'active',
        userNickname: 'KnowLink Demo',
        expiresAt: null,
      ),
      onPreviewImport: ({required courseId, required sourceUrl}) {
        previewStarted.complete();
        return previewCompleter.future;
      },
    );
    final container = _container(fakeApiClient);
    final notifier = container.read(bilibiliImportProvider.notifier);

    notifier.updateSourceUrl('https://www.bilibili.com/video/BV_old?p=1');
    await notifier.refreshAuthSession();

    final previewFuture = notifier.preview('101');
    await previewStarted.future;
    notifier.updateSourceUrl('https://www.bilibili.com/video/BV_new?p=2');
    previewCompleter.complete(
      _preview(defaultSelectedPartIds: const ['cid-1002']),
    );
    await previewFuture;

    final state = container.read(bilibiliImportProvider);
    expect(state.sourceUrl, 'https://www.bilibili.com/video/BV_new?p=2');
    expect(state.preview.valueOrNull, isNull);
    expect(state.selectedPartIds, isEmpty);
  });

  test('manual multi selection uses selected_parts and cancel refreshes run',
      () async {
    final fakeApiClient = FakeBilibiliApiClient(
      authSession: const BilibiliAuthSessionModel(
        loginStatus: 'active',
        userNickname: 'KnowLink Demo',
        expiresAt: null,
      ),
      previewResult: _preview(defaultSelectedPartIds: const ['cid-1002']),
      createdTask: _task(taskId: 72, importRunId: 9101, status: 'queued'),
      runStatuses: [
        _run(importRunId: 9101, status: 'downloading'),
        _run(importRunId: 9101, status: 'canceled'),
      ],
      cancelTask: _task(taskId: 73, importRunId: 9101, status: 'canceled'),
    );
    final container = _container(fakeApiClient);
    final notifier = container.read(bilibiliImportProvider.notifier);

    notifier.updateSourceUrl('https://www.bilibili.com/video/BV1xx411c7mD?p=2');
    await notifier.refreshAuthSession();
    await notifier.preview('101');
    notifier.togglePart('cid-1001', selected: true);
    await notifier.createImport('101');
    await notifier.cancelCurrentRun();

    final state = container.read(bilibiliImportProvider);
    expect(fakeApiClient.createCalls.single.request.selectionMode,
        'selected_parts');
    expect(
      fakeApiClient.createCalls.single.request.selectedPartIds,
      ['cid-1001', 'cid-1002'],
    );
    expect(fakeApiClient.cancelRunIds, [9101]);
    expect(state.currentTask.valueOrNull?.status, 'canceled');
    expect(state.currentRun.valueOrNull?.status, 'canceled');
    expect(state.currentRun.valueOrNull?.canCancel, isFalse);
    expect(state.runList.valueOrNull?.items.single.status, 'canceled');
    expect(state.isCanceling, isFalse);
  });

  test('cancel failure restores isCanceling and keeps current run', () async {
    final fakeApiClient = FakeBilibiliApiClient(
      runStatus: _run(importRunId: 9101, status: 'downloading'),
      failCancel: true,
    );
    final container = _container(fakeApiClient);
    final notifier = container.read(bilibiliImportProvider.notifier);

    await notifier.refreshCurrentRun(9101);

    await expectLater(
      notifier.cancelCurrentRun(),
      throwsA(isA<StateError>()),
    );

    final state = container.read(bilibiliImportProvider);
    expect(state.isCanceling, isFalse);
    expect(state.currentTask.hasError, isTrue);
    expect(state.currentRun.valueOrNull?.status, 'downloading');
    expect(state.currentRun.valueOrNull?.canCancel, isTrue);
  });

  test('cancel success keeps current run readable when refresh fails',
      () async {
    var statusFetchCount = 0;
    final fakeApiClient = FakeBilibiliApiClient(
      cancelTask: _task(taskId: 73, importRunId: 9101, status: 'canceled'),
      onFetchRunStatus: (_) {
        statusFetchCount++;
        if (statusFetchCount == 1) {
          return Future.value(_run(importRunId: 9101, status: 'downloading'));
        }
        throw StateError('status refresh failed');
      },
    );
    final container = _container(fakeApiClient);
    final notifier = container.read(bilibiliImportProvider.notifier);

    await notifier.refreshCurrentRun(9101);

    await expectLater(
      notifier.cancelCurrentRun(),
      throwsA(isA<StateError>()),
    );

    final state = container.read(bilibiliImportProvider);
    expect(state.isCanceling, isFalse);
    expect(state.currentTask.valueOrNull?.status, 'canceled');
    expect(state.currentRun.hasError, isFalse);
    expect(state.currentRun.valueOrNull?.status, 'downloading');
    expect(state.currentRun.valueOrNull?.canCancel, isTrue);
    expect(state.runList.hasError, isFalse);
    expect(state.runList.valueOrNull?.items.single.status, 'downloading');
  });

  test('pollQrSession refreshes auth when QR session is confirmed', () async {
    final fakeApiClient = FakeBilibiliApiClient(
      authSession: const BilibiliAuthSessionModel(
        loginStatus: 'inactive',
        userNickname: null,
        expiresAt: null,
      ),
      qrSession: buildQrSession(status: 'pending_scan'),
      polledQrSession: buildQrSession(status: 'confirmed'),
      refreshedAuthSession: const BilibiliAuthSessionModel(
        loginStatus: 'active',
        userNickname: 'Confirmed User',
        expiresAt: null,
      ),
    );
    final container = _container(fakeApiClient);
    final notifier = container.read(bilibiliImportProvider.notifier);

    await notifier.createQrSession();
    await notifier.pollQrSession();

    final state = container.read(bilibiliImportProvider);
    expect(fakeApiClient.polledSessionIds, ['bili_qr_session_001']);
    expect(state.qrSession.valueOrNull?.isConfirmed, isTrue);
    expect(state.authSession.valueOrNull?.isActive, isTrue);
    expect(state.authSession.valueOrNull?.userNickname, 'Confirmed User');
  });

  test('pollQrSession keeps confirmed QR when auth refresh fails', () async {
    final fakeApiClient = FakeBilibiliApiClient(
      qrSession: buildQrSession(status: 'pending_scan'),
      polledQrSession: buildQrSession(status: 'confirmed'),
      failAuthSession: true,
    );
    final container = _container(fakeApiClient);
    final notifier = container.read(bilibiliImportProvider.notifier);

    await notifier.createQrSession();

    await expectLater(
      notifier.pollQrSession(),
      throwsA(isA<StateError>()),
    );

    final state = container.read(bilibiliImportProvider);
    expect(state.qrSession.valueOrNull?.isConfirmed, isTrue);
    expect(state.qrSession.hasError, isFalse);
    expect(state.authSession.hasError, isTrue);
  });

  test('preview stores AsyncError when request fails', () async {
    final fakeApiClient = FakeBilibiliApiClient(
      authSession: const BilibiliAuthSessionModel(
        loginStatus: 'active',
        userNickname: 'KnowLink Demo',
        expiresAt: null,
      ),
      failPreview: true,
    );
    final container = _container(fakeApiClient);
    final notifier = container.read(bilibiliImportProvider.notifier);

    notifier.updateSourceUrl('https://www.bilibili.com/video/BV1xx411c7mD?p=2');
    await notifier.refreshAuthSession();

    await expectLater(
      notifier.preview('101'),
      throwsA(isA<StateError>()),
    );

    final state = container.read(bilibiliImportProvider);
    expect(state.preview.hasError, isTrue);
    expect(state.preview.valueOrNull, isNull);
    expect(state.canPreview, isTrue);
  });
}

ProviderContainer _container(FakeBilibiliApiClient fakeApiClient) {
  final container = ProviderContainer(
    overrides: [
      apiClientProvider.overrideWithValue(fakeApiClient),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

BilibiliQrSessionModel buildQrSession({required String status}) {
  return BilibiliQrSessionModel(
    sessionId: 'bili_qr_session_001',
    status: status,
    qrCodeUrl: 'https://passport.bilibili.com/qrcode-demo',
    expiresAt: null,
  );
}

BilibiliPreviewModel _preview({
  required List<String> defaultSelectedPartIds,
}) {
  final defaults = defaultSelectedPartIds.toSet();
  return BilibiliPreviewModel(
    previewId: 'bili_preview_9101',
    sourceUrl: 'https://www.bilibili.com/video/BV1xx411c7mD?p=2',
    sourceType: 'multi_p',
    title: '课程样例',
    coverUrl: null,
    totalParts: 2,
    parts: [
      BilibiliPreviewPartModel(
        partId: 'cid-1001',
        title: 'P1 导论',
        durationSec: 600,
        cid: 1001,
        pageNo: 1,
        selectedByDefault: defaults.contains('cid-1001'),
      ),
      BilibiliPreviewPartModel(
        partId: 'cid-1002',
        title: 'P2 例题',
        durationSec: 900,
        cid: 1002,
        pageNo: 2,
        selectedByDefault: defaults.contains('cid-1002'),
      ),
      BilibiliPreviewPartModel(
        partId: 'cid-1003',
        title: 'P3 总结',
        durationSec: 300,
        cid: 1003,
        pageNo: 3,
        selectedByDefault: defaults.contains('cid-1003'),
      ),
    ],
    defaultSelectionMode: 'current_part',
  );
}

BilibiliImportTaskModel _task({
  required int taskId,
  required int importRunId,
  required String status,
}) {
  return BilibiliImportTaskModel(
    taskId: taskId,
    status: status,
    nextAction: 'poll',
    entity: BilibiliImportTaskEntityModel(
      type: 'bilibili_import_run',
      id: importRunId,
    ),
  );
}

BilibiliImportRunModel _run({
  required int importRunId,
  required String status,
}) {
  return BilibiliImportRunModel(
    importRunId: importRunId,
    courseId: 101,
    sourceUrl: 'https://www.bilibili.com/video/BV1xx411c7mD?p=2',
    sourceType: 'multi_p',
    status: status,
    progressPct: status == 'imported' ? 100 : 42,
    stage: status,
    taskId: 71,
    resourceIds: const [],
    preview: const BilibiliImportRunPreviewModel(
      title: '课程样例',
      parts: [
        BilibiliImportRunPreviewPartModel(
          partId: 'cid-1002',
          title: 'P2 例题',
          durationSec: 900,
        ),
      ],
    ),
    errorCode: null,
    failureReason: null,
    recoverable: false,
    nextAction: status == 'imported' ? null : 'poll',
  );
}

class CreateImportCall {
  const CreateImportCall({
    required this.courseId,
    required this.request,
    required this.idempotencyKey,
  });

  final String courseId;
  final BilibiliImportCreateRequestModel request;
  final String idempotencyKey;
}

class FakeBilibiliApiClient extends ApiClient {
  FakeBilibiliApiClient({
    BilibiliAuthSessionModel? authSession,
    BilibiliAuthSessionModel? refreshedAuthSession,
    List<BilibiliImportRunModel> runList = const [],
    BilibiliQrSessionModel? qrSession,
    BilibiliQrSessionModel? polledQrSession,
    BilibiliPreviewModel? previewResult,
    BilibiliImportTaskModel? createdTask,
    BilibiliImportRunModel? runStatus,
    List<BilibiliImportRunModel>? runStatuses,
    BilibiliImportTaskModel? cancelTask,
    bool failPreview = false,
    bool failAuthSession = false,
    bool failRunList = false,
    bool failCancel = false,
    Future<BilibiliImportRunModel> Function(int importRunId)? onFetchRunStatus,
    Future<BilibiliPreviewModel> Function({
      required String courseId,
      required String sourceUrl,
    })? onPreviewImport,
  })  : _authSession = authSession,
        _refreshedAuthSession = refreshedAuthSession,
        _runList = runList,
        _qrSession = qrSession,
        _polledQrSession = polledQrSession,
        _previewResult = previewResult,
        _createdTask = createdTask,
        _runStatus = runStatus,
        _runStatuses = runStatuses == null ? null : Queue.of(runStatuses),
        _cancelTask = cancelTask,
        _failPreview = failPreview,
        _failAuthSession = failAuthSession,
        _failRunList = failRunList,
        _failCancel = failCancel,
        _onFetchRunStatus = onFetchRunStatus,
        _onPreviewImport = onPreviewImport,
        super(baseUrl: 'http://127.0.0.1');

  final BilibiliAuthSessionModel? _authSession;
  final BilibiliAuthSessionModel? _refreshedAuthSession;
  final List<BilibiliImportRunModel> _runList;
  final BilibiliQrSessionModel? _qrSession;
  final BilibiliQrSessionModel? _polledQrSession;
  final BilibiliPreviewModel? _previewResult;
  final BilibiliImportTaskModel? _createdTask;
  final BilibiliImportRunModel? _runStatus;
  final Queue<BilibiliImportRunModel>? _runStatuses;
  final BilibiliImportTaskModel? _cancelTask;
  final bool _failPreview;
  final bool _failAuthSession;
  final bool _failRunList;
  final bool _failCancel;
  final Future<BilibiliImportRunModel> Function(int importRunId)?
      _onFetchRunStatus;
  final Future<BilibiliPreviewModel> Function({
    required String courseId,
    required String sourceUrl,
  })? _onPreviewImport;

  var authFetchCount = 0;
  final runListCourseIds = <String>[];
  final polledSessionIds = <String>[];
  final createCalls = <CreateImportCall>[];
  final cancelRunIds = <int>[];

  @override
  Future<BilibiliAuthSessionModel> fetchBilibiliAuthSession() async {
    authFetchCount++;
    if (_failAuthSession) {
      throw StateError('auth failed');
    }
    if (_refreshedAuthSession != null && polledSessionIds.isNotEmpty) {
      return _refreshedAuthSession;
    }
    return _authSession ??
        const BilibiliAuthSessionModel(
          loginStatus: 'inactive',
          userNickname: null,
          expiresAt: null,
        );
  }

  @override
  Future<BilibiliImportRunListModel> fetchBilibiliImportRuns(
    String courseId,
  ) async {
    runListCourseIds.add(courseId);
    if (_failRunList) {
      throw StateError('run list failed');
    }
    return BilibiliImportRunListModel(items: _runList);
  }

  @override
  Future<BilibiliQrSessionModel> createBilibiliQrSession() async {
    return _qrSession ?? _qrSessionDefault;
  }

  @override
  Future<BilibiliQrSessionModel> fetchBilibiliQrSession(
    String sessionId,
  ) async {
    polledSessionIds.add(sessionId);
    return _polledQrSession ?? _qrSession ?? _qrSessionDefault;
  }

  @override
  Future<void> deleteBilibiliAuthSession() async {}

  @override
  Future<BilibiliPreviewModel> previewBilibiliImport({
    required String courseId,
    required String sourceUrl,
  }) async {
    final onPreviewImport = _onPreviewImport;
    if (onPreviewImport != null) {
      return onPreviewImport(courseId: courseId, sourceUrl: sourceUrl);
    }
    if (_failPreview) {
      throw StateError('preview failed');
    }
    return _previewResult ?? _preview(defaultSelectedPartIds: const []);
  }

  @override
  Future<BilibiliImportTaskModel> createBilibiliImport({
    required String courseId,
    required BilibiliImportCreateRequestModel request,
    required String idempotencyKey,
  }) async {
    createCalls.add(
      CreateImportCall(
        courseId: courseId,
        request: request,
        idempotencyKey: idempotencyKey,
      ),
    );
    return _createdTask ??
        _task(taskId: 71, importRunId: 9101, status: 'queued');
  }

  @override
  Future<BilibiliImportRunModel> fetchBilibiliImportRunStatus(
    int importRunId,
  ) async {
    final onFetchRunStatus = _onFetchRunStatus;
    if (onFetchRunStatus != null) {
      return onFetchRunStatus(importRunId);
    }
    final runStatuses = _runStatuses;
    if (runStatuses != null && runStatuses.isNotEmpty) {
      return runStatuses.removeFirst();
    }
    return _runStatus ?? _run(importRunId: importRunId, status: 'queued');
  }

  @override
  Future<BilibiliImportTaskModel> cancelBilibiliImportRun(
    int importRunId,
  ) async {
    cancelRunIds.add(importRunId);
    if (_failCancel) {
      throw StateError('cancel failed');
    }
    return _cancelTask ??
        _task(taskId: 73, importRunId: importRunId, status: 'canceled');
  }

  BilibiliQrSessionModel get _qrSessionDefault =>
      buildQrSession(status: 'pending');
}
