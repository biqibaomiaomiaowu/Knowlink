import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/course_import/course_import_page.dart';
import 'package:knowlink_client/shared/models/bilibili_import_models.dart';
import 'package:knowlink_client/shared/models/resource_upload_models.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('B站导入区块在无 courseId 时禁用预览', (tester) async {
    _useLargeTestSurface(tester);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(_BilibiliPageFakeApiClient()),
        ],
        child: const MaterialApp(home: CourseImportPage()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('B站导入'), findsOneWidget);
    expect(find.text('请先创建课程或从推荐页进入已有课程。'), findsOneWidget);

    final previewButton = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, '预览B站资源'),
    );
    expect(previewButton.onPressed, isNull);
  });

  testWidgets('B站导入区块可预览并创建导入任务', (tester) async {
    _useLargeTestSurface(tester);
    final fakeApiClient = _BilibiliPageFakeApiClient(
      authSession: const BilibiliAuthSessionModel(
        loginStatus: 'active',
        userNickname: 'KnowLink Demo',
        expiresAt: null,
      ),
      runStatuses: [
        _run(status: 'imported', resourceIds: const [601]),
      ],
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: const MaterialApp(home: CourseImportPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('已登录：KnowLink Demo'), findsOneWidget);

    await tester.enterText(
      find.widgetWithText(TextField, 'B站链接'),
      'https://www.bilibili.com/video/BV1demo',
    );
    await tester.pump();
    final previewButton = find.widgetWithText(FilledButton, '预览B站资源');
    expect(tester.widget<FilledButton>(previewButton).onPressed, isNotNull);
    await tester.tap(previewButton);
    await tester.pumpAndSettle();

    expect(find.text('课程样例'), findsWidgets);
    expect(find.text('P2 例题'), findsOneWidget);

    await tester.tap(find.widgetWithText(FilledButton, '创建导入任务'));
    await tester.pumpAndSettle();

    expect(find.text('已导入'), findsOneWidget);
    expect(fakeApiClient.createCalls, hasLength(1));
    expect(fakeApiClient.createCalls.single.request.selectedPartIds, [
      'cid-1002',
    ]);

    expect(find.widgetWithText(FilledButton, '创建导入任务'), findsOneWidget);
    final createButton = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, '创建导入任务'),
    );
    expect(createButton.onPressed, isNotNull);
  });

  testWidgets('已有进行中 run 时输入和预览后仍禁用创建', (tester) async {
    _useLargeTestSurface(tester);
    final fakeApiClient = _BilibiliPageFakeApiClient(
      authSession: const BilibiliAuthSessionModel(
        loginStatus: 'active',
        userNickname: 'KnowLink Demo',
        expiresAt: null,
      ),
      runList: [
        _run(status: 'queued'),
      ],
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: const MaterialApp(home: CourseImportPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.widgetWithText(FilledButton, '导入进行中'), findsOneWidget);

    await tester.enterText(
      find.widgetWithText(TextField, 'B站链接'),
      'https://www.bilibili.com/video/BV1demo',
    );
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, '预览B站资源'));
    await tester.pumpAndSettle();

    expect(find.text('课程样例'), findsWidgets);
    final createButton = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, '导入进行中'),
    );
    expect(createButton.onPressed, isNull);
    expect(fakeApiClient.createCalls, isEmpty);
  });

  testWidgets('创建导入后轮询到 imported 并刷新资源列表', (tester) async {
    _useLargeTestSurface(tester);
    final fakeApiClient = _BilibiliPageFakeApiClient(
      authSession: const BilibiliAuthSessionModel(
        loginStatus: 'active',
        userNickname: 'KnowLink Demo',
        expiresAt: null,
      ),
      runStatuses: [
        _run(status: 'queued'),
        _run(status: 'imported', resourceIds: const [601]),
      ],
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: const MaterialApp(home: CourseImportPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    expect(fakeApiClient.fetchResourcesCount, 1);

    await tester.enterText(
      find.widgetWithText(TextField, 'B站链接'),
      'https://www.bilibili.com/video/BV1demo',
    );
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, '预览B站资源'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, '创建导入任务'));
    await tester.pumpAndSettle();

    expect(find.text('已导入'), findsOneWidget);
    expect(find.text('资源：601'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, '进入解析'), findsOneWidget);
    expect(fakeApiClient.fetchResourcesCount, 2);
    expect(find.text('bilibili-import.mp4'), findsOneWidget);
  });

  testWidgets('合集预览显示中文来源和默认选择方式', (tester) async {
    _useLargeTestSurface(tester);
    final fakeApiClient = _BilibiliPageFakeApiClient(
      authSession: const BilibiliAuthSessionModel(
        loginStatus: 'active',
        userNickname: 'KnowLink Demo',
        expiresAt: null,
      ),
      preview: const BilibiliPreviewModel(
        previewId: 'preview-collection',
        sourceUrl:
            'https://space.bilibili.com/123/channel/collectiondetail?sid=456',
        sourceType: 'collection',
        title: '合集样例',
        coverUrl: null,
        totalParts: 2,
        defaultSelectionMode: 'all_parts',
        parts: [
          BilibiliPreviewPartModel(
            partId: 'collection-1',
            title: '合集第一讲',
            durationSec: 600,
            cid: 1001,
            pageNo: 1,
            selectedByDefault: true,
          ),
          BilibiliPreviewPartModel(
            partId: 'collection-2',
            title: '合集第二讲',
            durationSec: 900,
            cid: 1002,
            pageNo: 2,
            selectedByDefault: true,
          ),
        ],
      ),
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: const MaterialApp(home: CourseImportPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(
      find.widgetWithText(TextField, 'B站链接'),
      'https://space.bilibili.com/123/channel/collectiondetail?sid=456',
    );
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, '预览B站资源'));
    await tester.pumpAndSettle();

    expect(find.text('合集样例'), findsWidgets);
    expect(find.textContaining('合集 · 2 个条目 · 默认全部条目'), findsOneWidget);
  });

  testWidgets('B站失败导入显示重试按钮且不显示取消按钮', (tester) async {
    _useLargeTestSurface(tester);
    final fakeApiClient = _BilibiliPageFakeApiClient(
      runList: [
        _run(
          status: 'recoverable',
          failureReason: '内容不可访问',
          recoverable: true,
        ),
      ],
      runStatuses: [
        _run(status: 'imported', resourceIds: const [601]),
      ],
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: const MaterialApp(home: CourseImportPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('内容不可访问'), findsOneWidget);
    expect(find.text('可重试'), findsOneWidget);
    expect(find.widgetWithText(OutlinedButton, '重试导入'), findsOneWidget);
    expect(find.widgetWithText(OutlinedButton, '取消导入'), findsNothing);

    await tester.tap(find.widgetWithText(OutlinedButton, '重试导入'));
    await tester.pumpAndSettle();

    expect(fakeApiClient.retriedTaskIds, [7001]);
    expect(find.text('已导入'), findsOneWidget);
  });

  testWidgets('B站登录状态错误时仍保留扫码入口', (tester) async {
    _useLargeTestSurface(tester);
    final fakeApiClient = _BilibiliPageFakeApiClient(
      failAuthSession: true,
      qrSession: const BilibiliQrSessionModel(
        sessionId: 'qr-error',
        status: 'pending',
        qrCodeUrl: 'https://bilibili.test/qr-error.png',
        expiresAt: null,
      ),
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: const MaterialApp(home: CourseImportPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('B站登录状态暂不可用'), findsOneWidget);
    expect(find.widgetWithText(OutlinedButton, '重新扫码'), findsOneWidget);

    await tester.tap(find.widgetWithText(OutlinedButton, '重新扫码'));
    await tester.pumpAndSettle();

    expect(find.text('扫码状态：pending'), findsOneWidget);
    expect(
      find.textContaining('二维码链接：https://bilibili.test/qr-error.png'),
      findsOneWidget,
    );
  });

  testWidgets('未登录时扫码后可刷新扫码状态并更新登录态', (tester) async {
    _useLargeTestSurface(tester);
    final fakeApiClient = _BilibiliPageFakeApiClient(
      qrSession: const BilibiliQrSessionModel(
        sessionId: 'qr-1',
        status: 'pending',
        qrCodeUrl: 'https://bilibili.test/qr.png',
        expiresAt: null,
      ),
      polledQrSession: const BilibiliQrSessionModel(
        sessionId: 'qr-1',
        status: 'confirmed',
        qrCodeUrl: 'https://bilibili.test/qr.png',
        expiresAt: null,
      ),
      refreshedAuthSession: const BilibiliAuthSessionModel(
        loginStatus: 'active',
        userNickname: 'Confirmed User',
        expiresAt: null,
      ),
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: const MaterialApp(home: CourseImportPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('未登录B站'), findsOneWidget);

    await tester.tap(find.widgetWithText(OutlinedButton, '重新扫码'));
    await tester.pumpAndSettle();

    expect(find.text('扫码状态：pending'), findsOneWidget);
    expect(find.textContaining('二维码链接：https://bilibili.test/qr.png'),
        findsOneWidget);
    expect(find.widgetWithText(OutlinedButton, '刷新扫码状态'), findsOneWidget);

    await tester.tap(find.widgetWithText(OutlinedButton, '刷新扫码状态'));
    await tester.pumpAndSettle();

    expect(find.text('已登录：Confirmed User'), findsOneWidget);
  });
}

void _useLargeTestSurface(WidgetTester tester) {
  tester.view.physicalSize = const Size(1200, 1800);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

class _BilibiliPageFakeApiClient extends ApiClient {
  _BilibiliPageFakeApiClient({
    BilibiliAuthSessionModel? authSession,
    BilibiliAuthSessionModel? refreshedAuthSession,
    List<BilibiliImportRunModel> runList = const [],
    List<BilibiliImportRunModel>? runStatuses,
    BilibiliQrSessionModel? qrSession,
    BilibiliQrSessionModel? polledQrSession,
    BilibiliPreviewModel? preview,
    bool failAuthSession = false,
  })  : _authSession = authSession ??
            const BilibiliAuthSessionModel(
              loginStatus: 'none',
              userNickname: null,
              expiresAt: null,
            ),
        _refreshedAuthSession = refreshedAuthSession,
        _runList = runList,
        _runStatuses = runStatuses == null ? null : List.of(runStatuses),
        _qrSession = qrSession,
        _polledQrSession = polledQrSession,
        _preview = preview,
        _failAuthSession = failAuthSession;

  final BilibiliAuthSessionModel _authSession;
  final BilibiliAuthSessionModel? _refreshedAuthSession;
  final List<BilibiliImportRunModel> _runList;
  final List<BilibiliImportRunModel>? _runStatuses;
  final BilibiliQrSessionModel? _qrSession;
  final BilibiliQrSessionModel? _polledQrSession;
  final BilibiliPreviewModel? _preview;
  final bool _failAuthSession;
  final createCalls = <_CreateImportCall>[];
  final retriedTaskIds = <int>[];
  var fetchResourcesCount = 0;
  var _runStatusIndex = 0;
  var _hasPolledQrSession = false;

  @override
  Future<BilibiliAuthSessionModel> fetchBilibiliAuthSession() async {
    if (_failAuthSession) {
      throw StateError('auth failed');
    }
    if (_hasPolledQrSession && _refreshedAuthSession != null) {
      return _refreshedAuthSession;
    }
    return _authSession;
  }

  @override
  Future<BilibiliImportRunListModel> fetchBilibiliImportRuns(
    String courseId,
  ) async {
    return BilibiliImportRunListModel(items: _runList);
  }

  @override
  Future<List<CourseResourceModel>> fetchCourseResources(
    String courseId,
  ) async {
    fetchResourcesCount++;
    if (fetchResourcesCount < 2) {
      return const [];
    }
    return [
      CourseResourceModel.fromJson({
        'resourceId': 601,
        'resourceType': 'mp4',
        'originalName': 'bilibili-import.mp4',
        'objectKey': 'raw/1/101/bilibili-import.mp4',
        'ingestStatus': 'completed',
        'validationStatus': 'valid',
        'processingStatus': 'ready',
      }),
    ];
  }

  @override
  Future<BilibiliQrSessionModel> createBilibiliQrSession() async {
    return _qrSession ??
        const BilibiliQrSessionModel(
          sessionId: 'qr-default',
          status: 'pending',
          qrCodeUrl: null,
          expiresAt: null,
        );
  }

  @override
  Future<BilibiliQrSessionModel> fetchBilibiliQrSession(
    String sessionId,
  ) async {
    _hasPolledQrSession = true;
    return _polledQrSession ??
        _qrSession ??
        BilibiliQrSessionModel(
          sessionId: sessionId,
          status: 'pending',
          qrCodeUrl: null,
          expiresAt: null,
        );
  }

  @override
  Future<BilibiliPreviewModel> previewBilibiliImport({
    required String courseId,
    required String sourceUrl,
  }) async {
    return _preview ??
        const BilibiliPreviewModel(
          previewId: 'preview-1',
          sourceUrl: 'https://www.bilibili.com/video/BV1demo',
          sourceType: 'single_video',
          title: '课程样例',
          coverUrl: null,
          totalParts: 2,
          defaultSelectionMode: 'current_part',
          parts: [
            BilibiliPreviewPartModel(
              partId: 'cid-1001',
              title: 'P1 导论',
              durationSec: 600,
              cid: 1001,
              pageNo: 1,
              selectedByDefault: false,
            ),
            BilibiliPreviewPartModel(
              partId: 'cid-1002',
              title: 'P2 例题',
              durationSec: 900,
              cid: 1002,
              pageNo: 2,
              selectedByDefault: true,
            ),
          ],
        );
  }

  @override
  Future<BilibiliImportTaskModel> createBilibiliImport({
    required String courseId,
    required BilibiliImportCreateRequestModel request,
    required String idempotencyKey,
  }) async {
    createCalls.add(_CreateImportCall(request));
    return const BilibiliImportTaskModel(
      taskId: 7001,
      status: 'queued',
      nextAction: 'poll',
      entity: BilibiliImportTaskEntityModel(
        type: 'bilibili_import_run',
        id: 9001,
      ),
    );
  }

  @override
  Future<BilibiliImportRunModel> fetchBilibiliImportRunStatus(
    int importRunId,
  ) async {
    final runStatuses = _runStatuses;
    if (runStatuses != null && _runStatusIndex < runStatuses.length) {
      return runStatuses[_runStatusIndex++];
    }
    return _run(importRunId: importRunId, status: 'queued');
  }

  @override
  Future<BilibiliImportTaskModel> retryAsyncTask(int taskId) async {
    retriedTaskIds.add(taskId);
    return BilibiliImportTaskModel(
      taskId: taskId,
      status: 'queued',
      nextAction: 'poll',
      entity: const BilibiliImportTaskEntityModel(
        type: 'bilibili_import_run',
        id: 9001,
      ),
    );
  }
}

class _CreateImportCall {
  const _CreateImportCall(this.request);

  final BilibiliImportCreateRequestModel request;
}

BilibiliImportRunModel _run({
  int importRunId = 9001,
  String status = 'queued',
  String? failureReason,
  bool recoverable = false,
  List<int> resourceIds = const [],
}) {
  return BilibiliImportRunModel(
    importRunId: importRunId,
    courseId: 101,
    sourceUrl: 'https://www.bilibili.com/video/BV1demo',
    sourceType: 'single_video',
    status: status,
    progressPct: status == 'queued' ? 0 : 100,
    stage: status,
    taskId: 7001,
    resourceIds: resourceIds,
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
    failureReason: failureReason,
    recoverable: recoverable,
    nextAction: recoverable ? 'retry' : 'poll',
  );
}
